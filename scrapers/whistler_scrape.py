#!/usr/bin/env python3
"""
Polite scraper for The Correspondence of James McNeill Whistler (University of Glasgow).

robots.txt sets `Crawl-delay: 10`, and it is honoured strictly: one connection, a ten second
sleep between requests, no concurrency. This is a small academic site, not a CDN-backed
target. The stated delay is respected; it is not worked around with parallel connections.

Two-phase design (avoids guessing ~13,600 sequential IDs one-by-one):
  Phase 1: "letters by date" listing (.../correspondence/date/result/?year=YYYY&month=&Submit=Search),
           paginated 20/page. Each row already gives cid + date + "AUTHOR to RECIPIENT" + repository
           WITHOUT needing to fetch the individual letter page. Years 1829-1903.
  Phase 2: filter Phase-1 index to entries authored by JW himself ("JW to ..."), then fetch
           each individual letter page (.../recno/display/?cid=NNNNN) for the full body text.

Raw HTML is saved for every page fetched in both phases, not just the parsed fields. At ten
seconds a request, re-fetching anything later is expensive, so nothing is thrown away.

Output goes to data/raw/whistler by default; set WHISTLER_RAW to put it elsewhere.
"""
import re, json, os, time, sys
import requests

REPO    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.environ.get("WHISTLER_RAW") or os.path.join(REPO, "data", "raw", "whistler")
LISTING_HTML_DIR = os.path.join(OUT_DIR, "html_listing")
LETTER_HTML_DIR = os.path.join(OUT_DIR, "html_letters")
for d in (OUT_DIR, LISTING_HTML_DIR, LETTER_HTML_DIR):
    os.makedirs(d, exist_ok=True)

CRAWL_DELAY = 10.0  # seconds, per robots.txt
YEARS = list(range(1829, 1904))  # site's own year dropdown range

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"})

LISTING_URL = "https://www.whistler.arts.gla.ac.uk/correspondence/date/result/index.php"
LETTER_URL = "https://www.whistler.arts.gla.ac.uk/correspondence/recno/display/"

ROW_RE = re.compile(
    r"\[(?P<cid>\d+)\]\s*(?P<date>[^:]+):\s*(?P<author>.+?)\s+to\s+(?P<recipient>.+?)\s*\((?P<doctype>[^)]+)\)\s*(?P<repo>[^\[]*)\[more\]",
    re.S,
)
PAGE_RE = re.compile(r"Page\s+(\d+)\s+of\s+(\d+)")


def polite_get(url, params, save_path):
    r = session.get(url, params=params, timeout=30)
    with open(save_path, "w") as f:
        f.write(r.text)
    time.sleep(CRAWL_DELAY)
    return r.text


def strip_ws(html_fragment):
    text = re.sub(r"<[^>]+>", " ", html_fragment)
    text = re.sub(r"&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_listing_page(html):
    m = re.search(r'id="container".*?id="footer"', html, re.S)
    block = m.group(0) if m else html
    text = strip_ws(block)
    rows = []
    for rm in ROW_RE.finditer(text):
        rows.append({
            "cid": rm.group("cid"),
            "date": rm.group("date").strip(),
            "author": rm.group("author").strip(),
            "recipient": rm.group("recipient").strip(),
            "doctype": rm.group("doctype").strip(),
            "repo": rm.group("repo").strip(),
        })
    pm = PAGE_RE.search(text)
    cur_page, total_pages = (int(pm.group(1)), int(pm.group(2))) if pm else (1, 1)
    return rows, cur_page, total_pages


def phase1_index():
    index_path = os.path.join(OUT_DIR, "phase1_full_index.jsonl")
    done_years_path = os.path.join(OUT_DIR, "phase1_done_years.json")
    done_years = set(json.load(open(done_years_path))) if os.path.exists(done_years_path) else set()
    all_rows = []
    if os.path.exists(index_path):
        all_rows = [json.loads(l) for l in open(index_path)]

    out_f = open(index_path, "a")
    for year in YEARS:
        if year in done_years:
            continue
        page = 1
        total_pages = 1
        while page <= total_pages:
            save_path = os.path.join(LISTING_HTML_DIR, f"{year}_p{page}.html")
            html = polite_get(LISTING_URL, {"year": year, "month": "", "Submit": "Search", "page": page}, save_path)
            rows, cur_page, total_pages = parse_listing_page(html)
            for r in rows:
                r["year_query"] = year
                out_f.write(json.dumps(r, ensure_ascii=False) + "\n")
                out_f.flush()
            print(f"[phase1] year={year} page={page}/{total_pages} rows={len(rows)}", file=sys.stderr, flush=True)
            page += 1
        done_years.add(year)
        json.dump(sorted(done_years), open(done_years_path, "w"))
    out_f.close()
    print("PHASE1_DONE", file=sys.stderr, flush=True)


def phase2_fetch_jw_letters():
    index_path = os.path.join(OUT_DIR, "phase1_full_index.jsonl")
    rows = [json.loads(l) for l in open(index_path)]
    seen_cids = set()
    jw_rows = []
    for r in rows:
        if r["cid"] in seen_cids:
            continue
        seen_cids.add(r["cid"])
        if re.match(r"^JW\b", r["author"]):
            jw_rows.append(r)
    print(f"[phase2] {len(jw_rows)} JW-authored (outgoing) letters to fetch (of {len(seen_cids)} unique total)", file=sys.stderr, flush=True)

    out_path = os.path.join(OUT_DIR, "whistler_JW_letters_full.jsonl")
    done_cids_path = os.path.join(OUT_DIR, "phase2_done_cids.json")
    done_cids = set(json.load(open(done_cids_path))) if os.path.exists(done_cids_path) else set()
    out_f = open(out_path, "a")

    for i, r in enumerate(jw_rows):
        cid = r["cid"]
        if cid in done_cids:
            continue
        save_path = os.path.join(LETTER_HTML_DIR, f"{cid}.html")
        html = polite_get(LETTER_URL, {"cid": cid.zfill(5)}, save_path)
        body = extract_body(html)
        rec = dict(r)
        rec["body_raw"] = body
        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out_f.flush()
        done_cids.add(cid)
        if (i + 1) % 25 == 0:
            json.dump(sorted(done_cids), open(done_cids_path, "w"))
            print(f"[phase2] {i+1}/{len(jw_rows)} fetched", file=sys.stderr, flush=True)
    json.dump(sorted(done_cids), open(done_cids_path, "w"))
    out_f.close()
    print("PHASE2_DONE", file=sys.stderr, flush=True)


def extract_body(html):
    m = re.search(r"Document Type:.*?(?=Notes:|top\s*The Correspondence|$)", html, re.S)
    if not m:
        return ""
    text = strip_ws(m.group(0))
    # after "Document Type: <short code>" the letter body follows
    mm = re.match(r"Document Type:\s*\S+\s*(.*)", text, re.S)
    return mm.group(1).strip() if mm else ""


if __name__ == "__main__":
    phase1_index()
    phase2_fetch_jw_letters()
    print("ALL_DONE", file=sys.stderr, flush=True)
