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

## WIRED 2026-08-20: the Looker feed

`tools/load_looker_campaigns.py` loads `data/looker/en_gb_campaigns.tsv` into a
new `looker_campaigns` table, and `rf1_expectation` reads it.

**There is no Looker credential in this repo** -- the connection is an MCP tool
available to Claude in session, not to a scheduled script. So the export is
pulled by hand and committed, the same shape as `log_campaign_performance.py`
parsing Max's Slack replies. To refresh, run this through the Looker MCP and
replace the TSV body:

```
model  gbq_2_0_reports
explore aa_downstream_report
fields  program, bound, topic, start_date, total_signatures,
        new_members_count, otd_amount, md_amount, sent_emails
filters program: "EN_GB%", series_email_number: "<=20",
        start_date: "after 2024/01/01"
sort    total_signatures desc
```

**A SEPARATE TABLE, never pooled with campaign_performance**, because they are
not the same metric: `campaign_performance` holds lifetime PETITION totals,
Looker holds signatures attributed to an email CAMPAIGN. "Protect Christian
Teaching in NI Schools" is **129,007 lifetime and 100,521 campaign-attributed**
-- averaging those would produce a figure describing nothing. `rf1_expectation`
uses whichever source has more comparables for the area and NAMES it in the
cell; a test asserts the counts never sum.

**Areas do NOT come from Looker's `topic`.** It is blank on most EN_GB rows
(the program's own topic code reads `NA`) and is five coarse buckets where
present. Areas come from `log_campaign_performance.areas_for()`, the existing
explicit keyword table, applied to the campaign name recovered from `program`.
36 of 60 map to no area -- digital ID, pandemic treaty, Olympics, Sadiq Khan --
which is that table's documented intent, not a failure.

**Third instance of the templates-vs-campaigns problem, this time in Looker.**
The EN_GB population contains a SECOND program naming format -- underscore
dates, `TEST_WARM_UP`, `Warmup`, `L1` -- and every one of those rows carries
zero signatures. The `>= 100` signature rule removes them too, so the same
instrument fixes both sources.

What this bought: **money baselines where there were none.** Area 2 now reads
"median EUR 2,812 (p25 40, p75 3,811, n=3)" against a previous NOT HELD.

Known thinness, recorded rather than hidden: the export is the **top 60 by
signatures**, so per-area `n` is small (area 1 has 1 Looker campaign against 13
local). Signatures and members therefore still come from the local table for
most areas. Widening the export is the single highest-value follow-up and needs
only a larger `limit` on the query above.

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


## The export is now the whole EN_GB population (2026-08-20)

The first pull was the top 60 by signatures, recorded at the time as a thin
slice needing a wider `limit`. Widening it showed the slice was 58% of
everything: with the documented filters there are only **104** EN_GB campaigns
in `aa_downstream_report` at all.

| band (signatures) | rows |
|---|---|
| >= 20,037 | 60 |
| 9,000-20,036 | 33 |
| 3,000-8,999 | **4** |
| 100-2,999 | 7 |
| total | 104 |

Two findings from that.

**`total_signatures` is a MEASURE, not a dimension.** It cannot go in
`filter_expression` -- Looker returns `400 Filter expressions cannot reference
aggregate field` -- so band it through the `filters` map as a HAVING, e.g.
`"9000 to 20036"`. This is how to page a large explore without a row cap.

**The mid-range is genuinely near-empty.** Four campaigns since 2024 landed
between 3,000 and 9,000 signatures. EN GB campaigns either clear ~9,000 or
they are not campaigns.

Per-area coverage after widening: 8 areas -> 10 (areas 9 and 10 appear for the
first time), area 3 went 5 -> 9, area 2 3 -> 7, area 6 7 -> 10.

### Two floors, both measured

`MIN_LOOKER_SIGNATURES = 3000`, higher than the local `100`. The 7 rows below
3,000 are not weak campaigns but a different population: response rate
(signatures / sent_emails) runs **0.02%-0.78%** against **2.1%-8.4%** for every
row above. Two independent 4x gaps -- signatures (876 -> 3,627) and response
rate -- partition the same 7 rows. A send that reached 677,000 inboxes for 139
signatures did not function as a campaign. That band holds the one explicit
`TEST-` program and the one list-segment split (`INB_12th_Meeting-Yahoo`, 323
signatures, same petition id 14242 as its parent's 22,697 -- the reason to key
on date+pid rather than on the program string). The rows stay in the table and
are excluded at display, with the count printed.

### Donation attribution stops at 2026-02-01 -- UNRESOLVED

One-time donations per 1,000 signatures, over the 94 campaigns above the floor:

| start year | n | EUR per 1,000 signatures |
|---|---|---|
| 2024 | 39 | 52.86 |
| 2025 | 48 | 53.27 |
| 2026 | 10 | **2.29** |

2024 and 2025 agree to within 1%, so the underlying rate is stable and 2026 is
an artefact. The break is sharp rather than a taper: campaigns started up to
2026-01-19 carry money (EUR 6,040 / 1,317 / 388), every one from 2026-02-02 on
is under EUR 70. Signature and member counts for those same rows are normal
(2026 median 24,105 signatures), so it is the money columns specifically.

This is either a broken attribution join or donation asks being dropped from
campaign emails. **The data cannot tell which; whoever owns the money pipeline
can.** Both readings mean the same thing for a baseline, so `make_briefs.py`
excludes those rows from MONEY only -- their signatures still count -- and the
cell says how many and why. It mattered: area 3's money baseline read EUR 56
with them in and EUR 397 with them out, a 7x understatement that would have
shipped as a campaigner's expectation.

**To settle:** ask whoever owns `aa_downstream_report`'s donation join whether
attribution broke around 2026-02-01. If it is fixed, move
`MONEY_COMPLETE_BEFORE`; if the cause is a real change in practice, the cutoff
should stay and the reason be recorded here.


## Mapping the unmapped campaigns (2026-08-20)

64 of the 104 Looker rows mapped to no area. Adding keywords turned out to be
the smaller half of the fix.

### The name in the Looker export is not the campaign name

It is a truncated program slug: `Support NHS nurses in their fi`, `Stand for
Stornoway Sa`, `Guide with Pride  Withdraw the` -- cut mid-word by the program
string with punctuation flattened to underscores. Keyword-matching that slug
loses campaigns whose distinguishing word was the part cut off, and re-derives
badly what `campaign_performance` already holds well: the full name and a
curated area mapping.

So `load_looker_campaigns.py` now joins the program's **petition id** to
`campaign_performance.petition_id` -- an exact key -- and takes that row's
areas. It resolved 49 of 58, 30 of them to areas already recorded locally.
`area_source` records the route taken for every row.

Two caveats found while building it, both now in the fallback path: the ids are
**not aligned between the systems** ("Justice for Jennifer" is 15124 in Looker
and 15129 locally), and six programs carry no usable id (`-NA-` or an empty
segment). A local row with an EMPTY area list is treated as an answer, not a
miss -- the curated sweep looked at it and left it out -- so keywords never
overrule it.

### Two bugs the join exposed

**`rse\b` matched the end of other words.** Unanchored, it caught *Reverse*,
*Nurse*, *Verse* and *Morse*, filing four campaigns into area 6 -- a nurse's
disciplinary case, a blasphemy trial, a DIY-abortion campaign. Area 6 is the
largest area, so the noise landed where it was least visible. Anchored to
`\brse\b` all three genuine RSE campaigns still match. `\bpupil` was added so
"Sacked for Answering a Pupil's Question" keeps area 6 for the real reason;
`\bteacher` was considered and rejected because it would have added area 6 to
a free-speech sacking that is area 7.

**The topic code is two OR three letters.** `FM` and `FAM` both occur; the
parser demanded exactly two, so "Demand BBC Children In Need CEO Resigns!"
(14,583 signatures) was dropped as unparseable.

**`areas` is a stored column**, so editing `KEYWORD_AREAS` changes nothing
until `log_campaign_performance.py --rederive` runs. It prints every change
rather than a count, because a keyword edit that silently reclassified
campaigns would move a benchmark with no trace. Seven rows moved: four newly
mapped, three losing the false area 6.

Result: unmapped 64 -> 30, and per-area n went from 1/3/5/1/1/7/3/3 across
eight areas to 7/7/16/1/4/13/12/17/2/1 across ten.

### The 30 still unmapped are mostly a standing decision

21 of them have a local row that the 2026-08-13 curated sweep deliberately left
out of the taxonomy -- 601,246 signatures of WHO/pandemic-treaty/IHR/INB,
digital ID, UN governance (Agenda 2030, Defund the UN, UN Colonialism Pact),
election tools and a few one-offs. Those are not keyword misses. Mapping them
needs a taxonomy DECISION, not a regex: the eleven areas have no home for
health sovereignty or digital ID, and adding areas 12 and 13 would also start
classifying Westminster and NI parliamentary material into them, which is a
much larger change than a benchmark fix. Left for Christopher.

The genuine residue is small: `Schools Bill Stealth Digital ID` (digital ID
substance, schools framing -- mapping it to area 6 would misfile it),
`Fundraising-Stay Out` (an appeal, not a campaign), two more pandemic-treaty
rounds, and one program with neither an id nor a name.


## Area 7 widened to civil liberties (2026-08-20)

Christopher's decision: health sovereignty, the pandemic treaty and digital ID
are freedom/civil-liberties issues and belong in the existing freedom category,
by **widening and renaming area 7** rather than adding an area — and they should
drive **parliamentary monitoring** too, not benchmarks alone.

Area 7 is now **"Free speech, privacy and civil liberties"** (taxonomy v0.6).

### Why widen rather than add an area

Measured first. **Digital ID already landed in area 7**: 31 of 32 `mp_events`
rows carrying it were tagged, mostly via `age verification` and `Online Harms`,
and area 7 already held encryption and client-side scanning. A new area would
have split one campaign family by wording. **Health sovereignty had almost no
Westminster footprint** — a single ledger row, "International Health Regulations
2005", already tagged area 7. One UN document of 112 matched.

*Correction:* an earlier draft of this note said that row was mis-filed into
area 2. That was inferred from the `(re: coercion)` matched-term annotation in
the line text rather than read from the stored `areas` value, and it was wrong —
the row reads `[7]`. No backfill is needed. Re-filtering the line today would
add area 2 via the assisted-dying tier-2 term `coercion`, but that is
pre-existing behaviour of the annotation text and not something this change
introduced.

So nothing already stored was reclassified. The new parliamentary surface comes
from the sweep terms, which is the point of the second decision.

### The rename needed a code change, not just a heading

`intel.area_names()` derived the display label from the yaml **key**, and a key
cannot hold the commas in "Free speech, privacy and civil liberties". That label
is what the weekly digest publishes.

The fix is an optional `name:` field per area, which `generate_taxonomy.py`
reads from an explicit `- **Name:**` line, with the key derivation kept as the
fallback. It is **opt-in on purpose**: `make_5ca.py` builds its CSV **filenames**
from the label, so auto-deriving all eleven labels from their headings would have
renamed every 5CA sheet and orphaned the published ones. Only area 7 declares a
name; the other ten keep their exact previous labels and filenames, and
`config/un-taxonomy.yaml` (hand-maintained, no name fields) is untouched.

The area **key stays `7_free_speech_online_safety`**. It also lives in
un-taxonomy.yaml and `filter.load_taxonomy` reads only its leading number, so
renaming it would be a two-file migration for nothing. The name/key divergence
is deliberate and recorded in the md.

`make_5ca.py` now slugifies the label rather than only swapping spaces, so a
comma cannot reach a filename. Labels without punctuation slug to exactly what
they did before.

### Bare WHO is both case-sensitive and guarded

`WHO` is an English pronoun. The taxonomy's own convention covers half of it —
ALL-CAPS terms match case-sensitively, the same rule that stops `RSE` matching
"nurse" — but case-sensitivity does not survive an ALL-CAPS heading, and most
WHO mentions are global health aid rather than sovereignty. So the term also
requires company: `WHO [with: pandemic, treaty, "health regulations", accord]`.
`IHR`, `INB` and `CBDC` rely on case-sensitivity alone; if triage shows noise,
guard them rather than delete them, per the file's stated preference.

### The campaign layer does not inherit that protection

`KEYWORD_AREAS` in `log_campaign_performance.py` is a separate **lowercase**
regex list. It is precisely where `rse\b` came to match "nurse", so the new
acronyms are `\b`-anchored there by hand.

Re-deriving moved **25 campaigns, all pure additions, no reclassifications** —
every one a genuine pandemic-treaty, WHO, digital-ID or Agenda 2030 campaign.
The local table reaches back further than the 2024+ Looker export, so area 7
gained more than the export alone suggested. Unmapped Looker rows went **30 to
14**, and area 7's benchmark n went **12 to 28**.

Found while testing: the two layers **disagreed about Islamophobia**. The
taxonomy carries `Islamophobia` and `"Islamophobia definition"` in area 7, but
`KEYWORD_AREAS` had no pattern, so "Defend the freedom to critique Islam — stop
'Islamophobia' blasphemy law" reached only area 8 via `blasphem`. It is both a
blasphemy-law and a free-speech campaign; the layers now agree.

### Included but flagged

`"Agenda 2030"` and `"sustainable development goal*"` at tier 2, plus the
matching campaign pattern, covering *Reject Agenda 2030* (20,037) and the *Doha
Summit* (16,191). These are UN governance rather than one of the three issues
named, so they are one line to strike in each place if unwanted.
