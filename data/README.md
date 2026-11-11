# Data

Sentences are keyed by an opaque `id` (e.g. `vangogh_01480`). The same `id` is the join key
in `runs/`, `data/`, and the calibration sample. No file in this repository contains a
sentence identifier derived from the sentence text.

## `public/corpus_public.jsonl`

867 sentences (Beethoven 490, Mozart 377), full text included.

Read in Lady Grace Wallace's 1866 English translations, which are in
the public domain (Project Gutenberg 5307, 13065, 13272); Wallace died in 1878. Redistribution is permitted, so the
sentence text is included.

## `derived/corpus_restricted_keys.jsonl`

3,061 sentences (Van Gogh 1,334, Whistler 1,727), keys only. The sentence text is not included.

| Source | Rights |
|---|---|
| Van Gogh letters (vangoghletters.org) | "Copyright © 2009 Van Gogh Museum, Amsterdam, Huygens ING, The Hague. All Rights Reserved. No part of this publication may be reproduced or transmitted in any form or by any means…" The letters themselves are long out of copyright; the 2009 critical edition's transcription and translation are not. |
| Whistler correspondence (University of Glasgow) | "These letters are protected by copyright… their letters should not be reproduced or published in any form without the prior written consent of the University…" |

Each record carries what is needed to reattach the text without redistributing it:

| field | use |
|---|---|
| `id` | join key across this repository |
| `corpus` | the correspondence the sentence belongs to (`vangogh`, `whistler`) |
| `letter_id` | locate the letter in the source edition |
| `sentence_sha256` | verify an exact match after re-fetching |
| `n_chars` | sanity check before hashing |
| `tertile` | the third of the correspondence a sentence falls in. Van Gogh, Beethoven and Mozart follow their edition's sequence (near-chronological). Whistler's dated letters are ordered by year of writing and split into equal-count thirds (1849–1892 / 1892–1894 / 1894–1903). Empty (`null`) = no letter date; those sentences stay in the corpus but leave the §5.3 thirds analysis |
| `year` | year the letter was written, from the edition's letter metadata. `null` for the 161 Whistler sentences from undated letters. Not present in the Beethoven and Mozart file |

`scrapers/` documents how the texts were fetched and cleaned; `./repro/reproduce.sh --rebuild`
is not yet wired up. A re-fetched sentence is matched to its row by `sentence_sha256`.
Re-fetching is subject to each source's own terms of use.
In the model outputs (`runs/`), spans quoted from the Van Gogh and Whistler sentences in the
models' `reasons` and `raw` fields were replaced with `[…]`; labels are unchanged.

## `derived/calibration_sample_120.jsonl`

The 120-sentence reliability sample.

30 per correspondence, drawn with a seed fixed before labelling. The file holds keys only; the
text of the Beethoven and Mozart sentences is in `public/corpus_public.jsonl`.
