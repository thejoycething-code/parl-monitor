# Poland: the sixteen voivodeship assemblies (sejmiki województw)

Probed live on 13 October 2026 from Christopher's laptop with the repo's own
client (`src/http.py`: the CitizenGO User-Agent, throttled, retry with
backoff) and the run-time robots guard (`src/robots_guard.py`). Every number
below was measured. Raw replies are archived under `data/raw/2026-10-13/`
(`pl-regions_*`); the test run went to a scratch store, never the published
one. The national edition is `docs/poland-scope.md`.

## Why the sejmiki matter

A sejmik is the elected assembly of a voivodeship (30 to 51 councillors,
five-year term, the seventh term since April 2024). It adopts the region's
budget, development strategy, health and social programmes, and
non-binding positions (stanowiska) and appeals. That last kind is where the
CitizenGO ground was fought: in 2019-20 five sejmiki (Lubelskie,
Podkarpackie, Świętokrzyskie, Małopolskie, Łódzkie) adopted declarations
against "LGBT ideology" or the "Samorządowa Karta Praw Rodzin" (the Family
Charter); the European Commission tied cohesion funding to them and most
were repealed or amended in 2021-24. Regional in-vitro funding programmes
(Mazowieckie, Pomorskie, Zachodniopomorskie, Łódzkie and others), domestic
violence programmes, sex education in regional schools and family policy
("Karta Dużej Rodziny" equivalents) are the live topics now.

Every sejmik must publish each councillor's vote (art. 19 of the
voivodeship self-government act: "imienne wykazy głosowań radnych",
promptly, in the BIP and on the voivodeship's website).

## Sources, region by region

Two platforms serve many regions:

1. **The voivodeship official journals** (Dziennik Urzędowy Województwa
   ...). Each voivode publishes one, and **fifteen of the sixteen run the
   same e-Dziennik platform** (an Angular application over a JSON API). Its
   month list, `/api/positions?year=Y&month=M&isList=true`, is one reply
   with every position of the month: title, act type, act date, publication
   date, publishers, subject, PDF. robots.txt disallows only `/login`.
   The journal carries a sejmik's local law, budget changes, statutes,
   programmes adopted as local law, consolidated texts, and the voivode's
   supervisory rulings (rozstrzygnięcia nadzorcze) that annul a sejmik's
   act. It never carries non-binding resolutions (stanowiska, apele,
   declarations such as the Family Charter).
2. **eSesja** (`<name>.esesja.pl`, sittings, agendas, materials, the
   per-councillor vote of every resolution): every subdomain probed,
   including `lodzkie.esesja.pl`, which Łódzkie's BIP links, answers our
   client with a Cloudflare challenge ("Just a moment...", 403). **Blocked:
   never bypassed.** (`esesja.pl` itself answers; its robots.txt disallows
   PDFs and attachments.)

The sejmiki's own registers of resolutions are in each marshal's office
BIP, sixteen different sites:

| Code | Voivodeship (pop.) | Journal (e-Dziennik) | Register of resolutions (BIP) | Votes | Status |
|---|---|---|---|---|---|
| mz | Mazowieckie (5.5 m) | edziennik.mazowieckie.pl: answers | bip.mazovia.pl, CMS year/month list ('?p=2026^wrzesień'), 178 resolutions Jan to Sep 2026 | PDFs | **both read** |
| sl | Śląskie (4.3 m) | dzienniki.slask.eu: answers | bip.slaskie.pl, the same CMS as Mazowieckie, 118 resolutions in 2026 | PDFs | **both read** |
| wp | Wielkopolskie (3.5 m) | edziennik.poznan.uw.gov.pl: answers (no sejmik act in Sep-Oct) | bip.umww.pl: VII-term index of sittings, each a table (number, subject, PDF); answered promptly on the second probe | page "Imienne wykazy głosowań" | **both read** (second build) |
| ma | Małopolskie (3.4 m) | edziennik.malopolska.uw.gov.pl: answers | bip.malopolska.pl: an AngularJS application over its own JSON API, `bip.malopolska.pl/api/` (app-conf.js names it; robots.txt disallows only admin pages and listed articles); register menu 1032 (a child per year), Deklaracje 1070, Apele 1088 | - | **both read** (second build) |
| ds | Dolnośląskie (2.9 m) | edzienniki.duw.pl: answers | bip.dolnyslask.pl: a React application on the same platform as Małopolskie, JSON at `/api/`; register menu 1914 (a child per year; only a publication date per row) | PDFs with the minutes | **both read** (second build) |
| ld | Łódzkie (2.4 m) | dziennik.lodzkie.eu: answers | bip.lodzkie.pl, one table of the whole term (number, date, title, PDF), 396 resolutions since May 2024 | eSesja (blocked) | **both read** |
| pm | Pomorskie (2.3 m) | edziennik.gdansk.uw.gov.pl: answers | bip.pomorskie.eu: the same platform, JSON at `/api/`; register menu 42 (a child per year; numbers printed '366/XXX/26') | page "Imienne wykazy głosowań" | **both read** (second build) |
| pk | Podkarpackie (2.1 m) | edziennik.rzeszow.uw.gov.pl: answers | bip.podkarpackie.pl, an index of sittings, each with its resolutions as attachments ('XXXI/520/26 - w sprawie ...'); Crawl-delay 3; sittings before 22 May 2026 on archiwumbip.podkarpackie.pl | page "Imienne wykazy głosowań" | **both read** |
| lu | Lubelskie (2.0 m) | edziennik.lublin.uw.gov.pl: answers | umwl.bip.lubelskie.pl: the document lists are filled by the page's own DataTables call (`index.php?id=56&action=list-ajax`, 4,441 resolutions of every term; id=57 the stanowiska, apele and oświadczenia, unnumbered); robots.txt answers 404 (no rules) | - | **both read** (second build) |
| kp | Kujawsko-Pomorskie (2.0 m) | edzienniki.bydgoszcz.uw.gov.pl: **connection times out** from the UK (three tries on 13 October; edziennik.bydgoszcz.uw.gov.pl answers 403) | bip.kujawsko-pomorskie.pl: no list of adopted resolutions (the sejmik's own site, sejmik.kujawsko-pomorskie.pl, answers our client 403); each sitting's agenda lists its draft resolutions with print numbers | "Wydruki głosowań" | agendas read as drafts (second build) |
| zp | Zachodniopomorskie (1.6 m) | e-dziennik.szczecin.uw.gov.pl: answers (publisher printed in the genitive, "Sejmiku Województwa ...") | bip.wzp.pl: resolutions to 2020 in one article; since 2021 in "Baza Aktów Własnych" (baw2.wzp.pl), an Angular application whose bundle is the staff editor (login, document-editing calls) with no public list endpoint found; sitting pages carry only an agenda PDF | - | journal read |
| wn | Warmińsko-Mazurskie (1.4 m) | edzienniki.olsztyn.uw.gov.pl: answers | bip.warmia.mazury.pl (robots.txt allows all): the act list with a GET filter (`akty.html?VAktPrawnySearch[rodzaj]=Uchwały Sejmiku`, 20 rows a page) and the stanowiska category 159 | category 116 | **both read** (second build) |
| sk | Świętokrzyskie (1.2 m) | edziennik.kielce.uw.gov.pl: answers | bip.sejmik.kielce.pl: the per-year pages list only files ('Uchwała nr XXIV 287.26', no subject); the "Rejestr uchwał" of the term is one PDF (850 KB, number, subject, organ), re-published after each sitting, under /download/ (allowed) | page "Imienne wykazy głosowań" | **both read** (second build, needs pypdf) |
| pd | Podlaskie (1.1 m) | edziennik.bialystok.uw.gov.pl: answers (genitive publisher) | bip.wrotapodlasia.pl does not resolve (NXDOMAIN); new address not found | - | journal read |
| lb | Lubuskie (1.0 m) | dzienniki.luw.pl (linked from bip.lubuskie.uw.gov.pl): answers | bip.lubuskie.pl: the act list `/akty/20/typ/` filtered by its own form (a POST; the filter is kept in the PHP session, so a cookie jar for the run), the year's sejmik acts newest first, 30 rows | - | **both read** (second build) |
| op | Opolskie (0.95 m) | duwo.opole.uw.gov.pl: answers | bip.opolskie.pl: connection times out | minutes as PDFs (named results printed in the minutes) | journal read |

### What one run reads (measured, 13 October 2026)

- **Journals:** 30 requests (current and previous month, fifteen
  journals). A month list is 400 to 1,130 positions (Mazowieckie
  September: 1,126); 80 of them, across the fifteen, were sejmik acts in
  1 September to 13 October 2026 (Mazowieckie 2, Śląskie 7, Wielkopolskie 0,
  Małopolskie 11, Dolnośląskie 1, Łódzkie 6, Pomorskie 3, Podkarpackie 12,
  Lubelskie 7, Zachodniopomorskie 4, Warmińsko-Mazurskie 10,
  Świętokrzyskie 3, Podlaskie 6, Lubuskie 4, Opolskie 4). No supervisory
  ruling on a sejmik's act was published in those weeks.
- **Registers:** Mazowieckie and Śląskie a year page plus the newest two
  month pages (the whole year on the first read: 10 and 9 pages);
  Łódzkie one page; Podkarpackie the index plus the newest three sittings
  (all five on the first read), at 3 s a request.
- **First run (scratch store):** 892 acts stored (800 from the registers,
  92 journal positions), all 19 sources ok, about 3 minutes.

### On our ground (first run)

Three of the 800 register resolutions matched the Polish taxonomy, all at
tier 2: Łódzkie's 2026-2030 programme against domestic violence
("przemoc* domow*", area 5), Mazowieckie's yearly social-care resources
assessment ("demograf*", area 9) and Śląskie's network plan of teacher-
training centres ("prawo oświatowe", area 6). The last two are yearly
boilerplate every sejmik adopts and are left out by
`config/edition-noise-pl.yaml`. None of the 92 journal positions matched.
That is the honest picture of an ordinary month: sejmiki mostly vote
grants, budget changes and appointments. The layer is there for the
months when one of them adopts a family charter, an in-vitro programme,
a sex-education position or a repeal.

## What was built (13 October 2026)

- `tools/pl_regions.py` into `plr_acts` and `plr_reads`
  (`src/pl_regions_store.py`, created by `db.init_db`): the fifteen journals
  and four registers above, every request through
  `src/robots_guard.GuardedClient` (robots.txt read at run time per host,
  Crawl-delay honoured, a refusal is a gap). Keys:
  `<region>/dz/<year>/<position>` for the journals,
  `<region>/<number as printed>` for the registers. A register's first read
  is stored as `seed`, so the first edition is not a flood.
- Classified with `config/taxonomy-pl.yaml` (country "pl") on the title,
  plus `config/watchlist-pl.yaml`'s new `regional` section by key (empty:
  seeded once the live store shows what is on our ground).
- A step of `jobs/pl-weekly.sh` (Sundays, on the Mini; GitHub backup runs
  the same script): five minutes of the hour
  (`tools/collector_budget.sh 300`), reserved out of the Sejm collector's
  budget; its failure is a `[gap]` line, never the run's.
  `PL_RECLASSIFY=true` reclassifies it too.
- The Polish edition (`src/editions/pl.py`) has a **"Regional assemblies"**
  section before the Watchlist: "Adopted by the sejmiki" (register
  resolutions adopted in the window, or listed late within 28 days) and
  "In the voivodeship journals" (positions published in the window, unless
  the same resolution is already shown from its register), through the
  edition's noise filters, with coverage lines (journals read, registers
  read, what is not read).
- `tools/coverage.py`: `plr_reads` and `plr_acts` freshness (7 days, 4 of
  grace), excused while empty until 25 October 2026.
- Tests: `tests/test_pl_regions.py` (24 tests, fixtures in
  `tests/fixtures/pl_regions/`, no network).

No new Mini job: the step rides the Poland weekly.

Shared files touched: `src/db.py` (two table names and one
`ensure_schema` call), `tools/coverage.py` (three additive entries),
`config/edition-noise-pl.yaml` (two exclude_titles patterns),
`config/watchlist-pl.yaml` (an empty `regional` section),
`jobs/pl-weekly.sh` (the step, the reclassify line, the budget reserve).

## Second build (13 October 2026): nine more registers, the terms, the watchlist

Chris, 13 October: "Add both", "Build all reachable ones", "Yes, seed it".

**Readers added** (`tools/pl_regions.py`, the same store, keys and seed
rule; every request through the run-time robots guard and the identified
User-Agent):

| Code | Reader | A weekly run reads | Keys |
|---|---|---|---|
| ma | Madkom JSON: `/api/menu/1032` (year children), then the year's list, newest 60; Deklaracje (1070) and Apele (1088) the same way, newest 20 | 6 requests | `ma/XXXIV/513/26`, `ma/deklaracja/5/21`, `ma/apel/6/25` |
| pm | Madkom JSON, menu 42 | 2 | `pm/366/XXX/26` (Pomorskie's own order) |
| ds | Madkom JSON, menu 1914 (adoption date not listed: the publication date stands in) | 2 | `ds/XXX/898/26` |
| lu | the page's own DataTables JSON: menu 56 newest 60, menu 57 newest 20 (450 and 40 on the first read) | 2 | `lu/XXV/427/2026`, `lu/doc/<BIP id>` for the unnumbered positions |
| sk | the register page, then its PDF (pypdf); sittings as headings, organ columns stripped | 2 (one 850 KB PDF) | `sk/XXX/362/26` |
| wp | the VII-term index, then the newest two sittings' tables | 3 | `wp/XXVIII/681/26` |
| wn | the filtered act list, two pages, and the stanowiska category | 3 | `wn/XXVII/465/26`, `wn/doc/<id>` |
| lb | the act list, then its filter form posted (the year's group id read from the form's own options) | 2 | `lb/XXIII/365/26` |
| kp | the index of sittings, then the newest two agendas; draft resolutions stored as kind `projekt uchwały`, adopted = the sitting's date | 3 | `kp/druk/64/26` |

The edition shows Kujawsko-Pomorskie's drafts under their own heading, "On a
sejmik's agenda", as "Draft resolution (druk nr 64/26) on the agenda of ...
for its sitting of ...; the outcome is not published as a list", never as
adopted. The coverage line names the three registers not read and why.

**Measured** (scratch store, laptop, 13 October): first read of the thirteen
registers 2,961 resolutions in 76 s, plus the fifteen journals (80 acts) in
30 s; a weekly run of everything 74 s. The step's five minutes stand
(`jobs/pl-weekly.sh` unchanged but for its comment). 25 acts on our ground
after the watchlist (2 at tier 1): the Małopolskie Family Charter petition
(XXVIII/418/26) and appeal on religion teaching (apel 6/25), two
domestic-violence programmes (Łódzkie, Lubelskie), foster-care and
social-care programmes, Małopolskie's appeal for a social-media ban for
under-15s, Lubelskie's position defending the "Pamięć i Tożsamość" museum,
and some noise: Gmina Kościelisko ("Kościel*") and the Catholic University of
Lublin's property deals ("katolick*"), now excluded in
`config/edition-noise-pl.yaml`.

**Taxonomy-pl v0.3** (`docs/keyword-taxonomy-pl.md`, regenerated):
"Kart* Praw Rodzin*" (area 9, tier 1) and "stref* wolne od ideologii" (area
5, tier 1, beside "strefy wolne od LGBT"). National store, read-only (Polish
prints, processes, divisions, questions): 0 matches for either. Regional live
read: the Family Charter term 1 (Małopolskie XXVIII/418/26), the zones term
0. The registers' history, read once to seed the watchlist (Lubelskie's whole
register and positions, Małopolskie 2019-21, Świętokrzyskie's VI-term PDF):
2 more for the Family Charter term (Lubelskie XXXVIII/591/2022, Świętokrzyskie
XLIV/558/22, both petitions to adopt the "Karta Praw Rodziny"), 0 for the
zones term (the declarations say "ideologii LGBT", already matched). No false
positive.

**The regional watchlist** (`config/watchlist-pl.yaml`, `regional:`): 19
entries. From the live run: ma/XXVIII/418/26, ma/apel/6/25, ma/apel/8/26,
ld/XXV/307/2026, lu/XVII/264/2025. From 2019-21, keyed as the readers store
them: Lubelskie's 25 April 2019 position (lu/doc/1382854), its 27 September
2021 amendment (lu/doc/1677532, in the first read's window), the Ombudsman
complaint answer (lu/XVI/268/2020) and the Karta Praw Rodziny petition
(lu/XXXVIII/591/2022); Małopolskie's Deklaracja Nr 1/19, its repeal
Deklaracja Nr 5/21 and two repeal petitions (XLVI/652/21, XLVI/653/21);
Świętokrzyskie's X/125/19, two complaints and a repeal petition against it
(XII/168/19, XXV/350/20, XXVII/369/20), the replacement position of 22
September 2021 (XXXV/486/21) and the Karta Praw Rodziny petition
(XLIV/558/22). Most are older than any window read, so the store module now
matches by citation too: a later act of the same voivodeship whose title cites
a watched act's number ("uchylenia uchwały nr X/125/19", "Deklaracji Nr
1/19", which needs the kind named) or an entry's `cites:` phrase inherits its
areas ("cites:<key>" in the stored row). To add when first collected:
Łódzkie's Samorządowa Karta Praw Rodzin and its repeal, and Podkarpackie's
2019 position and its 2021 change (their registers before the current term
are not read).

Shared files touched by the second build: `src/editions/pl.py` (registers
list, draft heading and takeaway, coverage line), `src/pl_regions_store.py`
(citations), `config/watchlist-pl.yaml`, `config/edition-noise-pl.yaml` (two
patterns), `docs/keyword-taxonomy-pl.md` and the generated
`config/taxonomy-pl.yaml`, `jobs/pl-weekly.sh` (comment only).

## Not built, and why

- **Three registers:** Zachodniopomorskie (since 2021 in a staff
  application, baw2.wzp.pl, with no public list endpoint found; nothing was
  forced), Podlaskie (the BIP domain no longer resolves; new address not
  found), Opolskie (times out). Their published acts still arrive through
  the journals; their non-binding positions do not.
- **Kujawsko-Pomorskie's adopted resolutions:** only the agendas' drafts
  are read; the sejmik's own site answers 403 and the BIP has no list.
- **The Kujawsko-Pomorskie journal:** no answer from the UK. Listed, not
  read by default; `python3 tools/pl_regions.py --region kp` tries it. Worth
  one try from the Mini.
- **Roll-call votes and members (phase 2):** published per sitting as PDFs
  (Podkarpackie, Wielkopolskie, Warmińsko-Mazurskie, Pomorskie,
  Świętokrzyskie, Kujawsko-Pomorskie "Wydruki głosowań", Opolskie inside its
  minutes) or on eSesja (blocked by a bot check). A PDF reader per layout,
  like the provinces' Hansard PDFs, is the route; councillors' lists are
  plain BIP pages.
- **Draft resolutions (projekty uchwał)** outside Kujawsko-Pomorskie: in
  each sitting's materials (Małopolskie and Dolnośląskie have "Projekty
  Uchwał" menus on the same JSON API); phase 2 with the votes.
- **The Mini needs pypdf** for Świętokrzyskie's PDF register; without it
  that source is a gap line each run, nothing else changes.

## Waiting on Chris

Nothing from the first build: the two terms, the watchlist and the
registers were all answered on 13 October (above). Open: whether pypdf is on
the Mini (Świętokrzyskie), and whether to keep Kujawsko-Pomorskie's drafts
in the edition.

## Forward agenda (regional_agenda, 16 October 2026)

`src/regional_agendas/pl.py`, run by `tools/regional_agenda.py pl` (the
step in `jobs/pl-weekly.sh` is the lead's). The chairman must send the
date and proposed porządek obrad at least seven days before a sitting
(art. 21 of the voivodeship self-government act); most sejmiki post it in
the BIP the same day, so the plenary horizon is about a week, with
timetables (Mazowieckie, Dolnośląskie) reaching December. Every route was
probed live from the laptop on 16 October 2026 with robots.txt read first
(the run-time guard), honest user agent, a handful of requests per host.
eSesja (`*.esesja.pl`) still answers with a Cloudflare bot check: never
bypassed, and it is where Małopolskie's plenary and Łódzkie's committee
materials live.

| Code | Route | Format | Horizon (live run) | robots.txt |
|---|---|---|---|---|
| mz | bip.mazovia.pl: the term's sitting timetable (`/pl/bip/sejmik/sesje-sejmiku/vii-kadencja-2024-2029/`), the year's sitting folders (`.../2026/`), each folder's `porzadek-obrad*.html`; committees' `komisje-sejmiku/planowane-posiedzenia.html` (date, hour, porządek obrad inline) | HTML | plenary dates to 15 December (27 Oct and 17 Nov booked, agenda not yet posted); committees to 19 October | allowed |
| sl | bip.slaskie.pl: `sesje_sejmiku/projekty_uchwal/?p=2026^październik` (one entry per sitting, 'z dnia 2026-10-19'); the drafts are one 3.5 MB PDF, so each sitting is to be announced. The host is slow (a detail page took over 100 s) | HTML | 19 October | allowed |
| ma | bip.malopolska.pl JSON API (Madkom): `/api/menu/437636/articles` (committee timetable: date, hour, place, committee) and `/api/articles/<id>` (each invitation with its 'proponowany porządek posiedzenia') | JSON | 26 October (15 committee meetings) | allowed (admin pages only disallowed) |
| pm | bip.pomorskie.eu JSON API: `/api/articles/60421` ('Materiały na sesję'), each sitting's porządek obrad `.docx` (`e,pobierz,get.html?id=...`), read with zipfile | JSON + DOCX | 26 October | allowed |
| ds | bip.dolnyslask.pl JSON API: `/api/articles/107616` (the year's sitting dates) and `/api/articles/99529` (standing committees' dates; the agendas are .doc/.pdf attachments) | JSON | 26 November (dates only) | allowed |
| pk | sejmik.podkarpackie.pl (Joomla): `/prace-sejmiku/sesje` (sittings), each sitting's materials page with the porządek obrad `.docx` under `/images/sesje_7/`; `/prace-sejmiku/posiedzenia-komisji` (committee notices with date, hour and numbered agenda) | HTML + DOCX | 26 October | allowed (only system folders disallowed) |
| kp | bip.kujawsko-pomorskie.pl: the term's index of sittings and each 'Porządek obrad' page (HTML list), posted about a week ahead | HTML | nothing yet (newest 28 September) | allowed |
| ld | bip.lodzkie.pl: `/sejmik-wojewodztwa/plan-pracy/sesje-sejmiku` (K2 notices) and each `item/<id>` (numbered points, 4.1 ... under 'Rozpatrzenie projektów uchwał') | HTML | 20 October | allowed |
| wn | bip.warmia.mazury.pl: categories 135 (one article per sitting) and 9 (one article a month, each committee meeting a PDF named 'Porządek posiedzenia KSR 21.10.2026'); agendas are PDFs: to be announced | HTML | 21 October | allowed |
| zp | bip.wzp.pl: `/tabela/artykuly/771/2328` (sitting articles); the porządek obrad is a scanned PDF (no text layer): to be announced | HTML | 22 October | allowed |

Not read, and what was tried:

- **Wielkopolskie:** bip.umww.pl has resolutions, protocols and roll calls by
  sitting; no forward list or porządek obrad in any sejmik category.
- **Lubelskie:** umwl.bip.lubelskie.pl's menus list sittings only with their
  protocols (newest menu 2020); no timetable or agenda found.
- **Świętokrzyskie:** bip.sejmik.kielce.pl's 'Terminy i porządek obrad'
  article is one PDF per sitting and the list stops at 29 September 2025;
  committee pages are protocols.
- **Podlaskie:** the BIP has moved to **bip.podlaskie.eu** (the same CMS as
  Mazowieckie and Śląskie; worth noting for tools/pl_regions.py, whose
  register is listed as gone): draft resolutions by sitting, with the
  month only, no date or agenda.
- **Lubuskie:** bip.lubuskie.pl has only a live-stream page for sittings.
- **Opolskie:** bip.opolskie.pl's robots.txt timed out three times again.

**Live run** (scratch store, 16 October 2026, 56 days): 10 of 16 read, 162
items (8 to be announced), 66 s, no gap. Mazowieckie 10, Śląskie 1,
Małopolskie 69, Dolnośląskie 2, Łódzkie 19, Pomorskie 13, Podkarpackie 45,
Kujawsko-Pomorskie 0, Zachodniopomorskie 1, Warmińsko-Mazurskie 2. None
matched taxonomy-pl: budgets, grants, statutes of regional hospitals and
road works, the ordinary business of a sejmik's month. Throttles: 3 s for
bip.slaskie.pl and sejmik.podkarpackie.pl, 1.5 s for bip.mazovia.pl and
bip.malopolska.pl.
