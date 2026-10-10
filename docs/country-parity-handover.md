# Country editions: parity plan and handover (10 October 2026)

Written by the personal-account Claude session that built the 30 new
countries (9-10 October 2026), for Chris's work-account Claude to take over.
Everything it built is on main. Read this with
`docs/country-decisions-2026-10-10.md` (Chris's signed-off decisions) and each
`docs/<country>-scope.md` (sources, quirks, phase lists, "Waiting on Chris").

## What exists now

| Layer | UK | DE | US / IE / AU | CA | New countries |
|---|---|---|---|---|---|
| Collector (bills, votes, members) | yes | yes | yes | yes | yes, 25 countries (see below) |
| Weekly edition, Slack DM to Chris | yes | yes | yes | yes | 14 own editions + Hungary gazette edition + one monthly Latam edition |
| Triage | API judge | API judge | API or session judge | session judge (provinces) | free session judge, Sundays 16:45 (`tools/edition_judge.py`) |
| Noise filters, mute lists | yes | partly | yes | yes | yes (`src/noise.py`, `config/edition-noise-<cc>.yaml`) |
| Same-day vote briefs (division watch) | yes | no | yes (`*_division_brief.py`, `src/vote_brief.py`) | no | **no** |
| 5CA (member stance, five columns) | yes | yes | yes | yes | **built** 10 Oct (`tools/country_5ca.py`, branch `parity-5ca`): sheets from confirmed readings only, none confirmed yet; AT/PT/NL rows derived (X5). Tracker and partner sheet built 10 Oct (`tools/make_country_5ca_web.py`, branch `camp-5ca-sheets`): `docs/5ca-countries.html` weekly, "awaiting sign-off: N readings" per country; partner page gated until a country has a confirmed placement |
| Stance sign-off per vote (`config/*_stance.yaml`) | yes | yes | yes | yes | **built** 10 Oct: 2,012 drafts in 18 countries (71 with proposed values, 43 procedural, 1,898 need reading), weekly digest DM; signers per country to name (`config/stance_signers.yaml`) |
| Member profiles | yes | yes | US yes | no | yes, 23 countries (`profiles/<cc>/`, weekly step; X5 derived and X6 as-listed labelled; HR and CL party history sourced), branch `parity-profiles` |
| Debates / speeches | yes | yes | IE, AU | yes | NL, CH, AT, FR, BE (10 Oct, `tools/<cc>_chamber.py`); not PL (transcripts never answered), BR (per-deputy cost), IT (Senate 403), ES (dissolved), PT (no open source) |
| Parliamentary questions | yes | no | IE | no | NL, PL, FR, PT, BR requests (10 Oct, `tools/<cc>_chamber.py`); already in the editions: SK interpellations, AT J/AB, CH Vorstösse, HU, UY pedidos, HN press, BO written questions: BO4, built 10 Oct, `parity-phases-b` |
| Committees, courts, petitions, consultations | yes | yes | US courts | yes | constitutional courts (X8) built for CO, EC, PE, PT (10 Oct, `parity-phases-b`); GT gap; no committees or petitions |
| Week ahead / agenda | yes | yes | yes | no | yes for NL, PL, CH, BR, IT (Camera), FR, AT, ES (fills from 23 Dec), AR (Senate), HR; not BE, PT, SK, HU, MX or Latam (item 4) |
| Debate packs, campaign briefs, campaign targets | yes | yes | no | yes | debate packs **built** 10 Oct (`tools/country_debate_pack.py`, manual, 26 countries; placements from confirmed readings only, none yet); briefs and targets **no** |
| Debate today, live read | yes | no | no | no | **built** 10 Oct (`tools/country_debate_today.py`, `tools/country_live_debate.py`, branch `camp-live-debate`) for the four countries whose chamber publishes the same day: NL, CH, FR, BE; not AT (next day or later) or the question-only countries. Before sign-off the live read names no contradiction ("awaiting sign-off"); debate today is a step of the 16:45 net task |
| Regional / state parliaments | devolved | Länder (part) | US states (in progress) | provinces | **no** (later, per decisions) |
| Later phases, set A (item 6) | | | | | **built 10 Oct** (branch `parity-phases-a`): FR5 Senat votes and dossiers, NL4 Eerste Kamer votes and bills, IT2 dati.camera.it for the Camera, CH6 Swiss Italian texts, SK6 Slovak bill documents |

New-country collectors and what their vote data supports:

- **Member-level votes** (5CA possible): Italy, Switzerland, France
  (Assemblée), Netherlands (mostly party votes, X5 derived), Belgium, Poland
  (Sejm), Croatia, Slovakia, Spain (Congreso), Brazil, Argentina (Senate),
  Mexico (Chamber), Chile, Peru (partial, scans lost), Ecuador, Dominican
  Republic (Chamber), El Salvador, Guatemala (GitHub only), Hungary
  (karzat, 9 May to 28 Aug only).
- **Party-group votes only** (5CA by party, X5 derived and labelled):
  Austria, Portugal, Netherlands.
- **No member votes**: Colombia (current Congress), Bolivia, Panama,
  Honduras, Uruguay, Venezuela, Nicaragua; Costa Rica and Paraguay blocked.

## The parity work, in priority order

### 1. Same-day vote briefs (cheapest win)
Generalise `src/vote_brief.py` (IE/AU/US already share it) to the new
countries with member-level votes, reading from each `<cc>_store` after the
weekly collection, or from the source directly where it is cheap (NL OData,
PL Sejm API, CH OData, BR Câmara API publish same-day). Watched and tier-1
votes only, DM to Chris, de-duplicated like `tools/latam_alerts.py`.
No new decisions needed.

### 2. 5CA and stance sign-off (needs people)
5CA (`docs/5ca-notes.md`) needs CitizenGO's position on each vote that counts
(`config/<cc>_stance.yaml`, signed off by Chris or the country team, as with
Canada's C-218). Build per country: stance drafts generated from the watched
and tier-1 votes, a sign-off flow, then `make_5ca`-style output and the
tracker. Without sign-off the 5CA cannot be published. Ask Chris who signs
off per country (country teams are the natural owners). Start with the
countries with the richest member data and live campaigns: Poland, Italy,
Spain (after 23 December), Croatia, Slovakia, Brazil.

**Built 10 October 2026 (branch `parity-5ca`; docs/5ca-notes.md, "The new
country editions").** `tools/country_5ca.py` drafts readings for every
watched and tier-1 vote by rules (area, the bill's direction from a
`bill_directions` line, the kind of vote; `needs_reading` where unclear),
confirms only with `--by NAME` and a date, and writes sheets from confirmed
readings only. `tools/stance_digest.py` DMs Chris the weekly list of what
waits. Still open: Chris to name the signer per country in
`config/stance_signers.yaml`, and to confirm the first readings.

### 3. Member profiles
One profile per member from the stores already collected (party history,
votes on our ground, watched-bill authorship where the source has it).
Reuse the US/DE profile code. X6 applies: party at the vote needs party
history before member-level claims (HR, CL, GT currently show party as
listed).

**Built 10 October 2026 (branch `parity-profiles`).** `src/member_profiles.py`
(one generic generator, a few SQL statements per country) and
`tools/member_profiles.py <cc>`, a step of every new country's weekly job:
`profiles/<cc>/<member>.md` and `index.md` for AR, AT, BE, BR, CH, CL, CO,
DO, EC, ES, FR, GT, HR, HU, IT, MX, NL, PE, PL, PT, SK, SV, UY. Votes come
from each edition adapter with its noise rules and judge scores (the
framework's `item(division=)` field, additive); positions verbatim; party at
the vote with its basis on every line. X6: Croatia's transcripts
(`tools/hr_party_history.py`, `hr_party_seen`) and Chile's senators from the
BCN (`tools/cl_senate_parties.py`); Guatemala, Ecuador, Colombia and Belgium
labelled "not party at the vote". X5: AT, PT, NL positions DERIVED, labelled.
Authorship where the store links it (PT, AT, FR, BE, CH, AR, PE, CL, CO);
questions for SK, UY, AT. Not built: Bolivia, Panama, Honduras (no member
records on our ground), Mexico authorship (presenter is prose).

### 4. Week ahead
The framework already renders a week-ahead section when a store holds
agenda data. Add agenda collection where the source has it: NL (OData
Activiteit), PL (Sejm proceedings), CH (sessions), BR (Câmara pauta), IT, FR,
AT (Sitzungen), ES (from 23 December).

**Built 10 October 2026 (branch `parity-week-ahead`).** One table and one
collector for all of them (`src/agenda.py`, `country_agenda`;
`tools/country_agenda.py <cc>`), a source module per country
(`src/agendas/<cc>.py`), run as a step of each country's weekly job after
its collector. Points are matched to the store's bills by number only
(Kamerstuk/zaak, druk/process, Geschäftsnummer, proposição, Atto Camera,
dossier ref, d.B./A(E), expediente); watched and tier-1 points are flagged,
and the edition's Coverage line says how far each agenda reaches and when
the next sitting is. Measured on the live sources that day: NL 661 points
(12 on our ground), PL sitting 67's 41 points (the abortion bill, druk 223,
watched), BR 47, IT 48 (the Camera's October calendar), FR 216, AT 31, CH
none (between sessions), ES 17 (dissolved: the Diputación Permanente),
AR the Senate's committee meetings (cultural events left out).
Not done: the Italian Senate (refuses us), the Spanish plenary's order of
the day (a PDF), committee convocations in IT and CH, the Argentine
Diputados agenda (www.hcdn.gob.ar, AR4: left to a later decision), Belgium
(no open agenda source probed), Portugal, Slovakia, Hungary, Mexico and
the Latam monitor's countries (monthly, no week-ahead section; their
agendas are HTML per day or PDF: Colombia, Peru, the Dominican Republic;
Panama's orden del día is already collected in pa_agenda but not shown).

### 5. Debates, speeches, questions
Per country where the source is open: NL Handelingen, PL transcripts (the
endpoint timed out on 9 October), AT Stenographische Protokolle, CH, FR, IT
Senate, BR. Written questions where cheap (BR, PL interpellations, FR).


**Done, 10 October 2026 (branch `parity-debates`).** One shared module,
`src/chamber_store.py` (tables `<cc>_speeches`, `<cc>_questions`,
`<cc>_record_reads`; per-speech classification; the run loop; the edition
items), and one collector per country, `tools/<cc>_chamber.py`, run as a
step of each country's weekly through `tools/chamber_step.sh` (time-boxed to
what is left of the hour, at most ten minutes, never fatal, skipped on
GitHub). The edition gains "Said in the chamber" (one entry per debate,
speakers with a short excerpt each) and fills "Questions"; a Coverage line
says how many reports and speeches were read. Guard against long transcripts:
a speech is matched passage by passage in its own words (tier 1 in the
passage, or tier 2 when the debate's title is tier 1); a sitting is never
matched whole; the chair is never stored. Built: Netherlands (Handelingen,
Kamervragen), Switzerland (Bulletin, per-language lists), Austria (speeches
from the provisional protocol), France (comptes rendus, QE and QAG), Belgium
(Integraal Verslag), Poland (interpellations, written questions), Portugal
(perguntas and requerimentos), Brazil (requerimentos de informação). Not
built, with the reason in each scope doc's phase list: Polish transcripts,
Brazilian speeches, Italy (the Senate's SPARQL refuses us, 403), Spain
(dissolved until 23 December), Croatia and Slovakia debates, Belgian written
questions. The first Mini run of each step reads from 1 September 2026.

### 6. Later phases already approved (in each scope doc's phase list)
Set A BUILT 10 October 2026 (branch `parity-phases-a`; each scope doc's
"as built" section): French Senate (FR5), Eerste Kamer via web pages (NL4),
Slovak bill documents (SK6), Swiss Italian texts (CH6), Italy's official
Camera service (IT2). Still to build: Uruguay vote totals from Diario PDFs
(UY5), Bolivian written questions (BO4), constitutional courts (X8: CO, EC, PT, PE, GT), OCR with Tesseract on
the Mini (X7: PE scans, HR opposition bills, CO Gazette), regions and
Landtage after national (IT3, AT6, PE4).

**Set B, built 10 October 2026 (branch `parity-phases-b`):** X8
constitutional courts for Colombia (the exhortations file; the Court's
press releases are behind a keyed API and are not read), Ecuador (the
Court's WordPress API), Peru (the Tribunal's press notes, at its 30 s
Crawl-delay) and Portugal (acórdãos, 30 s apart, ten a week), into
`<cc>_rulings` (`src/courts.py`) and the Latam edition and the Portuguese
edition; Guatemala's court is a recorded gap (GT5). UY5 Diario vote totals
(`tools/uy_diario.py`), BO4 written questions (`tools/bo_questions.py`),
X7 OCR designed and guarded (`src/ocr.py`, `tools/pe_ocr.py`; install steps in
`docs/mac-mini.md`, nothing installed). One hand-run backfill after merge:
`jobs/latam-courts-backfill.sh`. Samples: `editions/latam-monitor-2026-06-30.md`,
`editions/latam-monitor-2025-08-31.md`, `editions/pt-monitor-2023-02-05.md`.

### 7. Campaign tools
Debate packs, campaign briefs (`docs/brief-builder`), campaign targets: only
once 5CA exists for a country, and only where CitizenGO runs campaigns there.

**Debate packs built 10 October 2026 (branch `camp-debate-packs`).**
`tools/country_debate_pack.py --country cc --date D --find WORDS | --item KEY`
(src/country_debatepack.py) assembles one upcoming or recent debate on our
ground for the 15 own-edition and 11 collected Latam countries: the item and
bill, the agenda slot, the votes on the bill and topic, likely speakers
(`--speakers`), members to watch, every member's record and profile link, and
the campaigner checklist, in the country's language (src/debatepack_i18n.py).
Manual, no job. Placements only from confirmed readings: until a signer
confirms, every pack renders "awaiting sign-off". Usage in each scope doc and
docs/debate-pack-social.md, "New countries".

**Debate today and the live read built 10 October 2026 (branch
`camp-live-debate`).** `tools/country_debate_today.py` and
`tools/country_live_debate.py` (src/country_live.py), the UK pair generalised,
for the countries whose chamber source publishes the day's speeches the same
day, measured on the live sources: the Netherlands (Handelingen, 2.5 to 3
hours behind, re-issued all day), Switzerland (the Bulletin, during the
sitting by the Parliament's account; to confirm in the Wintersession),
France (each sitting's compte rendu the same night) and Belgium (the
Thursday record the same evening). Not Austria (speech files the next day or
later), nor Poland, Brazil, Portugal (questions only) or any country without
a speech collector. The day is read by each country's own collector into an
in-memory store; the real store is only read. The live read sets each
speaker's words beside their votes on the area and names a contradiction
only when the vote's reading is CONFIRMED and the words have been read by a
person or the session judge (`--queue-out` / `--reads`); until then
"awaiting sign-off". Debate today is STEP 1B of the existing 16:45 net task
(`ops/scheduled-tasks/debate-day-net.md`): recreate that task from the file.
Table and usage: docs/debate-pack-social.md, "New countries".

## Blocked, waiting on replies (letters drafted in Chris's Gmail)

| Country | Blocker | Route |
|---|---|---|
| Hungary bills and votes | parlament.hu CAPTCHA | W-API token (email drafted to api-reg2@parlament.hu); karzat covers 9 May to 28 Aug |
| Spain Senate | 403 everywhere | email to Senado open data (address to find) |
| Costa Rica | refuses all foreign connections | email to the Asamblea |
| Paraguay | SILpy robots.txt disallows | email to the Senate (addresses from 2016) |
| El Salvador missing votes | unpublished sessions 41-64, 98 | information request (address to find) |
| Guatemala court | bot challenge | email (address to find) |
| Uruguay main site | 403 from laptop, GitHub and the Mini (10 Oct) | write to the open-data team |
| Argentina Diputados votes | no connection from anywhere (Mini 10 Oct) | write to HCDN or ask an Argentine contact |
| meineabgeordneten.at | licence | email drafted |

## Rules to keep (learned the hard way)

- Never solve or bypass CAPTCHAs or bot checks; respect robots.txt; never use
  credentials found in a site's code (Ecuador portal, DR Senate, Peru's
  encrypted endpoint: PE2 left out).
- Never hand-edit generated taxonomy YAML; edit `docs/keyword-taxonomy-*.md`
  and regenerate. `taxonomy-qc` stays unchanged for Belgium and Switzerland.
- AI judge: the paid API judge stays off (X16); the free session judge runs
  on the Mini under the work account's plan, capped at about 100 items a week.
- Never dispatch store-writing GitHub workflows from the laptop (they lose the
  publish race to Mini jobs). One store-writing Mini job at a time.
- Guatemala and Mexico run on GitHub, fortnightly (alternate ISO weeks).
- New Mini jobs: add them to `ops/install_country_jobs.sh` and rerun it on the
  Mini (`cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh`).
- Ownership: the 30 new countries and Latam were this session's; US, IE, AU,
  Canada, devolved, EU, DE and UN belong to the Ireland/Australia session.

## Reaching the Mini

The Mini's Claude sessions run on the work account. A personal-account session
reaches the Mini only by SSH with the `parl_mini` key (approved by Chris on 10
October). A work-account session on the Mini can run Mini steps directly.
