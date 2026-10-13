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
| wp | Wielkopolskie (3.5 m) | edziennik.poznan.uw.gov.pl: answers (no sejmik act in Sep-Oct) | bip.umww.pl, category pages; slow, read timeouts on 13 October | page "Imienne wykazy głosowań" | journal read |
| ma | Małopolskie (3.4 m) | edziennik.malopolska.uw.gov.pl: answers | bip.malopolska.pl is an Angular application (empty shell to a plain client) | - | journal read |
| ds | Dolnośląskie (2.9 m) | edzienniki.duw.pl: answers | bip.umwd.dolnyslask.pl does not resolve; bip.dolnyslask.pl is a React application | - | journal read |
| ld | Łódzkie (2.4 m) | dziennik.lodzkie.eu: answers | bip.lodzkie.pl, one table of the whole term (number, date, title, PDF), 396 resolutions since May 2024 | eSesja (blocked) | **both read** |
| pm | Pomorskie (2.3 m) | edziennik.gdansk.uw.gov.pl: answers | bip.pomorskie.eu, React application (the same shell as Dolnośląskie) | - | journal read |
| pk | Podkarpackie (2.1 m) | edziennik.rzeszow.uw.gov.pl: answers | bip.podkarpackie.pl, an index of sittings, each with its resolutions as attachments ('XXXI/520/26 - w sprawie ...'); Crawl-delay 3; sittings before 22 May 2026 on archiwumbip.podkarpackie.pl | page "Imienne wykazy głosowań" | **both read** |
| lu | Lubelskie (2.0 m) | edziennik.lublin.uw.gov.pl: answers | umwl.bip.lubelskie.pl answers (a 1.1 MB home page); register layout not parsed yet | - | journal read |
| kp | Kujawsko-Pomorskie (2.0 m) | edzienniki.bydgoszcz.uw.gov.pl: **connection times out** from the UK (three tries on 13 October; edziennik.bydgoszcz.uw.gov.pl answers 403) | bip.kujawsko-pomorskie.pl answers; register and "Wydruki głosowań" pages listed, not parsed | "Wydruki głosowań" | not read |
| zp | Zachodniopomorskie (1.6 m) | e-dziennik.szczecin.uw.gov.pl: answers (publisher printed in the genitive, "Sejmiku Województwa ...") | bip.wzp.pl answers; "Uchwały Organów Województwa" article, not parsed | - | journal read |
| wn | Warmińsko-Mazurskie (1.4 m) | edzienniki.olsztyn.uw.gov.pl: answers | bip.warmia.mazury.pl answers (robots.txt allows all), categories for stanowiska and named votes, not parsed | category 116 | journal read |
| sk | Świętokrzyskie (1.2 m) | edziennik.kielce.uw.gov.pl: answers | bip.sejmik.kielce.pl answers; the VII-term register page (175 KB) is a long menu, not parsed yet | - | journal read |
| pd | Podlaskie (1.1 m) | edziennik.bialystok.uw.gov.pl: answers (genitive publisher) | bip.wrotapodlasia.pl does not resolve (NXDOMAIN); new address not found | - | journal read |
| lb | Lubuskie (1.0 m) | dzienniki.luw.pl (linked from bip.lubuskie.uw.gov.pl): answers | bip.lubuskie.pl answers; '/akty/' pages, not parsed | - | journal read |
| op | Opolskie (0.95 m) | duwo.opole.uw.gov.pl: answers | bip.opolskie.pl: connection times out | minutes as PDFs (named results printed in the minutes) | journal read |

Ranking for the next registers, by population and our ground: Małopolskie
and Lubelskie (both adopted the 2019-20 declarations; Małopolska needs its
Angular JSON backend found and checked against robots.txt), Świętokrzyskie
(same history; plain HTML), Wielkopolskie (plain HTML, slow), then
Warmińsko-Mazurskie and Lubuskie (plain HTML).

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

## Not built, and why

- **Twelve registers:** two hosts do not answer (Opolskie times out,
  Podlaskie's BIP domain no longer resolves), three are JavaScript
  applications (Małopolskie, Pomorskie, Dolnośląskie; their JSON backends
  were not looked for), seven are plain HTML not parsed yet (Wielkopolskie,
  Lubelskie, Kujawsko-Pomorskie, Zachodniopomorskie, Warmińsko-Mazurskie,
  Świętokrzyskie, Lubuskie). Their published acts still arrive through the
  journals; their non-binding positions do not.
- **The Kujawsko-Pomorskie journal:** no answer from the UK. Listed, not
  read by default; `python3 tools/pl_regions.py --region kp` tries it. Worth
  one try from the Mini.
- **Roll-call votes and members (phase 2):** published per sitting as PDFs
  (Podkarpackie, Wielkopolskie, Warmińsko-Mazurskie, Kujawsko-Pomorskie
  "Wydruki głosowań", Opolskie inside its minutes) or on eSesja (blocked by
  a bot check). A PDF reader per layout, like the provinces' Hansard PDFs,
  is the route; councillors' lists are plain BIP pages.
- **Draft resolutions (projekty uchwał):** in each sitting's materials, on
  eSesja or as attachments; phase 2 with the votes.

## Waiting on Chris

1. **Taxonomy terms (proposal, not generated):** the Polish list has no
   term for the Family Charter. Proposed for `docs/keyword-taxonomy-pl.md`,
   area 9, tier 1: `"Kart* Praw Rodzin*"` (matches "Samorządowa Karta Praw
   Rodzin" and "Samorządowej Karty Praw Rodzin"); area 5, tier 1:
   `"stref* wolne od ideologii"`. The LGBT declarations already match
   ("LGBT*") and in-vitro programmes match ("zapłodnieni* pozaustrojow*",
   "in vitro", "leczeni* niepłodności"). Regenerate with
   `python3 tools/generate_taxonomy.py --lang pl` once approved.
2. **The regional watchlist:** seed `regional:` in
   `config/watchlist-pl.yaml` from the first live run (keys as above), for
   repeals whose titles name only a resolution number.
3. **Which registers next:** the ranking above suggests Małopolskie,
   Lubelskie and Świętokrzyskie (the 2019-20 declarations' sejmiki).
