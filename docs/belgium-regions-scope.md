# Belgium: community and regional parliaments (scope and build, 13 October 2026)

Probed live from the laptop on 12 and 13 October 2026 with the identified UA
`CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)`, a few requests
per host, through `src/http.py` (raw responses archived under `data/raw/`).
Every number below was measured on those days. Built in the same branch
(`regions-be`): `tools/be_regions.py`, `src/be_regions_store.py`, a
"Communities and regions" section of the Belgian edition and a step of
`jobs/be-weekly.sh`.

## Why these parliaments matter more than their size

Belgium splits power three ways. The **communities** (Flemish, French,
German-speaking) hold education, youth, culture, family allowances and much of
health prevention; the **regions** (Flanders, Wallonia, Brussels-Capital) hold
territory, the economy, local government and the recognition and funding of
local religious communities. So the questions CitizenGO campaigns on in
Belgium are often decided here and not in the federal Chamber:

- school relational and sexual education: the French Community's compulsory
  **EVRAS** (the 2023 campaign) is a decree of the Parliament of the
  Wallonia-Brussels Federation; Flanders' equivalent sits in its attainment
  targets;
- gender in schools, school rules on religious symbols, home education;
- family allowances (Flanders' **Groeipakket**, the Walloon and Brussels
  allocations familiales) and childcare;
- adoption (Flanders is debating ending intercountry adoption);
- recognition of local faith communities and ritual slaughter (regions).

The Flemish Parliament exercises both the community and the regional powers
of Flanders; Brussels members of it vote on community matters only.

## The parliaments, ranked

Ranked by CitizenGO relevance (population, our ground in the measured
documents) and source quality.

| # | Parliament | Population covered | Source | Format | robots.txt | Reachable | Built |
|---|---|---|---|---|---|---|---|
| 1 | Vlaams Parlement (124 members) | 6.8 m | open-data web services `ws.vlpar.be/e/opendata/` and the search service `ws.vlpar.be/api/search/` | JSON | the website (vlaamsparlement.be) is behind a Cloudflare bot challenge; ws.vlpar.be has no robots.txt (it redirects to the F5 access page: no rules) | yes (ws.vlpar.be); the website no | **yes**: documents, statuses, recorded votes with every member, members |
| 2 | Parlement de la Fédération Wallonie-Bruxelles (French Community, 94 members) | 4.8 m (education for Wallonia and francophone Brussels) | www.pfwb.be (Nuxt site over Drupal; documents via Algolia) | HTML | `Disallow:` empty (everything allowed) | yes | **partial**: newest documents page and plenary agendas |
| 3 | Parlement de Wallonie (75 members) | 3.7 m | documented Open Data `www.parlement-wallonie.be/opendata/` | JSON, CSV | allows /opendata/ | yes | **yes**: every publication of the legislature, members |
| 4 | Parlement bruxellois / Brussels Parlement (89 members), with the United Assembly of the COCOM (ARCCC) | 1.25 m | the dossier file its website loads, `/prb_includes/weblex/data/dos_leg_legis_24-29.json` | JSON (DataTables) | only GPTBot disallowed | yes (one transient stall on 12 October) | **yes**: PRB and COCOM dossiers, French and Dutch titles |
| 5 | Parlament der Deutschsprachigen Gemeinschaft (25 members) | 0.08 m | pdg.be | - | robots.txt itself answers a Cloudflare challenge | **no** | blocked |
| 6 | Parlement francophone bruxellois (COCOF, 72 members) | francophone Brussels | parlementfrancophone.brussels | Plone faceted search loaded by script | everything allowed | yes | not built (no list to read without the script; few decrees) |
| 7 | Raad van de VGC (Flemish Community Commission, Brussels) | Dutch-speaking Brussels | vgc.be | PDFs | allowed apart from Drupal paths | yes | not built (regulations and minutes as PDFs only) |

## What each source gives (measured)

### 1. Vlaams Parlement

- **Documents.** The search service filters on a metadata term in the path
  (`inmeta:aggregaattype~decreet`; the `requiredfields` parameter is
  ignored), 100 a page. For the legislature (from 9 June 2024): bills for
  decrees 421 hits, resolutions 336, motions 118, concept notes 124,
  petitions 228. Each document is listed once per published part, so 899
  distinct documents. Every status is dated (`statusdatum_ingediend`,
  `statusdatum_plen_aangenomen`, ...), with the themes (`thema`), the
  introducers and the committee. Key `vl/<zittingsjaar>/<stuk>`; petitions
  have their own number series (`vl/<year>/vzs-<n>`).
- **Votes.** A document's open-data record (`/e/opendata/pi/<id>`) carries
  `journaallijn-stemmingen`: every recorded plenary vote on it, the tally
  (with the separate count of members entitled on a regional matter) and
  **every member's vote with the fractie the record prints**. Read only for
  documents on our ground or watched whose status reached the plenary in the
  last 21 days (400 on a store's first read, at most 40 records a run).
  First read: one vote, resolution 552 on the persecution of Christians in
  Sudan, rejected 27-91, 118 positions.
- **Sittings and agendas.** `/verg/vorige?type=plen` and
  `/verg/<id>` (agenda, journal lines, the handelingen PDF): probed, not
  stored (the votes come through the documents).
- **Members.** `/vv/op-datum?datum=DDMMYYYY`: 124 sitting members with fractie
  and constituency.
- **Written questions** (78 of every 100 search hits) are not read: volume,
  and the federal edition does not read them either.

### 2. Parlement de la Fédération Wallonie-Bruxelles

- The document search (`/documents-parlementaires`) is an Algolia index
  queried from the browser with an application key in the site's
  JavaScript. **Not used** (never use credentials found in site code).
- What is read instead, both server-rendered HTML: the newest-documents page
  (18 cards: type, number, session, title, date; questions with their
  authors), and the plenary agendas listed on `/agenda` (item text with the
  document number, `doc. 285 (2025-2026)`). A text adopted in plenary
  (`texadopt`) is stored as a status of the document it adopts.
- Document pages (`/documents-parlementaires/document-pjd-<id>`) render the
  type, number, title, deposit date and chronology server-side; not read yet
  (discovery is the limit, not the page).
- The site's sitemap (back.pfwb.be, 98 pages of 2,000 URLs) lists agenda,
  commission and meeting-video pages, not documents, and is mostly
  duplicate slugs: not used.
- Votes: in the integral report (PDF); not read. Members: not read yet.
- First read: 18 documents, none on our ground (the session had just
  opened; questions on indexation, school meals, TikTok).

### 3. Parlement de Wallonie

- `publications_od.php?f=json&idleg=12&type=<T>` for DECRET (632
  publications), RES (128), MOTION (394) and PARCHEMIN (123): four requests,
  1.2 MB, the whole legislature. Grouped by document number and session
  (`DECRET 657 N° 4 (2025-2026)` and `PARCHEMIN 657` are one document): 505
  documents. The first part gives the title and introducers ("déposée par
  ..."), the latest the status ("Texte adopté en séance plénière",
  "Rapport", the parchemin sent to the Government). Key
  `pw/<session>/<number>`; the special session of 2024 is `se2024`.
- Members: `composition_dep_od.php?f=json`, 75 deputies. The file carries
  postal addresses, e-mail and social accounts: **only name, group and
  constituency are stored**.
- Agenda (`agenda_od.php`) and reports (`CRI`, `CRA`) exist; votes are in
  the reports (PDF). Not read.

### 4. Brussels (PRB and COCOM)

- One JSON file per legislature, 471 KB, 340 dossiers (275 PRB, 65 ARCCC):
  assembly, dossier code (`A-222` PRB, `B-74` ARCCC), deposit date, type in
  French and Dutch, and every document of the dossier with its French and
  Dutch title (`A-222/1-25/26 - Proposition de résolution ...`,
  `.../4 - Texte adopté par la séance plénière`). The last document is the
  status; the source dates only the deposit, so a status change is dated the
  day a run first sees it. Key `bru/24-29/<code>` or `cocom/24-29/<code>`.
- Members (`/meps/<code>`): pages per member, not read yet. Votes: in the
  integral report; not read.

### 5. German-speaking Community: blocked

pdg.be, www.pdg.be, ostbelgienlive.be and ostbelgienrecht.be (the
Community's consolidated law) all answer with a Cloudflare "Just a moment"
challenge, robots.txt included. Never bypassed. Would be classified with
taxonomy-atch (country scoping would need a `be` tag for Belgian German
terms); a gap until the parliament offers a reachable source or allows us.

## Classification (as the federal collector does it)

Dutch titles against `config/taxonomy-nl.yaml`, French titles against
`config/taxonomy-fr.yaml`, both loaded for country `be` (their Belgian terms:
EVRAS, signes convictionnels, erediensten, kinderbijslag ...). Brussels has
both titles and each is matched against its own list (A-8, the ban on ritual
slaughter without stunning, matched on its Dutch title only: "ritueel
slachten"). Flemish themes are matched with the title. Migration (area 11)
is stored, never counted or shown. Watched documents by key from
`config/watchlist-be.yaml`, `regions`.

First read, on our ground: Flanders 17 of 899 (the 18-week abortion
resolution, youth care for the unborn child, ending intercountry adoption,
the persecution of Christians, the faith-communities recognition decree, a
petition on transgender protection), Wallonia 2 of 505, Brussels 3 of 275,
COCOM 2 of 65, FWB 0 of 18.

### Terms (APPLIED 13 October 2026: taxonomy-nl v0.3, taxonomy-fr v0.3)

Chris, 13 October 2026: "Accept the watchlists, apply the terms after measuring". Applied after measuring on a scratch read of the five readable
parliaments (1,762 documents) and the federal, French and Swiss stores
(read-only); the counts are in each master's dated note:

- **Applied, NL** (tagged `be`): `Groeipakket*` and `gezinsbijslag*`, area 9
  tier 2: 16 documents gain them, 12 newly on our ground (the Groeipakket
  decree amendments and 5 petitions; COCOM B-19, B-26, B-27, B-58, B-70);
  0 false positives.
- **Applied, FR** (shared, not tagged): `allocations familiales`, area 9 tier
  2: Wallonia 10 motions and COCOM B-39, plus 1 federal, 13 French and 14
  Swiss titles, all family-allowance policy (39 newly on our ground, 0 false
  positives), so the term serves all three French-speaking countries.
- **Not added**: the spelled-out EVRAS (every title that spells it out
  already matches "éducation à la vie relationnelle", tier 1) and the
  Erkenningsdecreet (already caught by `geloofsgemeenschap*`).

The proposals as first written (first read, 13 October):

- NL, area 9, tier 2: `Groeipakket*` (Flanders' family allowance since 2019;
  10 documents and 5 petitions, none matched except through "gezinsbeleid"),
  `gezinsbijslag*`.
- FR, area 9, tier 2: `allocations familiales` (Walloon and Brussels family
  allowances; Walloon motions of September 2026 on cutting them, unmatched;
  COCOM B-39 matched only through its Dutch title).
- FR, area 6, tier 1: `éducation à la vie relationnelle, affective et
  sexuelle` (EVRAS spelled out; "vie relationnelle" is already a term).
- NL, area 8, tier 2: `Erkenningsdecreet Lokale Geloofsgemeenschappen`
  (already caught by `geloofsgemeenschap*`; listed for completeness).
- DE (taxonomy-atch, `only: [be]`): none until a German source is readable.

## Built (13 October 2026)

- `tools/be_regions.py` (`--parliament`, `--reclassify`, `--dry-run`,
  `--budget-seconds`, default 300) into `ber_docs`, `ber_votes`,
  `ber_positions`, `ber_members`, `ber_reads` (`src/be_regions_store.py`,
  created by `db.init_db`). A live run on the laptop into a temporary store:
  about 30 requests, 20 seconds.
- Robots at run time through `src/robots_guard.guard()`: the two open-data
  APIs (`ws.vlpar.be/e/opendata/`, `www.parlement-wallonie.be/opendata/`)
  added to `DOCUMENTED_APIS`; every website request asks robots.txt.
- Edition: a "Communities and regions" section of the Belgian edition after
  the Watchlist (`src/editions/be.py`, `Country.extra_sections`), with the
  new documents, the stage moves (dated by the source, or the day first
  seen), the Flemish recorded votes with the group split and the members
  who broke from their group, and Coverage lines naming what is partial or
  blocked. The DM counts the section.
- Job: a step of `jobs/be-weekly.sh` after the federal collector (budget 300
  s, never fatal), and `BE_RECLASSIFY=true` reclassifies the regional rows
  too. No new Mini job, nothing to install.
- Watchlist: a `regions` section in `config/watchlist-be.yaml`, seeded with
  nine documents from the first read (decision 24's rule).
- Coverage: `ber_docs` watched (7 days, grace 4), awaiting its first
  Saturday run until 18 October.
- Tests: `tests/test_be_regions.py` (30 tests, fixtures in
  `tests/fixtures/be_regions/`).

## Not built, and why

- German-speaking Community: Cloudflare challenge (above).
- FWB full index: Algolia key in site code; votes and members not read.
- COCOF and VGC: no list without script; PDFs only.
- Votes outside Flanders: PDF reports only (the Walloon CRI, the Brussels and
  FWB integral reports). A later phase could read the Walloon CRI PDFs.
- Brussels and FWB members; sittings and agendas of all but the FWB plenary.

## Shared files touched

`src/db.py` (five table names, one ensure_schema call), `src/robots_guard.py`
(two API prefixes), `src/editions/be.py` (the extra section),
`jobs/be-weekly.sh` (one step), `config/watchlist-be.yaml` (`regions`),
`tools/coverage.py` (one feed, one awaiting entry, one exemption),
`docs/robots-runtime.md`, `docs/mac-mini.md`, `docs/belgium-scope.md`,
`docs/country-parity-handover.md`.

## Forward agenda (regional_agenda, 16 October 2026)

`src/regional_agendas/be.py`, read by `tools/regional_agenda.py be` into
`regional_agenda` (not wired into a job yet). Probed live from the laptop on
16 October 2026 with the identified UA, a handful of requests per host;
every website request asks robots.txt (`src/robots_guard.guard`). Region
codes are the parliament codes of `tools/be_regions.py`.

| Code | Parliament | Route | Format | Reaches | robots.txt | First run (16 Oct) |
|---|---|---|---|---|---|---|
| vl | Vlaams Parlement | `ws.vlpar.be/e/opendata/verg/komende?type=plen` and `?type=comm` (next week's meetings), then `/verg/<id>/agd` per meeting | JSON (documented open data) | the coming week (convened a week ahead) | not asked: `ws.vlpar.be/e/opendata/` is in DOCUMENTED_APIS | 21 meetings, 246 items to 23 Oct, 12 on our ground |
| pw | Parlement de Wallonie | `opendata/agenda_od.php?f=json&cal=recherche&idleg=12&annee=Y&mois=M` (this month and the next two), the order of the day as a PDF on `nautilus.parlement-wallon.be/Archives/<session>/ODJS|ODJC/` | JSON (documented open data) + PDF (pypdf) | a few days: the agenda appears once the Conference of Presidents has planned the week | opendata not asked (DOCUMENTED_APIS); nautilus has no rule against us | 0 meetings: on 16 October the agenda RSS said the orders of the day were still being planned |
| bru | Parlement bruxellois | `www.parlement.brussels/agenda/` (this week and next), each meeting's convocation `weblex.irisnet.be/display_pdf.php?info=convoc_fr&key=N` | HTML + PDF (pypdf) | to the end of next week | only GPTBot disallowed; weblex.irisnet.be allows | 7 meetings, 77 items to 21 Oct |
| cocom | Assemblée réunie (ARCCC) | the same agenda page, meetings marked ARCCC only (a joint PRB/ARCCC plenary is filed under bru) | HTML + PDF | to the end of next week | as bru | 0 meetings in the window |
| fwb | Parlement de la FWB | `www.pfwb.be/agenda`, each `/agendas/seances-plenieres-<date>-<id>` and `/agendas/commissions-permanentes-<date>-<id>` page (order of the day server-rendered, one item per question) | HTML | about a week | `Disallow:` empty | 6 meetings, 185 items to 21 Oct, 4 on our ground |
| cocof | Parlement francophone bruxellois | `www.parlementfrancophone.brussels/agenda?navyear=&navmonth=`, the meeting page, its convocation page (the documents on the order of the day) | HTML (Plone) | the current and next month as published | everything allowed | 1 meeting, 1 item (a resolution on pregnancy, birth and parenthood rights) |
| pdg | Parlament der DG | none | | | pdg.be, www.pdg.be: Cloudflare challenge (HTTP 403), robots.txt included | blocked |
| vgc | Raad van de VGC | none | | | | no route (PDFs only, no agenda list) |

Notes:

- The Brussels agenda links its convocations on `weblex.brussels`, whose
  TLS certificate does not match its name (TLS verification is never
  switched off). The same weblex service answers on `weblex.irisnet.be`,
  the host every Brussels parliamentary document is published on, so the
  convocation is read there.
- The Flemish API has no documented forward query beyond `komende`
  (`volgende`, date searches and `dagen=` answered 400); `komende` returns
  the next week's plenary and committee meetings, which is what the
  Parliament publishes.
- PDFs (Wallonia, Brussels) are read with pypdf, imported only when needed.
  Without it the meetings are stored as booked slots ('to be announced')
  and the run note says so.
- A meeting whose order of the day fails is a gap line; the window is then
  not pruned, so its stored rows stay.
- Live run (laptop, 16 October): 6 of 8 read, 509 items, 16 on our ground,
  0 to be announced, about 4 minutes (about 60 requests at 1 to 1.5 s, the
  Flemish service answering slowly).
