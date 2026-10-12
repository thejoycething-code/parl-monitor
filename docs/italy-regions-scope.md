# Italy's regional councils (IT3): scope and first build

12 October 2026, branch `regions-it`. Live-probed from the laptop (UK) with
`src/http.py`'s user agent (`CitizenGO-ParlMonitor/1.0 (contact:
cjoyce@citizengo.net)`), unreachable hosts retried from the Mac Mini (also
UK). Probes were a handful of requests per council; nothing was solved,
spoofed or forced. Raw replies of the collector's reads are archived under
`data/raw/` by the client.

## In one paragraph

Twenty regional councils (consigli regionali; five with special statute) plus
the two provincial councils of Trento and Bolzano, which hold most of
Trentino-Alto Adige's legislative power. No shared platform publishes their
bills: each council runs its own site, and only a few publish open data.
**Four are read now**: Lombardia (the council's own open data on
dati.lombardia.it, every act of the legislature with its stage dates),
Campania and Marche (clean HTML lists of the legislature's bills) and the
Provincia autonoma di Trento (open-data XML of bills, motions, orders of the
day and petitions). Together they hold 958 acts of the current legislatures;
22 are on our ground under taxonomy-it, among them five regional
assisted-dying bills (the "Liberi Subito" text, tabled in Lombardia, Campania
twice, Marche and Trento), a Lombardia bill on fertility preservation and
gamete freezing, two Marche bills reforming the consultori familiari, two
gender and sexuality education bills, and Trento's "culle per la vita"
motion. Sixteen councils are not read: six did not answer from the UK at all
(very likely geo-blocking), two refuse every agent in robots.txt or behind a
disallowed API, one serves an Akamai refusal, one a self-signed certificate,
and the rest publish only search forms or pages this pass did not reduce to a
list. No council publishes per-member votes in a form we read.

## Shared platforms and aggregators

| What | Finding |
|---|---|
| **dati.gov.it** (the national CKAN catalogue, harvesting every regional portal) | The way in. It found Lombardia's "CRL - ..." datasets (bills, laws, members, groups), Trento's council XML (bills, motions, orders of the day, petitions, questions), Calabria's members and organs CSVs, the Marche laws catalogue and Piemonte's Arianna laws. Campania's council has motions and questions 2003 to 2017 only (last modified 2024). Trap: the "Regione Toscana / Mozioni - Anno 2013-2024" and "Interrogazioni" datasets are the **Comune di Firenze**'s city council (data.comune.fi.it), not the regional council. |
| **Conferenza dei Presidenti delle Assemblee legislative** (parlamentiregionali.it) | WordPress news site (robots allows; `/feed/`), a page of regional electoral laws, no database of bills or motions. Not a source for acts. |
| **Normattiva** (normattiva.it, dati.normattiva.it) | State legislation. Regional laws are in each council's own database (Lombardia's "CRL - Leggi Regionali" dataset, Emilia-Romagna's Demetra, Piemonte's Arianna, Trento's own XML). Laws are the end of a bill's road, so Phase 1 reads bills, not laws. Note: Trento's provincial-law XML sits under `/normattiva/`, which its robots.txt disallows; it is not read. |
| **Video and session platforms** | Emilia-Romagna uses concilium.tv (assemblea-emr.concilium.tv); Lazio and Puglia use digital4democracy's "seduteonline". Video and live streams only; no act data. |
| **Senate / Camera** | No regional data. The Camera's annual "Rapporto sulla legislazione" covers regional laws in aggregate, not a feed. |

## Council by council

Population in millions (ISTAT, rounded). "UK" is reachability on 12 October
2026 from the laptop, and from the Mini where the laptop failed. Ranked by
CitizenGO relevance (size, and recorded activity on our ground: assisted
dying, consultori and abortion, gender and sex education, family policy)
and then by source quality.

| # | Council | Pop. | Source(s) | Format | robots.txt | UK | Status |
|---|---|---|---|---|---|---|---|
| 1 | **Lombardia** | 10.0 | dati.lombardia.it "CRL - Elenco PDL" (8muw-8v6p), Socrata SODA; also members, groups, laws | JSON API | Crawl-delay 1; API paths allowed | yes | **BUILT** |
| 2 | Lazio | 5.7 | consiglio.regione.lazio.it (`?vw=` PHP views) | HTML | disallows the Aula agendas and reports binaries and `?vw=elencolavoriaula` | yes | Not built: no bill list found outside the disallowed views in this pass; a later pass should look for a `?vw=` bill list |
| 3 | **Campania** | 5.6 | cr.campania.it/leggi-progetti/proposte (Drupal view, newest first, 10 a page); RSS is news only | HTML | allows | yes | **BUILT** (no status in the list) |
| 4 | Sicilia (ARS) | 4.8 | dati.ars.sicilia.it "Disegni di Legge" search | HTML form | the search backend `/icaro/` is **disallowed** | yes | Blocked by robots.txt. The Aula sitting pages on www.ars.sicilia.it are allowed (an agenda, later) |
| 5 | Veneto | 4.85 | consiglioveneto.it | | robots.txt itself refused | **403 Access Denied** (Akamai), laptop and Mini | Blocked: a bot refusal is never worked around |
| 6 | Emilia-Romagna | 4.45 | assemblea.emr.it (Plone/Volto); Demetra laws DB | HTML/JS | disallows `/search` and `/@@search` | yes | Not built: the acts database was not found without the disallowed search; worth a look at the site's REST API with the council's agreement |
| 7 | Piemonte | 4.25 | cr.piemonte.it; Arianna laws CSV (smartdatanet.it) | | not readable | timed out from the laptop; answered once from the Mini, then nothing | Unreachable |
| 8 | Puglia | 3.9 | consiglio.puglia.it | | **`User-agent: *` / `Disallow: /`** | yes | Blocked by robots.txt |
| 9 | Toscana | 3.65 | consiglio.regione.toscana.it (ASP.NET `default.aspx?nome=...` banca dati) | HTML forms | not read (timed out first, answered on retry) | slow | Not built. High relevance: Toscana's 2025 regional assisted-dying law (l.r. 16/2025). A later pass on its banca dati |
| 10 | Calabria | 1.84 | consiglioregionale.calabria.it/portale/BancheDati/PL (bill search forms), OpenData CSVs (members, organs) | HTML forms, CSV | allows these paths | yes | Not built: forms; feasible later (members CSV now) |
| 11 | Sardegna | 1.57 | consiglio.regione.sardegna.it (CNAME consregsardegna.it) | | | timed out (www host NXDOMAIN) | Unreachable |
| 12 | Liguria | 1.5 | the council's pages inside regione.liguria.it (Joomla), atom/rss of the council's home page | HTML, feed of news | no robots.txt (404) | yes | Not built: the feed is news; the acts pages were not reduced to a list |
| 13 | **Marche** | 1.48 | consiglio.marche.it iter degli atti, PdL index of the XII legislature (10 a page, with "Esito") | HTML (Latin-1) | no robots.txt (404) | yes | **BUILT** |
| 14 | Abruzzo | 1.27 | consiglio.regione.abruzzo.it | | | timed out, laptop and Mini | Unreachable |
| 15 | Friuli Venezia Giulia | 1.19 | consiglio.regione.fvg.it/cms/leggi/IterLeggiRicerca.aspx | ASP.NET form | disallows /pagine/attivita/ and others | yes | Not built: a postback form |
| 16a | **Provincia autonoma di Trento** | 0.54 | consiglio.provincia.tn.it/open_data/{DDL,MOZ,ODG,PET,INR}_opendata.xml | XML, rebuilt nightly | disallows `/opendata/` (not `/open_data/`) and `/normattiva/` | yes | **BUILT** (DDL, MOZ, ODG, PET; questions not read) |
| 16b | Provincia autonoma di Bolzano (Südtiroler Landtag) | 0.53 | consiglio-bz.org | JavaScript app | allows | yes | Not built: nothing without running its JavaScript; German first |
| 16c | Trentino-Alto Adige (regional council) | 1.08 | consiglio.regione.taa.it | HTML | disallows `/api/` | yes | Not built: few powers (the provinces legislate on our ground) |
| 17 | Umbria | 0.85 | alumbria.it | | | timed out, laptop and Mini | Unreachable |
| 18 | Basilicata | 0.53 | consiglio.basilicata.it (a JavaScript shell over `/consiglio-api`) | | **disallows `/consiglio-api`** | yes | Blocked by robots.txt |
| 19 | Molise | 0.29 | consiglio.regione.molise.it | | | self-signed certificate | Not read: TLS verification is never switched off |
| 20 | Valle d'Aosta | 0.12 | consiglio.vda.it | | | timed out, laptop and Mini | Unreachable |

Votes: none of the four built sources carries a roll call. Lombardia links
each Aula vote's PDF verbale (`link_testo_votazione_aula`, e.g.
`PDL_127_verbale_votazione_22092026.pdf`), which may name how each member
voted: a later phase (PDF) if Chris wants it. Members: Lombardia
("CRL - Consiglieri e Assessori", "Composizione dei Gruppi") and Calabria
publish members as open data; not read in Phase 1.

## As built (Phase 1)

- `tools/it_regions.py`: one collector, four readers, about twenty requests a
  week. Lombardia: one SODA query for the XII legislature's Pdl, Plp, Pda and
  Inp (254 acts), re-read whole. Trento: the four XML files, re-read whole
  (563 acts; keyed on the council's document id, as motions appear before
  they are numbered, and 10 of them have no title yet). Campania: list pages
  until the legislature changes (69). Marche: index pages until a short one
  (72; statutory bills marked `PDLS`, the law parsed from "Legge n. 6 del
  22/06/2026"). `--reclassify`, `--dry-run`, `--region`, a time budget, gaps
  in the `gaps` table and exit 3, as the national collector.
- `it_reg_acts` in `src/it_store.py` (one table, key
  `<region>/<legislature>/<council id>`: `lom/XII/pdl-212`,
  `tn/XVII/at3009929`, `cam/XII/36089`, `mar/XII/pdl-72`). Lombardia dates
  every stage, so its `status_date` is the source's; the others print only
  the current status, so a run that sees a change stamps the day it saw it
  (`status_seen` = 1), and a first sighting is never a change.
- Classification: `config/taxonomy-it.yaml` for `it` on the title (plus
  Trento's subject heading and Campania's categories), and
  `config/watchlist-it.yaml`'s new `regional:` section by act key. Nothing
  hand-classified; no taxonomy file edited.
- **The edition**: `src/editions/it.py` adds a "Regional councils" section
  (`post_render`) before the Watchlist, one sub-heading per council, with the
  usual item lines (key, date, areas, tier; title; who presented it, the
  committee, the status in the council's own words; source link), through
  the edition's noise filters. New = presented in the window; a stage move =
  an older act whose status changed in the window ("status changed on" for
  Lombardia, "status change seen by the weekly run of" elsewhere). National
  counts, the lead and the DM summary stay national; the DM links the full
  edition. The Coverage section names the four councils and points here.
- **Schedule**: a step in `jobs/it-weekly.sh` after `it_rollcalls.py`,
  before the edition (5-minute budget via `tools/collector_budget.sh`; the
  national collector's budget now leaves those 5 minutes). Its failure is a
  `[gap]` line, never the run's. `IT_RECLASSIFY=true` reclassifies regional
  acts too. **No new Mini job and nothing to install**: the runner picks it
  up on its next `git pull`.
- Coverage: `tools/coverage.py` watches `it_reg_acts.last_seen` (7 days plus
  4: the table is re-stamped every run, recess included).
- Tests: `tests/test_it_regions.py` (28 tests, fixtures under
  `tests/fixtures/it_regions/`, no network).

Measured on 12 October 2026, first full run into a scratch store: 958 acts,
22 on our ground (Lombardia 4 of 254, Campania 2 of 69, Marche 4 of 72,
Trento 12 of 563), about 40 seconds.

## Terms the regional titles suggest (APPLIED 12 October 2026, taxonomy-it v0.3)

Chris, 12 October 2026: "Add the Mexico and Italy keyword terms too", and
for gambling "gioco d'azzardo, tier 2 under marriage and family". Applied in
`docs/keyword-taxonomy-it.md` (v0.3) and regenerated; measured on the local
store and on the 958 acts of the 12 October regional archive:

- `educazione relazionale` added at area 6 tier 1 (`educazione
  all'affettività` and `educazione affettiva` were already terms). Trento's
  tn/XVII/at3008268 now matches (it had no area before); nothing else moved.
- `consultorio` (singular) added at area 1 tier 2, vetoed for legal, tax,
  veterinary and labour advice offices: Trento tn/XVII/at1942291 (more
  consultorio services) now matches.
- `gioco d'azzardo` (with `giochi d'azzardo`, TESEO's `giochi d' azzardo`,
  `ludopatia`, `ludopatie`, `azzardopatia`) added at area 9 tier 2, triage
  decides: Marche pdl-68 and Trento at1942284 now match, with 9 national
  bills and 2 Swiss Italian titles.
- No false positives in any of the 15 new matches. The stored `it_reg_acts`
  rows pick the new terms up on the next weekly (every council's list is
  re-read and classified as it is stored), or at once with
  `python3 tools/it_regions.py --reclassify` on the store that holds them;
  the laptop store has no regional rows yet. The 9 national bills need one
  weekly run with `IT_RECLASSIFY=true` (it reclassifies bills, divisions and
  regional acts together).

## Shared files touched

- `src/db.py`: `it_reg_acts` added to `db.TABLES` (one line).
- `tools/coverage.py`: one FEEDS line.
- `src/it_store.py`: the new table, and `watchlist()` reads the `regional`
  section as well as `bills` (Italy's own module).
- `src/editions/it.py`, `jobs/it-weekly.sh`, `config/watchlist-it.yaml`
  (an empty `regional:` section), `docs/italy-scope.md`,
  `docs/country-parity-handover.md`, `docs/mac-mini.md` (one table row).

## Waiting on Chris

1. **Order for the next councils.** Feasible with more work: Lazio and
   Toscana (HTML, find the list), Calabria and FVG (search forms), the Aula
   agendas of Sicilia, Marche and Calabria (a regional week ahead). Each is a
   reader in `tools/it_regions.py`.
2. **The blocked six** (Veneto's Akamai refusal; Puglia's, Basilicata's and
   ARS's robots.txt; Molise's certificate) and **the unreachable five**
   (Abruzzo, Piemonte, Sardegna, Umbria, Valle d'Aosta: no answer from UK
   addresses): ask the councils' open-data offices, or accept the gap. A
   runner on an Italian address would probably reach the unreachable five;
   that is a new service, so only on your say-so.
3. **Lombardia's vote PDFs** as a later phase (per-member votes, if the
   verbale prints them).
4. **The proposed terms** above.
5. **Regional watchlist entries**: add acts by key under `regional:` in
   `config/watchlist-it.yaml` (e.g. the Liberi Subito bills, if they should
   lead even when nothing changes).
