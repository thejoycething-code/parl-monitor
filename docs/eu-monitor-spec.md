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
