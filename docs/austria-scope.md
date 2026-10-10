# Austria: scoping the Nationalrat and Bundesrat monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (honest
UA, one request a second to the Parliament's host). Every number below was
measured, not estimated. Raw replies are archived under
`data/raw/2026-10-09/` (`at_probe_*` for the probes, `at-rollcalls_*` for the
collector's first run); the archive is gitignored and was NOT pushed to the
`raw-archive` release from this branch. National Parliament only; the nine
Landtage are listed at the end and are a later decision.

## Decisions already taken (Christopher, before this work)

- **Own edition**, delivered to Christopher alone (Slack DM), like the US.
- **Shared taxonomy.** `config/taxonomy-de.yaml` is used unchanged. No
  taxonomy file was edited. Austria-specific terms are PROPOSED below for
  Christopher to accept or refuse; Switzerland is being scoped in parallel
  and also reads German, so whatever is accepted should suit both.
- **National Parliament first**, Landtage later.
- **Mac Mini first, GitHub Actions as backup**, no new paid services, never
  post publicly anywhere.

## The finding that shapes everything

**Austria publishes its whole parliamentary record as keyless open data, but
it records votes by Klub, not by member.** The Nationalrat and the Bundesrat
vote by standing up. The record says which Klubs (Fraktionen in the
Bundesrat) were for and against: "Dafür: FPÖ, dagegen: ÖVP, SPÖ, NEOS,
GRÜNE". Members' names appear only in a *namentliche Abstimmung*, and there
were **5 in the Nationalrat in the whole XXVIII. Gesetzgebungsperiode** (24
October 2024 to date): the Waffengesetz, party financing, the Preisgesetz,
the Günstiger-Strom-Gesetz and the state-protection law. None of the five is
on our ground.

So the Austrian equivalent of a member's voting record is the Klub's record,
plus the rare named vote. Party discipline is close to total, so for 5CA
purposes the Klub position is the member's position unless a namentliche
Abstimmung says otherwise. That is a design decision for Christopher (see
"Waiting on Chris").

**The second finding: taxonomy-de catches about half of Austria's ground.**
Run on titles, it found 43 Nationalrat bills and motions on our ground in
XXVIII; with the Austrian terms proposed below, 90. The misses are Austrian
words for things the German list knows in German German: *Sterbeverfügung*
(Austria's assisted-suicide law), *LGBTIQ* (Germany writes LSBTIQ),
*intergeschlechtlich*, *eingetragene Partnerschaft*, *Gesichtsverhüllung*,
*Hass im Netz*. Details under "Taxonomy".

## What Austria publishes

Everything below is on `www.parlament.gv.at`, served by nginx, licensed
**CC BY 4.0** (25 datasets; statements on draft bills, *Stellungnahmen*, are
expressly excluded from the licence). **No key, no login, no rate-limit
headers, no Crawl-delay for our UA in robots.txt.** data.gv.at lists the
same 25 datasets and points back here (731 hits for "parlament" on its hub
search API; the old CKAN endpoint `/katalog/api/3/...` now returns 404).

### Gegenstände (bills, motions, questions, reports): WORKS TODAY

`POST https://www.parlament.gv.at/Filter/api/filter/data/101?js=eval&showAll=true`
with a JSON body of dimensions, e.g. `{"NRBR": ["NR"], "GP_CODE": ["XXVIII"]}`.

- **One request returns every item of a period for one chamber.** Nationalrat
  XXVIII: **24,735 rows in 15.4 s**, 1.6 MB gzipped. Bundesrat XXVIII: 1,319
  rows in 2.6 s. Nationalrat XXVII (2019 to 2024): 70,953 rows in 106 s,
  4.4 MB gzipped. No paging needed; `showAll=true` returns everything.
- Each row: period, type (`ITYP`, `Art`), number, title (`Betreff`),
  citation, status 1 to 5, date of the latest step, date received, introducers
  (PAD IDs) and their Klubs, the Parliament's Themen, Schlagworte and EuroVoc,
  and **for laws the third-reading vote by Klub**: `"Dafür: F, V, S, N,
  Dagegen: G"` (195 items in XXVIII carry one; the 5 named votes carry the
  totals, "abgegebene Stimmen: 171; davon Ja-Stimmen: 121, Nein-Stimmen: 50").
- What the 24,735 Nationalrat rows are: 7,202 written questions (J), 6,465 EU
  documents, 6,173 answers (AB), 881 selbständige Entschließungsanträge,
  484 committee reports, 223 unselbständige Entschließungsanträge, 211
  Beschlüsse, 174 Gesetzesanträge, 127 Regierungsvorlagen, and procedure.
- **Quirks.** The body must name the chamber (`NRBR`) or it returns nothing
  useful. The column labels arrive in a `header` array; the collector checks
  them and records a gap if one is renamed, rather than reading by position.
  Bundesrat items live under `/gegenstand/BR/...` although the row says
  `XXVIII`. The Nationalrat's Beschluss (`BNR`) appears in BOTH lists under
  the Nationalrat's key: one item, not two. Dates come as `dd.mm.yyyy`.

### History pages, where every vote is: WORKS TODAY

`GET https://www.parlament.gv.at/gegenstand/XXVIII/I/525?json=TRUE` (any
item path plus `?json=TRUE`). 1 to 8 KB gzipped each.

- **Every vote taken on the item is a stage**, in committee and in both
  plenaries, with the Klubs for and against:
  `"81. Sitzung des Nationalrates: Abstimmung: Antrag, den ablehnenden
  Ausschussbericht zur Kenntnis zu nehmen: <b>angenommen</b><br>Dafür: ÖVP,
  SPÖ, NEOS, GRÜNE, dagegen: FPÖ"`. Plenary votes carry a link to the exact
  passage of the Stenographisches Protokoll (`#121.2`), a stable anchor.
- **Two shapes.** Items with a procedure carry `content.phase[].stages`; an
  unselbständiger Entschließungsantrag carries `content.stages` directly. A
  parser that knows only one sees no votes on the other.
- Committee votes are recorded too (Justizausschuss, Gleichbehandlungs-
  ausschuss, Ausschuss für Arbeit und Soziales), but with no protocol anchor.
- Long title (`description`), names with PAD and Klub, documents, the
  Parlamentskorrespondenz, and for Regierungsvorlagen since XXVI a summary
  (`shortinfo`).
- **robots.txt disallows a few hundred individual pages** by path (privacy
  takedowns: `/gegenstand/XXVIII/SN/501`, `/person/30969`, ...). The
  collector checks each path and skips a disallowed one; none on our ground
  were disallowed on 9 October.

### Members: WORKS TODAY

- Nationalrat: `POST .../Filter/api/json/post?jsMode=EVAL&FBEZ=WFW_002&listeId=10002&showAll=true`,
  **183 rows** (the full house).
- Bundesrat: `...FBEZ=WFW_005&listeId=10005...`, **60 rows**: ÖVP 22,
  SPÖ 18, FPÖ 16, ohne Fraktion 4.
- **Quirk:** both return nothing for an empty body or `{"FR": ["ALLE"]}`;
  `{"M": ["M"], "W": ["W"]}` (both sexes) returns everyone.
- PAD, name, Klub (inside a `<span>` tooltip), Wahlkreis, Bundesland.
- Every parliamentarian since 1918: `FBEZ=WFW_008&listeId=10008` (documented,
  not probed).

### Sittings, agenda, protocols: WORKS TODAY

- Plenarsitzungen (`FBEZ=WFP_007&listeId=11070`): **108 Nationalrat sittings
  listed for XXVIII** (to the 104th on 15 October 2026, scheduled ones
  included), **74 Bundesrat sittings** since the 971st on 3 October 2024.
- Termine (`/Filter/api/filter/data/600`, body
  `{"GREMIUM": ["Nationalrat"], "DATERANGE": ["2026-10-01", "2026-10-31"]}`):
  **44 entries for October 2026** (plenaries and committee meetings, each
  with its agenda link). This is the week-ahead source.
- Stenographische Protokolle (`/Filter/api/filter/data/211`): 100 rows for
  XXVIII (possibly a cap; not checked). Each protocol is one HTML file: the
  41st sitting is 2.0 MB, 3.3 s.
- Sitting history page (`/gegenstand/XXVIII/NRSITZ/41?json=TRUE`): the
  debates and timeline of the day.

### Namentliche Abstimmungen: member names in the protocol only

The history page says a named vote happened and gives the totals. The names
are in the protocol at the vote's anchor, by surname, with a first name only
where two members share one: *"Mit „Ja" stimmten die Abgeordneten: Auer,
Auinger-Oberzaucher; Baumann, ..."*. Mapping those to PADs means matching
surnames against the sitting members (183, so feasible, with the
first-name disambiguation the protocol already prints). Phase 1b; rare
enough (5 in two years) that it can wait.

### Parliamentary questions: WORKS TODAY

Written questions (J, 7,202 in XXVIII) and answers (AB, 6,173) are in the
same Gegenstände list, with the asker's PAD and Klub. Taxonomy-de puts 104
questions on our ground; with the proposed terms, 265. Answers are linked
from the question ("beantwortet durch 595/AB"). The collector stores them
but reads no history page for them (they are never voted on).

### Ministerialentwürfe (consultation drafts): history pages only

Government drafts sent out for Begutachtung live at `/gegenstand/XXVIII/ME/<n>`
and their history pages answer (`1/ME`, `50/ME` probed). **The Open Data list
does not return them** with any body tried (`VHG: ME`, `DOKTYP: MEG`); the web
filter at `/recherchieren/gegenstaende/ministerialentwuerfe/` must use another
list ID, readable from its Export dialog in a browser. Worth finding: the
Begutachtung is when CitizenGO can still submit a Stellungnahme, before a
bill reaches the Nationalrat. Note that Stellungnahmen themselves are
excluded from the CC BY licence.

### Not probed

Parlamentskorrespondenz (the Parliament's press service, a dataset since
1997), Petitionen and Bürgerinitiativen details, Ausschüsse and their
memberships, the EU committee statements, and the RIS (`ris.bka.gv.at`,
the federal law gazette, which has its own OGD API).

### meineabgeordneten.at: profiles, no votes, licence needed

The Austrian counterpart of abgeordnetenwatch (which covers only Germany and
the EU Parliament: 18 parliaments, none Austrian, measured). **No API**, no
votes; 830 dossiers on politicians' side jobs, company and association
roles and income bands, each fact sourced. robots.txt allows everything, but
the site states that use of its data needs a licence agreement
(office@meineabgeordneten.at). Useful context for member profiles later; not
to be scraped without that agreement.

## Phase 1: built, 9 October 2026

`tools/at_rollcalls.py` into `at_members`, `at_items`, `at_divisions` and
`at_votes` (schema in `src/at_store.py`, declared in `db.TABLES`). Live run
into a scratch database, not the store:

| | Read | On our ground |
|---|---|---|
| Nationalrat items, XXVIII (EU documents dropped) | 18,055 of 24,735 | 259 |
| Bundesrat items, XXVIII | 1,319 | 15 |
| Items stored (BNR shared by both lists) | 19,176 | 271 |
| ... of which bills and motions (not questions or answers) | | 85 |
| History pages read | 85 | |
| Votes found on those pages | 49 | 49 |
| Klub positions | 240 | |
| Members (Nationalrat 183, Bundesrat 60) | 243 | |

Two minutes forty seconds, no gaps. 17 items carry a
`config/watchlist-at.yaml` entry; taxonomy-de matched none of them.

- **One list request per chamber, every week**, re-reads everything; an
  item's history page is read again only when the list's date for it moves.
- **What a vote is.** A stage with "angenommen" or "abgelehnt" AND Klub
  positions, "Einstimmig", or a namentliche Abstimmung. "Antrag auf Einholung
  einer Stellungnahme ... angenommen", with no Klubs named, is procedure and
  is left out.
- **Division keys.** A plenary vote is keyed on its protocol anchor:
  `XXVIII/I/525@XXVIII/NRSITZ/87#210`. Second and third readings can share an
  anchor, so the second is `#210+2`, in page order. A committee vote has no
  anchor: `XXVIII/I/567@Justizausschuss/2026-06-30#1`.
- **One floor vote can sit on several items.** The Sterbeverfügung amendment
  vote appears on the Regierungsvorlage, on its committee report and on the
  Abänderungsantrag, because each item's page records it. An edition should
  fold them by (sitting, anchor).
- **Votes carry their item's areas.** The vote stages carry no subject text
  of their own beyond the item.
- **Classification is on titles only**, with taxonomy-de unchanged plus the
  watchlist by key. The Parliament's Schlagworte are stored but not matched:
  its tag "Familienpolitik" is a tier-1 taxonomy-de term and put 49 bills
  and motions into area 9 where titles put 3 (measured).
- **Scheduled** by `jobs/at-weekly.sh` on the Mac Mini (Saturdays 03:00
  London, `ops/launchd/net.citizengo.parlmonitor.at-weekly.plist`) with
  `.github/workflows/at-weekly.yml` as backup (Saturdays 03:00 and 05:00 UTC,
  gated by `mini-check.yml` with job `AT_WEEKLY`). Nothing is live until the
  branch is merged and the plist installed.
- **Tests:** `tests/test_at_rollcalls.py`, 23 tests on real replies trimmed
  into `tests/fixtures/at/`.

### What it found on our ground (samples)

- **Sterbeverfügungsgesetz-Novelle 2026** (XXVIII/I/525): passed on 7 July
  2026, Dafür FPÖ, ÖVP, SPÖ, NEOS; dagegen GRÜNE. No Bundesrat objection on
  15 July. Invisible to taxonomy-de; on our ground through the watchlist.
- **Schutz des Frauensports** (XXVIII/UEA/139, A/506, A/507): FPÖ motions,
  rejected by all other Klubs.
- **Wirksame Schutzzonen vor Abtreibungsgegner:innen** (XXVIII/UEA/177),
  rejected on 26 March 2026.
- **Konversionsmaßnahmen-Schutz-Gesetz** (XXVIII/A/295, 296, 923): a Greens
  motion to set the committee a deadline was rejected on 11 June 2026.
- **Schluss mit Gender-Ideologie an Schulen!** (XXVIII/A/504): the committee's
  rejection was noted on 7 July 2026, FPÖ against.
- Telemedical abortion (A/449, A/526), abortion out of the criminal code
  (A/452), abortion as an EU fundamental right (A/516), the Kopftuchverbot
  motions, chat control, the Fortpflanzungsmedizingesetz (A/496, A/497).

## Taxonomy: how well taxonomy-de reads Austria

`config/taxonomy-de.yaml` (v0.6), unchanged, on item titles. "On our ground"
means any area other than 11 (migration is collated, never campaigned).

| Text matched | Items | On our ground |
|---|---|---|
| XXVIII bills and motions*, titles | 2,000 | 43 |
| XXVIII bills and motions, titles + Schlagworte + EuroVoc | 1,789** | 85 (49 of them area 9 via "Familienpolitik") |
| XXVIII written questions, titles | 7,228 | 104 |
| XXVII bills and motions, titles | 8,446 | 143 |
| XXVII written questions, titles | 19,611 | 189 |

\* RV, A, A(E), UEA, AEA, BUA, BRA, AA, E, BI, PET, AUA, BNR. \*\* the first
cut, without AA and BNR.

On our ground by area (XXVIII bills and motions, titles): abortion 7, sex-based
rights 7, free speech 8, religion 8, conversion practices 4, marriage and
family 3, parental rights 2, surrogacy 2, organ donation 2. **Assisted dying
0**, although Austria amended its assisted-suicide law this year.

### What it misses: Austrian words, measured

Searched in Nationalrat XXVIII titles and Schlagworte (EU documents
excluded); "missed" means taxonomy-de matched nothing on the title.

| Word | Items | Missed |
|---|---|---|
| Sterbeverfügung | 6 | 6 |
| LGBT(IQ) | 84 | 83 |
| Gender | 67 | 67 |
| Pride | 63 | 63 |
| Personenstand | 50 | 42 |
| Kinderschutz | 32 | 32 |
| Gesichtsverhüllung / Verhüllung | 12 | 12 |
| Obsorge | 12 | 12 |
| Eingetragene Partnerschaft / Ehe | 6 | 6 |
| intergeschlechtlich | 4 | 4 |
| Hass im Netz | 1 | 1 |
| Fristenlösung | 0 | 0 |

Austria never wrote "Fristenlösung" in a title in either period; abortion
items say "Schwangerschaftsabbruch", which taxonomy-de catches (31 of 31).

### Proposed Austrian additions (for Christopher; NOT applied)

Tried in a scratch copy of the taxonomy, never in the repo. Each count is
items newly on our ground on titles, as
[XXVIII bills and motions / XXVIII questions / XXVII bills and motions /
XXVII questions]. Where a row names several terms the counts are summed, so
an item matching two of them counts twice; the totals after the table are
counted by item.

| Area | Tier | Term | Gain | Note |
|---|---|---|---|---|
| 1 | 1 | `Fristenlösung*` | 0/0/0/0 | the statutory name; expected in speeches and long titles, not in Betreffs |
| 2 | 1 | `Sterbeverfügung*` | 4/0/3/1 | the law itself (2021) and its 2026 amendment |
| 2 | 1 | `StVfG` | 3/0/0/0 | its abbreviation, all-caps, case-sensitive |
| 3 | 1 | `Geschlechtsumwandlung*` | 0/4/0/2 | FPÖ wording on minors |
| 3 | 2 | `intergeschlechtlich*`, guarded (Kind, Jugendliche, Behandlung, medizinisch) | in the 5 row | operations on intersex children |
| 5 | 1 | `Genderideologie*`, `Gender-Ideologie*` | 2/0/1/0 | |
| 5 | 1 | `biologische* Geschlecht*` | 1/6/2/2 | taxonomy-de has the singular only; Austria writes "zwei biologischen Geschlechter" |
| 5 | 1 | `Transgender*` | 0/1/2/4 | |
| 5 | 2 | `LGBTIQ*`, `LGBTQ*` | 4/39/31/131 | Austria's spelling; taxonomy-de has LSBTIQ |
| 5 | 2 | `intergeschlechtlich*` | 2/1/15/18 | |
| 5 | 2 | `queer*` | 0/35/1/0 | mostly FPÖ questions on queer funding |
| 5 | 2 | `Pride*`, guarded (Parade, Flagge, LGBT, queer, Kosten, Förderung) | 0/29/2/0 | questions on Pride spending; triage will want most of these low |
| 5 | 2 | `Binnen-I`, `Regenbogen*` guarded (Flagge, Parade, Fahne) | 0/1/0/2 | gendered spelling; rainbow flags on public buildings |
| 6 | 2 | `Kinderschutz*`, guarded (digital, online, Internet, Social Media, Plattform) | 2/0/1/0 | children online |
| 6 | 2 | `Ethikunterricht*` | 0/0/6/4 | Austria's compulsory ethics class beside religious education |
| 6 | 2 | `Altersverifikation*` | 0/1/0/0 | |
| 7 | 1 | `Hass im Netz` | 1/0/2/10 | Austria's 2021 online-hate package, its NetzDG |
| 7 | 1 | `Kommunikationsplattformen-Gesetz*`, `KoPl-G` | 0/0/4/1 | the law itself |
| 7 | 1 | `Bundestrojaner*`; `Messenger-Überwachung*` | 4/1/0/4; 4/3/0/0 | the state-spyware fight; the two mostly hit the same four motions |
| 7 | 2 | `Verhetzung*` | 0/3/1/0 | § 283 StGB, Austria's Volksverhetzung |
| 8 | 1 | `Gesichtsverhüllung*`, `Islamgesetz*` | 2/9/2/0 | the 2017 face-covering ban; the 2015 Islam Act |
| 8 | 2 | `politische* Islam*`, `Dokumentationsstelle Politischer Islam`, `Zwangsverschleierung*`, `Kopftuchtrend*` | 6/6/3/7 | |
| 9 | 2 | `eingetragene* Partnerschaft*` | 2/2/1/3 | Austria's civil partnership |
| 9 | 2 | `Obsorge*` | 4/3/1/6 | Austria's word for Sorgerecht (taxonomy-de has Sorgerecht) |
| 9 | 2 | `Kinderbetreuungsgeld*`, `Familienbeihilfe*`, `Familienbonus*` | 15/20/56/161 | Austria's Elterngeld, Kindergeld and child tax credit; NOISY (benefit administration), and taxonomy-de already carries the German equivalents, so it is a parity question |

Together (XXVIII bills and motions, titles): **43 to 90 on our ground**;
XXVIII questions 104 to 265; XXVII bills and motions 143 to 275; XXVII
questions 189 to 538. The largest single gains are LGBTIQ (area 5) and the
family benefits (area 9). Dropped after measuring 0 in titles across both
periods: `§ 96 StGB`, `§ 97 StGB` (abortion), `§ 78 StGB` and "Mitwirkung am
Selbstmord" (assisted suicide), `Hospiz- und Palliativfonds*`,
`Sexualdienstleist*`, `Social-Media-Verbot*`. Germany's `Trans*`
problem (taxonomy-de area 3 note) recurs: Austria writes "Trans*-Personen"
with a literal star, which no term above catches.

Until Christopher decides, `config/watchlist-at.yaml` puts the 17 most
important misses on our ground by item key (all six Sterbeverfügung items,
the two-sexes bills, intersex children, civil partnership, face covering,
Hass im Netz).

## Phases

1. **Done (this branch):** members, every item of both chambers, Klub votes
   on items on our ground, weekly on the Mini with a GitHub backup.
2. **1b:** namentliche Abstimmungen, member by member, from the protocol;
   Ministerialentwürfe (find the list ID) so drafts in Begutachtung are seen
   before they reach the Nationalrat; the week ahead from Termine. **Week ahead built 10 October 2026** (branch `parity-week-ahead`, `src/agendas/at.py`, a step of the weekly job): Termine and each Tagesordnung, d.B. and A(E) numbers as item keys, robots.txt checked per document.
3. **2:** an edition (Slack DM to Christopher, as the US), the triage judge
   on Austrian items (German prompt, as Germany's), Klub-level 5CA, speeches
   from the protocols (the debate entries on each history page already name
   speaker and Klub, with protocol anchors), the Parlamentskorrespondenz.
4. **Later:** the nine Landtage (below), meineabgeordneten.at only with a
   licence.

### The Landtage (listed, not probed)

Burgenland, Kärnten, Niederösterreich, Oberösterreich, Salzburg, Steiermark,
Tirol, Vorarlberg, Wien (the Wiener Landtag is also the Gemeinderat). Each
publishes on its own site; none was checked for open data.

## Shared files touched (13 branches will merge)

Every edit outside Austria's own files, all additions, none rewriting a line:

- `src/db.py`: 4 table names in `TABLES` (+ comment) and 2 lines in
  `init_db` calling `at_store.ensure_schema`. +8 lines.
- `tools/coverage.py`: "Austria weekly" in `PIPELINES`, three `FEEDS` rows
  (`at_items`, `at_members` 7/4; `at_divisions` 31/31), `PIPELINE_FEEDS`,
  `AWAITING_FIRST_RUN`. +16 lines.
- `.github/workflows/alert.yml`: "Austria weekly" in the watched workflows.
  +1 line.

Austria's own files: `docs/austria-scope.md`, `src/at_store.py`,
`tools/at_rollcalls.py`, `config/watchlist-at.yaml`,
`tests/test_at_rollcalls.py`, `tests/fixtures/at/`, `jobs/at-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.at-weekly.plist`,
`.github/workflows/at-weekly.yml`.

## Test suite, 9 October 2026

3,308 tests: all pass except 11 (10 errors, 1 failure) in `test_holyrood`,
`test_senedd` and `test_db_state`. The same 11 fail on a clean copy of
`origin/main` in the same environment: they need raw-archive folders and a
local store that a fresh worktree does not carry. The frozen
`data/raw/2026-08-01` fixtures were copied in from the main checkout to run
the rest; without them a further 63 fail for the same reason.

## Waiting on Chris

1. **Klub votes as the record.** Accept that an Austrian member's position is
   their Klub's (party discipline is near total), overridden by a namentliche
   Abstimmung where one exists? Without it there is no member-level 5CA in
   Austria at all.
2. **The proposed taxonomy terms** above, term by term, with Switzerland in
   mind; in particular whether the family benefits (Kinderbetreuungsgeld,
   Familienbeihilfe, Familienbonus) belong in area 9, and whether Pride and
   queer funding questions are our ground.
3. **The watchlist** (`config/watchlist-at.yaml`, 17 entries): review, or
   retire it once the terms are accepted.
4. **Merge and install.** Merge `austria` into main (the GitHub cron only
   runs from the default branch), then on the Mini
   `cp ops/launchd/net.citizengo.parlmonitor.at-weekly.plist ~/Library/LaunchAgents/`
   and `launchctl bootstrap`. Optionally an `HC_AT_WEEKLY` heartbeat URL in
   `~/runner/env`.
5. **Edition shape**: same as the US (Slack DM, own edition), and which
   phase 1b items first (named votes, Ministerialentwürfe, week ahead).
6. **meineabgeordneten.at**: ask them for a licence, or leave it.
7. **Landtage**: which first, when national is settled.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Additions approved (AT1, AT2 family benefits area 9, AT3 Pride and queer funding) and generated as the addendum `config/taxonomy-atch.yaml` (taxonomy-de plus Austria and Switzerland); the collector loads it for `at`.
- X5: `at_store.derived_member_positions()` gives each member their Klub's position, labelled derived (Klub at the latest sighting).

Later phases and items for Chris (not built at the merge):

- meineabgeordneten.at licence (AT5): a request in Chris's name.
- Phase: the Landtage after national (AT6).

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/at_stance.yaml` holds 9 bill direction(s) (Claude's drafts from the watchlist) and 19 vote reading(s): 3 with proposed values, 1 procedural, 15 need reading, 0 confirmed. Guide: `docs/5ca-at-readings.md`; confirm with `python3 tools/country_5ca.py --cc at --sign-from-doc --by NAME`. Sheets (`data/5ca/at-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for Austria (`config/stance_signers.yaml`). Only the Klub's vote is recorded, so every member row is DERIVED from it (X5) and labelled; committee votes are not sheeted (no membership list).
