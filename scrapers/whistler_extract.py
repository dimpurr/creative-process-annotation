#!/usr/bin/env python3
"""Extract letter bodies from the scraped Whistler HTML.

The scrape stored metadata for every letter but left the body empty. The HTML itself is
intact and the text sits in <div class="corresp"> as <p> paragraphs, so this is a parsing gap. No
data was lost.

The metadata is worth keeping in its own right. Each record carries a full date, an
addressee, an author field that separates Whistler's own letters from his correspondents',
and a document type.

Rules: keep only <p> inside the corresp div. Drop the first paragraph, which repeats the
metadata header ("System Number: ... Date: ... Author: ..."). Strip tags, footnote markers
such as [5], and editorial [sic]. Normalise entities and whitespace.
"""
import re, os, json, glob, html
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.environ.get("WHISTLER_RAW") or os.path.join(REPO, "data", "raw", "whistler")
meta = {}
for line in open(f"{SRC}/whistler_JW_letters_full.jsonl"):
    d = json.loads(line)
    meta[str(d.get("cid"))] = d

CORRESP = re.compile(r'<div[^>]*class="corresp"[^>]*>(.*?)</div>', re.S)
PARA = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
TAG = re.compile(r"<[^>]+>")
FOOT = re.compile(r"\[\d+\]")

def clean(x):
    x = TAG.sub(" ", x)
    x = html.unescape(x)
    x = FOOT.sub("", x)
    x = x.replace("[sic]", "")
    return re.sub(r"\s+", " ", x).strip()

out, empty, nofile = [], 0, 0
files = sorted(glob.glob(f"{SRC}/html_letters/*.html"))
for f in files:
    t = open(f, encoding="utf-8", errors="replace").read()
    m = CORRESP.search(t)
    if not m:
        empty += 1
        continue
    ps = [clean(p) for p in PARA.findall(m.group(1))]
    ps = [p for p in ps if p]
    if not ps:
        empty += 1
        continue
    head = ps[0]
    body = " ".join(ps[1:]).strip()
    sysno = re.search(r"System Number:\s*(\d+)", head)
    cid = os.path.basename(f)[:-5]
    row = dict(meta.get(cid, {}))
    row["cid"] = cid
    row["sysno"] = sysno.group(1) if sysno else None
    row["body"] = body
    row["n_words"] = len(body.split())
    if not body:
        empty += 1
        continue
    out.append(row)

dst = f"{SRC}/whistler_JW_letters_BODY.jsonl"
with open(dst, "w") as fh:
    for r in out:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"html files {len(files)}, bodies extracted {len(out)}, empty or failed {empty}")
print(f"written {dst} ({os.path.getsize(dst)/1e6:.1f} MB)")
tw = sum(r["n_words"] for r in out)
print(f"total words {tw:,}, mean per letter {tw/max(1,len(out)):.0f}")
print(f"\nauthors, top 5: {Counter(r.get('author') for r in out).most_common(5)}")
print(f"document types, top 5: {Counter(r.get('doctype') for r in out).most_common(5)}")
yrs = [int(y) for r in out for y in [str(r.get('year_query',''))] if y.isdigit()]
if yrs:
    c = Counter(yrs)
    print(f"\nyears {min(yrs)} to {max(yrs)}, {len(c)} distinct")
    print(f"letters per year: mean {len(yrs)/len(c):.1f}, median {sorted(c.values())[len(c)//2]}")
print("\nrecipients, top 12:")
for k, v in Counter(r.get("recipient") for r in out).most_common(12):
    print(f"  {v:>5}  {k}")
