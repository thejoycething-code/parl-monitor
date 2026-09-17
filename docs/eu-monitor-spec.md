# EU Monitor — spec and build state

Christopher, 2026-09-01: "like the Westminster one but catching all items of
concern the EU are promoting." This document records what was live-probed,
what is built, and the decisions that are his before it goes further.

## Sources, live-probed 2026-09-01 (raw responses in data/raw/eu-probe-2026-09-01/)

| Source | Endpoint | Probe result | Verdict |
|---|---|---|---|
| Commission "Have your say" | `ec.europa.eu/.../brpapi/searchInitiatives` | 200; 4,101 initiatives; `feedbackStatus=OPEN` filters server-side to 41; `text=` search works; per-item feedback window with start/end dates | **Phase 1, BUILT** |
| HYS initiative detail | `brpapi/groupInitiatives/{id}` | 200; EN `dossierSummary`, DG, committee, publications | **Phase 1, BUILT** (one fetch per new item) |
| HYS public page | `have-your-say/initiatives/{id}` | 200 direct | the citizen-facing URL every row carries |
| EP Open Data: adopted texts | `data.europarl.europa.eu/api/v2/adopted-texts` | 200; JSON-LD; multilingual titles, subjects, dates | Phase 2 |
| EP Open Data: meetings | `/api/v2/meetings` | 200; plenary calendar | Phase 2 (the "coming up" strip) |
| EP Open Data: parliamentary questions | `/api/v2/parliamentary-questions` | 200 but id-only stubs; one fetch PER question for content | Phase 2/3, expensive |
| OEIL (Legislative Observatory) RSS | `oeil.secure.europarl.europa.eu/.../rss` | 307 redirect, not yet chased | Phase 2 (dossier tracking = bills-board analog) |

## Why "Have your say" is phase 1

Everything the EU is *promoting* passes through the Better Regulation
portal: legislative proposals, delegated/implementing acts, evaluations and
fitness checks all take public feedback in defined windows. It is the one
EU source where the action-window rule (docs/parl-monitor-devolved-fix.md)
transfers unchanged — open window, stated closing date, open to anyone.
It is also the *actionable* end: a feedback window is something supporters
can be pointed at, where an EP resolution is already history.

## Built (phase 1)

- `eu_consultations` table (src/db.py), mirroring `dg_consultations` plus
  `reference`, `act_type`, `topics`, `stage`.
- `tools/eu_monitor.py`: one listing call weekly (41 items today), one
  detail call per NEW initiative for the EN summary, same taxonomy pass as
  the devolved monitors over title + summary, ON-OUR-GROUND / WATCHING
  render with nothing silently suppressed.
- Separation guarantee held: the tool writes `eu_consultations` only —
  never `items`/`mp_events` — so nothing reaches the Westminster digest
  until wired deliberately.
- 7 tests on fixtures cut from the real probe responses.
- First live pull (2026-09-01): 41 open, 0 matched the taxonomy — a real
  zero (the week's crop is vineyards, batteries, Chips Act; the test
  fixture proves a VAW/abortion text matches). The EU Strategy on victims'
  rights (closes 4 Sep) and Quality Education for All 2040 (closes 8 Sep)
  are the nearest misses, visible in WATCHING.

**NOT yet wired into CI** — no sunday-pull step, no digest section, no
Top lines, no briefs. The local pull was validation; canonical population
happens when the wiring is approved.

## Checkpoint 1 — ANSWERED (Christopher, 2026-09-01)

1. **Taxonomy vocabulary: DONE, v1.5.** EU terms across seven areas; his
   scope answers: rule-of-law conditionality tier 1 in area 7 ("Article 7"
   guarded); migration Pact vocabulary in area 11 under the same
   collate-never-campaign rule; DSA tier 1 with Democracy Shield / FIMI /
   content moderation triage-gated; demography terms tier 2 in area 9
   (opportunities, not just threats). Istanbul Convention, LGBTIQ Equality
   Strategy, SRHR, comprehensive sexuality education, the Parenthood
   Regulation family, SoHO, chat control / CSA Regulation all in.
2. **Wiring: a SEPARATE EU edition.** `tools/eu_monitor.py --edition`
   writes `editions/eu-monitor-<date>.md`; `.github/workflows/eu-weekly.yml`
   runs Saturdays (07:00/15:00 UTC, same parl-monitor-state concurrency
   group), commits the edition and publishes the store. Nothing EU touches
   the Westminster digest.
3. **Downstream: briefs WIRED (2026-09-01, second instruction).**
   `actionable.eu_actionable` extends the action-window rule to
   eu_consultations; make_briefs generates for on-our-ground EU items with
   slug prefix `eu-`, the 5CA populate-manually marker, and the List cell
   as a campaigner's-call marker (good EU briefs cross country lists).
   The Asana approval task gates every one; good ones are passed to team
   members by hand. Still no Top lines, no Slack.
4. **5CA + tracker: BUILT (2026-09-01, "Build all these").** The full
   parity arc:
   - **Verdict sign-off flow**: config/eu_divisions.yaml, the Westminster
     pattern (our_side + meaning lines per division, signed_off gates).
     Meanings are grounded in what was ACTUALLY voted -- the decision
     events and official annexes corrected two list-title readings before
     anything shipped: the ePrivacy 331-304 roll call was the REQUEST FOR
     URGENT PROCEDURE on the scanning-derogation file (not the substance),
     and the stored SDG vote was an electronic split on paragraph 10 with
     no name lists, left deliberately unverdicted. Anchor check passed:
     Greens/EFA 0-49 and The Left 0-29 against the fast-track, EPP 172-1
     for -- the known chat-control partisans on the predicted sides.
   - **MEP enrichment**: country + political group per MEP (719/743;
     the rest between groups, NULL never guessed), incremental weekly.
   - **"How did your MEP vote?"** (templates/eu-votes.html via
     tools/make_eu_tracker.py): search by name or country, verdict-led
     cards, group-cohesion lines. The gate is structural: unsigned
     divisions ship WITHOUT verdict fields in the page data, so an
     unsigned meaning cannot be coloured.
   - **EU 5CA** (tools/make_eu_5ca.py): MEP placements ++/+/0/-/-- over
     SIGNED divisions only, group defiance in Comments; with nothing
     signed it refuses to build and says why.
   - Collector fix found against the RCV annex: one vote-results item can
     carry several decision events (a paragraph split AND the motion as a
     whole); taking consists_of[0] had cost us the SDG whole-motion roll
     call. Every event is now stored.

## Forward look (2026-09-01, Christopher: "extend the forward look for both")

The EU plenary horizon is 90 days (was 60); Westminster's "Further
afield" is 8 weeks (was 3, set 2026-08-24). Both monitors now look as far
as their sources publish — unpublished weeks return nothing and cost
nothing.

## Phase 2 (building in this order)

1. **Dossier tracking — BUILT (2a).** `config/eu_watchlist.yaml` (curated,
   ids verified against the procedures API before entry — the listing has
   no titles, so enumeration would cost one fetch per procedure against a
   500/5min limit) + `tools/eu_dossiers.py`: weekly stage check, movement
   marked "▲ moved (First reading → Second reading)" in the edition's
   Dossier board. Seeded with the CSA Regulation 2022/0155(COD) (chat
   control, area 7) and the Parenthood Regulation 2022/0402(CNS) (areas
   9/10), both verified live at first reading. OEIL's own RSS is dead (the
   relaunched site 400s the old export path); the EP Open Data procedures
   endpoint replaced it.
2. **Plenary forward look — BUILT (2b).** `tools/eu_agenda.py`: sittings
   inside a 60-day horizon from the meetings calendar, one
   foreseen-activities call per published sitting, every EN label
   taxonomy-matched; the edition's "Coming up in plenary" shows matches
   dated with the rest counted per sitting. 204-empty and 404 both mean
   "agenda not yet published" and stay quiet (measured live). First run
   caught the 15 Sep Democracy Shield special-committee debate via a
   v1.5 term. **Committee agendas (LIBE/FEMM/JURI/EMPL) remain an open
   probe**: EP Open Data carries no committee meetings, and the eMeeting
   service is an Angular shell whose backend the blind probe did not
   find -- needs browser XHR discovery.
3. **Adopted texts — BUILT (2c).** `tools/eu_texts.py`: the year listing
   (one ~12MB call) filtered to a 60-day window, EN titles taxonomy-
   matched, the edition's "Adopted by the Parliament" section. Doubles as
   the watchlist auto-proposal feed: a matched text's procedure id (parsed
   from its decision event) is VERIFIED against the procedures API before
   being printed as a candidate -- a human confirms by editing the config,
   nothing is added automatically. First run: 39 texts in the window, 2
   matched (the Nigeria Christian-persecution resolution of 9 July; an SDG
   text), 2 verified candidates proposed. TA pages sit behind europarl.eu's
   bot-wall (202), so rows ship linkless rather than with unverified URLs.
4. **MEP roll calls — BUILT, collection only (2d).** `tools/eu_rollcalls.py`:
   the MEP roster (743 rostered), every plenary vote in a 60-day lookback
   with its EN label taxonomy-matched, and for MATCHED votes the decision
   event's full roll call (who voted favor/against/abstention, by person
   id). eu_divisions carries NO verdict column by design: a division's
   meaning is signed off per division by Christopher before any MEP is
   judged on it (the Lords inversion lesson), and the eventual EU 5CA
   builds on this data only after that sign-off flow exists. First run:
   46 plenary votes in the window, 3 on our ground -- the Nigeria
   Christian-persecution resolution (510-1-86, 597 positions), the
   ePrivacy child-sexual-abuse scanning derogation (331-304-11, a 27-vote
   knife edge, 646 positions), and an SDG text (totals only, no roll
   call). The 5CA path from here: verdict sign-off flow, then group/
   country enrichment of the roster, then the grid.

## Triage and delivery (2026-09-01, Christopher's second round)

- **Triage: LIVE.** `tools/eu_triage.py` sends every taxonomy-matched EU
  row (consultations, agenda items, adopted texts, divisions) through the
  SAME judge Westminster uses -- rubric, model, batching -- scored once,
  ever; spend in api_spend as 'eu-triage'. A live failure retries once,
  then leaves rows UNSCORED for next week (never stub-frozen: scores are
  once-ever). First run: 6 items, three 3s -- both Nigeria items and the
  ePrivacy scanning derogation. Why-lines render in the edition and DM.
- **Delivery: DM only.** The channel is deliberately NOT posted (his
  call: hold the Slack). The weekly run DMs the summary -- scored items
  with why lines, counts, the dossier board -- to Christopher alone.
  First DM sent 2026-09-01; the workflow sends it each Saturday.

## Costs

All sources are public JSON, no keys, no LLM spend in phase 1. The weekly
pull is ~1 + new-items requests. Taxonomy triage stays deterministic; LLM
triage would only enter if Christopher wants EU items scored like
Westminster ones.

## Gap analysis (2026-09-02, Christopher: "something must be missing")

**Built from it:**
- **ECI watch** (tools/eu_eci.py): the citizens' instrument was unmonitored.
  First pull found both million-signature ECIs on our ground -- the
  conversion-practices ban (1,128,063, ANSWERED) and My Voice, My Choice
  (1,124,513, ANSWERED) -- plus a live digital-ID/age-verification
  initiative. Supporter deltas tracked weekly; edition section added.
- **MEP contact** on the tracker: hasEmail from the enrichment pass; the
  page's card now carries the parliamentary email, closing the
  actionability gap Westminster's contact column never had here.

**Built 2026-09-03 ("build all"):**
- **Strasbourg watch** (tools/eu_courts.py): HUDOC's open JSON API,
  bare-term query grammar (the fulltext: field silently returns zero --
  measured); term net nominates, taxonomy judges. First haul: Rainbow
  Mission Foundation v. Hungary, A.P. and R.P. v. Poland (surrogacy
  parenthood recognition), G.K. v. Switzerland. Edition section added.
  CJEU stays out: curia retired its RSS routes (404, probed) and
  InfoCuria is POST-driven -- future session.
- **EP written questions** (tools/eu_pqs.py): capped drain (150/run,
  newest first) over id-only stubs; askers join the MEP roster. First
  drain: migration Pact questions (area 11, collated) and a
  detransitioner-representation question on the LGBTIQ+ strategy.
- **Across the parliaments** (src/across.py): the cross-parliament
  synthesis, rendered in the MONDAY Westminster edition when an area is
  active in 2+ of the eight watched jurisdictions inside a fortnight;
  tier-1/scored-only for Westminster and devolved chambers (a hospice
  charity fundraiser taught why). First live render crossed abortion
  (Scotland reform question x Westminster stillbirths 2R), parental
  rights (NI RE consultation x Westminster SEND/foster), and free
  speech across FOUR jurisdictions.
- **Council of the EU: BLOCKED UPSTREAM, recorded.** The votes dataset
  is officially DISCONTINUED (its endpoints are the 404s), and
  consilium.europa.eu sits behind a GSC challenge the browser pane
  cannot clear. Council STAGES are already tracked via the procedures
  API on the dossier board; EUR-Lex/CELLAR is the future route for
  Council positions -- its own session.

**Remaining scoped:**
1. **The Council of the EU** -- the biggest true hole. The Parenthood
   Regulation is CNS: the Council DECIDES and Parliament is only
   consulted, so our top-watched dossier's decisive chamber is
   unmonitored. Council public votes exist as open data but the portal
   and SPARQL endpoints refused every path probed (404/403); needs a
   browser-network discovery session like eMeeting's. Presidency
   programmes and Council agendas same.
2. **Courts as upstream drivers** -- CJEU and ECtHR judgments create the
   consultations we later catch (JR87 created the NI RE consultation;
   the EP fitness checks follow Strasbourg rulings). A curia/HUDOC press
   watch would be the earliest warning in the whole system.
3. **Cross-parliament synthesis** -- the system now watches six
   legislatures as silos, but the stories cross them (RVE: Wales lost
   withdrawal -> Scotland narrowed -> NI consulting; scanning: chat
   control EU <-> OSA UK). A weekly cross-parliament themes note is
   analysis no one else has; needs a design decision on where it lives.
4. **EP written questions** -- deferred by cost (one fetch per stub), last.


## Eleven dark days, and what they cost (17 September 2026)

Christopher: "Let's get the EU parliament on par with the UK version." The
first finding was not a parity gap but a fault, and a silent one.

**What had happened.** The 9 September store rebuild came back without five
EU tables -- `eu_divisions` (21 plenary roll calls), `eu_votes`, `eu_texts`,
`eu_consultations`, `eu_speeches` -- exactly as it came back without
`pq_link`. Nothing said so. Then both Saturday slots of the EU weekly were
CANCELLED on 12 September and the pipeline stopped running at all. Fifteen
workflows share the `parl-monitor-state` concurrency group; GitHub keeps only
ONE run pending per group, so a second arrival cancels the one already
waiting. At 07:00 Saturday the day sweep (`0 7 * * 2-6`) fires into the group
while the NI weekly (06:00) may still hold it, and the EU run is the one that
loses. A cancelled run is not a failed run, so the failure alert never fired.

**Why the watch missed it.** `tools/coverage.py` exists to catch precisely
this. It printed `NO DATA` beside each emptied table and moved on, because
an empty table and a never-populated one read identically, and the three
worst-hit tables (`eu_divisions`, `eu_votes`, `eu_speeches`) were in
`ONCE_EVER`, which is "listed but never fails the run" -- correct for
cadence, since a quiet plenary month is not a fault, and useless against a
wipe.

**The cost, measured.** The 15 September plenary was never collected: the
Special Committee on the European Democracy Shield report, 87 roll calls, all
area 7, one of them 467-185-11. The first backfill found it.

**Fixed.**
- An empty watched feed is now OVERDUE, not silence, with `ALLOWED_EMPTY` for
  the ones a human excuses and `PAUSED_TABLES` for the stopped UN pipeline.
  A write-once feed is judged on emptiness rather than cadence, and that check
  runs even in `--quiet`.
- The EU weekly moved to Saturday 10:00 and 18:00, clear of every other cron
  in the group.
- `eu_rollcalls.py`, `eu_texts.py` and `eu_speeches.py` take `--days N`. Their
  windows were a fixed 60 days, so by 17 September the July plenary was out of
  reach and a plain re-run could not have recovered it. A gap needs a wider
  window, the way the Westminster backfills do.

**Restored**, by `--days 120`: 121 divisions over four sitting days (21 May,
7 and 9 July, 15 September) and 72,705 MEP vote positions; 135 adopted texts,
5 on our ground; 34 open Commission consultations. The three divisions
Christopher signed on 1 September survived in config and re-joined their
roll calls, so the MEP page and the EU 5CA rebuild unchanged.

## Where the EU still differs from Westminster (17 September 2026)

Open, in the order they matter:

1. **Sign-off coverage.** 3 of 121 divisions carry a verdict. The 15 September
   Democracy Shield report alone is 87 unsigned roll calls on area 7. The EU
   5CA places 743 MEPs on three divisions; Westminster's places 650 on about
   fifty. This is a human decision per division, not code, and it is the whole
   difference between a sheet that means something and one that does not.
2. **Cadence.** Westminster sweeps every sitting day; the EU is weekly. A
   Tuesday plenary waits until Saturday even when everything works.
3. **No Evaluate phase.** `tools/evaluate_5ca.py` scores the Westminster sheet
   against each division after the fact. The EU has no equivalent, so nothing
   measures whether its placements predict anything.
4. **No absence record.** Westminster ledgers who was present and did not vote.
   An MEP who stays away is invisible here.
5. **No issue pages, no per-area view.**
6. **Delivery stays DM-only** by Christopher's standing instruction.


## Adopted texts ARE readable (17 September 2026)

Phase 2c recorded that "TA pages sit behind europarl.eu's bot-wall (202), so
rows ship linkless rather than with unverified URLs". That is true of the
doceo page and false of the text. The adopted-texts metadata carries an ELI
distribution path, and `https://data.europarl.europa.eu/distribution/doc/
TA-10-2026-0286_en.docx` answers 200 with the whole resolution -- 130 KB, 390
paragraphs. There is a `.pdf` and an `.xml` beside it.

This matters more than a link. It is the difference between signing a verdict
off a title and signing it off the text, which is the Lords inversion lesson
in one line. The Democracy Shield sign-off below is the first that quotes
operative paragraph numbers because it is the first where the text could be
read.

Not yet wired: `eu_texts.py` still stores title and identifier only. Storing
the distribution URL, and fetching the text for matched rows, is the obvious
next build.

## The Democracy Shield sign-off, and what the queue said next (17 September 2026)

Christopher: "sign off the Democracy Shield whole-text vote." Of the 86 roll
calls on report A10-0199/2026, exactly one is not a recital, paragraph or
amendment split: `MTG-PL-2026-09-15-DEC-195987`, "Motion for a resolution (as
a whole)", adopted 420-220-26. Our side is AGAINST, grounded in the text
(paras 21, 22, 25, 27, 30 build out DSA enforcement over platform speech;
paras 35-36 carry the free-expression safeguards that argue the other way)
and confirmed by the anchor check: Patriots for Europe 0-33, ECR 1-21, ESN
0-7 and Non-attached 0-9 against, EPP 84-0, S&D 60-0, Renew 42-0 and
Greens/EFA 28-1 for.

The EU 5CA went from three signed divisions to four, and the zero column from
68 MEPs to 35.

**What the queue then showed, which was not expected.** `meaning_line_queue.py`
now has an EU arm ranking by MARGINAL placement -- MEPs a line would move off
zero -- because every MEP still sits, so turnout ranks nothing, and because
one report generates dozens of splits. Its answer after this sign-off: the
best remaining division in 116 unverdicted roll calls would place ONE more
MEP, and every other would place none. The backlog is nearly exhausted on
placement.

That is a real finding and also the measure's limit. More sign-offs would
still add EVIDENCE DEPTH for MEPs already placed -- the difference between an
MEP placed on one vote and one placed on five -- and the queue does not
measure that at all. Westminster's 5CA carries confidence and conflict flags
off exactly that depth. Ranking the EU backlog by depth rather than breadth
is the next thing this tool needs.


## Swept per sitting day (17 September 2026)

Christopher: "Make the EU sweep per sitting day like Westminster." The last
parity gap, and the one the week had just demonstrated: the 15 September
plenary sat uncollected for two days because the weekly was the only path and
the weekly had been cancelled.

`src/eudaysweep.py` + `tools/eu_day_sweep.py`, modelled on Hansard's day sweep
and sharing its `sweep_log` under source `ep-plenary`, house `EP`. Nightly at
23:00 UTC, clear of every other cron in the state group.

**What moves per day, and what deliberately does not.** A roll call is final
the moment the President reads it out and an adopted text is published the same
day, so those are swept once per sitting day and remembered. Written questions
are answered weeks after tabling, ECI signatures accrue, dossiers move between
readings and consultation windows run on their own clock: all of those change
after the fact, so a once-per-day sweep would freeze them wrong and they stay on
the weekly rolling window. The same division Hansard's sweep makes.

**A calendar, not a per-day probe.** Hansard has no sitting-dates endpoint, so
Westminster asks each day whether the House sat. The Parliament publishes a
whole year of meetings in one call, so a year of sitting dates costs one request
and is cached for the run. The EP sits in blocks, so most days cost nothing.
A calendar that fails returns None rather than an empty set: recording "did not
sit" from a failed lookup would bury the day for ever.

**Weekends are not skipped by the clock.** Hansard's sweep skips Saturdays
without a call. Here the Parliament's own calendar decides, because its
part-sessions do not follow a working week.

First run, backfilling a week: four sittings found (14 to 17 September), the
15 September Democracy Shield business collected, and the Hong Kong media
freedom resolution of 17 September picked up **on the day it was adopted**
rather than the following Saturday.

Registered in `coverage.py` PIPELINES at a daily cadence and in the failure
alert. It is deliberately NOT in `PIPELINE_FEEDS`: that drives the clobber
check, and the EP's weeks of recess would age its feeds legitimately and raise
a false alarm every time. The nightly heartbeat is the honest signal, because
the sweep runs and stamps one even when nothing sat.
