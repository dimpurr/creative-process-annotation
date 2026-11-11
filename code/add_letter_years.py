"""Attach letter years and rebuild Whistler's date-ordered thirds (one-off).

Reads a JSONL of letter dates (one object per letter with `corpus`, `letter_id`
and `year`) and writes them into data/derived/corpus_restricted_keys.jsonl:

  python3 code/add_letter_years.py --years letter_dates.jsonl

The years come from each edition's own metadata, not from model inference: the
Van Gogh scholarly edition records a date with each letter, and the Whistler
online edition does the same. Every Van Gogh row in the corpus carries its
letter's year. Whistler rows with a dated letter are sorted by year (stable) and
split into three equal-count thirds, stored as tertile 0/1/2 (paper Fig. 3).
The 161 Whistler sentences whose letters carry no date stay in the corpus with
year and tertile set to null; they are skipped only by the thirds analysis
(paper §5.3). Beethoven and Mozart rows are untouched.
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument("--years", required=True,
                help="JSONL of letter dates: {corpus, letter_id, year}")
ap.add_argument("--corpus", default=os.path.join(
    REPO, "data/derived/corpus_restricted_keys.jsonl"))
a = ap.parse_args()

if not os.path.exists(a.years):
    sys.exit(f"letter-dates file not found: {a.years}")

YEAR = {(r["corpus"], str(r["letter_id"])): r.get("year")
        for r in map(json.loads, open(a.years, encoding="utf-8"))}

rows = [json.loads(line) for line in open(a.corpus, encoding="utf-8")
        if line.strip()]
wh = [r for r in rows if r.get("corpus") == "whistler"]
other = [r for r in rows if r.get("corpus") != "whistler"]

dated = [r for r in wh if YEAR.get(("whistler", str(r["letter_id"])))]
undated = [r for r in wh if not YEAR.get(("whistler", str(r["letter_id"])))]
print(f"whistler: {len(wh)} = dated {len(dated)} + undated {len(undated)}")
assert len(dated) == 1566 and len(undated) == 161, (len(dated), len(undated))

dated.sort(key=lambda r: YEAR[("whistler", str(r["letter_id"]))])
n = len(dated)
cut = (round(n / 3), round(2 * n / 3))
for i, r in enumerate(dated):
    r = dict(r)
    r["year"] = YEAR[("whistler", str(r["letter_id"]))]
    r["tertile"] = 0 if i < cut[0] else (1 if i < cut[1] else 2)
    dated[i] = r
undated = [dict(r, year=None, tertile=None) for r in undated]
y0 = [YEAR[("whistler", str(r["letter_id"]))] for r in dated]
print(f"tertile 0: {y0[0]}-{y0[cut[0] - 1]} ({cut[0]} rows)")
print(f"tertile 1: {y0[cut[0]]}-{y0[cut[1] - 1]} ({cut[1] - cut[0]} rows)")
print(f"tertile 2: {y0[cut[1]]}-{y0[-1]} ({n - cut[1]} rows)")

out = other + dated + undated
with open(a.corpus, "w", encoding="utf-8") as fh:
    for r in out:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"wrote {a.corpus}: {len(out)} rows "
      f"({len(other)} other + {len(dated)} whistler dated + "
      f"{len(undated)} undated)")
