#!/usr/bin/env python3
"""Assemble the analysis corpus and the letter context that goes with it.

Input is the screening decisions for the three sentence-route correspondences and the
identifier-route rows for the fourth. Output is one JSONL of rows and one JSON of letter
context keyed by row, which is what the annotation step reads.

Three points need stating, because each has caused silent errors before.

`tertile` records where a row sits in the correspondence, early, middle or late. That is
only meaningful if the rows are in letter order, and a pool assembled from a source file
inherits whatever order that file happens to use. The Whistler pool was once out of
letter order, which put a fifth of its rows in the wrong third. The order is asserted
here rather than assumed.

`uid` is the first characters of a sentence behind a corpus prefix, which collides whenever
two sentences open the same way. Scoring code keys on it and drops the duplicates without
saying so. A counter is appended when a collision would otherwise happen.

Rows are put through the admission test in `corpus_filter` before anything else. The
sentence-route corpora have already passed it during screening; the identifier route has
not, and its rows are passages rather than sentences, so it is tested in passage mode.
"""
import collections, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.environ.get("WORK_DIR") or os.path.join(REPO, "data", "work")
sys.path.insert(0, HERE)
import corpus_filter

CORPORA = ("vangogh", "whistler", "beethoven", "mozart")
PASSAGE_ROUTE = {"vangogh"}

norm = lambda s: re.sub(r"\s+", " ", s).strip()


def letter_key(letter_id):
    s = str(letter_id)
    m = re.search(r"letter-(\d+)", s) or re.search(r"^(\d+)$", s)
    return int(m.group(1)) if m else 10 ** 9


def letters_for(corpus):
    """Return {letter_id: whole letter text}."""
    if corpus == "whistler":
        out = {}
        p = os.path.join(WORK, "whistler", "whistler_letters_clean2.jsonl")
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            if r.get("author") == "JW" and r.get("doctype") == "Letter":
                out[str(r["cid"])] = norm(r.get("body_clean2") or "")
        return out
    if corpus == "vangogh":
        return {}                      # carried in with the identifier-route rows
    raw = json.load(open(os.path.join(WORK, "parsed",
                                      "%s_letters_stripped.json" % corpus.capitalize()),
                         encoding="utf-8"))
    return {str(k): norm(" ".join(v) if isinstance(v, list) else str(v))
            for k, v in raw.items()}


def main():
    selected = json.load(open(os.path.join(WORK, "screening", "selected.json"),
                              encoding="utf-8"))
    vg_rows = [json.loads(l) for l in
               open(os.path.join(WORK, "identifier_route", "vangogh_rows.jsonl"),
                    encoding="utf-8")]
    vg_ctx = json.load(open(os.path.join(WORK, "identifier_route", "vangogh_context.json"),
                            encoding="utf-8"))

    vg_kept, vg_dropped = corpus_filter.apply(vg_rows, mode="passage")
    print("vangogh  %d -> %d  %s" % (len(vg_rows), len(vg_kept), dict(vg_dropped)))

    rows, ctx, seen = [], {}, collections.Counter()

    def add(corpus, sentence, letter_id, row_id, letter_text):
        base = "%s_%s" % (corpus[:2], sentence[:25])
        seen[base] += 1
        uid = base if seen[base] == 1 else "%s#%d" % (base, seen[base])
        rows.append({"uid": uid, "row_id": row_id, "corpus": corpus, "sentence": sentence,
                     "sentence_id": sentence[:60], "letter_id": str(letter_id),
                     "tertile": None})
        pos = letter_text.find(sentence[:80]) if letter_text else -1
        ctx[row_id] = {"corpus": corpus, "letter_id": str(letter_id),
                       "letter_text": letter_text,
                       "span": [pos, pos + len(sentence)] if pos >= 0 else None}

    for corpus in CORPORA:
        if corpus in PASSAGE_ROUTE:
            for r in vg_kept:
                add(corpus, r["sentence"], r["letter_id"], r["row_id"],
                    vg_ctx.get(r["row_id"], {}).get("letter_text", ""))
            continue
        letters = letters_for(corpus)
        for i, it in enumerate(selected[corpus]):
            add(corpus, norm(it["sentence"]), it["letter_id"],
                "%s_%05d" % (corpus, i), letters.get(str(it["letter_id"]), ""))

    # tertile, assigned over letter order rather than over whatever order the rows arrived in
    for corpus in CORPORA:
        w = [r for r in rows if r["corpus"] == corpus]
        order = sorted(range(len(w)), key=lambda i: (letter_key(w[i]["letter_id"]), i))
        n = len(w)
        for rank, i in enumerate(order):
            w[i]["tertile"] = 0 if rank < n // 3 else (1 if rank < 2 * n // 3 else 2)
        spans = [[letter_key(r["letter_id"]) for r in w if r["tertile"] == t] for t in (0, 1, 2)]
        for a, b in zip(spans, spans[1:]):
            if a and b and max(a) > min(b):
                raise SystemExit("tertile ranges overlap in %s: rows are not in letter order"
                                 % corpus)

    ids = [r["row_id"] for r in rows]
    assert len(set(ids)) == len(ids), "row_id collision"
    uids = [r["uid"] for r in rows]
    assert len(set(uids)) == len(uids), "uid collision"

    out = os.path.join(WORK, "corpus.jsonl")
    os.makedirs(WORK, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump(ctx, open(os.path.join(WORK, "context.json"), "w", encoding="utf-8"),
              ensure_ascii=False)

    print("\n%d rows, row_id and uid unique, tertiles follow letter order" % len(rows))
    for c, k in collections.Counter(r["corpus"] for r in rows).most_common():
        print("  %-10s %5d" % (c, k))
    print("\ncorpus.jsonl sha256 %s"
          % hashlib.sha256(open(out, "rb").read()).hexdigest()[:16])


if __name__ == "__main__":
    main()
