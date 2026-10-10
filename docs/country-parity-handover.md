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
| 5CA (member stance, five columns) | yes | yes | yes | yes | **no** |
| Stance sign-off per vote (`config/*_stance.yaml`) | yes | yes | yes | yes | **no** |
| Member profiles | yes | yes | US yes | no | yes, 23 countries (`profiles/<cc>/`, weekly step; X5 derived and X6 as-listed labelled; HR and CL party history sourced), branch `parity-profiles` |
| Debates / speeches | yes | yes | IE, AU | yes | **no** |
| Parliamentary questions | yes | no | IE | no | only where collected (SK interpellations, UY pedidos, HN press) |
| Week ahead / agenda | yes | yes | yes | no | partial (HR, BE; framework supports it) |
| Committees, courts, petitions, consultations | yes | yes | US courts | yes | **no** (courts approved as a later phase, X8) |
| Debate packs, campaign briefs, campaign targets | yes | yes | no | yes | **no** |
| Regional / state parliaments | devolved | Länder (part) | US states (in progress) | provinces | **no** (later, per decisions) |

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

### 5. Debates, speeches, questions
Per country where the source is open: NL Handelingen, PL transcripts (the
endpoint timed out on 9 October), AT Stenographische Protokolle, CH, FR, IT
Senate, BR. Written questions where cheap (BR, PL interpellations, FR).

### 6. Later phases already approved (in each scope doc's phase list)
French Senate (FR5), Eerste Kamer via web pages (NL4), Slovak bill documents
(SK6), Uruguay vote totals from Diario PDFs (UY5), Bolivian written questions
(BO4), constitutional courts (X8: CO, EC, PT, PE, GT), OCR with Tesseract on
the Mini (X7: PE scans, HR opposition bills, CO Gazette), Swiss Italian texts
(CH6), Italy's official Camera service as backup (IT2), regions and
Landtage after national (IT3, AT6, PE4).

### 7. Campaign tools
Debate packs, campaign briefs (`docs/brief-builder`), campaign targets: only
once 5CA exists for a country, and only where CitizenGO runs campaigns there.

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
