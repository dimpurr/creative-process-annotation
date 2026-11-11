"""Recompute the paper's figures that rest only on the model labels, from the shipped outputs.

Offline: reads only runs/ and data/. No API key, no network.
Writes repro/out/results.md and, if matplotlib is available, the two figures.
"""
import json, os, collections, itertools

SCHEMES = ["MaceWard", "Tinio", "Botella17", "Wallas"]
CORPORA = ["vangogh", "whistler", "beethoven", "mozart"]
NAMES = {"vangogh": "Van Gogh", "whistler": "Whistler", "beethoven": "Beethoven", "mozart": "Mozart"}
NONE, NA = "none", "__NA__"


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def load(repo):
    rows = read_jsonl(f"{repo}/data/public/corpus_public.jsonl") + \
           read_jsonl(f"{repo}/data/derived/corpus_restricted_keys.jsonl")
    meta = {r["id"]: r for r in rows}
    runs = {}
    for sub in ("annotation-full", "reliability-120"):
        d = f"{repo}/runs/{sub}"
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".jsonl"):
                runs[(sub, fn[:-6])] = {r["id"]: r for r in read_jsonl(f"{d}/{fn}")}
    return meta, runs


def coverage(meta, arm_rows):
    """Non-`none` rate per scheme x corpus, and the any-label / all-none rates."""
    per = {s: collections.Counter() for s in SCHEMES}
    tot = collections.Counter()
    any_lab = collections.Counter()
    for rid, r in arm_rows.items():
        c = meta[rid]["corpus"]
        tot[c] += 1
        labs = r.get("labels") or {}
        hit_any = False
        for s in SCHEMES:
            v = labs.get(s)
            if v and v not in (NONE, NA):
                per[s][c] += 1
                hit_any = True
        any_lab[c] += hit_any
    return per, tot, any_lab


def krippendorff_nominal(units):
    """Nominal-scale Krippendorff's alpha. units = list of lists of labels."""
    units = [[v for v in u if v is not None] for u in units]
    units = [u for u in units if len(u) >= 2]
    if not units:
        return None
    n_total = sum(len(u) for u in units)
    Do = 0.0
    for u in units:
        m = len(u)
        disagree = sum(1 for a, b in itertools.permutations(u, 2) if a != b)
        Do += disagree / (m - 1)
    Do /= n_total
    counts = collections.Counter(v for u in units for v in u)
    De = sum(counts[a] * counts[b] for a, b in itertools.permutations(counts, 2))
    De /= (n_total * (n_total - 1))
    return 1 - Do / De if De else None


def pairwise_alpha(runs, arms, scheme):
    a, b = arms
    ra, rb = runs[("reliability-120", a)], runs[("reliability-120", b)]
    units = []
    for rid in sorted(set(ra) & set(rb)):
        la = (ra[rid].get("labels") or {}).get(scheme)
        lb = (rb[rid].get("labels") or {}).get(scheme)
        if la in (None, NA) or lb in (None, NA):
            continue
        units.append([la, lb])
    return krippendorff_nominal(units), len(units)


def tertile_series(meta, arm_rows, scheme, category, details=False):
    out = {}
    for c in CORPORA:
        num = collections.Counter(); den = collections.Counter()
        for rid, r in arm_rows.items():
            m = meta[rid]
            if m["corpus"] == "whistler" and m.get("tertile") is None:
                continue  # Undated Whistler sentences stay in the corpus but leave the thirds analysis
            if m["corpus"] != c:
                continue
            t = m.get("tertile")
            if t is None:
                continue
            den[t] += 1
            if (r.get("labels") or {}).get(scheme) == category:
                num[t] += 1
        rates = [100 * num[t] / den[t] if den[t] else None for t in (0, 1, 2)]
        out[c] = (rates, sum(num.values()), sum(den.values())) if details else [round(v, 1) if v is not None else None for v in rates]
    return out


PLOTTED = [("MaceWard", "development"), ("MaceWard", "finalization"),
           ("Botella17", "trials"), ("Tinio", "finalizing")]


def main(repo):
    meta, runs = load(repo)
    out_dir = f"{repo}/repro/out"; os.makedirs(out_dir, exist_ok=True)
    L = []
    def w(s=""): L.append(s); print(s)

    w("# Reproduced results\n")
    counts = collections.Counter(m["corpus"] for m in meta.values())
    w("Corpus: %d sentences (%s)\n" % (len(meta), ", ".join(f"{NAMES[c]} {counts[c]}" for c in CORPORA)))

    # --- 5.2 coverage ---
    w("## 5.2 Coverage, non-`none` rate by scheme and correspondence\n")
    w("| annotator | scheme | " + " | ".join([NAMES[c] for c in CORPORA]) + " |")
    w("|---|---|" + "---|" * len(CORPORA))
    any_by_arm = {}
    for arm in ("M1", "M2"):
        key = ("annotation-full", arm)
        if key not in runs:
            continue
        per, tot, any_lab = coverage(meta, runs[key])
        any_by_arm[arm] = (any_lab, tot)
        for s in SCHEMES:
            cells = [f"{100*per[s][c]/tot[c]:.1f}" if tot[c] else "-" for c in CORPORA]
            w(f"| {arm} | {s} | " + " | ".join(cells) + " |")
    w("")
    for arm, (any_lab, tot) in any_by_arm.items():
        n = sum(any_lab.values()); d = sum(tot.values())
        w(f"- **{arm}**: at least one label on {100*n/d:.1f}% of sentences; "
          f"`none` under all four on {100*(d-n)/d:.1f}%")
        wh = f"{100*any_lab['whistler']/tot['whistler']:.1f}" if tot["whistler"] else "-"
        w(f"  - Whistler, four schemes together: {wh}%")
    w("")

    # --- 5.1 reliability ---
    w("## 5.1 Reliability, pairwise Krippendorff's alpha on the 120-sentence sample\n")
    w("Agreement between the two model annotators on the calibration sample.\n")
    pairs = [("M1", "M2")]
    have = {a for (sub, a) in runs if sub == "reliability-120"}
    pairs = [p for p in pairs if p[0] in have and p[1] in have]
    w("| pair | " + " | ".join(SCHEMES) + " | n |")
    w("|---|" + "---|" * (len(SCHEMES) + 1))
    for p in pairs:
        cells, n = [], 0
        for s in SCHEMES:
            a, n = pairwise_alpha(runs, p, s)
            cells.append(f"{a:.3f}" if a is not None else "-")
        w(f"| {p[0]}–{p[1]} | " + " | ".join(cells) + f" | {n} |")
    w("")

    # --- 5.3 trends ---
    w("## 5.3 Trends across correspondence position (thirds, %)\n")
    arm = "M1" if ("annotation-full", "M1") in runs else "M2"
    w(f"Using {arm}. Sixteen combinations: four series x four correspondences.\n")
    w("| scheme.category | " + " | ".join([NAMES[c] for c in CORPORA]) + " |")
    w("|---|" + "---|" * len(CORPORA))
    same_dir = 0
    for scheme, cat in PLOTTED:
        series = tertile_series(meta, runs[("annotation-full", arm)], scheme, cat)
        cells = []
        for c in CORPORA:
            v = series[c]
            arrow = ""
            if None not in v:
                arrow = " ↑" if v[2] > v[0] else (" ↓" if v[2] < v[0] else " →")
            cells.append(" → ".join("-" if x is None else f"{x}" for x in v) + arrow)
        w(f"| {scheme}.{cat} | " + " | ".join(cells) + " |")
    w("")
    w("Direction reported in the paper: `development` and `trials` fall while `finalization` and "
      "`finalizing` rise for Van Gogh and Beethoven; Whistler's series change little; Mozart "
      "shows a more complex picture: `development` rises sharply in the final third, "
      "`finalization` falls from its middle-third high, `finalizing` continues to decline, "
      "and `trials` changes little.\n")

    # --- Appendix C trend-choice audit ---
    w("## Appendix C · Trend-choice audit (M1, final minus first third, percentage points)\n")
    w("Cells show the change in percentage points and the number of hits across the three thirds.\n")
    w("| scheme.category | " + " | ".join(NAMES[c] for c in CORPORA) + " |")
    w("|---|" + "---|" * len(CORPORA))
    with open(f"{repo}/codebook/schemes.json", encoding="utf-8") as fh:
        schemes = json.load(fh)
    for scheme in schemes:
        for category in scheme["categories"]:
            cat = category["key"]
            if cat == NONE:
                continue
            series = tertile_series(meta, runs[("annotation-full", "M1")], scheme["id"], cat, details=True)
            cells = [f"{series[c][0][2] - series[c][0][0]:+.1f} ({series[c][1]})" for c in CORPORA]
            w(f"| {scheme['id']}.{cat} | " + " | ".join(cells) + " |")
    w("")

    # --- 5.3 Van Gogh by year ---
    w("## 5.3 Van Gogh by year (all analysed sentences as denominator; years with <20 excluded)\n")
    w("| year | n | M1 finalization | M1 trials | M2 finalization | M2 trials |")
    w("|---|---|---|---|---|---|")
    for y in sorted({m.get("year") for m in meta.values()
                     if m["corpus"] == "vangogh" and m.get("year")}):
        ids = [rid for rid, m in meta.items()
               if m["corpus"] == "vangogh" and m.get("year") == y]
        if len(ids) < 20:
            continue
        cells = [str(y), str(len(ids))]
        for arm_rows, scheme, cat in (
                (runs[("annotation-full", "M1")], "MaceWard", "finalization"),
                (runs[("annotation-full", "M1")], "Botella17", "trials"),
                (runs[("annotation-full", "M2")], "MaceWard", "finalization"),
                (runs[("annotation-full", "M2")], "Botella17", "trials")):
            n = k = 0
            for rid in ids:
                v = (arm_rows[rid].get("labels") or {}).get(scheme)
                if v in (None, NA):
                    continue
                n += 1
                k += (v == cat)
            cells.append(f"{100*k/n:.1f}" if n else "-")
        w("| " + " | ".join(cells) + " |")
    w("")

    # --- figures ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        per, tot, _ = coverage(meta, runs[("annotation-full", arm)])
        fig, ax = plt.subplots(figsize=(7, 3.2))
        x = range(len(CORPORA)); width = 0.2
        for i, s in enumerate(SCHEMES):
            ax.bar([v + i * width for v in x],
                   [100 * per[s][c] / tot[c] if tot[c] else 0 for c in CORPORA],
                   width, label=s)
        ax.set_xticks([v + 1.5 * width for v in x]); ax.set_xticklabels(CORPORA)
        ax.set_ylabel("non-`none` (%)"); ax.legend(fontsize=7); fig.tight_layout()
        fig.savefig(f"{out_dir}/fig-coverage.pdf"); plt.close(fig)

        fig, axes = plt.subplots(1, 4, figsize=(11, 2.8), sharey=True)
        for axi, c in zip(axes, CORPORA):
            for scheme, cat in PLOTTED:
                ser = tertile_series(meta, runs[("annotation-full", arm)], scheme, cat)[c]
                if None in ser:
                    continue
                axi.plot([1, 2, 3], ser, marker="o", ms=3, label=f"{scheme}.{cat}")
            axi.set_title(c, fontsize=9); axi.set_xticks([1, 2, 3])
        axes[0].set_ylabel("% of sentences")
        axes[-1].legend(fontsize=6, loc="best"); fig.tight_layout()
        fig.savefig(f"{out_dir}/fig-tertile.pdf"); plt.close(fig)
        w("Figures written to `repro/out/fig-coverage.pdf` and `repro/out/fig-tertile.pdf`.\n")
    except ImportError:
        w("_matplotlib not installed; tables above are complete, figures skipped._\n")

    with open(f"{out_dir}/results.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"\nWritten: {out_dir}/results.md")


if __name__ == "__main__":
    # The repository root is the parent of this file's directory.
    main(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
