# CLAUDE CODE HANDOFF: CitizenGO Parliamentary Monitor

**Version 1.0 | 1 August 2026 | Prepared by: Christopher (CitizenGO UK) with Claude**
**Status: ready to build. All endpoints below were exercised live on 1 August 2026 and the quirks documented are observed behaviour, not guesses.**

---

## 1. What you are building

A weekly parliamentary monitoring pipeline for CitizenGO UK. It ingests the UK Parliament's open data feeds plus gov.uk and Holyrood, filters everything through an issue taxonomy, stores each surviving item as a structured record, and renders a Monday digest as a *byproduct* of that store. Nothing is ever written "for the digest": the digest, alerts and MP intelligence are all queries over the same records.

Three design decisions are fixed and non-negotiable:
1. **Weekly edition, not a live tracker.** One digest per week, generated Monday morning.
2. **The active bills board is persistent.** Every edition renders the board of live tagged bills with each bill's next key date, sorted ascending, regardless of whether anything moved. Bills leave the board only at Royal Assent or fall, with exactly one closing entry.
3. **Digest as byproduct.** All content lives in SQLite first. The markdown edition is a view.

Two companion documents ship with this handoff and should be committed to the repo unchanged: `keyword-taxonomy.md` (the human-readable taxonomy master, v0.1) and `digest-template.md` (the edition format and section rules). A worked reference edition also ships: `parliamentary-monitor-2026-08-03-pilot.md`. **Acceptance for Phase 1 is reproducing that pilot's findings from code** (section 9).

## 2. Repo layout

```
parl-monitor/
  config/
    taxonomy.yaml          # generated config, source of truth for matching (section 6)
    watchlist.yaml         # bills by ID, processes, orgs, parliamentarians
    settings.yaml          # dates, caps, owners, Slack webhook (phase 2)
  docs/
    keyword-taxonomy.md    # human master (edit here, regenerate yaml)
    digest-template.md
    pilot-2026-08-03.md
  src/
    db.py                  # schema + connection
    http.py                # fetch wrapper: UA, timeout, retry/backoff, throttle
    ingest/
      bills.py  pqs.py  wms.py  edms.py  sis.py  divisions.py
      whatson.py  consultations.py  legislation.py  scotland.py
      committees.py        # phase 2
    filter.py              # taxonomy matching -> candidate items
    triage.py              # Claude scoring pass -> score + why_it_matters draft
    board.py               # bills board state machine, session logic
    digest.py              # edition renderer (recess detection, caps, sections)
    members.py             # member id -> name/party/seat resolution + cache
  data/raw/YYYY-MM-DD/     # every raw API response, gzipped json (provenance)
  editions/                # rendered markdown editions
  run_weekly.py            # orchestrator
  run_alerts.py            # phase 2, daily during sitting weeks
  tests/
```

Python 3.11+, stdlib `urllib` or `httpx`, `pyyaml`, `sqlite3`. No Parliament API keys exist or are needed. `ANTHROPIC_API_KEY` env var required for triage (Phase 1 may stub it, section 7).

## 3. HTTP layer (build this first, everything depends on it)

Observed behaviour that must be encoded in `src/http.py`:

- **User-Agent:** `CitizenGO-ParlMonitor/1.0 (contact: <team email>)` on every request.
- **The Written Questions/Statements API is slow and flaky.** 7 to 30+ seconds per query; intermittent timeouts that persist for minutes. Required: per-request timeout 35s, up to 3 retries with exponential backoff and jitter (2s, 8s, 20s), and a per-host concurrency cap of 4. A failed term after retries is logged to a `gaps` table and reported in the edition footer, never silently dropped. (In the pilot, "home education", "safe access zones" and "Cass Review" sweeps failed even on retry; the edition disclosed this.)
- **Everything else is fast** (Bills, EDMs, SIs, votes, What's On, gov.uk, legislation.gov.uk: sub-2s typically). Still throttle: 0.2s sleep between sequential calls per host.
- Save every raw response to `data/raw/<date>/<feed>_<slug>.json.gz` before parsing. Disk is cheap; provenance settles arguments.

## 4. Feed reference (verified endpoints, parameters and quirks)

### 4.1 Bills — `bills-api.parliament.uk`
- Search: `GET /api/v1/Bills?SearchTerm={q}&SortOrder=DateUpdatedDescending&Take=15`
- Detail: `GET /api/v1/Bills/{billId}` → `shortTitle`, `sponsors[].member.{name,party}`, `originatingHouse`, `currentHouse`, `currentStage.description`, `isAct`, `isDefeated`, `introducedSessionId`, `includedSessionIds`, `lastUpdate`.
- Stages: `GET /api/v1/Bills/{billId}/Stages?Take=30` → `items[].{description, house, stageSittings[].date}`. **Next key date = earliest stageSitting date >= today across all stages; else TBA.**
- **Quirks (all observed):**
  - Bills that **fall at prorogation are not flagged**: `isDefeated=false`, stage frozen at the last sitting. Detect falls via session: track `current_session_id = max(introducedSessionId)` seen across recent bills (session 39 = 2024-26, session 40 = opened June 2026). A non-Act bill whose `includedSessionIds` excludes the current session has fallen → one closing entry, remove from board.
  - **Acts vanish from a "live bills" mindset**: `isAct=true`, `currentHouse="Unassigned"`, stage "Royal Assent". Never rely on bill search to notice an Act happened; the board state machine must treat Royal Assent as a terminal transition and emit the closing entry.
  - **Same-title collisions are real** (two "Terminally Ill Adults (End of Life) Bill"s exist, IDs 3774 and 4157). Key everything on `billId`.
- Bill page link: `https://bills.parliament.uk/bills/{billId}`.

### 4.2 Written questions — `questions-statements-api.parliament.uk`
- `GET /api/writtenquestions/questions?searchTerm={q}&answered=Answered&take=6`
- **Do not use `answeredWhenFrom`** for routine sweeps: it makes queries dramatically slower. Results already come newest-first; filter `dateAnswered` client-side.
- **Do not use `expandMember=true`** (adds latency). Store `askingMemberId`; resolve via Members API (4.9) only for shortlisted items, with a local cache.
- Fields used: `id, uin, heading, questionText, answerText, askingMemberId, answeringBodyName, dateTabled, dateAnswered, house`.
- **Store `dateTabled`.** The canonical public link is `https://questions-statements.parliament.uk/written-questions/detail/{dateTabled:YYYY-MM-DD}/{uin}` and cannot be built without it (pilot gap #4).
- **Search matching is loose** ("Red Diesel: Taxation" matched "assisted dying"). This is why triage exists; never publish raw keyword hits.

### 4.3 Written ministerial statements — same host
- `GET /api/writtenstatements/statements?madeWhenFrom={YYYY-MM-DD}&take=60` (this endpoint tolerates the date filter). Filter title+text against taxonomy client-side. Duplicate rows appear (same statement, both Houses): dedupe on title+date.

### 4.4 EDMs — `oralquestionsandmotions-api.parliament.uk`
- `GET /EarlyDayMotions/list?parameters.searchTerm={q}&parameters.take=10` — note the literal `parameters.` prefix on every query arg.
- Response envelope: `{PagingInfo, Response:[...]}`. Fields: `Id, Title, MotionText, DateTabled, PrimarySponsor.{Name, Constituency}, SponsorsCount, UIN`.
- Link: `https://edm.parliament.uk/early-day-motion/{Id}`. Filter `DateTabled` client-side. Track signature deltas week on week (store `SponsorsCount` per edition).

### 4.5 Statutory instruments — `statutoryinstruments-api.parliament.uk`
- `GET /api/v2/StatutoryInstrument?Name={q}&Take=25` → `items[].value.{name, procedure.name, commonsLayingDate, lordsLayingDate, paperMadeDate, id}`.
- No reliable server-side date ordering: take laid date = first non-null of the three date fields, filter client-side.
- Sweep terms must include **Act short titles** ("Crime and Policing", "Children's Wellbeing") to catch commencement and consequential regulations: this is how implementation gets tracked.

### 4.6 Divisions
- **Commons:** `GET https://commonsvotes-api.parliament.uk/data/divisions.json/search?queryParameters.startDate={d}&queryParameters.endDate={d}&queryParameters.take=60`. PascalCase fields: `DivisionId, Date, Number, Title, AyeCount, NoCount`. Member-level breakdown: `GET /data/division/{DivisionId}.json` (feeds MP profiles and the existing voting tracker).
- **Lords:** `GET https://lordsvotes-api.parliament.uk/data/Divisions/search?StartDate={d}&EndDate={d}`. **Observed: content/notContent counts were null in the list view**; fetch the division detail endpoint for counts when a Lords division is shortlisted.
- **Match division titles against the entity watchlist, not just keywords.** The 8 July approval of a Children's Wellbeing Act SI (369-102) slipped past keyword matching in the pilot.

### 4.7 What's On — `whatson-api.parliament.uk`
- `GET /calendar/events/list.json?queryParameters.startDate={d}&queryParameters.endDate={d}`
- **Range limit:** long ranges return HTTP 400. Chunk requests to <= 4 weeks.
- **Keys are PascalCase:** `StartDate, StartTime, House, Category, Type, Description, BillId, BillName, Committee, Location`. An empty array `[]` is a valid response and means no calendared business (= recess signal).
- Main-chamber PMB business appears with `Type: "Main Chamber"`, `Category: "Private Members' Bills"` and the bill in `Description` (BillId often null for Commons PMBs; match on description text against the watchlist). **Order in the response reflects Order Paper order**: first PMB listed gets the day's debate.
- Recess detection for `digest.py`: zero Commons AND Lords events in the edition week → recess mode. Return date = earliest event date per house in the following 6 weeks.

### 4.8 legislation.gov.uk (Act verification)
- Year browse: `GET https://www.legislation.gov.uk/ukpga/{year}` (HTML); extract chapters with regex `/ukpga/{year}/(\d+)/contents`.
- Contents: `GET /ukpga/{year}/{chapter}/contents/data.xml` → `<ContentsNumber>` / `<ContentsTitle>` pairs. Grep for taxonomy terms to locate relevant sections.
- In-force status: fetch the section HTML (`/ukpga/{year}/{chapter}/section/{n}`) and search for annotations ("in force at Royal Assent", "not yet in force", "comes into force"). This is how the pilot confirmed s.241 Crime and Policing Act 2026 has been in force since 11 May 2026. Run this check whenever a watched bill reaches Royal Assent.

### 4.9 Members — `members-api.parliament.uk`
- `GET /api/Members/{id}` → `value.nameDisplayAs`, `value.latestParty.name`, `value.latestHouseMembership.membershipFrom`. Fast. Cache permanently in a `members` table.

### 4.10 gov.uk consultations
- `GET https://www.gov.uk/api/search.json?filter_content_store_document_type=open_consultation&count=200&fields=title,link,end_date,organisations`. Fast and reliable. Match titles against taxonomy **plus a broadened area-6 set** ("education otherwise than at school", "child protection", "foster care"): government labels rarely match campaign vocabulary (pilot lesson).

### 4.11 Scottish Parliament
- `https://data.parliament.scot/api/bills` returns the full bills dataset and **timed out at 60s in the pilot**. Approach: attempt the API with a 90s timeout and cache the dump for 30 days; **proven fallback** is scraping the bill page `https://www.parliament.scot/bills-and-laws/bills/s6/{slug}` and regexing the status text ("Current status:", "fell on", "Stage 3", "Royal Assent"). The pilot extracted "fell on 17 March 2026 at Stage 3" this way. Maintain watched Holyrood bills as slugs in `watchlist.yaml`.

### 4.12 Committees (Phase 2)
- Swagger: `https://committees-api.parliament.uk/swagger/v1/swagger.json`. No endpoint named for calls-for-evidence; the candidate is **`/api/CommitteeBusiness`** (business items carry submission periods; see also `/api/SubmissionPeriod/{id}`). Untested. Task: probe, then surface open calls with deadlines into section 6 of the digest.

### 4.13 Hansard (Phase 2)
- `https://hansard-api.parliament.uk/` for debate contributions by watched members and terms. Not exercised in the pilot; wire after Phase 1 acceptance.

## 5. Data model (SQLite, `src/db.py`)

```sql
CREATE TABLE items (
  id TEXT PRIMARY KEY,            -- '{feed}:{source_id}'
  captured_at TEXT NOT NULL,
  source_feed TEXT NOT NULL,      -- bills|pq|wms|edm|si|division|whatson|consultation|scotland|committee
  item_type TEXT NOT NULL,
  title TEXT, url TEXT,
  legislature TEXT,               -- Commons|Lords|Holyrood|Senedd|NIA
  jurisdiction TEXT,
  event_date TEXT, deadline TEXT,
  date_tabled TEXT,               -- PQs: required for deep links
  issue_areas TEXT,               -- json list of area numbers
  matched_terms TEXT,             -- json list, for taxonomy maintenance
  tier INTEGER, triage_score INTEGER,
  priority_tag TEXT,              -- ACT|WATCH|NOTE (human-set at review)
  why_it_matters TEXT,            -- <=35 words, drafted by triage, edited by human
  owner TEXT, action_status TEXT DEFAULT 'none',
  mp_refs TEXT, bill_ref INTEGER,
  raw_path TEXT                   -- provenance pointer into data/raw/
);
CREATE TABLE bills_board (
  bill_id INTEGER PRIMARY KEY, title TEXT, sponsor TEXT,
  house TEXT, stage TEXT, next_key_date TEXT, what_next TEXT,
  areas TEXT, status TEXT,        -- live|closed
  closed_note TEXT, closed_edition TEXT,
  session_ids TEXT, last_update TEXT, board_snapshot TEXT -- json of prior edition row for movement marker
);
CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT, party TEXT, seat TEXT, house TEXT);
CREATE TABLE mp_events (member_id INTEGER, date TEXT, kind TEXT, ref TEXT, line TEXT);
CREATE TABLE edm_signatures (edm_id INTEGER, edition TEXT, count INTEGER, PRIMARY KEY (edm_id, edition));
CREATE TABLE editions (week_commencing TEXT PRIMARY KEY, generated_at TEXT, mode TEXT, path TEXT);
CREATE TABLE gaps (edition TEXT, feed TEXT, detail TEXT);
CREATE TABLE discards (edition TEXT, item_id TEXT, title TEXT, matched_terms TEXT); -- monthly false-negative review
```

## 6. Taxonomy config (`config/taxonomy.yaml`)

Generated from `docs/keyword-taxonomy.md`; **includes the four v0.2 patches from the pilot**. Matching: case-insensitive; quoted strings = phrase match; trailing `*` = stem; short tokens word-boundary. Global exclusions never match alone: termination, conversion, transition, blocker, gender, safeguarding, education, equality.

```yaml
version: 0.2
areas:
  1_abortion:
    tier1: [abortion, "Abortion Act 1967", "termination of pregnancy", "safe access zone*",
            "buffer zone*", "abortion time limit", "foetal viability", "fetal viability",
            "pills by post", "telemedicine abortion", "sex-selective abortion",
            "Offences against the Person Act 1861", "Infant Life (Preservation)",
            "Ground E", "disability-selective", BPAS, "MSI Reproductive Choices"]
    tier2: ["reproductive rights", "reproductive healthcare", "crisis pregnancy",
            "conscientious objection", "gestational limit", "foetal pain", "silent prayer"]
    note: decriminalisation now law (CPA 2026 s241, in force 11 May 2026); watch = implementation, pardons scheme s242, amendment vehicles on any Home Office/MoJ bill
  2_assisted_dying:
    tier1: ["assisted dying", "assisted suicide", euthanasia, "Terminally Ill Adults",
            "End of Life Bill", "Suicide Act 1961", "physician-assisted", "assisted death"]
    tier2: ["palliative care", hospice, "end of life care", "terminal illness",
            "mental capacity", "right to die", coercion, anorexia]
  3_gender_medicine_children:
    tier1: ["puberty blocker*", "puberty-suppressing hormones", "puberty suppressing hormones",
            "cross-sex hormones", "Cass Review", Tavistock, GIDS, "gender identity service*",
            "gender dysphoria", "gender questioning children", "youth gender", PATHWAYS]
    tier2: [detransition*, "gender-affirming", "Gillick competence", "gender clinic*",
            "private prescriptions", "indefinite ban"]
  4_conversion_practices:
    tier1: ["conversion therapy", "conversion practices", "Conversion Practices Bill"]
    tier2: ["gender exploratory therapy", "talking therap*", "religious exemption", "affirmation-only"]
  5_sex_based_rights:
    tier1: ["single-sex space*", "single-sex service*", "single-sex ward*",
            "Gender Recognition Act", "gender recognition certificate", "self-identification",
            "self-ID", "biological sex", "legal definition of woman", "For Women Scotland",
            "women's sport", "female category"]
    tier2: ["Equality Act 2010", "Sullivan Review", "sex and gender data", "changing room*",
            "toilet provision", transgender, "protected characteristic", "women's prison*"]
  6_parental_rights_education:
    tier1: ["relationships and sex education", RSE, "sex education guidance",
            "parental consent", "parental rights", "right to withdraw", "home education",
            "elective home education", "children not in school",
            "education otherwise than at school", EOTAS]          # v0.2 patch
    tier2: [PSHE, "curriculum review", "external providers", "smartphone* in schools",
            "faith school*", "collective worship", "child protection", "foster care"]  # v0.2 broadened
  7_free_speech_online_safety:
    tier1: ["Online Safety Act", "age verification", "age assurance", "free speech",
            "freedom of expression", "non-crime hate incident*", "silent prayer",
            "Higher Education (Freedom of Speech)", censorship,
            "anti-Muslim hostility", "Islamophobia definition"]   # v0.2 patch
    tier2: [Ofcom, misinformation, disinformation, "harmful content", "hate speech",
            blasphemy, "client-side scanning", encryption, "street preacher*"]
  8_freedom_of_religion:
    tier1: ["freedom of religion or belief", FoRB, "Christian persecution",
            "persecution of Christians", "religious persecution", "Truro Review",
            "Special Envoy for Freedom of Religion", apostasy, "blasphemy law*"]
    tier2: ["religious minorit*", "religious conversion", chaplain*, "places of worship"]
  9_marriage_family:
    tier1: ["marriage law", "weddings law", "Tying the Knot", "Law Commission",
            "cohabitation reform", "cohabitation rights", "marriage allowance",
            "family breakdown", "no-fault divorce"]               # v0.2: Tying the Knot
    tier2: ["civil partnership*", "family hub*", fatherhood, "forced marriage", "humanist marriage"]
  10_surrogacy_embryology:
    tier1: [surrogacy, surrogate, "Surrogacy Arrangements Act", "Human Fertilisation and Embryology",
            HFEA, "commercial surrogacy", "embryo research", "14-day rule", "gamete donation", "egg donation"]
    tier2: ["fertility treatment", IVF, "donor conception", "donor-conceived",
            "mitochondrial donation", "genome editing"]
exclusions_global: [termination, conversion, transition, blocker, gender, safeguarding, education, equality]
```

`config/watchlist.yaml` (seed; the board state machine keeps it current):

```yaml
bills:                    # Westminster, by ID (never by title)
  4157: {title: "Terminally Ill Adults (End of Life) Bill", areas: [2]}
  4144: {title: "Complications from Abortions (Annual Report) Bill [HL]", areas: [1]}
  4178: {title: "Hospice Funding Bill", areas: [2]}
  4171: {title: "Relationships and Sex Education (FE Sector) Bill", areas: [6]}
acts_watch:               # implementation tracking via SI name sweeps + legislation.gov.uk
  - {short: "Crime and Policing", chapter: "ukpga/2026/20", sections: [241, 242], areas: [1]}
  - {short: "Children's Wellbeing and Schools", chapter: "ukpga/2026/21", areas: [6]}
holyrood:
  - {slug: assisted-dying-for-terminally-ill-adults-scotland-bill, status: fell-2026-03-17, areas: [2]}
processes: ["Cass Review", "Sullivan Review", "PATHWAYS", "Tying the Knot",
            "Modern Service Framework", "anti-Muslim hostility definition",
            "Online Safety Act codes"]
organisations: [Right To Life UK, SPUC, CARE, Christian Concern, ADF International,
                Care Not Killing, Sex Matters, Christian Institute, Coalition for Marriage,
                BPAS, MSI Reproductive Choices, Dignity in Dying, Humanists UK, Stonewall, Mermaids]
parliamentarians:         # seed only; extended from voting tracker + EDM signatories
  - Kim Leadbeater
  - Lauren Edwards
  - Danny Kruger
  - Tonia Antoniazzi
  - Andrew Snowden
  - Carla Lockhart
  - Jim Shannon
  - Lord Moylan
  - Lord Falconer of Thoroton
  - Baroness Grey-Thompson
  - Baroness Maclean of Redditch
```

Watchlist rule: any item mentioning a watchlist entity is included at minimum score 2, regardless of keyword match. Division titles are matched against `bills:` titles and `acts_watch.short` values explicitly.

## 7. Triage pass (`src/triage.py`)

Tier-2 matches and all watchlist hits go through a Claude scoring call. Model: `claude-sonnet-4-6`. Batch up to 20 items per call. Phase 1 may run with `TRIAGE=stub` (score 2 for tier-1, 1 for tier-2, flag for human) but the live pass is the design intent.

System prompt (verbatim):

```
You are the triage layer of CitizenGO UK's parliamentary monitor. CitizenGO campaigns
on: abortion (pro-life), assisted dying (opposed), youth gender medicine (opposed to
paediatric transition), conversion practices bans (concerned re therapy/parental/religious
freedom), single-sex spaces (sex-based rights), parental rights in education, free speech
and online safety overreach, freedom of religion or belief, marriage and family, surrogacy
(opposed to commercial surrogacy).

For each item, return JSON: {"id": ..., "score": 0-3, "areas": [..],
"why_it_matters": "..."}.
Score 0 = irrelevant to every area. 1 = background only. 2 = belongs in the weekly
digest. 3 = likely campaign or lobbying trigger.
why_it_matters: maximum 35 words, CitizenGO voice: direct, concrete, no hedging,
British spelling, no em dashes. State the implication, not a summary.
Score on relevance to the areas above regardless of whether an item helps or hurts
the campaign position: opposition activity scores as highly as friendly activity.
Return only the JSON array.
```

All score>=2 items land in a review queue (Phase 1: a generated `review-YYYY-MM-DD.md` checklist the human edits; edits write back `priority_tag`, `owner`, final `why_it_matters`). Score-0 discards are logged to `discards` for the monthly false-negative review.

## 8. Board logic and edition rendering

**`board.py`:**
- New bill matching taxonomy/watchlist → propose board entry (human confirms in review file).
- Weekly refresh per live bill: detail + stages → recompute `next_key_date` (earliest sitting >= today, else TBA); diff against `board_snapshot` → movement marker (▲ changed / — unchanged).
- Terminal transitions: `isAct` → Royal Assent closing entry + create `acts_watch` row + trigger legislation.gov.uk section/in-force check; current session absent from `includedSessionIds` → fell-at-prorogation closing entry. Closing entries render in exactly one edition (`closed_edition` guard).

**`digest.py`:**
- Edition query: bills board (always) + items with `event_date` in the coming week + items `captured_at` in the past 7 days + open deadlines within 6 weeks.
- Recess mode when What's On returns zero chamber events for the edition week: render sections 1, 2, 6, 7, 11 plus return-dates line; deadlines always render.
- Caps: top lines 3-5; PQs 5; EDMs 5; enforce, demote NOTE items first. Every ACT requires non-null `owner` (hard validation, refuse to render otherwise).
- Section order, tags and formats exactly per `docs/digest-template.md`. Footer lists any rows in `gaps` for the edition. Write to `editions/parliamentary-monitor-YYYY-MM-DD.md` and insert into `editions`.

**`run_weekly.py`** (cron: Sunday 21:00 pull + triage + review file; Monday 06:30 render after review edits, or render draft immediately with `--draft`): target end-to-end runtime under 20 minutes including retries.

**`run_alerts.py`** (Phase 2, daily 07:30 on sitting days). Triggers: (a) new stage sitting within 7 days on a board bill; (b) division scheduled/announced on a board bill; (c) What's On description matches a board bill for the next sitting day; (d) new SI whose name matches `acts_watch.short`; (e) consultation opening on any tier-1 term. Channel: Slack incoming webhook from `settings.yaml`. One message per trigger, dedupe on (trigger, ref, date).

## 9. Phase 1 acceptance test

Run the pipeline with a captured-at window of 1 August 2026 (raw fixtures from the pilot are in `data/raw/2026-08-01/` if live data has moved on). The generated edition must reproduce, from code alone:

1. Board: bill 4157 next key date **2026-09-11**; 4144 **TBA**; 4178 **2026-11-27**; 4171 **2026-12-04**; all marked NEW.
2. Closing entries: bill 3774 fell at prorogation (last Lords committee sitting 2026-04-24, 14 sittings from 2025-11-14); Crime and Policing Act 2026 RA 2026-05-11; Children's Wellbeing and Schools Act 2026 RA 2026-06-26; Holyrood assisted dying bill fell 2026-03-17.
3. Legislation check: ukpga/2026/20 contains s.241 "Removal of women from the criminal law related to abortion" and s.242, with s.241 in force at Royal Assent.
4. Recess mode active for w/c 2026-08-03; both Houses' return detected as 2026-09-01; the 2026-09-11 Order Paper lists the TIA bill first among Commons PMBs.
5. PQ clusters surfaced: PATHWAYS (asker resolves to Andrew Snowden, Con, Fylde), hospices cluster, HL2262/HL2263 (Baroness Maclean), age assurance (Lord Black), anti-Muslim hostility definition PQs.
6. EDM 603 (Antoniazzi, 6 sigs), 536, 342 captured with correct dates.
7. SI: CWSA (Establishment of Schools) Regs laid 2026-05-20, and Commons division #51 of 2026-07-08 (369-102) linked to it via the entity match.
8. Consultation "SEND reform: education otherwise than at school" captured (closes 2026-09-18) via the v0.2 EOTAS term.
9. `gaps` table carries any PQ terms that failed after retries, and the footer discloses them.

## 10. Build order

1. `http.py` + `db.py` + raw archiving.
2. `ingest/bills.py` + `board.py` with session/fall/assent logic (hardest logic, highest value).
3. Remaining Phase 1 ingesters: pqs, wms, edms, sis, divisions, whatson, consultations, legislation, scotland, members.
4. `filter.py` from taxonomy.yaml + watchlist.yaml.
5. `triage.py` (stub first, then live Claude call).
6. `digest.py` + review-file round trip.
7. Acceptance run (section 9). Ship.
8. Phase 2: committees CfE probe, Hansard, Senedd (`business.senedd.wales` — research needed) and NI Assembly (`aims.niassembly.gov.uk` — research needed), `run_alerts.py`, PQ deep links, backoff hardening.
9. Phase 3: archive search CLI ("what has {member} said on {area} since {date}"), MP profile roll-up exporting 5CA scoring inputs, HTML email skin matching the MP voting tracker branding, hosted option (Supabase) if the team wants shared access.

## 11. Things not to do

- Do not key anything on bill titles. IDs only.
- Do not trust `isDefeated` to mean "no longer live". It doesn't cover prorogation.
- Do not publish keyword hits without triage; Parliament's search relevance is loose.
- Do not use `answeredWhenFrom` or `expandMember` on the PQ API.
- Do not request What's On ranges over four weeks.
- Do not paste full PQ answers into editions; takeaway line + link, full text stays in the store.
- Do not render an ACT item without an owner.
- Do not hand-edit `config/taxonomy.yaml`; edit `docs/keyword-taxonomy.md` and regenerate.
