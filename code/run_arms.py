#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the annotation arms.

Every arm sees the same thing: one sentence at a time, the whole letter as context, and
one scheme's definitions from codebook/schemes.json. Each scheme is a
separate call carrying only its own definitions; the four are never mixed in one call.
With --combined all four schemes are presented at once instead, which is a different
condition: presentation turns out to matter, so the two are not interchangeable.

Output: one .jsonl per arm, plus a .meta.json recording the model, temperature, token
limit and calling mode (--combined or separate) actually used.

Keys are read from the environment and never written into the source or printed. Do not
pass a key on a command line: shell history records it verbatim.

"""
import json, os, re, sys, time, argparse, threading, collections
import urllib.request, urllib.error
import concurrent.futures as cf

HERE   = os.path.dirname(os.path.abspath(__file__))
REPO   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
DATA   = os.environ.get("CHR_DATA") or REPO
IN_    = os.path.join(DATA, "data")
RUNS   = os.path.join(DATA, "runs")
# The sentinel requires --corpus to be passed explicitly.
SAMPLE = os.environ.get("CALIB_SAMPLE") or os.path.join(IN_, "__MUST_PASS_--corpus__")
# Default context file.
CTX    = os.environ.get("CALIB_CTX") or os.path.join(IN_, "context.json")
# Category definitions are based on the published theories, with brief explanations where needed.
TEMPLATE = os.environ.get("CHR_SCHEMES") or os.path.join(REPO, "codebook", "schemes.json")
ENV    = os.path.join(REPO, ".env")   # copy .env.example -> .env and fill in

TEMPERATURE = 0.0
MAX_TOKENS  = 1200
NA = "__NA__"            # parse failure or refusal. Never fall back to `none`, which is a real label

# Provider routing. Each vendor is called directly where possible.
# The four APIs differ in protocol and in how reasoning is switched off, and a wrong
# parameter is ignored, not rejected, so each is written out separately
# instead of sharing one call path.
ARMS = {
    # The two annotators reported in the paper: one proprietary, one open-weight.
    "M1":  {"provider": "openai",    "model": "gpt-5.6-luna"},      # proprietary
    "M2":  {"provider": "dashscope", "model": "qwen3-32b"},         # open weights
    # Self-consistency arms, not currently run. Kept so they can be switched back on.
    "M1p": {"provider": "openai",    "model": "gpt-5.6-luna"},
    "M2p": {"provider": "dashscope", "model": "qwen3-32b"},
}

PROVIDERS = {
    "openai":     {"key": "OPENAI_API_KEY",
                   "url": "https://api.openai.com/v1/chat/completions"},
    "deepseek":   {"key": "DEEPSEEK_API_KEY",
                   "url": "https://api.deepseek.com/chat/completions"},
    "dashscope":  {"key": "DASHSCOPE_API_KEY",
                   "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"},
}

_KEYS = {}
def get_key(name):
    """Read a key from the environment or the local .env. Never printed, not even a prefix."""
    if name in _KEYS:
        return _KEYS[name]
    k = os.environ.get(name)
    if not k:
        for line in open(ENV, encoding="utf-8"):
            if line.startswith(name + "="):
                k = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not k:
        sys.exit(f"missing {name} (set it in the environment or in .env)")
    _KEYS[name] = k
    return k

def load_theories():
    """Load the four schemes' categories and definitions.

    Human annotators and the models must receive definitions that are identical word for
    word; otherwise the human-model agreement is measured on two different instruments.
    """
    with open(TEMPLATE, encoding="utf-8") as fh:
        return json.load(fh)

def codebook(theories):
    out = []
    for t in theories:
        out.append(f'## {t["id"]}  ({t.get("fullname", t["id"])})')
        for c in t["categories"]:
            out.append(f'- {c["key"]}: {c["def"]}')
        # Do not append `none` here. It is already a category in schemes.json, with its own
        # wording. Adding another sentence would give the models one definition
        # and human annotators another.
    return "\n".join(out)

# Placing the target sentence both in place and once more at the end is the default:
# it keeps the sentence findable between a whole letter and a long codebook.
PROMPT_VARIANT = "repeat_tail"
COMBINED = False   # --combined presents all four schemes in one call; default is separate calls

def build_prompt(theories, cb, item, ctx):
    letter, span = ctx["letter_text"], ctx["span"]
    if span:                                  # mark the target sentence inside the letter
        # The delimiter is <<< >>>. An earlier version used full-width CJK brackets, which
        # sit oddly in an English prompt and may be rare tokens, so they may affect
        # how the boundary is read.
        marked = letter[:span[0]] + "<<< " + letter[span[0]:span[1]] + " >>>" + letter[span[1]:]
    else:
        marked = letter
    if len(marked) > 24000:                   # truncate very long letters, keeping the target
        s = max(0, (span[0] if span else 0) - 8000)
        marked = ("…" if s else "") + marked[s:s + 24000] + "…"
    keys = {t["id"]: [c["key"] for c in t["categories"]] for t in theories}   # `none` included
    # Variants, for the same lost-in-the-middle problem:
    #   repeat_tail  leave in place and repeat once at the end
    #   move_tail    place at the end only
    tail = ""
    tgt_block = f"TARGET SENTENCE:\n{item['sentence']}\n"
    if PROMPT_VARIANT == "repeat_tail":
        tail = f"\nThe sentence you are labelling, once more:\n{item['sentence']}\n"
    elif PROMPT_VARIANT == "move_tail":
        tgt_block = ""
        tail = f"\nTARGET SENTENCE (the sentence you are labelling):\n{item['sentence']}\n"
    # The number of schemes comes from `theories`. It is not written into the text.
    # Under separate calls only one scheme is present, and saying there are four would send the model
    # looking for three that are not there.
    _n = len(theories)
    _nw = {1: "one", 2: "two", 3: "three", 4: "four"}.get(_n, str(_n))
    _hdr = (f"using {_nw} different theories of the creative process. Each theory has been turned into an annotation scheme."
            if _n > 1 else
            "using a theory of the creative process that has been turned into an annotation scheme.")
    _ask = (f"Assign the TARGET SENTENCE exactly ONE category under EACH of the {_nw} schemes."
            if _n > 1 else
            "Assign the TARGET SENTENCE exactly ONE category under the scheme below.")
    return f"""You are annotating a sentence from an artist's letter, {_hdr}

Below is the FULL LETTER for context. The TARGET SENTENCE is marked with <<< >>>.

--- LETTER ({ctx['corpus']}, id {ctx['letter_id']}) ---
{marked}
--- END LETTER ---

{tgt_block}
ANNOTATION SCHEMES (verbatim definitions):
{cb}

{_ask} The categories within each scheme are mutually exclusive. Use `none` when the sentence does not fit any category of that scheme — `none` is a legitimate judgement, not a failure.

Each category definition must be satisfied in full. If a sentence matches only part of a definition, that category does not apply; choose `none` rather than a partial match.

Valid keys per scheme:
{json.dumps(keys, ensure_ascii=False, indent=1)}

Return STRICT JSON only, no prose, no markdown fences:
{{"<scheme_id>": {{"label": "<one key>", "reason": "<max 30 words, referring to the definition>"}}, ...}}
""" + tail

def call(spec, prompt, tries=5):
    """Dispatch by provider.

    The parameter that switches reasoning off differs between vendors, and a wrong one is
    ignored, not rejected, so it is easy to believe it is off when it is not. Each vendor is
    handled separately, and the meta file records what was actually sent.
    """
    prov, model = spec["provider"], spec["model"]
    P = PROVIDERS[prov]
    key = get_key(P["key"])
    url = P["url"].format(model=model)

    body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if prov == "openai":
        # gpt-5.x requires max_completion_tokens; max_tokens returns 400. It also rejects an
        # explicit temperature, so the default is left alone. The parameters follow the model
        # not the provider: gpt-4.x accepts neither max_completion_tokens nor reasoning_effort.
        if model.startswith("gpt-5"):
            body["max_completion_tokens"] = MAX_TOKENS
            body["reasoning_effort"] = "none"
        else:
            body["max_tokens"] = MAX_TOKENS
            body["temperature"] = TEMPERATURE
    elif prov == "dashscope":
        # Qwen3 on the DashScope compatibility endpoint. enable_thinking is its own switch.
        body["max_tokens"] = MAX_TOKENS
        body["temperature"] = TEMPERATURE
        body["enable_thinking"] = False
    elif prov == "deepseek":
        body["max_tokens"] = MAX_TOKENS
        body["temperature"] = TEMPERATURE
        body["thinking"] = {"type": "disabled"}
    else:
        body["max_tokens"] = MAX_TOKENS
        body["temperature"] = TEMPERATURE
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    headers["User-Agent"] = "creative-process-artists-letters/1.0"

    last = ""
    for a in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"], d.get("usage", {})
        except urllib.error.HTTPError as e:
            code = e.code
            try:    detail = e.read().decode()[:300]
            except Exception: detail = ""
            last = f"HTTP {code}: {detail}"
            if code in (400, 401, 403, 404):
                break                                  # configuration error; retrying will not help
            time.sleep(min(30, 3 * (2 ** a)))          # longer backoff for 429 and 5xx
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(2 ** a)
    return None, {"error": last}

def parse(text, theories):
    # Anything that cannot be parsed becomes __NA__. Never `none`, which is a real label.
    labels = {t["id"]: NA for t in theories}
    reasons = {t["id"]: "" for t in theories}
    if not text:
        return labels, reasons
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        return labels, reasons
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return labels, reasons
    for t in theories:
        v = obj.get(t["id"])
        if not isinstance(v, dict):
            continue                                    # leave as __NA__
        lab = str(v.get("label", "")).strip()
        valid = {c["key"] for c in t["categories"]}          # includes `none`
        labels[t["id"]] = lab if lab in valid else NA   # out of range is a failure, not `none`
        reasons[t["id"]] = str(v.get("reason", ""))[:300]
    return labels, reasons

def run_arm(arm, items, ctxs, theories, cb, workers):
    spec = ARMS[arm]; model = spec["model"]
    out_path = os.path.join(RUNS, f"{arm}.jsonl")
    os.makedirs(RUNS, exist_ok=True)
    lock, results = threading.Lock(), {}
    usage_tot = {"prompt_tokens": 0, "completion_tokens": 0}
    t0 = time.time()

    def one(it):
        ctx = ctxs[it.get("_k", it["uid"])]
        if not COMBINED:
            # Each scheme is called on its own, with a codebook containing only that scheme, so
            # the four cannot see each other. Changing the definitions of two schemes moved the gap
            # between the two models on the other two as well, which is what a shared codebook block
            # does. The cost is 2.81x the input tokens, not 4x, because the letter itself accounts for
            # under a quarter of the prompt.
            labels, reasons, txt = {}, {}, []
            sub_errs = []
            for t in theories:
                sub = [t]
                _tx, u = call(spec, build_prompt(sub, codebook(sub), it, ctx))
                _l, _r = parse(_tx, sub)
                labels.update(_l); reasons.update(_r); txt.append(_tx or "")
                if (u or {}).get("error"):
                    sub_errs.append("%s=%s" % (t["id"], u["error"]))
                with lock:
                    for k in usage_tot:
                        usage_tot[k] += (u or {}).get(k, 0) or 0
            txt = "\n---\n".join(txt)
            # Each scheme is a separate call, so each can fail separately.
            # Discarding the per-call result here would hide the reason: a provider that
            # refuses every request returns no labels, which is indistinguishable from a
            # model that declines to label, and the run reports the second.
            u = {"error": " | ".join(sub_errs)} if sub_errs else None
        else:
            txt, u = call(spec, build_prompt(theories, cb, it, ctx))
            labels, reasons = parse(txt, theories)
        # Write provider errors to disk for diagnosis.
        err = (u or {}).get("error")
        with lock:
            if COMBINED:
                for k in usage_tot:
                    usage_tot[k] += (u or {}).get(k, 0) or 0
            results[it["n"]] = {
                "uid": it["uid"], "row_id": it.get("_k"), "corpus": it["corpus"], "arm": arm,
                "labels": labels, "reasons": reasons, "raw": txt or "",
                **({"error": str(err)[:300]} if err else {})}
            n = len(results)
            if n % 25 == 0:
                print(f"  [{arm}] {n}/{len(items)}", flush=True)

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, items))

    with open(out_path, "w", encoding="utf-8") as f:
        for n in sorted(results):
            f.write(json.dumps(results[n], ensure_ascii=False) + "\n")

    na = {t["id"]: sum(1 for r in results.values() if r["labels"][t["id"]] == NA)
          for t in theories}
    errs = collections.Counter(r["error"].split(":")[0] for r in results.values() if r.get("error"))
    meta = {"arm": arm, "provider": spec["provider"], "model": model, "error_kinds": dict(errs), "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS, "reasoning": "disabled", "mode": ("combined" if COMBINED else "separate"),
            "n": len(results), "seconds": round(time.time() - t0, 1),
            "usage": usage_tot, "na_counts": na,
            "na_rate_overall": round(sum(na.values()) / (len(results) * len(theories)), 4)}
    json.dump(meta, open(os.path.join(RUNS, f"{arm}.meta.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"{arm}: {len(results)} sentences, {meta['seconds']}s, __NA__ {meta['na_rate_overall']:.2%}")
    if meta["na_rate_overall"] > 0.05:
        print(f"  {arm}: __NA__ above 5%. Treat as a pipeline failure and re-run.", file=sys.stderr)
    return meta

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="M1,M2")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N sentences")
    ap.add_argument("--workers", type=int, default=12, help="concurrency per arm")
    ap.add_argument("--combined", action="store_true", help="present all four schemes in one call (default: one call per scheme)")
    ap.add_argument("--corpus", default=None, help="corpus file to label")
    ap.add_argument("--context", default=None, help="matching context file")
    ap.add_argument("--outdir", default=None, help="output directory (default: runs/)")
    ap.add_argument("--variant", default="repeat_tail", choices=["base","repeat_tail","move_tail"])
    a = ap.parse_args()
    global COMBINED
    COMBINED = a.combined
    if COMBINED: print('combined mode: all four schemes in one call')

    global PROMPT_VARIANT
    PROMPT_VARIANT = a.variant
    theories = load_theories()
    cb = codebook(theories)
    global RUNS
    # Relative paths resolve against the data root. Absolute paths still work: os.path.join
    # discards everything before an absolute component.
    if a.outdir: RUNS = os.path.join(DATA, "runs", a.outdir) if not os.path.isabs(a.outdir) else a.outdir
    src = os.path.join(IN_, a.corpus) if a.corpus else SAMPLE
    cx  = os.path.join(IN_, a.context) if a.context else CTX
    items = [json.loads(l) for l in open(src, encoding="utf-8")]
    ctxs = json.load(open(cx, encoding="utf-8"))
    # row_id is the primary key. uid is a prefix of the sentence text and is not unique.
    KEY = "row_id" if "row_id" in items[0] else "uid"
    for i, it in enumerate(items):
        it.setdefault("n", i + 1); it["_k"] = it[KEY]
    if a.limit:
        items = items[:a.limit]
    print(f"schemes {len(theories)}, categories {[len(t[chr(39)+chr(39)] if False else t['categories']) for t in theories]}")
    print(f"sentences {len(items)}, contexts {len(ctxs)}, workers {a.workers}\n")

    arms = a.arms.split(",")
    for arm in arms:
        if arm not in ARMS:
            sys.exit(f"unknown arm {arm}")
    # The arms run in parallel because they hit four different upstreams. That spreads the
    # load. Running them one after another only costs wall clock.
    with cf.ThreadPoolExecutor(max_workers=len(arms)) as ex:
        futs = {ex.submit(run_arm, arm, items, ctxs, theories, cb, a.workers): arm
                for arm in arms}
        for f in cf.as_completed(futs):
            try: f.result()
            except Exception as e:
                print(f"arm {futs[f]} failed: {type(e).__name__}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
