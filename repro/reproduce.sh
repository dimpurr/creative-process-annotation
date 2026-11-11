#!/usr/bin/env bash
# Reproduce the paper's numbers and figures that rest only on the model annotators' labels.
#
#   ./repro/reproduce.sh              offline, no API key, no network. Default.
#   ./repro/reproduce.sh --annotate   re-run the annotators on the 120-sentence sample (needs keys; not yet wired up)
#   ./repro/reproduce.sh --annotate full
#                                     re-run on all 3928 sentences (needs keys; not yet wired up)
#   ./repro/reproduce.sh --rebuild    re-fetch the restricted texts (needs network; not yet wired up)
#
# The default path recomputes those numbers and figures from the model outputs shipped
# in runs/. The models are served over APIs that change without notice, so re-running
# the annotators is not expected to reproduce the outputs exactly.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

MODE="verify"
case "${1:-}" in
  --annotate) MODE="annotate"; SCOPE="${2:-sample}" ;;
  --rebuild)  MODE="rebuild" ;;
  ""|--verify) MODE="verify" ;;
  -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown option: $1  (try --help)" >&2; exit 2 ;;
esac

python3 - "$MODE" "${SCOPE:-}" <<'PY'
import hashlib, json, os, sys, subprocess
mode, scope = sys.argv[1], sys.argv[2]
REPO = os.getcwd()

def sha16(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]

# ---- fingerprint gate -------------------------------------------------------
print("Verifying inputs")
bad = 0
for line in open(os.path.join(REPO, "repro", "MANIFEST.txt"), encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    want, rel = line.split(None, 1)
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        print(f"  MISSING  {rel}"); bad += 1; continue
    got = sha16(path)
    ok = want.startswith(got)
    print(f"  {'ok  ' if ok else 'FAIL'}     {rel}  {got}")
    bad += (not ok)
if bad:
    sys.exit("\nInput verification failed. Refusing to compute: a changed corpus or sample "
             "silently invalidates every number below.")
print("  all inputs match MANIFEST.txt\n")

if mode == "annotate":
    print("Annotation is not yet wired up; see code/run_arms.py.")
    sys.exit(0)

if mode == "rebuild":
    print("Rebuilding is not yet wired up; see scrapers/ for the steps.")
    sys.exit(0)

# ---- default: recompute everything from the shipped model outputs -----------
sys.path.insert(0, os.path.join(REPO, "repro"))
import analyse
analyse.main(REPO)
PY
