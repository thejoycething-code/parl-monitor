# Judge evaluation

*Agreement between the judge's score and a human verdict on the same item. The human verdict is the truth here; this measures the judge. Generated 2026-09-07.*

Banked verdicts: 70 live. Labelled: 1 (0 by explicit sample verdict, 1 by review priority).

## Overall

| Labelled | Exact agreement | Within one | Judge over | Judge under | Digest precision | Digest recall |
|---|---|---|---|---|---|---|
| 1 | 0% | 100% | 1 | 0 | 0% | - |

*Digest precision: of what the judge put in the edition (score 2 or 3), the share a human agreed belonged. Digest recall: of what a human said belonged, the share the judge caught.*

## Confusion matrix (rows = human verdict, columns = judge score)

| Human \\ Judge | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **0** | 0 | 0 | 0 | 0 |
| **1** | 0 | 0 | 1 | 0 |
| **2** | 0 | 0 | 0 | 0 |
| **3** | 0 | 0 | 0 | 0 |

## By month

| Month | Labelled | Exact | Within one | Digest precision | Digest recall | Models |
|---|---|---|---|---|---|---|
| 2026-08 | 1 | 0% | 100% | 0% | - | historic |

## By feed

| Feed | Labelled | Exact | Within one |
|---|---|---|---|
| pq | 1 | 0% | 100% |

## Prompt and model versions seen

| Prompt | Model | First week | Last week | Verdicts |
|---|---|---|---|---|
| ? | historic | 2026-08-03 | 2026-09-07 | 70 |
