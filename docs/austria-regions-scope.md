# Austria: the nine Landtage (AT6)

Scoped, probed and built on 12 October 2026 from the laptop, on branch
`regions-at`, following `.claude/regions-brief.md`. Every number below was
measured that day with the honest CitizenGO user agent, robots.txt read
first, at least 1.1 s between requests to a host. Live runs went into a
scratch database inside the worktree, never the store.

**Built:** `src/atl_store.py` (tables `atl_items`, `atl_reads`, declared in
`db.TABLES`), `tools/at_landtage.py` (one reader per Land, a common store
step), a `landtage` section in `config/watchlist-at.yaml` (empty), a
**Landtage** section in the Austrian edition (`src/editions/at.py`, through a
new additive `Country.extra_sections` hook in `src/country_edition.py`), a
step in `jobs/at-weekly.sh`, entries in `tools/coverage.py`, and
`tests/test_at_landtage.py` on trimmed real pages in
`tests/fixtures/at_landtage/`.

**Covered: seven of nine** (Wien, Niederösterreich, Oberösterreich,
Steiermark, Salzburg, Vorarlberg, Burgenland), about 85 per cent of Austria's
population, **plus Vienna's Gemeinderat** (added the same day; see
"Vienna's Gemeinderat" below). **Blocked: Kärnten and Tirol** (robots.txt), and **RIS
Landesrecht** (robots.txt and a bot check). Details below.

## The finding that shapes everything: no common platform

The national Parliament has one open API. The Länder have nothing shared:
seven readable Landtage run seven different systems (TYPO3, JSF/PrimeFaces,
JSP, Next.js, Spring MVC, Lotus Domino views, Domino XPages). There is no
open-data feed for any Landtag's motions or votes on data.gv.at that we
could find. So the collector has one small reader per Land and one common
store step; a site redesign breaks one reader, records a gap, and costs no
other Land.

The one common source would have been **RIS Landesrecht**, the federal
legal information system, which carries every Land's Landesgesetzblatt with
the Landtag's decision date and links to its materials. It is closed to us:

- `data.bka.gv.at/robots.txt` (the open-data API's host) reads
  `User-agent: * / Disallow: /` (only an EU justice crawler is named).
- `www.ris.bka.gv.at` and `ogd.ris.bka.gv.at` (which redirects there)
  answer a non-browser client with a "Security Check" page (Myra, HTTP 503).

One API reply (Wien, LGBl. Nr. 37/2026) was read while probing, before
robots.txt was read. It is kept as the test fixture for the parser
(`parse_ris`), which is ready; `--ris` asks robots.txt first and records the
refusal as a gap. RIS is not read in the weekly.

## Source by source

Ranked by population, then by what the week's read found on our ground.

| Land (pop.) | Landtag system | Format | robots.txt | Read? |
|---|---|---|---|---|
| Wien (2.0 m) | INFODAT, `www.wien.gv.at/infodat/suchergebnisse` | Next.js, server-rendered table, 20 a page | allows it; disallows the old `/infodat/ergli` and `/infodat/sukri`, never used | **yes** |
| Niederösterreich (1.7 m) | `noe-landtag.gv.at/gegenstaende/XX/suche?page=N` | TYPO3, 25 a page, newest first | `Allow: /` (bars `?id=` and `cHash`, not used) | **yes** |
| Oberösterreich (1.5 m) | LIS, `www2.land-oberoesterreich.gv.at/internetltgbeilagen/` | JSP, SessionID, search by Eingangsdatum, up to 500 a page | none on www2 (404); `Allow: /` on www | **yes** |
| Steiermark (1.3 m) | PALLAST, `pallast2.stmk.gv.at/pallast-p/pub/documents` | JSF/PrimeFaces, ViewState + cookie, paging call with rows=100 | none (the path returns the login page) | **yes** |
| Tirol (0.8 m) | `lte.tirol.gv.at` (parliamentary materials) | JSF | **`Disallow: /`** | **no** |
| Kärnten (0.6 m) | `www.ktn.gv.at/Politik/Landtag` | CMS pages | **`User-agent: * / Disallow: /`** (Google and Bing allowed) | **no** |
| Salzburg (0.6 m) | LPI, `service.salzburg.gv.at/lpi/searchExtern` | Spring MVC, search by date, every hit on one page | robots.txt answered 503 on 12 Oct 2026: read as Disallow: / (RFC 9309), skipped until it answers | **when robots.txt answers** |
| Vorarlberg (0.4 m) | LIS, `suche.vorarlberg.at/VLR/vlr_gov.nsf` | Lotus Domino view as XML (`?ReadViewEntries`) | none (redirects to an HTML page); `vorarlberg.at` bars `/documents/`, `/o/`, `/suche/`, not used | **yes** |
| Burgenland (0.3 m) | Vorlagen, `ltmobil.bgld-landtag.at/vorlagen.nsf/VorlZahl_GPXXIII.xsp` | Domino XPages, 30 a page by Zahl | none (404) | **yes** |

Tirol's `portal.tirol.gv.at` also disallows everything but its front page;
`www.tirol.gv.at` is open but lists no Landtag documents. Its page of
government drafts in consultation (`/buergerservice/landesgesetze-verordnungen-
und-richtlinien/gesetzentwuerfe-in-begutachtung/`) is open and is the one
Tirol source worth a later look. For Kärnten, `landtag.ktn.gv.at` and
`landtag-kaernten.at` do not resolve; there is no other Landtag host.

### What each system gives

- **Wien**: type (Antrag, Anfrage, Antwort, Gesetzesentwurf, Bericht,
  Aktuelle Stunde...), the sitting's date, INFODAT Id and Aktenzahl, title.
  The Landtag (`committees=L`) and, since 12 October 2026, the Gemeinderat
  (`committees=G`, below). A document is dated by the sitting it
  belongs to, so a new motion assigned to the next sitting shows the week
  of that sitting.
- **Niederösterreich**: Geschäftszahl (`Ltg.-1095/XX-2026`), type and
  Kürzel, introducer, title; the item's own page gives the dated Historie
  and the status. 1,073 items in the XX. GP (43 pages).
- **Oberösterreich**: Beilage number and year, a type code (IA, RV, AB,
  SAFR, SAAN, MAFR, BE...), title; the Beilage's page gives the Eingang
  date, and a law's page the full procedure with **the decision and the
  Klubs for and against** ("Antrag angenommen - mehrstimmig - Dafür: ÖVP,
  FPÖ, SPÖ / Dagegen: GRÜNE, MFG, NEOS"). The search itself can filter by
  decision; not used yet.
- **Steiermark**: EZ/OZ, type, Fraktion, title; 3,070 documents in the XIX.
  GP. Its **Landtagsbeschlüsse** are documents of their own and their page
  gives the sitting date and the decision with the Klubs ("Der Beschluss
  wurde einstimmig (mit den Stimmen von FPÖ und ÖVP) angenommen"). Begut-
  achtungsverfahren (consultation drafts) are listed too.
- **Salzburg**: date, title, Beilagennummer (numbered per Session, so the
  key carries the Session from the document's path), PDF.
- **Vorarlberg**: year, type, title and Domino ID for the whole
  Landtagsperiode in one XML reply; the document's page gives
  "Eingelangt in der Landtagsdirektion" (printed MM/DD/YYYY: checked against
  the Domino ID's own creation stamp) and "Behandelt im Landtag".
- **Burgenland**: Zahl, Vorlagenart, title. No dates anywhere; a second page
  needs an XPages postback, so a week with more than 30 new Vorlagen is a
  recorded gap.

None publishes per-member votes. Oberösterreich and Steiermark name the
Klubs on a decision; that line is stored verbatim (`atl_items.outcome`) and
shown in the Landtag's words, never turned into member positions.

## Measured on 12 October 2026

The first read of all seven took **78 seconds** (13 documents' own pages
included). Classified on titles with `taxonomy-atch` for `at`, the national
edition's list:

| Land | Read | Rows | On our ground |
|---|---|---|---|
| Wien | Landtag sitting days 1 Sep to 11 Dec 2026, 5 pages | 80 | 7 (Kopftuchverbot questions; single parents) |
| Niederösterreich | newest 50 | 50 | 1 (a petition on Familienbeihilfe) |
| Oberösterreich | Eingang 1 Sep to 12 Oct | 65 | 0 |
| Steiermark | newest 106 | 97 | 2 (Landtagsbeschlüsse: "Verbotsgesetz gegen den politischen Islam"; Kinderbetreuung) |
| Salzburg | 1 Sep to 12 Oct | 197 | 2 ("Salzburg als Safe Space für queere Menschen"; häusliche Gewalt) |
| Vorarlberg | the whole 32nd Landtagsperiode | 663 | 9 (LGBTIQ action plan; Palliativversorgung; Kinderbetreuung; social media and children) |
| Burgenland | newest 30 | 30 | 0 |

Hit rates are low (about 2 per cent), as they are nationally on titles
alone: Landtag business is mostly roads, budgets and audit. What it finds
is the right kind of thing: Land-level policy on religious dress, gender
and sexuality funding, palliative care and family support, the areas
where the Länder legislate.

## Vienna's Gemeinderat (added 12 October 2026, branch `vienna-gemeinderat`)

Vienna is both a Land and a city: the same 100 members sit as the Landtag
and as the Gemeinderat, the city council, and much of Vienna's policy
(funding decisions, the schools it owns, the city's ordinances) is decided
in the Gemeinderat, not the Landtag. Both are on INFODAT; the Gemeinderat is
the same search with `committees=G`, so the Wien reader reads it too.

- **Stored** in `atl_items` as the pseudo-Land `wien-gr` (land column and
  key prefix `wien-gr/<INFODAT Id>`), so no column was added and nothing
  reading `land='wien'` sees it. `atl_store.OTHER_BODIES` names it,
  `atl_store.READ` includes it (`--land wien-gr`), `atl_reads` has its row.
- **Baseline:** the Gemeinderat's first read is a baseline in full, dated
  rows included (`atl_store.BASELINE_ALL`): its window holds hundreds of
  routine items, so only business first seen afterwards reaches the edition.
  (The Landtage's baseline remains undated rows only.)
- **Shown** in the Landtage section beside the Wiener Landtag's documents,
  labelled "Wien, Gemeinderat", with the Aktenzahl as printed
  (`PGL-1310313-2026-KFP/GAT`); Coverage lists "Wien Gemeinderat" with its
  last read.
- **Politeness and budget:** the same robots.txt (it allows
  `/infodat/suchergebnisse`; the page carries a `noindex, nofollow` meta,
  which is about indexing, not reading), read per run through
  `prov_fetch.Context`, 1.1 s between requests; up to 40 pages a run (a gap
  beyond), inside the step's existing five minutes in `jobs/at-weekly.sh`.
  INFODAT ignores a page-size parameter (`perPage=100` still returns 20).

**Live smoke read, 12 October 2026** (laptop, scratch database, never the
store): sitting days 21 September to 11 December 2026, **455 rows on 23
pages in 28 seconds**, sittings of 21 and 23 September (448) and 21 October
(7 answers already filed). By type: 197 Antworten, 117 schriftliche
Anfragen, 60 Beschlussanträge, 39 Anträge des Stadtsenats (funding and
zoning), 17 Zusatzfragen, 8 mündliche Anfragen, 8 Vorsitzführungen, and a
handful of reports, Dringliche Anfragen and one Aktuelle Stunde.

**On our ground: 12** (2.6 per cent, about the Landtage's rate):
answers on the WIGEV's budget for medical abortion (three) and on prenatal
harm from alcohol and drugs; a written question on hormone treatment and
gender reassignment surgery; one on "Transgenderpropaganda im
Kindergarten"; Beschlussanträge for a headscarf ban for public servants and
a package against Islamist "Sittenwächter"; Stadtsenat funding for QWIEN
(a queer culture association) and two support schemes for children with
disabilities before and during compulsory schooling. One is a false
positive: a motion condemning the jailing of Istanbul's mayor Ekrem
İmamoğlu matched the term `Imam*` (a taxonomy matter, not changed here).

## What the edition now shows

A **Landtage** section after the Watchlist: each document on our ground or
watched, dated by the Landtag's own date (introduced, the sitting, the
decision, Salzburg's report date), with the Landtag's name, the document
type and number, the introducers where printed, Steiermark's and
Oberösterreich's recorded decisions with Klubs, and a link. The In-brief and
the DM add one line counting them. Aktuelle Stunden, follow-up questions and
chairing notes are stored, not shown. An undated document is shown by the
week we first saw it, except those seen on a Land's first read (`baseline`,
possibly years old). Coverage lists when each Land was last read, the two
blocked Landtage and RIS, every week. A sample is in the PR description.

## Rules kept

robots.txt read once per host and honoured (`src/prov_fetch.Context`), no
CAPTCHA or bot check touched (RIS left alone), no credentials, the honest
user agent, raw lists archived to `data/raw`, no paid AI, no posting; DMs
only through the existing edition (Chris alone). No members, so no personal
data beyond the introducers' names the Landtage print on each document.

## Shared files touched

- `src/db.py`: two table names in `TABLES`, one `ensure_schema` call.
- `src/country_edition.py`: `Country.extra_sections` (default `None`, so no
  other edition changes), `extras_of()`, its rendering, In-brief and DM
  lines; documented in the module's change log.
- `src/editions/at.py`: the Landtage section.
- `config/watchlist-at.yaml`: an empty `landtage` section.
- `jobs/at-weekly.sh`: the step, its reclassify line, and 300 s kept back
  from the national collector's budget for it.
- `tools/coverage.py`: `atl_items` watched, in the Austria weekly's
  pipeline, and excused while empty until 24 October.

## Waiting on Chris

1. **RIS Landesrecht.** robots.txt bars the open-data API. Leave it, or ask
   the Bundeskanzleramt's RIS team for written permission; if they agree,
   decide how such a host exception should be recorded (as the per-host
   user-agent exceptions in `src/http.py` are). The parser and test are
   ready.
2. **Kärnten and Tirol** stay out unless their Landtage open their
   robots.txt. Tirol's consultation-drafts page is open: worth a reader?
3. **Salzburg's robots.txt answered 503** (12 October 2026). Changed the
   same day: `src/prov_fetch.py` now reads a 5xx or unreachable robots.txt
   as Disallow: / (RFC 9309 2.3.1), so Salzburg is skipped, with a gap line,
   until its robots.txt answers; a 4xx still means no rules.
4. **Wien's Gemeinderat**: done, 12 October 2026 (above). `Imam*` in
   taxonomy-atch also matches "İmamoğlu"; worth an exclusion in the
   taxonomy source.
5. **Watchlist**: the `landtage` section is empty; keys are listed in
   `config/watchlist-at.yaml`.
6. **Votes**: Oberösterreich's search can list every decision with its
   Klub line and Steiermark's decisions are already read for items on our
   ground; reading all decisions is phase 2 if you want Land votes as votes.

No new Mini job: the step runs inside `jobs/at-weekly.sh` (Mini first,
`.github/workflows/at-weekly.yml` as the backup), so nothing to install.
