# Leveraging Creative-Process Theories to Enrich a Corpus of Artists' Letters through Annotation Schemes

This repository contains the code, model outputs and derived data for the paper of the same
title (Yang Chen and Mark Gotham, Computational Humanities Research 2027). The study takes four
published theories of the creative process and turns their definitions into annotation schemes,
adding brief explanatory notes where needed. Two language models apply the schemes to a
sentence-level corpus drawn from the letters of Van Gogh, Whistler, Beethoven and Mozart.

## Reproducing the results

```bash
./repro/reproduce.sh
```

The script runs offline in a few seconds and needs only Python 3.9 or later (`matplotlib` is
optional). It checks the inputs against `repro/MANIFEST.txt`,
then recomputes from the model outputs in `runs/` the numbers and figures in the paper that
rest only on the model annotators' labels. Results go to `repro/out/results.md`, with two PDF
figures and a year-by-year diagnostic for the Van Gogh correspondence. The two PDFs are
regenerated only when `matplotlib` is installed; otherwise the tables are written and the
shipped PDFs are left as they are.

The model outputs are included because the annotators are served over APIs that change
without notice, so a later rerun may not reach the same models. The models are M1 `gpt-5.6-luna` and
M2 `qwen3-32b`; parameters are recorded in `runs/*/*.meta.json`. Each scheme was given to the models in a
separate call. The second annotator (M2, Qwen3-32B) is no longer available at the DashScope
endpoint used for the paper.

`--annotate` (re-run the annotators; needs API keys, see `.env.example`) and `--rebuild`
(re-fetch the restricted texts) are not yet wired into the script and stop after their
checks. To re-run the annotation, call `code/run_arms.py` directly with the restricted texts
reattached and the inputs described in the script header. This is not a one-line rerun.
New labels will not match the shipped outputs exactly.

## Contents

| path | contents |
|---|---|
| `codebook/` | The four schemes. `schemes.json` holds the category definitions, based on the published theories with brief explanations where needed; `README.md` renders them for reading. |
| `prompts/` | The prompts as given to the models: one per scheme, and a combined version. |
| `code/` | Corpus construction, screening, and the annotation runner. |
| `runs/` | Model outputs: `annotation-full/` for the full corpus, `reliability-120/` for the 120-sentence calibration sample. Each `.meta.json` records parameters including temperature and token limits. |
| `data/` | Sentences keyed by an opaque `id`, the join key across `data/` and `runs/`. See `data/README.md`. |
| `scrapers/` | How the source texts were obtained and cleaned. |
| `repro/` | The entry script, the input manifest and the analysis code. |

## Data and rights

Beethoven's and Mozart's letters are read in Lady Wallace's 1866 English translations, which
are in the public domain, and their text is included. The Van Gogh edition (2009) and the
Whistler correspondence (University of Glasgow) cannot be redistributed. For those two the
repository gives letter references, character counts and SHA-256 hashes, so the text can be
reattached after fetching it from the source. `data/README.md` sets out the rights for each
source and the fields in each file.

`scrapers/whistler_scrape.py` keeps to the ten-second crawl delay in the site's `robots.txt`
and uses a single connection.

The paper also reports human annotation and a distillation experiment (a RoBERTa model
fine-tuned on one annotator's labels). Neither is part of this release.

## Licence

Code is released under the MIT licence (`LICENSE`). Data and model outputs are released under
CC BY 4.0 (`data/LICENSE`). No licence is granted over the Van Gogh and Whistler source texts,
which are not included.

## Citation

If you use this repository, please cite the paper:

> Yang Chen and Mark Gotham. Leveraging Creative-Process Theories to Enrich a Corpus of
> Artists' Letters through Annotation Schemes. In *Computational Humanities Research 2027*.

A DOI for this repository will be added here. Citation metadata are in `CITATION.cff`.
