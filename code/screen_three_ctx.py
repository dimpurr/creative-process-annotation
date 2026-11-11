#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screen the Whistler, Beethoven and Mozart sentences with the whole letter as context.

The screening criteria are copied word for word from the original prompt. Two things change,
neither of them a criterion: the letter is placed at the top of the prompt, and sentences
from the same letter are sent together, so the context is available.

One sentence is added to the criteria: a reference counts as identifiable if the letter
itself makes clear which work is meant, even when the sentence alone does not name it.
Without it the model has the context but no instruction to use it.

Batch size is 16. An earlier run at 40 returned short arrays that were padded with nulls,
leaving nearly a fifth of items unparsed and the failure rate correlated with letter length.

Every sentence carries the identifier of the letter it came from, so the letter is looked
up directly. An earlier version reconstructed the link with an n-gram index over the letter
texts, which attached three per cent of sentences to the wrong letter and left the short
ones with no context at all.

Sentences are put through the admission test in `corpus_filter` before the model sees them.
That removes letterheads, postal matter, catalogue entries and rows that begin or end inside
an abbreviation, none of which are sentences the criteria below can sensibly be applied to.
"""
import json, os, re, sys, time, html as _html, collections, urllib.request
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("WORK_DIR") or os.path.join(REPO, "data", "work")   # intermediates
CAN  = os.path.join(WORK, "screening")
WH_JSONL = os.path.join(WORK, "whistler", "whistler_letters_clean2.jsonl")
PARSED   = os.path.join(WORK, "parsed")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
ENV  = os.path.join(REPO, ".env")   # copy .env.example -> .env and fill in

MODEL = "deepseek-v4-flash"
BATCH, WORKERS, MAXLETTER = 16, 16, 22000
ARTIST = {"whistler": "James McNeill Whistler",
          "beethoven": "Ludwig van Beethoven",
          "mozart": "Wolfgang Amadeus Mozart"}

norm = lambda x: re.sub(r"\s+", " ", _html.unescape(x)).strip()

def key():
    for ln in open(ENV, encoding="utf-8"):
        if ln.startswith("DEEPSEEK_API_KEY="):
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("no DEEPSEEK_API_KEY")
K = key()

def make_prompt(artist, letter, batch):
    """Criteria copied word for word from the original prompt, plus the letter and one added
    sentence about references the letter makes identifiable."""
    lines = [f'  [{it["id"]}] {it["sentence"][:400]}' for it in batch]
    ctx = (f"Below is one complete letter by {artist}, given as context.\n\n"
           f"--- LETTER ---\n{letter[:MAXLETTER]}\n--- END LETTER ---\n\n") if letter else ""
    return f"""{ctx}For each sentence from {artist}'s letters, determine if it discusses a SPECIFIC WORK created by {artist} himself.

A sentence counts as "discussing own work" if it clearly refers to a particular artwork/picture/composition that {artist} made, is making, or plans to make.

Answer YES only when the reference is specific and identifiable. Answer NO for:
- Works by OTHER artists (even if named)
- Art theory, techniques, materials, or general aesthetic discussion
- Vague references ("my work", "what I'm doing", "my picture")
- Business, travel, health, or personal matters
- Places, people, or events without a clear link to a specific work of {artist}
- Descriptions of the act of working without naming/identifying the product
{'''
Use the letter above to resolve what a sentence refers to. A reference counts as identifiable if the letter itself makes clear which work is meant, even when the sentence alone does not name it.
''' if letter else ''}
Return ONLY a JSON array of "YES"/"NO" strings, one per sentence, in the same order.

SENTENCES:
{chr(10).join(lines)}"""

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
            last = f"{type(e).__name__}:{str(e)[:110]}"; time.sleep(2 * (t + 1))
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
    # A short array is not a short answer. Padding the tail assumes the model left out the
    # last item; if it left out one in the middle, every verdict after that point belongs to
    # a different sentence and nothing in the output says so. The batch is discarded and
    # re-sent by repair_alignment, which asks for the identifier beside the verdict.
    if len(out) != n:
        return [None] * n
    return out

# Corpus loading. Both come back as (items, letters): items carry a letter_id, letters maps
# an id to the full text.
def load(corpus):
    if corpus in ("beethoven", "mozart"):
        # With STRIPPED set, the sentence pool is the one with editorial marks removed. Sentences and
        # letter text come from the same run; the two are never mixed.
        if os.environ.get("STRIPPED"):
            raw = json.load(open(os.path.join(WORK, "stripped", f"{corpus.capitalize()}_letters_stripped.json"),
                                 encoding="utf-8"))
            items = [{"id": f"{corpus[0]}{i:05d}", "sentence": norm(sn),
                      "letter_id": k, "corpus": corpus}
                     for i, (k, sn) in enumerate((k, sn) for k, v in raw.items() for sn in v)]
        else:
            raw = json.load(open(f"{PARSED}/{corpus.capitalize()}_letters_parsed.json",
                                 encoding="utf-8"))
            items = json.load(open(f"{CAN}/prep_{corpus}.json", encoding="utf-8"))
        letters = {k: norm(" ".join(v)) for k, v in raw.items()}
        return items, letters, 0
    # Whistler sentences carry no letter id, so a 6-gram inverted index maps them back.
    sents = json.load(open(f"{CAN}/prep_whistler_clean2.json", encoding="utf-8"))
    wl = [(str(r["cid"]), norm(r.get("body_clean2") or ""))
          for r in map(json.loads, open(WH_JSONL, encoding="utf-8"))]
    # Two levels of index. 6-grams are close to unique, but short sentences cannot produce one and
    # would silently fall back to no context, creating a mixed condition inside one corpus. A
    # 3-gram index catches those, and every candidate letter is checked for the sentence as a
    # substring, since 3-grams are not unique.
    idx, idx3 = collections.defaultdict(list), collections.defaultdict(list)
    low = {}
    for cid, body in wl:
        low[cid] = body.lower()
        w = low[cid].split(); seen = set(); seen3 = set()
        for i in range(len(w) - 5):
            k = " ".join(w[i:i + 6])
            if k not in seen: seen.add(k); idx[k].append(cid)
        for i in range(len(w) - 2):
            k = " ".join(w[i:i + 3])
            if k not in seen3: seen3.add(k); idx3[k].append(cid)
    letters = dict(wl)
    items, unmapped = [], 0
    for i, s in enumerate(sents):
        ns = norm(s); w = ns.lower().split()
        cid = None
        # A 6-gram hit is verified by looking for the sentence in the candidate letter. Without that
        # check, formulaic openings such as "i am going to send you" match several letters and the
        # first hit wins: 69 of 2,021 Whistler sentences were attached to the wrong letter.
        for j in range(max(1, len(w) - 5)):
            for c in idx.get(" ".join(w[j:j + 6]), [])[:40]:
                if ns.lower() in low[c]: cid = c; break
            if cid: break
        if cid is None and len(w) >= 3:                  # short sentences: 3-gram plus the same check
            for c in idx3.get(" ".join(w[:3]), [])[:60]:
                if ns.lower() in low[c]: cid = c; break
        if cid is None: unmapped += 1
        items.append({"id": f"c{i:05d}", "sentence": norm(s),
                      "letter_id": cid or f"__NOLETTER_{i}"})
    return items, letters, unmapped

def run(corpus):
    items, letters, unmapped = load(corpus)
    by = collections.defaultdict(list)
    for it in items: by[str(it["letter_id"])].append(it)
    print(f"[{corpus}] {len(items):,} sentences across {len(by)} letters, unmapped {unmapped}", flush=True)

    dec, usage, err, done = {}, collections.Counter(), collections.Counter(), [0]
    lock = __import__("threading").Lock()

    def work(lid):
        txt = letters.get(lid, "")
        if not txt: err["no_letter"] += 1
        out = {}
        for i in range(0, len(by[lid]), BATCH):
            b = by[lid][i:i + BATCH]
            raw, us = call(make_prompt(ARTIST[corpus], txt, b))
            if raw.startswith("__ERROR__"): err[raw[:38]] += 1
            for it, v in zip(b, parse(raw, len(b))): out[it["id"]] = v
            with lock:
                usage["in"] += us.get("prompt_tokens", 0); usage["out"] += us.get("completion_tokens", 0)
        with lock:
            dec.update(out); done[0] += 1
            if done[0] % 400 == 0:
                print(f"  [{corpus}] {done[0]}/{len(by)} letters, YES "
                      f"{sum(1 for v in dec.values() if v)} · in {usage['in']:,}", flush=True)

    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, sorted(by)))
    yes = sum(1 for v in dec.values() if v is True)
    na = sum(1 for v in dec.values() if v is None)
    cost = usage["in"] * 0.10 / 1e6 + usage["out"] * 0.30 / 1e6
    tag = "_stripped" if os.environ.get("STRIPPED") else ""
    json.dump(dec, open(f"{HERE}/screen_{corpus}{tag}_ctx_decisions.json", "w"), ensure_ascii=False)
    print(f"[{corpus}] DONE {time.time()-t0:.0f}s · YES {yes:,}/{len(dec):,} "
          f"({yes/max(1,len(dec))*100:.2f}%), unparsed {na:,} ({na/max(1,len(dec))*100:.2f}%) "
          f", ${cost:.2f}, errors {dict(err)}", flush=True)
    return {"corpus": corpus, "n": len(dec), "yes": yes, "na": na, "cost": cost,
            "unmapped": unmapped, "letters": len(by)}

if __name__ == "__main__":
    which = sys.argv[1:] or ["whistler", "beethoven", "mozart"]
    res = [run(c) for c in which]
    print("\n=== summary ===")
    for r in res:
        print(f"  {r['corpus']:10} {r['yes']:>6}/{r['n']:>6} = {r['yes']/r['n']*100:5.2f}%"
              f" · NA {r['na']/r['n']*100:5.2f}% · ${r['cost']:.2f}")
    print(f"  total ${sum(r['cost'] for r in res):.2f}")
