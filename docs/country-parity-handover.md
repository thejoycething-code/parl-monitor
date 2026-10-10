# Country editions: parity plan and handover (updated 10 October 2026)

Written by the personal-account Claude session that built the 30 new
countries and their parity layers (9-10 October 2026), for Chris's
work-account Claude to take over. Everything it built is merged to main.
Read this with `docs/country-decisions-2026-10-10.md` (Chris's signed-off
decisions, the spec) and each `docs/<country>-scope.md` (sources, quirks,
phase lists, "Waiting on Chris"). The Mini runbook is `docs/mac-mini.md`.

## Start here: where things stand

**Built and merged (PRs on thejoycething-code/parl-monitor):** collectors and
weekly jobs for 30 countries (#14), Brazil areas 14-15 (#17), Latam monitor
and alerts (#19, noise filters #23), Mini install script (#20), the edition
framework and 14 own editions (#47, #49, #50, #52, fixes #55), Hungary gazette
and karzat backfill (#57, #58), free session judge (#60), 5CA with sign-off
(#65, France scope #77), week ahead (#66), member profiles (#67), 5CA tracker
and partner sheet (#68), campaign targets (#69), constitutional courts, UY5,
BO4, OCR stub (#70), debate packs (#71), later phases set A (#72), debates and
questions (#73), campaign briefs (#74, English per rule 6 #75), same-day vote
briefs (#76), debate today and live read (#78), taxonomy noise round (#79),
small fixes (#80).

**Nothing is published from a 5CA yet.** Every stance is a draft: 975
readings await sign-off across the countries (France limited to final votes
and watched amendments). Briefs, packs, targets, the partner sheet and the
live read all render "awaiting sign-off" until a named person confirms.

**Waiting on Chris (decisions and actions):**

1. Name a signer per country in `config/stance_signers.yaml` (country teams
   are the natural owners), then start confirming readings
   (`docs/5ca-<cc>-readings.md`, `tools/country_5ca.py --cc CC --sign-from-doc --by NAME`).
2. Review the flagged bill directions in the stance files (Belgium's
   religious-symbol bans read as against us while CitizenGO supports
   Portugal's face-covering law; IVF; the euthanasia referendum).
3. Check France's five aide a mourir decrees in `config/watchlist-fr.yaml`
   against the promulgated law (drafted from the first-reading text).
4. Check the Looker list prefix per country before the first petition export
   (`docs/campaign-benchmarks.md`; the prefixes are guesses).
5. Send the parliament emails drafted in his Gmail (three still lack an
   address): Hungary W-API token, Spain Senado, Costa Rica, Paraguay, El
   Salvador missing votes, Guatemala court, meineabgeordneten.at.
6. Update the work account's **debate-day-net** scheduled task from
   `ops/scheduled-tasks/debate-day-net.md` (adds STEP 1B, debate today for
   NL, CH, FR, BE). It lives on the work account, not the personal one.
7. Whether the Dutch edition (votes only, NL3) should show the week ahead.
8. Whether the one watched Dutch motion in dossier 21501-02 (the rainbow-flag
   motion, zaak 2026Z21728) should stay watched.

**Still to run on the Mini (store writers, one at a time):**

- `latam-courts-backfill` (about 25 minutes; queued on 10 October behind the
  weeklies as the one-shot launchd job `net.citizengo.parlmonitor.oneshot-courts`;
  check `~/runner/logs/latam-courts-backfill.log`, then
  `launchctl bootout gui/$(id -u)/net.citizengo.parlmonitor.oneshot-courts`).
- `sk-docs-backfill`, three runs of about 55 minutes, never on a Tuesday
  morning (docs/mac-mini.md).
- Install Tesseract when wanted (X7; steps in docs/mac-mini.md) to switch on
  the OCR steps.
- Check the first `vote-briefs-daily` log: can the Mini reach `dati.senato.it`
  (it refuses the laptop)?
- The first Sunday 16:45 run of `editions-session-judge` (Claude Code on the
  Mini is signed in to the work account; over SSH it reports "Not logged in"
  because the keychain is locked for SSH, which is expected).

**What could come next (not started):** regions and Länder (IT3, AT6, PE4,
Spain's autonomous communities, Mexico's states); Croatia and Slovakia
debates; Polish transcripts when the Sejm endpoint answers; Brazilian
speeches (cost); Belgian, Portuguese, Slovak, Hungarian and Mexican agendas;
committees and petitions; Africa (Kenya, Nigeria, Uganda: Chris's aim is Q1
2027); a native read of each language's term list.

## What exists now

| Layer | UK | DE | US / IE / AU | CA | New countries |
|---|---|---|---|---|---|
| Collector (bills, votes, members) | yes | yes | yes | yes | yes, 25 countries (see below) |
| Weekly edition, Slack DM to Chris | yes | yes | yes | yes | 14 own editions + Hungary gazette edition + one monthly Latam edition |
| Triage | API judge | API judge | API or session judge | session judge (provinces) | free session judge, Sundays 16:45 (`tools/edition_judge.py`) |
| Noise filters, mute lists | yes | partly | yes | yes | yes (`src/noise.py`, `config/edition-noise-<cc>.yaml`) |
| Same-day vote briefs (division watch) | yes | no | yes (`*_division_brief.py`, `src/vote_brief.py`) | no | yes, 20 countries (`src/country_vote_brief.py`): daily for NL, PL, CH, BR, IT; after the weekly for the rest |
| 5CA (member stance, five columns) | yes | yes | yes | yes | **built** 10 Oct (`tools/country_5ca.py`, branch `parity-5ca`): sheets from confirmed readings only, none confirmed yet; AT/PT/NL rows derived (X5). Tracker and partner sheet built 10 Oct (`tools/make_country_5ca_web.py`, branch `camp-5ca-sheets`): `docs/5ca-countries.html` weekly, "awaiting sign-off: N readings" per country; partner page gated until a country has a confirmed placement |
| Stance sign-off per vote (`config/*_stance.yaml`) | yes | yes | yes | yes | **built** 10 Oct (#65): 975 readings awaiting sign-off after France was limited to final votes and watched amendments (#77), weekly digest DM; signers per country to name (`config/stance_signers.yaml`) |
| Campaign targets and outcomes (`ca_campaign.py`, the 5CA Evaluate) | yes | no | no | no | **built** 10 Oct (`tools/country_campaign.py`, branch `camp-targets`): open, targets, add, find, outcome, score; targets from confirmed readings only, candidates by vote record until then; petition numbers none yet (UK only) |
| Member profiles | yes | yes | US yes | no | yes, 23 countries (`profiles/<cc>/`, weekly step; X5 derived and X6 as-listed labelled; HR and CL party history sourced), branch `parity-profiles` |
| Debates / speeches | yes | yes | IE, AU | yes | NL, CH, AT, FR, BE (10 Oct, `tools/<cc>_chamber.py`); not PL (transcripts never answered), BR (per-deputy cost), IT (Senate 403), ES (dissolved), PT (questions only), HR, SK |
| Parliamentary questions | yes | no | IE | no | NL, PL, FR, PT, BR requests (10 Oct, `tools/<cc>_chamber.py`); already in the editions: SK interpellations, AT J/AB, CH Vorstösse, HU, UY pedidos, HN press, BO written questions: BO4, built 10 Oct, `parity-phases-b` |
| Committees, courts, petitions, consultations | yes | yes | US courts | yes | constitutional courts (X8) built for CO, EC, PE, PT (10 Oct, `parity-phases-b`); GT gap; no committees or petitions |
| Week ahead / agenda | yes | yes | yes | no | yes for NL, PL, CH, BR, IT (Camera), FR, AT, ES (fills from 23 Dec), AR (Senate), HR; not BE, PT, SK, HU, MX or Latam (item 4) |
| Debate packs, campaign briefs, campaign targets | yes | yes | no | yes | debate packs **built** 10 Oct (`tools/country_debate_pack.py`, manual, 26 countries; placements from confirmed readings only, none yet); campaign briefs **built** 10 Oct (`tools/country_briefs.py`, a weekly step): drafts in English per rulebook rule 6 (#75), NOT READY until stances are confirmed; targets **built** (#69) |
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

### 1. Same-day vote briefs (cheapest win) -- BUILT 10 October 2026

Branch `parity-vote-briefs`: `src/country_vote_brief.py` (shared, from the
editions' and the Latam monitor's own readers), `src/vote_brief_sources.py`
(the daily direct readers), `tools/country_vote_briefs.py`, a step in each
country's weekly job and one daily Mini job (`jobs/vote-briefs-daily.sh`);
see docs/mac-mini.md, "Vote briefs for the new countries", and the samples
in `docs/vote-brief-samples/`. The plan as written:

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
Camera service (IT2). Set B below covers UY5, BO4, X8 and X7. Still to
build: regions and Landtage after national (IT3, AT6, PE4).

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

**Campaign targets and outcomes built 10 October 2026 (branch `camp-targets`;
docs/5ca-notes.md, "Campaign targets and outcomes for the new countries").**
`tools/country_campaign.py` (src/country_campaign.py) is `ca_campaign.py` for
every country in `src/country5ca.COUNTRIES`: open a campaign on an area in a
chamber (a snapshot of the confirmed-only 5CA), suggest targets (`+`, `-`,
mixed confirmed records), add targets by name (`--by`), find and record the
outcome vote with our side, score it. Before sign-off it suggests nobody and
lists candidates by vote record, each "not a target until the stance is
confirmed". Petition performance joins from `data/looker/<cc>_campaigns.tsv`
(the UK export's shape); no country has one yet, and the command says so.
Manual only, no job. Still open: Chris to pull the first country export from
Looker (the list prefix per country is a guess: `PL`, `IT`, ...).

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
(`ops/scheduled-tasks/debate-day-net.md`): the task lives on Chris's work
account; update it from the file.
Table and usage: docs/debate-pack-social.md, "New countries".

**Campaign briefs built 10 October 2026 (branch `camp-briefs`).**
`tools/country_briefs.py` (`src/country_briefs.py`, phrases in
`src/brief_phrases.py`, lists and languages in `config/country-briefs.yaml`)
drafts an RF4 brief per watched or tier-1 bill that moved in the last 90 days,
in every new country with a collector (the fourteen own editions and eleven
Latam countries), as a step of its weekly job. Facts from the store only, no
AI call; every cell the record cannot fill is a `[CAMPAIGNER: ...]` line. The
ask, the 5CA, the targets and the segment split come from CONFIRMED stances
only, so every brief is NOT READY until its bill's direction
(`--confirm-direction`, new in `tools/country_5ca.py`) and every reading of
its votes are confirmed. Unedited briefs refresh weekly; edited ones are left
alone. Language: English, per rulebook rule 6 (Chris, 10 October 2026; #75).
Open: the framing glossary, the allies and opponents registers and Bluebook
access.

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
- Guatemala and Mexico run on GitHub, fortnightly (alternate ISO weeks), as
  their sites refuse UK connections (the Mini included).
- Member-level claims: non-attached members are never counted as breaking
  from a group (#80); party at the vote needs history (X6) or a label.
- New Mini jobs: add them to `ops/install_country_jobs.sh` and rerun it on the
  Mini (`cd ~/runner/parl-monitor && git pull --ff-only && bash ops/install_country_jobs.sh`).
- Ownership: the 30 new countries and Latam were this session's; US, IE, AU,
  Canada, devolved, EU, DE and UN belong to the Ireland/Australia session.

## Reaching the Mini

The Mini's Claude sessions run on the work account, so a personal-account
session cannot message them. From the laptop the Mini is reachable by SSH
with the `parl_mini` key (Chris approved, 10 October):
`ssh -i ~/.ssh/parl_mini -o IdentitiesOnly=yes christopherjoyce@christophers-mac-mini.local`.

- **Do not start `mini_run.sh` over plain SSH:** `gh` reads its login from
  the keychain, which SSH cannot open, so the job fails at "mark running"
  (HTTP 401). Run hand jobs as a one-shot launchd job instead: write a plist
  to /tmp with `RunAtLoad` true and `KeepAlive` false, `launchctl bootstrap
  gui/$(id -u) <plist>`, then `launchctl bootout` it when done.
- Over SSH, `claude` and `gh` live in `~/.local/bin`.
- Installing a new plist: `ops/install_country_jobs.sh` (idempotent), or copy
  one plist from `git show origin/main:ops/launchd/<label>.plist` and
  bootstrap it, without pulling the runner clone while jobs are running.
- A work-account session on the Mini can run Mini steps directly.
