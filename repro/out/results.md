# Reproduced results

Corpus: 3928 sentences (Van Gogh 1334, Whistler 1727, Beethoven 490, Mozart 377)

## 5.2 Coverage, non-`none` rate by scheme and correspondence

| annotator | scheme | Van Gogh | Whistler | Beethoven | Mozart |
|---|---|---|---|---|---|
| M1 | MaceWard | 68.0 | 43.3 | 33.7 | 54.9 |
| M1 | Tinio | 54.9 | 31.3 | 29.8 | 45.4 |
| M1 | Botella17 | 75.6 | 42.6 | 41.8 | 59.9 |
| M1 | Wallas | 58.3 | 32.3 | 20.8 | 45.9 |
| M2 | MaceWard | 79.7 | 37.6 | 46.5 | 71.9 |
| M2 | Tinio | 64.5 | 17.8 | 22.9 | 40.8 |
| M2 | Botella17 | 82.0 | 38.1 | 43.1 | 67.6 |
| M2 | Wallas | 63.4 | 27.2 | 30.8 | 58.4 |

- **M1**: at least one label on 70.6% of sentences; `none` under all four on 29.4%
  - Whistler, four schemes together: 62.5%
- **M2**: at least one label on 66.8% of sentences; `none` under all four on 33.2%
  - Whistler, four schemes together: 50.5%

## 5.1 Reliability, pairwise Krippendorff's alpha on the 120-sentence sample

Agreement between the two model annotators on the calibration sample.

| pair | MaceWard | Tinio | Botella17 | Wallas | n |
|---|---|---|---|---|---|
| M1–M2 | 0.467 | 0.515 | 0.605 | 0.466 | 120 |

## 5.3 Trends across correspondence position (thirds, %)

Using M1. Sixteen combinations: four series x four correspondences.

| scheme.category | Van Gogh | Whistler | Beethoven | Mozart |
|---|---|---|---|---|
| MaceWard.development | 18.7 → 13.0 → 11.2 ↓ | 8.4 → 10.5 → 7.5 ↓ | 4.9 → 4.3 → 3.0 ↓ | 6.4 → 10.3 → 34.9 ↑ |
| MaceWard.finalization | 11.9 → 19.3 → 16.9 ↑ | 26.1 → 25.1 → 26.2 ↑ | 12.3 → 16.0 → 14.0 ↑ | 12.0 → 20.6 → 10.3 ↓ |
| Botella17.trials | 14.4 → 6.1 → 2.7 ↓ | 1.3 → 1.9 → 1.0 ↓ | 2.5 → 0.6 → 0.6 ↓ | 3.2 → 4.8 → 4.0 ↑ |
| Tinio.finalizing | 11.0 → 14.6 → 17.5 ↑ | 23.9 → 22.6 → 21.8 ↓ | 14.1 → 24.5 → 22.6 ↑ | 20.8 → 19.0 → 14.3 ↓ |

Direction reported in the paper: `development` and `trials` fall while `finalization` and `finalizing` rise for Van Gogh and Beethoven; Whistler's series change little; Mozart shows a more complex picture: `development` rises sharply in the final third, `finalization` falls from its middle-third high, `finalizing` continues to decline, and `trials` changes little.

## Appendix C · Trend-choice audit (M1, final minus first third, percentage points)

Cells show the change in percentage points and the number of hits across the three thirds.

| scheme.category | Van Gogh | Whistler | Beethoven | Mozart |
|---|---|---|---|---|
| MaceWard.conception | -0.7 (162) | -1.0 (43) | +0.6 (30) | -7.2 (30) |
| MaceWard.development | -7.5 (191) | -1.0 (138) | -1.9 (20) | +28.5 (65) |
| MaceWard.realization | -8.4 (340) | -0.4 (93) | +1.8 (46) | -11.3 (58) |
| MaceWard.finalization | +4.9 (214) | +0.2 (404) | +1.8 (69) | -1.7 (54) |
| Tinio.initialization | -17.9 (468) | -3.4 (93) | -0.0 (32) | -8.0 (51) |
| Tinio.expansion_adaptation | -4.5 (73) | -0.4 (42) | -1.2 (14) | +30.1 (52) |
| Tinio.finalizing | +6.5 (192) | -2.1 (357) | +8.5 (100) | -6.5 (68) |
| Botella17.immersion | -0.5 (8) | +0.0 (3) | +0.0 (0) | -0.0 (4) |
| Botella17.reflection | -0.2 (12) | +0.0 (3) | -0.0 (2) | -1.6 (2) |
| Botella17.research | +0.4 (16) | +0.0 (19) | -1.2 (4) | -1.6 (3) |
| Botella17.inspiration | -0.2 (19) | +0.2 (6) | -1.2 (6) | +0.0 (0) |
| Botella17.illumination | +0.2 (4) | +0.0 (0) | +0.0 (1) | +0.0 (0) |
| Botella17.trials | -11.7 (103) | -0.4 (22) | -1.8 (6) | +0.8 (15) |
| Botella17.assembly | +0.7 (7) | +0.0 (4) | +0.0 (0) | +0.0 (0) |
| Botella17.ideation | +0.2 (38) | -0.2 (8) | +0.6 (2) | -0.8 (6) |
| Botella17.selection | +2.2 (46) | +2.1 (53) | -4.9 (21) | +7.1 (17) |
| Botella17.technique | -0.2 (26) | +0.0 (17) | +2.4 (5) | +1.6 (3) |
| Botella17.realization | -1.0 (397) | -1.5 (115) | +1.8 (51) | -20.1 (73) |
| Botella17.specification | +0.4 (50) | +1.1 (41) | -0.0 (16) | +8.7 (24) |
| Botella17.finalization | +0.4 (12) | +0.8 (37) | +2.4 (15) | +0.8 (6) |
| Botella17.examination | -3.2 (116) | +0.8 (117) | +2.4 (11) | +7.1 (33) |
| Botella17.presentation | +1.3 (139) | -8.6 (182) | -0.7 (62) | -4.8 (36) |
| Botella17.break | -0.7 (9) | +0.0 (5) | +0.0 (1) | +0.0 (1) |
| Botella17.abandoning | -0.5 (7) | +1.0 (27) | -0.0 (2) | +0.0 (3) |
| Wallas.preparation | -15.6 (318) | -1.1 (122) | +2.4 (25) | -1.7 (56) |
| Wallas.incubation | -0.2 (1) | -0.2 (1) | -0.6 (1) | +0.0 (1) |
| Wallas.illumination | -0.0 (10) | +0.2 (8) | -0.6 (6) | -1.6 (4) |
| Wallas.verification | +0.2 (449) | +0.8 (374) | +1.7 (70) | +23.7 (112) |

## 5.3 Van Gogh by year (all analysed sentences as denominator; years with <20 excluded)

| year | n | M1 finalization | M1 trials | M2 finalization | M2 trials |
|---|---|---|---|---|---|
| 1881 | 35 | 5.7 | 14.3 | 2.9 | 28.6 |
| 1882 | 154 | 13.0 | 14.9 | 6.5 | 23.4 |
| 1883 | 118 | 10.2 | 19.5 | 5.9 | 33.1 |
| 1884 | 78 | 9.0 | 6.4 | 3.8 | 15.4 |
| 1885 | 120 | 17.5 | 10.8 | 14.2 | 15.8 |
| 1888 | 420 | 16.9 | 5.0 | 12.6 | 11.0 |
| 1889 | 260 | 17.7 | 2.7 | 16.2 | 2.7 |
| 1890 | 119 | 21.0 | 2.5 | 22.7 | 2.5 |

Figures written to `repro/out/fig-coverage.pdf` and `repro/out/fig-tertile.pdf`.

