# Campaign benchmarks from Looker, for RF#1

**Probed 2026-08-20. Nothing built yet — this is the survey and the design
argument, recorded so the next session does not re-probe.**

## Why

Antonio, #campaigns 2026-08-19: during Planning, RF#1 should carry a
**numerical expectation** — expected signatures, expected new members,
expected € raised — because "RF1 comments often describe expectations only in
narrative terms. That makes the Evaluate stage weaker, because we end up
comparing an actual number against a qualitative expectation instead of against
a clear baseline." He names the RF4 Scorer / Campaigns Edge Twin as the
beneficiary. Christopher: the Looker MCP should supply the baseline, both from
comparable past campaigns and from a benchmark for the category.

## What already exists locally (do not rebuild)

`tools/make_briefs.py: rf1_hint()` already cites comparable campaigns, from
two store tables fed by `tools/log_campaign_performance.py`:

* `campaign_performance` — 366 rows: `signatures`, `new_members`,
  `reactivated`, `raised_eur`, `donations_once`, `donations_monthly`,
  `monthly_12mo_eur`, mapped to taxonomy areas by an explicit keyword table
  that never guesses.
* `fundraising_series` — 15 rows, joined to petitions by id.

Fed MANUALLY: Max's Slack replies are pasted into a text file and parsed. That
is the part Looker replaces.

**Three real gaps, in order of value:**

1. **Nothing records the expectation.** The RF4 CSV has a Plan score column and
   an Evaluate score column but no cell for "expected 40,000 signatures".
   Until that exists, expected-vs-actual is unbuildable however good the
   benchmark is. This is Antonio's actual ask and it needs no Looker at all.
2. **The feed is manual.** Looker can supply it.
3. **No category baseline.** The hint gives top comparables; a median and
   spread for the category is what makes an expectation defensible.

## The Looker boundary

| Call | Result |
| --- | --- |
| `get_models`, `get_connections` | EMPTY |
| `get_explores`, `get_dimensions`, `get_measures` | **404 — closed** |
| `get_projects`, `get_project_files` | work (names only, no file read) |
| `get_looks` (229), `run_look`, `get_dashboards`, `run_dashboard` | work |
| `query` | works |
| `query_sql` | GENERATES SQL only, does not execute |

So LookML introspection is unavailable. The workaround: `get_projects` gives
the real model names, and `query_sql` silently DROPS fields that do not exist,
so submitting guessed field names alongside one known-good field and reading
the returned SQL is a working substitute for `get_dimensions`.

Model names (= project names): `gbq_2_0_reports`, `drupal`, `salesforce`,
`marketo`, `marketo_programs`, `google_analytics_4`, `citizengo_dashboard_tabs`,
`sandbox`.

## The table that answers the question

**`gbq_2_0_reports` / explore `aa_downstream_report`**, over
`citizengo-analytics.2_0_reports.aa_downstream_report`. One row per campaign
carrying ALL THREE metric families, so no cross-model join is needed:

* identity/grouping: `program` (the campaign key), `campaign_name`, `topic`,
  `bound`, `location_global_campaign`, `start_date`, `series_email_number`
* signatures: `total_signatures`, `new_members_count`,
  `reactivated_members_count`, `existing_members_count`,
  `total_signatures_per_1000delivered`, `number_of_sharings`
* money: `otd_amount`, `otd_number`, `otd_avg_amount`, `md_amount`,
  `md_number`, `md_avg_amount`, `md_upsells_*`, and
  `*_per_1000emails_delivered` variants
* reach: `sent_emails`, `ctr`
* downstream cohorts: `new_after_12months_*` (also 3 and 6 month)

`hm_2022_fr_downstream` adds OTD detail on the same `program` key.
`campaigns_database_2_0` (dashboard 47) is metadata only — no metrics, and
`category`/`topic`/`issue`/`theme`/`tag` were all probed and do NOT exist there.

**`topic` IS the category field**, and it is the crux answer. Values:
`Freedom`, `Family and Education`, `Life`, `Patriotism`, `Election Season`,
`Other`, `Others`, `Family &amp; Education`, and a large blank bucket.

## THE LANDMINE — verified directly, not taken on trust

`aa_downstream_report` contains join-exploded rows. Verified by query
2026-08-20, top row by `total_signatures`:

```
program:            EN_IE-2026-01-02-International-FR-MMA-17273-End_the_Mass_...
series_email_number: 36,864
sent_emails:         423,350,272
total_signatures:    22,364,160
```

**423 million emails sent, for an organisation with 19 million supporters.**
The next-highest real campaign is 189,703 signatures — this row is 118x it, and
it alone is roughly 74% of the entire `Freedom` topic total. `series_email_number`
values of 4096 / 32768 / 36864 are powers of two and sums of them: a doubling
join upstream.

Consequences, and they are not optional:

* **Every topic-level SUM or MEAN in this table is materially wrong.** Do not
  report category totals.
* The grain is `program` x `start_date`, not `program`, and campaign-level
  metrics REPEAT verbatim across those rows, so naive `SUM` double-counts even
  without the explosion.
* `topic` tagging itself has errors: `DE-2025-11-19-Global-LF-CWI-17014-
  Stop_The-Digital_Euro_3` is tagged `Life`. A category benchmark inherits the
  tagging quality, so the brief must say how many campaigns a median rests on.

**The filter that restores sanity**, verified: `series_email_number <= 20` plus
`start_date after 2024/01/01`. Life campaigns then read:

| program | signatures | new members | OTD € | sigs/1000 delivered |
| --- | --- | --- | --- | --- |
| PL-2024-10-30 Block the Abortion Bill | 67,739 | 5,473 | 4,572 | 61.7 |
| PL-2025-03-06 Stop Abortion Help Centre | 58,681 | 3,810 | 4,147 | 66.8 |
| DE-2025-11-19 EU Abortion fund | 75,239 | 2,113 | 2,021 | 37.4 |
| DE-2026-01-03 UN Rights of the Child | 50,087 | 719 | 427 | 29.9 |

Plausible, comparable, and the per-1000-delivered column clusters 30–67, which
is the list-size-independent form and the one a benchmark should use.

History: `start_date` runs 2020-06 to 2026-08, ~14,184 rows, but volume is
concentrated in 2024–2026; 2020–2022 are near-empty and the blank-topic bucket
is worst in 2024–25. Hence the 2024 floor.

## Existing expected-vs-actual surfaces

`express_donations_view_by_programs` is the only true target-vs-actual model:
`actual_all_number`, `donation_gap`, `donation_gap_percentage`. Surfaced in
Look 226 "Donations by campaigns", Look 229 "Donations Gap", dashboard 51
"Express Donations Alerts". Dashboard 43 "Monthly Lists' Requirements" is
per-list targets. **Nothing compares a PROPOSED campaign to a category
baseline** — that is the gap.

## BUILT 2026-08-20: the expectation cells

`rf1_expectation()` in tools/make_briefs.py, rendered in both the markdown and
the CSV. Expected / Actual / Delta ship BLANK; the tool supplies only the
baseline. In the CSV it reuses the existing seven-column Plan / Evaluate /
Delta geometry, so the paste-in shape of the Brief template is unchanged --
asserted by a test, because a different column count there would break the
paste.

**A second data trap, found locally and NOT in Looker.** `campaign_performance`
holds 366 rows and **129 of them have fewer than ten signatures** -- one is
named "Petition template EN-GB". The population mixes templates and dormant
petitions with promoted campaigns, so the all-rows median for area 1 is **3
signatures** against a p75 of 5,689: two populations, not a skew. Quoting that
median into a Brief would have been worse than quoting nothing.

Fixed by excluding rows under `MIN_BENCHMARK_SIGNATURES = 100` -- a rule that
can be stated in the cell, where picking a percentile cannot. The resulting
baselines are coherent:

| area | n | p25 | median | p75 | median new members |
| --- | --- | --- | --- | --- | --- |
| 1 Abortion | 13 | 6,745 | 15,652 | 24,382 | 553 |
| 3 Gender medicine | 28 | 12,365 | 21,686 | 31,784 | 639 |
| 5 Sex-based rights | 4 | 35,584 | 38,916 | 80,068 | 1,517 |
| 6 Parental rights | 32 | 14,221 | 25,069 | 32,951 | 1,311 |
| 7 Free speech | 16 | 23,844 | 28,499 | 33,099 | 1,493 |
| 8 FoRB | 28 | 9,261 | 25,979 | 41,057 | 1,338 |

Thin areas (n < 5) are labelled THIN in the cell, and the excluded-row count is
printed so the reader can see the filter working.

**Money has no local baseline at all**: `raised_eur` is null on all 366 rows, so
that cell says NOT HELD rather than sitting empty and looking supported. This is
the first thing Looker would fix.

The RIGHT discriminator is still promotion -- did the campaign get an email
series -- which `aa_downstream_report.sent_emails` has and the local store does
not. The 100-signature rule is a proxy for it.

## Remaining design (not built)

1. ~~Add the expectation cells first.~~ DONE, above. RF#1 gains three blank Plan-stage
   fields (expected signatures / new members / € raised) and three Evaluate
   fields, plus a delta. This is Antonio's ask, needs no Looker, and unblocks
   everything downstream. Blank, never pre-filled — same rule that keeps RF4
   scores empty.
2. **The brief offers a BASELINE, not a forecast.** Print the category median
   and interquartile range with `n`, plus the top comparables already shown.
   "Life campaigns since 2024: median 12,400 signatures (IQR 4,100–31,800,
   n=61)" is evidence. "This campaign will get 12,400" is a prediction the tool
   has no business making, and would breach the same discipline as RF4 scoring
   and the NI stance lines.
3. **Medians with the outlier filter, never sums.** Per-campaign, deduplicated
   on `program`, `series_email_number <= 20`, `start_date after 2024/01/01`.
   Report `n` so a thin category is visible as thin.
4. **Normalise `topic` through an explicit map** — `Other`/`Others`,
   `Family and Education`/`Family &amp; Education` — and map Looker topics to
   our 11 taxonomy areas in a table that never guesses, exactly as
   `log_campaign_performance.py` already maps campaign names.
5. **Keep the local store as the cache.** Write Looker results into
   `campaign_performance` so briefs stay generatable offline and the Looker
   dependency is not on the critical path of a Monday publish.

## Open questions for Christopher

* Do we benchmark on `topic` (5 real buckets, coarse) or on the finer issue
  encoded in the third dash-segment of `program` (`Preschools`,
  `WHO_Corruption`, `Stop_IPAS`, `EU-Reject_Chat_Control`)? The latter is more
  precise but needs a parser and has thinner `n` per bucket.
* `bound` (Local/Global/International) is a real second axis — a Local
  campaign benchmarked against Global ones will mislead. Segment on it?
* The exploded rows are an upstream data bug worth reporting to whoever owns
  `aa_downstream_report`; filtering around it is a workaround, not a fix.
