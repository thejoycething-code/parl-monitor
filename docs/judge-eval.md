# Judge evaluation

*Agreement between the judge's score and a human verdict on the same item. The human verdict is the truth here; this measures the judge. Generated 2026-09-14.*

Banked verdicts: 72 live. Labelled: 11 (10 by explicit sample verdict, 1 by review priority).

## Overall

| Labelled | Exact agreement | Within one | Judge over | Judge under | Digest precision | Digest recall |
|---|---|---|---|---|---|---|
| 11 | 91% | 100% | 1 | 0 | 86% | 100% |

*Digest precision: of what the judge put in the edition (score 2 or 3), the share a human agreed belonged. Digest recall: of what a human said belonged, the share the judge caught.*

## Confusion matrix (rows = human verdict, columns = judge score)

| Human \\ Judge | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **0** | 2 | 0 | 0 | 0 |
| **1** | 0 | 2 | 1 | 0 |
| **2** | 0 | 0 | 2 | 0 |
| **3** | 0 | 0 | 0 | 4 |

## By month

| Month | Labelled | Exact | Within one | Digest precision | Digest recall | Models |
|---|---|---|---|---|---|---|
| 2026-08 | 1 | 0% | 100% | 0% | - | historic |
| 2026-09 | 10 | 100% | 100% | 100% | 100% | historic |

## By feed

| Feed | Labelled | Exact | Within one |
|---|---|---|---|
| pq | 7 | 86% | 100% |
| whatson | 3 | 100% | 100% |
| consultation | 1 | 100% | 100% |

## Prompt and model versions seen

| Prompt | Model | First week | Last week | Verdicts |
|---|---|---|---|---|
| ? | historic | 2026-08-03 | 2026-09-07 | 70 |
| 0069e56f1a3a | claude-sonnet-5 | 2026-09-07 | 2026-09-07 | 2 |
