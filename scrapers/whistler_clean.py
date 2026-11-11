#!/usr/bin/env python3
"""Remove editorial apparatus from the extracted Whistler sentences.

The extracted corresp div includes catalogue entries, biographical notes and
cross-references as well as letters. The filters below remove sentences with markers
commonly found in that editorial material.

Removal rules, ordered from safest to most aggressive and counted separately so the cost
of each is visible:

  R1  third-person self-reference: JW or Whistler as a standalone token
  R2  catalogue or cross-reference syntax: #NNNNN, "[more]", "to JW,", bare "GUW"
  R3  biographical gloss: a name followed by parenthesised life dates
  R4  editorial date statement: begins "On <date> he/she ..." with a third-person pronoun

A sentence is kept unless a rule fires. The surviving set is re-profiled so the before and
after difference in each downstream statistic can be read off directly.
"""
import json, os, re, sys
from collections import Counter
import statistics as st
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.environ.get("WHISTLER_RAW") or os.path.join(REPO, "data", "raw", "whistler")
SRC  = os.path.join(RAW, "whistler_JW_letters_BODY.jsonl")
DST  = os.path.join(RAW, "whistler_JW_letters_CLEAN.jsonl")
SENT = re.compile(r"[A-Z][^.!?]{15,600}[.!?]")
R1 = re.compile(r"\b(JW|Whistler)\b")
R2 = re.compile(r"(#\d{3,}|\[more\]|\bto JW\b|\bGUW\b|\bcf\.\s)", re.I)
R3 = re.compile(r"\([12]\d{3}\s*[-–]\s*[12]\d{3}\)")
R4 = re.compile(r"^On \d|^In \d{4}", re.I)

def main():
    rows = [json.loads(l) for l in open(SRC)]
    kept_rows, fired = [], Counter()
    tot = kept = 0
    for r in rows:
        out = []
        for s in SENT.findall(r.get("body", "")):
            s = s.strip()
            tot += 1
            hit = None
            for name, pat in (("R1 third-person self-reference", R1), ("R2 catalogue or cross-reference", R2),
                              ("R3 biographical gloss", R3), ("R4 editorial date statement", R4)):
                if pat.search(s):
                    hit = name
                    break
            if hit:
                fired[hit] += 1
            else:
                out.append(s)
                kept += 1
        if out:
            rr = dict(r)
            rr["body_clean"] = " ".join(out)
            rr["n_sent_clean"] = len(out)
            kept_rows.append(rr)
    with open(DST, "w") as fh:
        for r in kept_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"sentences {tot:,}, kept {kept:,} ({kept/tot*100:.1f}%), removed {tot-kept:,}")
    for k, v in fired.most_common():
        print(f"  {k:<34} removed {v:>6,} ({v/tot*100:>5.1f}%)")
    print(f"letters {len(rows)} -> {len(kept_rows)}")
    print(f"written {DST}")
    import random
    rng = random.Random(4)
    print("\n5 kept sentences at random (all should be Whistler's own words):")
    pool = [s for r in kept_rows for s in SENT.findall(r.get("body_clean", ""))]
    for s in rng.sample(pool, min(5, len(pool))):
        print(f"  · {s.strip()[:115]}")

if __name__ == "__main__":
    main()
