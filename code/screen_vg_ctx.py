#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screen the Van Gogh sentences with the whole letter as context.

Annotation already ran one sentence at a time with the full letter attached, while screening
still ran in batches with no context. Without the letter, a
model reading "I scraped off that study" has no way to tell which work is meant and can only
answer no. The identifier route reaches those sentences because the edition's
editors read the whole letter.

The screening criteria are copied word for word from the original prompt. Two things change,
neither of them a criterion: the letter goes at the top of the prompt, and sentences from one
letter are sent together. Batch size stays at 16, so this isolates the effect of context.

One sentence is added: a reference counts as identifiable if the letter itself makes clear
which work is meant, even when the sentence alone does not name it. Without it the original
wording about vague references keeps the answer at no.
"""
import json, os, re, sys, time, html as _html, collections, urllib.request
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("WORK_DIR") or os.path.join(REPO, "data", "work")   # intermediates
CAN  = os.path.join(WORK, "screening")
VG_TEI = f"{SCR}/process-chain/vangogh/vangogh-master/data"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
ENV  = os.path.join(REPO, ".env")   # copy .env.example -> .env and fill in
OUT  = os.path.join(HERE, "screen_vg_ctx_decisions.json")

MODEL, ARTIST = "deepseek-v4-flash", "Vincent van Gogh"
WORKERS, MAXLETTER = 16, 22000

norm = lambda x: re.sub(r"\s+", " ", _html.unescape(x)).strip()

def key():
    for ln in open(ENV, encoding="utf-8"):
        if ln.startswith("DEEPSEEK_API_KEY="):
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("no DEEPSEEK_API_KEY")

def vg_text(lid):
    for c in (f"{VG_TEI}/let{int(lid)}.xml", f"{VG_TEI}/let{int(lid):03d}.xml"):
        if os.path.exists(c):
            x = open(c, encoding="utf-8", errors="ignore").read(); break
    else:
        return ""
    m = re.search(r'<div type="translation"[^>]*>(.*?)(?=<div type="notes"|</body>|</text>)', x, re.S)
    if not m: return ""
    return norm(re.sub(r'<[^>]+>', '', re.sub(r'</ab>', '\n', m.group(1), flags=re.I)))

def make_prompt(letter, batch):
    """Criteria copied word for word from the original screening prompt; only the letter is added."""
    lines = [f'  [{it["id"]}] {it["sentence"][:400]}' for it in batch]
    return f"""Below is one complete letter by {ARTIST}, given as context.

--- LETTER ---
{letter[:MAXLETTER]}
--- END LETTER ---

For each sentence from {ARTIST}'s letters, determine if it discusses a SPECIFIC WORK created by {ARTIST} himself.

A sentence counts as "discussing own work" if it clearly refers to a particular artwork/picture/composition that {ARTIST} made, is making, or plans to make.

Answer YES only when the reference is specific and identifiable. Answer NO for:
- Works by OTHER artists (even if named)
- Art theory, techniques, materials, or general aesthetic discussion
- Vague references ("my work", "what I'm doing", "my picture")
- Business, travel, health, or personal matters
- Places, people, or events without a clear link to a specific work of {ARTIST}
- Descriptions of the act of working without naming/identifying the product

Use the letter above to resolve what a sentence refers to. A reference counts as identifiable if the letter itself makes clear which work is meant, even when the sentence alone does not name it.

Return ONLY a JSON array of "YES"/"NO" strings, one per sentence, in the same order.

SENTENCES:
{chr(10).join(lines)}"""

K = key()
def call(prompt, tries=5):
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.0, "max_tokens": 3000,
                       "thinking": {"type": "disabled"}}).encode()
    last = ""
    for t in range(tries):
        try:
            req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {K}"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"], d.get("usage", {})
        except Exception as e:
            last = f"{type(e).__name__}:{str(e)[:120]}"
            time.sleep(2 * (t + 1))
    return f"__ERROR__ {last}", {}

def parse(text, n):
    if not text or text.startswith("__ERROR__"): return [None] * n
    m = re.search(r'\[.*?\]', text, re.DOTALL)
    if not m: return [None] * n
    try: arr = json.loads(m.group(0))
    except Exception: return [None] * n
    out = []
    for x in arr[:n]:
        u = x.strip().upper() if isinstance(x, str) else ""
        out.append(True if u in ("YES", "Y") else (False if u in ("NO", "N") else None))
    return out + [None] * (n - len(out))

def main():
    prep = json.load(open(f"{CAN}/prep_vangogh.json", encoding="utf-8"))
    by = collections.defaultdict(list)
    for p in prep: by[str(int(p["letter_id"]))].append(p)
    letters = sorted(by, key=int)
    print(f"{len(prep):,} sentences across {len(letters)} letters", flush=True)

    dec, usage, err = {}, collections.Counter(), collections.Counter()
    lock = __import__("threading").Lock()
    done = [0]

    def work(lid):
        txt = vg_text(lid)
        items = by[lid]
        if not txt:                                   # no letter text; fall back and count it
            err["no_letter"] += 1; txt = ""
        # Batch size 16, as in the original screening. An earlier run used 40 and the model often
        # returned arrays shorter than the batch, which the parser padded with nulls: nearly a fifth
        # of items went unparsed. The failure rate tracked letter length, and letter length tracks
        # position in the correspondence, so the missing data lined up with the analysis axis and
        # could have manufactured a trend. Going back to 16 fixed the parsing and removed batch size
        # as a confound.
        out = {}
        for i in range(0, len(items), 16):
            b = items[i:i+16]
            raw, us = call(make_prompt(txt, b))
            if raw.startswith("__ERROR__"): err[raw[:40]] += 1
            for it, v in zip(b, parse(raw, len(b))):
                out[it["id"]] = v
            with lock:
                usage["in"] += us.get("prompt_tokens", 0)
                usage["out"] += us.get("completion_tokens", 0)
        with lock:
            dec.update(out); done[0] += 1
            if done[0] % 50 == 0:
                print(f"  {done[0]}/{len(letters)} letters, YES {sum(1 for v in dec.values() if v)}"
                      f" · in {usage['in']:,}", flush=True)

    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, letters))

    yes = sum(1 for v in dec.values() if v is True)
    na  = sum(1 for v in dec.values() if v is None)
    cost = usage["in"] * 0.10 / 1e6 + usage["out"] * 0.30 / 1e6
    json.dump(dec, open(OUT, "w", encoding="utf-8"))
    print(f"\ndone in {time.time()-t0:.0f}s, judged {len(dec):,}, YES {yes:,} "
          f"({yes/max(1,len(dec))*100:.1f}%), unparsed {na:,}")
    print(f"tokens in {usage['in']:,} out {usage['out']:,}, ${cost:.2f}, errors {dict(err)}")
    print(f"→ {OUT}")

if __name__ == "__main__":
    main()
