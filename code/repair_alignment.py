#!/usr/bin/env python3
"""Repair the screening batches whose answer did not line up with the question.

The screening call sends a batch of sentences and asks for a bare JSON array of YES/NO in
the same order. When the model returns fewer entries than the batch holds, `parse` fills
the tail with None. That is a guess: it assumes the entry the model left out was the last
one. If the model instead skipped something in the middle, every verdict after that point
is attributed to the wrong sentence, and nothing in the output says so.

The repair asks for the identifier next to the verdict, so alignment is read off the answer
instead of assumed. The criteria are the same text as before, character for character; the
only edit is the sentence describing the return format.

Changing the prompt changes the condition, so the repair runs in two stages:

  1. Validation. Batches that already parsed cleanly are re-run in the identifier format
     and compared against their original verdicts. If the two formats disagree, the repair
     is not a repair, and the disagreement rate says so before anything is overwritten.
  2. Repair. Only the batches that came back the wrong length are rewritten.

Stage 1 also gives the number worth knowing about the old data: among the mismatched
batches, how many verdicts the tail-padding had silently attributed to the wrong sentence.
"""
import collections, concurrent.futures as cf, importlib.util, json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.environ.get("WORK_DIR") or os.path.join(REPO, "data", "work")
spec = importlib.util.spec_from_file_location("screen", os.path.join(HERE, "screen_three_ctx.py"))
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)

RETURN_LINE = 'Return ONLY a JSON array of "YES"/"NO" strings, one per sentence, in the same order.'
RETURN_IDS = ('Return ONLY a JSON array of objects, one per sentence, each with the '
              'sentence\'s bracketed identifier and the verdict, like '
              '[{"id": "b00001", "verdict": "YES"}, ...].')


def prompt_ids(artist, letter, batch):
    p = screen.make_prompt(artist, letter, batch)
    assert RETURN_LINE in p
    return p.replace(RETURN_LINE, RETURN_IDS)


def parse_ids(text, batch):
    """Return {id: bool}. Anything not matched is absent, never guessed."""
    if not text or text.startswith("__ERROR__"):
        return {}
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return {}
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return {}
    valid = {it["id"] for it in batch}
    out = {}
    for o in arr:
        if not isinstance(o, dict):
            continue
        i, v = str(o.get("id", "")).strip(), str(o.get("verdict", "")).strip().upper()
        if i in valid and v in ("YES", "Y", "NO", "N"):
            out[i] = v in ("YES", "Y")
    return out


def batches(corpus):
    items, letters, _ = screen.load(corpus)
    by = collections.defaultdict(list)
    for it in items:
        by[str(it["letter_id"])].append(it)
    out = []
    for lid in sorted(by):
        for i in range(0, len(by[lid]), screen.BATCH):
            out.append((lid, by[lid][i:i + screen.BATCH]))
    return out, letters


def run(corpus, n_validate=40):
    path = os.path.join(WORK, "screening", "screen_%s_decisions.json" % corpus)
    dec = json.load(open(path, encoding="utf-8"))
    jobs, letters = batches(corpus)
    bad = [(l, b) for l, b in jobs if any(dec.get(x["id"]) is None for x in b)]
    good = [(l, b) for l, b in jobs if len(b) > 1 and not any(dec.get(x["id"]) is None for x in b)]

    def ask(job):
        lid, b = job
        raw, _ = screen.call(prompt_ids(screen.ARTIST[corpus], letters.get(lid, ""), b))
        return job, parse_ids(raw, b)

    # 1. is the identifier format the same question?
    sample = random.Random(20260812).sample(good, min(n_validate, len(good)))
    agree = differ = missing = 0
    with cf.ThreadPoolExecutor(max_workers=screen.WORKERS) as ex:
        for (lid, b), got in ex.map(ask, sample):
            for it in b:
                if it["id"] not in got:
                    missing += 1
                elif got[it["id"]] == dec.get(it["id"]):
                    agree += 1
                else:
                    differ += 1
    tot = agree + differ
    print("[%s] validation on %d clean batches: agreement %d/%d (%.1f%%), unanswered %d"
          % (corpus, len(sample), agree, tot, agree / max(1, tot) * 100, missing), flush=True)

    # 2. repair, and measure what the tail-padding had got wrong
    fixed = flipped = still = 0
    with cf.ThreadPoolExecutor(max_workers=screen.WORKERS) as ex:
        for (lid, b), got in ex.map(ask, bad):
            for it in b:
                if it["id"] not in got:
                    still += 1
                    continue
                old = dec.get(it["id"])
                if old is not None and old != got[it["id"]]:
                    flipped += 1
                dec[it["id"]] = got[it["id"]]
                fixed += 1
    json.dump(dec, open(path, "w"), ensure_ascii=False)
    left = sum(1 for v in dec.values() if v is None)
    print("[%s] repaired %d batches: %d verdicts written, %d had been attributed to the "
          "wrong sentence, %d still unanswered, None now %d"
          % (corpus, len(bad), fixed, flipped, still, left), flush=True)
    return {"corpus": corpus, "agree": agree, "differ": differ,
            "flipped": flipped, "none": left}


if __name__ == "__main__":
    res = [run(c) for c in sys.argv[1:] or ["beethoven", "mozart", "whistler"]]
    json.dump(res, open(os.path.join(WORK, "screening", "repair_report.json"), "w"), indent=1)
