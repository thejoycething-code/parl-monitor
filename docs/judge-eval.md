# Judge evaluation

*Agreement between the judge's score and a human verdict on the same item. The human verdict is the truth here; this measures the judge. Generated 2026-09-25.*

Banked verdicts: 900 live. Labelled: 11 (10 by explicit sample verdict, 1 by review priority).

## By jurisdiction

*Each judge measured against its own labels. A jurisdiction with no labelled verdicts shows a dash: it has not been checked, which is not the same as agreeing.*

| Jurisdiction | Banked | Labelled | Exact | Within one | Digest precision |
|---|---|---|---|---|---|
| Germany | 659 | 0 | - | - | - |
| Westminster | 241 | 11 | 91% | 100% | 86% |

## Answer kind

*What the judge said a minister's reply DID, against a reviewer reading the same reply. The edition routes on this: a reply judged "restated" is demoted to a single line under "Asked, but not answered", so a wrong label hides an answer rather than merely misplacing it.*

Banked with a kind: 62. Labelled by a reviewer: 0.

*No reviewer has labelled a kind yet. The judge is unchecked on this, which is not the same as agreeing -- and it is the label the edition acts on.*

**Never checked by a human: Germany.** Those judges are unmeasured, and every surface built on them rests on an assumption rather than evidence.

## Overall (all jurisdictions pooled)

*Kept for the long run of Westminster history. Read the table above first: pooling judges with different prompts flatters whichever has fewest labels.*

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
| 0069e56f1a3a | claude-sonnet-5 | 2026-09-07 | 2026-09-21 | 109 |
| 0668d754c487 | claude-sonnet-5 | 2026-09-21 | 2026-09-21 | 659 |
| 70a677ad2a81 | claude-sonnet-5 | 2026-09-21 | 2026-09-21 | 62 |
