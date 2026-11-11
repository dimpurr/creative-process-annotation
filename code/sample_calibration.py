#!/usr/bin/env python3
"""Draw the reliability sample: an equal number of sentences from each correspondence.

The seed is fixed. A sample redrawn with a new seed is a new sample, and the figures
computed from it are not comparable with the ones already reported. Changing the corpus
does change which sentences are drawn; the reliability figures have to describe the
corpus the rest of the analysis describes.

Writes the sample and its fingerprint. This step draws the sample; annotation happens
elsewhere.
"""
import collections, hashlib, json, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.environ.get("WORK_DIR") or os.path.join(REPO, "data", "work")

SEED = 20260804          # fixed, do not change
PER_CORPUS = int(os.environ.get("PER_CORPUS", "30"))
CORPORA = ["vangogh", "whistler", "beethoven", "mozart"]


def main():
    rows = [json.loads(l) for l in open(os.path.join(WORK, "corpus.jsonl"), encoding="utf-8")]
    by = collections.defaultdict(list)
    for r in rows:
        by[r["corpus"]].append(r)

    rng = random.Random(SEED)
    picked = []
    for c in CORPORA:
        items = sorted(by[c], key=lambda r: r["row_id"])   # order fixed before sampling
        picked += rng.sample(items, PER_CORPUS)

    for i, r in enumerate(picked, 1):
        r["n"] = i

    out = os.path.join(WORK, "calibration_sample.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in picked:
            f.write(json.dumps({k: r[k] for k in
                                ("n", "uid", "row_id", "corpus", "sentence",
                                 "sentence_id", "letter_id", "tertile")},
                               ensure_ascii=False) + "\n")

    uids = [r["uid"] for r in picked]
    print("%d rows, %s" % (len(picked), dict(collections.Counter(r["corpus"] for r in picked))))
    print("  uid unique %s   tertiles %s"
          % (len(set(uids)) == len(uids),
             dict(collections.Counter(r["tertile"] for r in picked))))
    print("  seed %d   sample sha256[:16] %s"
          % (SEED, hashlib.sha256(open(out, "rb").read()).hexdigest()[:16]))



if __name__ == "__main__":
    main()
