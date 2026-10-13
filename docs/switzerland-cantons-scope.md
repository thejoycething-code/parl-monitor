# Switzerland: the 26 cantonal parliaments (CH7)

Scoped, probed and built on 13 October 2026 from the laptop, on branch
`regions-ch`, following `.claude/regions-brief.md`. Every request went
through `src/http.py` with the honest CitizenGO user agent, and every
collector request goes through `src/robots_guard.GuardedClient` (robots.txt
read once per host per run, no exemptions). Live runs went into a scratch
database inside the worktree, never the store.

**Built:** `tools/ch_cantons.py` (one reader per canton, a common store
step), two additive tables in `src/ch_store.py` (`ch_canton_acts`,
`ch_canton_votes`, declared in `db.TABLES`), a `cantons` section in
`config/watchlist-ch.yaml` (five seeded entries, for Chris to review), a
**Cantons** section in the Swiss edition (`src/editions/ch.py`, through the
existing `Country.extra_sections` hook), a step in `jobs/ch-weekly.sh`,
entries in `tools/coverage.py`, and `tests/test_ch_cantons.py` on trimmed
real pages in `tests/fixtures/ch_cantons/`.

**Covered: five of 26** (Zürich, Bern, Vaud, Geneva, Ticino): the two
largest German-speaking cantons, the two largest French-speaking ones and
the Italian-speaking one, about 4.4 of Switzerland's 9 million people.
**Blocked by robots.txt: Basel-Stadt, Basel-Landschaft, St. Gallen,
Thurgau** (their open data is on Opendatasoft portals that disallow `/api/`)
and **Aargau** (`www.ag.ch` disallows `/grossrat`). **Not built yet:**
Lucerne and Valais (feasible, undocumented JSON backends) and the smaller
cantons. Details below.

## The finding that shapes everything

The cantons that publish their parliaments' business best do it as open
data, and half of that open data is closed to us by robots.txt. Basel-Stadt
(business, motions, members, interests and agendas), Basel-Landschaft
(business since 2017 and **every member's vote since 2018**), St. Gallen
(business and votes) and Thurgau (business, votes and speeches) all publish
through Opendatasoft portals listed on opendata.swiss. Each portal's
robots.txt reads `User-agent: * ... Disallow: /api/` (Googlebot alone is
allowed `/api/`, and even Googlebot is refused `/api/v2/*/exports/`). The
datasets are only reachable through `/api/`, so the collector does not read
them. This is the most valuable thing on this page for Chris to decide
(Waiting on Chris, 1).

The others each run their own system: Zürich a CMI document service with a
query language, Bern a daily JSON export, Geneva a keyword search, Vaud a
TYPO3 list per department, Ticino a TYPO3 order of the day. No two share a
platform, so a redesign breaks one reader, records a gap, and costs no other
canton.

## Canton by canton

Ranked by population, then by what the first read found on our ground.
"Read?" says what the weekly collector does.

| Canton (pop.) | Parliament | Source | Format | robots.txt | Read? |
|---|---|---|---|---|---|
| Zürich (1.6 m) | Kantonsrat | `parlzhcdws.cmicloud.ch/parlzh5/cdws/Index/GESCHAEFT/searchdetails` (the CMI service behind kantonsrat.zh.ch) | XML, CQL queries, 25 a page, 19,008 Geschäfte since 1987 | 404 (no rules) | **yes** |
| Bern (1.06 m) | Grosser Rat | `ogd.parl.apps.be.ch/data/geschaeft.json`, `abstimmung_tagblatt.json` (on opendata.swiss) | JSON, daily, DE and FR | 404 (no rules) | **yes** |
| Vaud (0.85 m) | Grand Conseil | `www.vd.ch/gc/liste-des-objets-en-attente-de-traitement-par-le-grand-conseil/<department>` | HTML, 8 pages | allows these paths | **yes** |
| Aargau (0.73 m) | Grosser Rat | `www.ag.ch/grossrat/grweb/` | HTML (GRWeb) | **`Disallow: /grossrat`** | **no** |
| St. Gallen (0.53 m) | Kantonsrat | `daten.sg.ch` datasets "Geschäfte im Kantonsrat", "Abstimmungen im Kantonsrat" | Opendatasoft API | **`Disallow: /api/`** | **no** |
| Geneva (0.52 m) | Grand Conseil | `ge.ch/grandconseil/searchm/search/index?q=<term>&date=y1` | HTML search, one page per term | none (the URL returns a web page, read as no rules) | **yes** |
| Lucerne (0.43 m) | Kantonsrat | `www.lu.ch/kr/parlamentsgeschaefte` (ASP.NET form posting to `/api/klu/search/result`); members, sessions and interests as CSV on opendata.swiss | HTML form, undocumented JSON | allows | not yet |
| Ticino (0.36 m) | Gran Consiglio | `www4.ti.ch/poteri/gc/attivita/ordine-del-giorno/` | HTML | allows it; **disallows the acts search** (`/poteri/gc/ricerca-messaggi-e-atti/ricerca/`) | **yes** (order of the day) |
| Valais (0.36 m) | Grand Conseil / Grosser Rat | `parlement.vs.ch/app/` (Sitrox single-page app, backend `api/fe/v1/search/...`) | undocumented JSON | empty (no rules) | not yet |
| Fribourg (0.34 m) | Grand Conseil | `www.fr.ch/gc` | Drupal pages | disallows `/fr/`, `/search/` and `?page` | not yet |
| Basel-Landschaft (0.30 m) | Landrat | `data.bl.ch` datasets 13090 (business since 2017), 13080 (member votes since 2018) | Opendatasoft API | **`Disallow: /api/`** | **no** |
| Solothurn (0.29 m) | Kantonsrat | `so.ch/parlament/` | TYPO3 pages | allows | not yet |
| Thurgau (0.29 m) | Grosser Rat | `data.tg.ch` datasets sk-stat-140 (business), sk-stat-136 (votes) | Opendatasoft API | **`Disallow: /api/`** | **no** |
| Graubünden (0.20 m) | Grosser Rat | `www.gr.ch` (SharePoint) | HTML | disallows search and list views | not yet |
| Basel-Stadt (0.20 m) | Grosser Rat | `data.bs.ch` datasets 100311 (business), 100086 (motions), members, agendas | Opendatasoft API | **`Disallow: /api/`** | **no** |
| Neuchâtel (0.18 m) | Grand Conseil | `www.ne.ch` | Drupal | allows | not yet |
| Schwyz (0.17 m) | Kantonsrat | `www.sz.ch/kantonsrat` | HTML | allows | not yet |
| Zug (0.13 m) | Kantonsrat | `zg.ch/de/kantonsrat` | Magnolia pages | allows | not yet |
| Schaffhausen (0.08 m) | Kantonsrat | `sh.ch` | CMS (answered 500 on 13 October) | allows | not yet |
| Jura (0.07 m) | Parlement | `www.jura.ch` | HTML | **disallows `/InterventionParlementaire.ashx`** | not yet |
| Appenzell AR, Nidwalden, Glarus, Obwalden, Uri, Appenzell IR (0.02 to 0.06 m each) | Kantonsrat / Landrat / Grosser Rat | cantonal websites | HTML | not probed | not yet |

### What each reader does

- **Zürich.** The CMI service's Geschaeft index, queried in its own
  language: the businesses begun in the last 45 days
  (`beginn_start > "<date> 00:00:00"`; the service wants that exact date
  form) and every business whose index sequence moved past the highest one
  stored (`seq > N`), which catches stage moves of older businesses. 25 a
  page, at most 12 pages per query. Each record carries the kind
  (Vorlage, Motion, Postulat, Parlamentarische Initiative, Anfrage,
  Interpellation ...), the title, the start date, the signatories with
  their parties, the committee and every step (Ablaufschritt) with its
  date; the last step is the status, dated by the source. Records also
  carry the documents' full text; it is not stored or matched. MEASURED:
  93 businesses begun since 1 August 2026, about 12 KB each; a run reads
  65 to 85 records in about 4 seconds.
- **Bern.** Both daily exports, re-read whole (17 MB together), kept from
  the legislature's start (1 June 2022): 1,875 of 6,139 businesses
  (appointments, pardons, deadline extensions and concessions are skipped)
  and 3,254 votes. Every business has a German and a French title; the
  submission date (epoch milliseconds), last treatment, decision and
  detail, the main signatory and Fraktion, the committee. Each vote has its
  tally and a description from which the business number, what was voted
  on ("Ziff. 3 als Postulat", "Antrag 2, BaK") and the result are read. No
  member positions are published in the export. About 9 seconds.
- **Geneva.** The Grand Conseil's own search, asked for 17 French words of
  our areas within the last year, first page each: PL, M, R, P, IN, RD, Q
  ... with the month of the latest document and the decision with its date
  ("Objet refusé 23 janv. 2026"). A report's title names the object it is
  about; the object's own words and its authors are split out. It is a
  keyword search, so an object no term finds is not read; taxonomy-fr still
  decides what is on our ground. MEASURED: 79 to 166 objects a run, 11 to
  12 on our ground. The search answers a narrow term in under a second and
  a broad one in 12 to 13 seconds, so Geneva takes about three minutes and
  runs last.
- **Vaud.** The eight lists of objects awaiting treatment (seven
  departments and the Grand Conseil): motions, postulates, initiatives,
  petitions, Council of State reports and bills, with authors, committee
  and the latest step ("Rapport de la commission reçu le 03.09.26",
  "Séance de commission le 09.03.26"). 605 objects, 26 on our ground. No
  submission date (the identifier carries the year), so a status change is
  dated by the run that sees it. About 5 seconds.
- **Ticino.** The order of the day of the next (or last) sitting: each point
  that carries an act (motion, initiative, message, report), with the
  department, the procedure and the sitting's date. 19 points on 5 October
  2026, none on our ground. The acts search would give far more, but its
  path is disallowed. About 1 second.

## Classification

As the federal collector (`tools/ch_rollcalls.py`): German text with
`taxonomy-atch` for `ch`, French with `taxonomy-fr` for `ch`, Italian
(Ticino) with `taxonomy-it` for `ch`; Bern's two titles are both matched and
unioned. Titles only. Plus `watchlist-ch.yaml`'s new `cantons` section by
key (`zh/376/2026`, `be/2026.GRPARL.151`, `ge/M3137`, `vd/26_MOT_10`,
`ti/134780`). No taxonomy file was edited.

Two reads, 13 October 2026: **81 acts on our ground** of 2,752 stored (Zürich 4, Bern 39,
Geneva 12, Vaud 26, Ticino 0). Hand-checked: no false positives worth
muting; the borderline ones are the taxonomy's own choices ("Suizidprävention"
under assisted dying, domestic violence and femicide under sex-based
rights). Highlights: Zürich's parliamentary initiative for a cantonal
initiative to ban conversion practices (376/2026, 28 September 2026);
Bern's motion on abortion numbers (2025.GRPARL.543), its motion on access to
irreversible gender-reassignment for minors (2023.RRGR.210, adopted point by
point, one point on the President's casting vote, 76 to 75), the national
face-covering ban (2025.GRPARL.493) and the church tax; Geneva's bills and
motions on gender reassignment for minors (PL 13324, M 3010, M 3137, all
refused 23 January 2026), its conversion-practices ban (PL 13327, LIMOIG),
contraception (IN 198 and its counter-project PL 13758), the laïcité law
(PL 13035) and medically assisted procreation for single women (R 1062);
Vaud's postulate on the headscarf at school (23_POS_17) and on mixed or
single-sex PE (26_POS_7).

**What the lists missed** (now in the `cantons` watchlist, for Chris to
review): Geneva M 3137 ("réassignation/conversion sexuelle"), Geneva M 3087
("soins de transition de genre"), Bern 2023.RRGR.193
("Geschlechtsänderungen"), Bern 2024.RRGR.225 ("Genderstern") and Bern
2023.RRGR.109 (sex education, "Aufklärung"). **Proposed terms** (not
applied; taxonomy files are generated): German `Geschlechtsänderung*`
(area 3, tier 2) and `Genderstern` (area 5, tier 2); French `transition de
genre` (area 3, tier 2) and a slash-tolerant `réassignation` stem (area 3).
All are Swiss-usable in the shared lists; none is canton-specific.

## Dates, new and moved

Zürich, Bern and Ticino date their steps, so `status_date` is the source's.
Geneva dates a decision; a report with no decision, and every Vaud step,
prints no date, so a run that sees a stored row's status change stamps the
day it saw it (`status_seen = 1`), and the first sighting is never a change.
Geneva, Vaud and Ticino print no submission date: a row first seen after a
canton's first read is new on the day we saw it; rows of the first read are
a baseline (`baseline = 1`) and are never shown as new.

## The edition

A **Cantons** section after the Watchlist (`Country.extra_sections`), never
mixed into the Federal Assembly's sections or the lead: new acts on our
ground by their submission date (or first sighting, above), stage moves by
their status date, questions only when new, and Bern's votes with the
published tally and result, each naming the act it belongs to. Titles
verbatim; Bern's French title as a second line. The Coverage block lists the
cantons read with their last read, the robots.txt refusals and what is not
read yet. Sample (window 31 August to 6 September 2026, rendered from a copy
of the store with the first read merged in): Bern's motion on suicide
prevention and its three point-by-point votes (145-0, 145-0, 77-63), its
withdrawn urgent motion on individual taxation, an urgent finance motion on
palliative care, and Geneva's PMA resolution and conversion-practices bill.

## Runtime

A step in `jobs/ch-weekly.sh` after the federal collector, before the
edition: about 60 requests, three to four minutes (Geneva's search is most
of it), its own 7-minute budget (`tools/collector_budget.sh 420`; the
federal collector's budget keeps those 7 minutes out). A failure is a
`[gap]` line, never the run's. `CH_RECLASSIFY=true` re-derives the cantonal
areas offline. Nothing new to install on the Mini.

## Phase list

1. **CH7a (built, 13 October 2026):** Zürich, Bern, Geneva, Vaud, Ticino as
   above.
2. **CH7b, if Chris agrees (Waiting on Chris, 1):** Basel-Stadt,
   Basel-Landschaft (with member votes), St. Gallen and Thurgau from their
   open data.
3. **CH7c:** Lucerne (the search form's JSON) and Valais (the Sitrox
   backend), both undocumented backends behind web pages, so robots.txt is
   asked first (both allow today); then Solothurn, Fribourg, Neuchâtel,
   Zug, Schwyz, Graubünden.
4. **CH7d:** Zürich votes (the Kantonsrat records electronic votes; no open
   source found yet) and Geneva's roll calls (published as PDFs, "vote
   nominal", per object in each session's documents).

## Waiting on Chris

1. **The four Opendatasoft cantons.** Basel-Stadt, Basel-Landschaft,
   St. Gallen and Thurgau publish exactly what we want as open government
   data, listed on opendata.swiss, but their portals' robots.txt disallows
   `/api/` to every agent but Googlebot. Options: leave them; write to the
   cantons' open-data offices asking for permission or an exemption for our
   agent; or decide that a listed OGD dataset counts as a documented API
   (the `DOCUMENTED_APIS` route in `src/robots_guard.py`, which the regional
   collectors do not use). Nothing is read until you decide.
2. **Review the five seeded `cantons` watchlist entries** and the proposed
   terms above.
3. **Aargau** disallows its whole parliament section; ask its Parlamentsdienst
   or leave it?

## Shared files touched

`src/ch_store.py` (two tables, `canton_watchlist`, additive), `src/db.py`
(two names in `TABLES`), `src/editions/ch.py` (the Cantons section and
`extra_sections`), `jobs/ch-weekly.sh` (one step, one reclassify line, the
federal budget's third argument), `tools/coverage.py` (two freshness rows,
two `AWAITING_STEP_UNTIL` entries), `config/watchlist-ch.yaml` (the
`cantons` section), `docs/country-parity-handover.md`, `docs/mac-mini.md`,
`docs/robots-runtime.md`.
