# Switzerland: the 26 cantonal parliaments (CH7)

Scoped, probed and built on 13 October 2026 from the laptop, on branch
`regions-ch`, following `.claude/regions-brief.md`. Every request went
through `src/http.py` with the honest CitizenGO user agent, and every
collector request goes through `src/robots_guard.GuardedClient` (robots.txt
read once per host per run, no exemptions). Live runs went into a scratch
database inside the worktree, never the store.

**Built:** `tools/ch_cantons.py` (one reader per canton, a common store
step), two additive tables in `src/ch_store.py` (`ch_canton_acts`,
`ch_canton_divisions`, declared in `db.TABLES`), a `cantons` section in
`config/watchlist-ch.yaml` (five seeded entries, for Chris to review), a
**Cantons** section in the Swiss edition (`src/editions/ch.py`, through the
existing `Country.extra_sections` hook), a step in `jobs/ch-weekly.sh`,
entries in `tools/coverage.py`, and `tests/test_ch_cantons.py` on trimmed
real pages in `tests/fixtures/ch_cantons/`.

**Update, 13 October 2026 (branch `access-routes`, below "Alternative
routes"):** Basel-Stadt, Basel-Landschaft, St. Gallen and Thurgau are now
read from their parliaments' own business systems, on hosts whose
robots.txt allows us, and Aargau from its official law collection (adopted
acts only). The open-data portals and www.ag.ch/grossrat are still never
asked. **Covered now: ten of 26**, about 6.4 of 9 million people.

**Update, 13 October 2026 (branch `permissions-1013`, below "Written
permissions"):** Basel-Stadt and Thurgau wrote back. Both allow our targeted
use of their Opendatasoft APIs, though robots.txt there disallows `/api/`.
Both cantons are now read from `data.bs.ch` and `data.tg.ch` (the Grand
Council datasets only, recorded in `src/robots_guard.PERMISSIONS`), **with
every member's vote**; the pages above are their fallback. Basel-Landschaft
and St. Gallen (no reply yet) and Aargau stay as they were.

**Update, 13 October 2026 (branch `bs-gribs`, below "Basel-Stadt: the
Grand Council's own exports"):** Peter Frankenbach, the Grand Council's IT
lead, offered its raw data exports on `grosserrat.bs.ch` (robots.txt allows
them). Basel-Stadt's business is now read from those exports first;
`data.bs.ch` (written permission) keeps the votes and is the business
fallback; the Grand Council's pages are the last resort.

**Update, 13 October 2026 (branch `ch-bl-ods`, below "Basel-Landschaft:
data.bl.ch"):** Basel-Landschaft wrote back too (Johannes Hool,
Statistisches Amt). The Landrat is now read from `data.bl.ch` (13090
business, 13140 authors, 13130 documents, 13080 **every member's vote**),
recorded in `src/robots_guard.PERMISSIONS`; `baselland.talus.ch` is the
fallback. St. Gallen (no reply yet) and Aargau stay as they were.

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
| Aargau (0.73 m) | Grosser Rat | `www.ag.ch/grossrat/grweb/` | HTML (GRWeb) | **`Disallow: /grossrat`** | **no**; adopted acts **yes** via `gesetzessammlungen.ag.ch` (below) |
| St. Gallen (0.53 m) | Kantonsrat | `daten.sg.ch` datasets "Geschäfte im Kantonsrat", "Abstimmungen im Kantonsrat" | Opendatasoft API | **`Disallow: /api/`** | **no**; **yes** via `www.ratsinfo.sg.ch` (below) |
| Geneva (0.52 m) | Grand Conseil | `ge.ch/grandconseil/searchm/search/index?q=<term>&date=y1` | HTML search, one page per term | none (the URL returns a web page, read as no rules) | **yes** |
| Lucerne (0.43 m) | Kantonsrat | `www.lu.ch/kr/parlamentsgeschaefte` (ASP.NET form posting to `/api/klu/search/result`); members, sessions and interests as CSV on opendata.swiss | HTML form, undocumented JSON | allows | not yet |
| Ticino (0.36 m) | Gran Consiglio | `www4.ti.ch/poteri/gc/attivita/ordine-del-giorno/` | HTML | allows it; **disallows the acts search** (`/poteri/gc/ricerca-messaggi-e-atti/ricerca/`) | **yes** (order of the day) |
| Valais (0.36 m) | Grand Conseil / Grosser Rat | `parlement.vs.ch/app/` (Sitrox single-page app, backend `api/fe/v1/search/...`) | undocumented JSON | empty (no rules) | not yet |
| Fribourg (0.34 m) | Grand Conseil | `www.fr.ch/gc` | Drupal pages | disallows `/fr/`, `/search/` and `?page` | not yet |
| Basel-Landschaft (0.30 m) | Landrat | `data.bl.ch` datasets 13090 (business since 2017), 13140 (authors), 13130 (documents), 13080 (member votes since 2018) | Opendatasoft API | **`Disallow: /api/`** | **yes, with written permission (13 Oct 2026)**, business and members' votes; fallback `baselland.talus.ch` (below) |
| Solothurn (0.29 m) | Kantonsrat | `so.ch/parlament/` | TYPO3 pages | allows | not yet |
| Thurgau (0.29 m) | Grosser Rat | `data.tg.ch` datasets sk-stat-140 (business), sk-stat-136 (votes) | Opendatasoft API | **`Disallow: /api/`** | **yes, with written permission (13 Oct 2026)**, business and members' votes; fallback `grgeko.tg.ch` (below) |
| Graubünden (0.20 m) | Grosser Rat | `www.gr.ch` (SharePoint) | HTML | disallows search and list views | not yet |
| Basel-Stadt (0.20 m) | Grosser Rat | the Grand Council's exports `grosserrat.bs.ch/component/gribs` (ges, dok, vor, siz; offered 13 Oct 2026; zuw, adr and gre since 15 Oct 2026, daily download allowed); `data.bs.ch` datasets 100311 (business), 100313 (documents), 100314 (steps), 100186 (votes, per member), 100086 (motions), members, agendas | JSON/CSV exports; Opendatasoft API | exports allowed; data.bs.ch **`Disallow: /api/`** | **yes**: business from the Grand Council's exports; members' votes from data.bs.ch (written permission, 13 Oct 2026); fallbacks data.bs.ch, then `grosserrat.bs.ch` pages (below) |
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

## Alternative routes (13 October 2026, branch `access-routes`)

Chris, 13 October 2026, on the five blocked cantons: "Email all and explore
external ways too". Every route below was asked from the laptop with the
honest user agent, robots.txt read first; the collector asks robots.txt
again every run (`GuardedClient`, no exemptions). Nothing was bypassed: the
open-data portals and www.ag.ch/grossrat are never asked.

### Routes tried

| Route | Outcome |
|---|---|
| **opendata.swiss** (the federal portal) | Its dataset pages for these parliaments (e.g. "Grosser Rat: Geschäfte", "Abstimmungen im Kantonsrat St.Gallen", "Abstimmungen im Grossen Rat des Kantons Thurgau") only **link back** to the cantons' `/api/v2/.../exports/` URLs; no file is hosted on opendata.swiss. `ckan.opendata.swiss` disallows `/api/` itself. **Does not help.** |
| The portals' other paths | `data.bs.ch`, `data.bl.ch`, `daten.sg.ch`, `data.tg.ch` also disallow `/explore/dataset/*/download` and `/explore/download`: there is no file route on the portals. |
| Official gazettes | `www.kantonsblatt.ch` (Basel-Stadt), `www.amtsblattportal.ch` (the shared platform), `www.publikationen.sg.ch` (St. Gallen) and `amtsblatt.tg.ch` (Thurgau) all answer `Disallow: /` to every agent. **Not used.** |
| LexFind (`www.lexfind.ch`) | robots.txt allows everything; an aggregator of all cantonal law. Not needed: Aargau's own collection answers (below). |
| **grosserrat.bs.ch** (Basel-Stadt's Grand Council) | robots.txt disallows `/api/` and system folders only. `/ratsbetrieb/neue-vorstoesse` (the motions, interpellations, written questions lodged for each of the last three sittings) and `/ratsbetrieb/neue-berichte-und-schreiben` (every weekly Grossratsversand since February: commission reports, the government's Ratschläge and written answers, each with its business number). **Built (`bs`).** A business's own page loads its content from `/api/` (disallowed): not read. The vote results page lists each vote with a PDF per vote, which has no text layer: not read. |
| **baselland.talus.ch** (the Landrat's "Politik Baselland" business system) | robots.txt disallows only `/*searchTerm=` and some named bad bots. `/de/politik/cdws/neuste-geschaefte.php`: about 200 newest documents (six weeks): motion, postulate and interpellation texts, Vorlagen, committee reports and decisions, answers, each with the business number, title and date. **Built (`bl`).** |
| **www.ratsinfo.sg.ch** (St. Gallen's Kantonsrat RIS) | robots.txt answers the app's page (no rules). The RIS page loads `/api/config`, `/api/businesses`, `/api/business_types`, `/api/process_states`, `/api/votings` and `/api/votings/<id>`: 6,741 businesses with type, state and dates, and 4,343 recorded votes with the tally and every member's ballot. **Built (`sg`):** business changed in the last 60 days, and the tallies of votes (last 120 days) on business on our ground. Ballots are not stored (the cantonal table holds tallies). |
| **grgeko.tg.ch** (Thurgau's Grosser Rat business database) | robots.txt `Disallow:` (empty: allows all). `/de/web/grgeko/pendente-geschaefte`: the 95 pending businesses with the registration date, the register number and the title (with authors). **Built (`tg`).** The search and per-type lists are JSF post-backs: not read. The newest pending item is dated 27 May 2026, so the list may lag. |
| **gesetzessammlungen.ag.ch** (Aargau's official law collection, LexWork) | robots.txt disallows its search paths only. `/api/de/change_documents/lightweight_index` (what the collection's app loads): every act published in the Aargauische Gesetzessammlung since 2007 with its AGS number, title and date. **Built (`ag`):** acts since January 2025 (laws, decrees, ordinances). The Grosser Rat's business itself stays on the disallowed `/grossrat`. |

### First live read (13 October 2026, scratch database)

| Canton | Read | On our ground |
|---|---|---|
| St. Gallen | 198 businesses (60 days of changes) | 5: the motion for a legal basis for assisted suicide (42.26.17), the motion on mosques and foreign influence (42.26.22), childcare and individual taxation |
| Basel-Landschaft | 199 businesses | 4: interpellation on the conversion-practices ban (2026/6529), palliative care, sex work, childcare tax |
| Basel-Stadt | 539 businesses (Versand since February, three sittings' motions) | 18: anonymous births (26.5228), the "LGBTI label" motion, religion or ethics classes, prostitution and trafficking, palliative care |
| Thurgau | 95 pending | 2: the motion to restrict irreversible gender reassignment to adults (2024/117), the interpellation on abortion (2024/261) |
| Aargau | 122 acts published since 2025 | 2 (family allowances) |

About 10 requests and 9 seconds for the five. No St. Gallen vote in the last
120 days was on business on our ground, so no tally was read.

## Written permissions (13 October 2026, branch `permissions-1013`)

Chris wrote to the four Opendatasoft cantons on 13 October. Two replied the
same day, and Chris approved acting on both:

| Canton | Who | What they wrote | Condition we keep |
|---|---|---|---|
| Basel-Stadt | Orhan Saeedi, Statistisches Amt (data.bs.ch) | "Sie können sehr gerne die API benutzen unter Einhaltung der Lizenz. Das heisst sie müssen die Datenquelle irgendwie verlinken." If the API is slow, download in batches. | CC BY 4.0: every Basel-Stadt item and vote in the edition carries a "Source:" link to its dataset, and the Cantons coverage line links all four datasets. Votes are exported in 14-day batches |
| Thurgau | Felix Lorenz, Amt für Daten und Statistik (ogd@tg.ch) | robots.txt targets crawlers indexing the whole portal; targeted API retrieval of individual datasets is explicitly intended; "CitizenGO-ParlMonitor/1.0" may retrieve the Grosser Rat datasets about weekly; the licence allows commercial and non-commercial use. | About weekly (a step of `jobs/ch-weekly.sh`); CC0, the dataset is linked all the same |

How it is recorded: `src/robots_guard.PERMISSIONS` lists each permission with
its URL prefixes (one dataset each: Basel-Stadt 100311, 100313, 100314,
100186; Thurgau sk-stat-140, 141, 136, 139), the grantor, the date, the
condition and a pointer to docs/robots-runtime.md ("Written permissions").
Only those prefixes skip the robots.txt read; any other path on either host
is still asked and refused.

What each API gives (read by `tools/ch_cantons.py`, `fetch_baselstadt_api`
and `fetch_thurgau_api`, JSON exports filtered server-side, 3 s between
requests):

| | Basel-Stadt (data.bs.ch) | Thurgau (data.tg.ch) |
|---|---|---|
| Business | 100311 Geschäfte: number, type, title, author with party and co-authors, begun and ended dates, state. Read: begun or ended in the last 45 days, or touched in them by a document or a step | sk-stat-140: number, type, title, received and closed dates, state, where it is pending, answer date, Erheblicherklärung and other flags as printed. Read: received or closed in the last 45 days, and everything pending |
| Status | the newest dated document (100313, e.g. "Text Anzug", "Schriftliche Antwort") or Grosser Rat step (100314, the step's own words, e.g. "Überweisung an RR Frist: 23.12.2026"); future sittings are not a status | the dataset's state, "pendent bei", the newest dated step, the flags (e.g. "Erheblicherklärung: nein") |
| Authors | in 100311 itself | sk-stat-141 Vorstösser (first signatories and co-signatories with party) |
| Votes | 100186 Live-Abstimmungsergebnisse: **every member's vote** (J, N, E, A, P: yes, no, abstain, absent, president), the Fraktion at the vote, the published counts, the business it was on, a link to the vote's own record | sk-stat-136: **every member's vote** (Ja, Nein, Enthaltung, absent, or the option chosen in a vote between motions, e.g. "Antrag GFK"), the Fraktion at the vote, the day and agenda item; no totals, so the counts are tallied from the members' votes |
| Weekly volume | 3 exports for business (about 1,000 rows of which a few hundred kept), then votes from the newest stored day: one or two 14-day batches (about 100 rows per vote) | 1 export for business (about 130 rows), 2 to 3 for signatories, then votes from the newest stored day in quarterly batches (the first read: the 2024-2028 legislature, about 300 votes) |
| Stored | `ch_canton_acts` (dated; `source_url` = the dataset link refined to the business), `ch_canton_divisions` (`counts_from` = published), `ch_canton_votes` (one row per member) | the same; `counts_from` = tallied; keys `tg/<legislature>/<GRG number>`, the same as the pending list's, so the page rows were updated in place |

First live read (13 October 2026, scratch database, never the store):
Basel-Stadt 326 businesses in the 45-day window, 9 on our ground (anonymous
births 26.5228, the facial-recognition Anzug, written questions on the
safety of queer people, sexual exploitation of minors, ethics or religion
classes, femicide prevention, prostitution's withholding tax), 63 votes
since 14 August with 6,300 members' votes; the vote on the anonymous-births
Anzug (23 September, 44-38-10) shows the Fraktion split and six SP members
against their Fraktion. Thurgau 104 businesses (62 of them the pending list's,
updated in place, 42 new), 2 on our ground (the gender-reassignment motion
2024/117, closed on 16 September 2026, "Erheblicherklärung: nein"; the
abortion interpellation 2024/261, answered 26 May 2026), 302 votes since June
2024 with 39,357 members' votes. Thurgau's vote dataset was last updated on
26 June 2026 and ends on 29 April 2026: it lags the sittings by months, so
recent Thurgau votes arrive late. A second run read one batch per canton
(27 and 4 votes re-read): about weekly volume.

The fallback: if an API fails, the canton is read from its parliament's
own pages (grosserrat.bs.ch, grgeko.tg.ch) as before, with one gap line
saying so; Basel-Stadt's API rows are dated, so they are never a baseline.

## Basel-Landschaft: data.bl.ch (13 October 2026, branch `ch-bl-ods`)

Johannes Hool (Project Manager, Statistisches Amt / Office for Data and
Statistics, Finance and Church Directorate) wrote on 13 October 2026, in
substance: our client "CitizenGO-ParlMonitor/1.0" is authorised to retrieve
the Landrat's open data records, voting results included, through the
data.bl.ch API, and large-scale retrieval is fine; the robots.txt `/api/`
rule targets generic crawlers, and requests to specific, deliberately
selected dataset endpoints count as API-client usage, so it does not apply;
no robots.txt change is needed, the email is the confirmation.

The Landrat datasets, found through the portal's sitemap (`/sitemap.xml`,
allowed) and the dataset pages on opendata.swiss, never by crawling `/api/`.
All are published by the Landeskanzlei des Kantons Basel-Landschaft, updated
nightly, under opendata.swiss `terms_by` ("Freie Nutzung. Quellenangabe ist
Pflicht": free use, commercial allowed, the source must be cited):

| Dataset | Title | Rows (13 Oct 2026) | Read |
|---|---|---|---|
| 13090 | Landratsgeschäfte (seit 2017) | 6,412 | yes: number (Laufnummer), type and Vorstoss type, title, state, Landrat standing, committee, begun, ended, referred (Überweisung), the business id. Begun or ended in the last 45 days, and everything in progress (about 650 rows) |
| 13140 | Beteiligungen von Landratsmitgliedern an Vorstössen (seit 2017) | 5,379 | yes: authors (Urheber/in) and the count of co-signatories (Mitunterzeichner/in) of motions and questions not yet stored with them ("Zuständig", the member of government in charge, is not an author) |
| 13130 | Unterlagen zu Landratsgeschäften (seit 2017) | 17,676 | yes: documents dated in the window; a business's newest one is its latest step |
| 13080 | Abstimmungsverhalten der Landratsmitglieder (seit 2018) | 266,253 | yes: **every member's vote** (Ja, Nein, Enthaltung, abwesend), party and Fraktion, the subject (e.g. "Überweisung", "Schlussabstimmung LRB"), the time, the business and agenda item. No totals: counts are tallied from the members' votes. Each row's `abstimmung_id` is the member's, so a vote is its agenda item, time and subject |
| 13100, 13110, 13120, 13150, 13160 | interests, memberships, agendas, bodies | | no (not in the permission entry; still refused at run time) |

Keys: `bl/<Laufnummer>`, the same as the talus pages', so the rows read
there are updated in place. Items link the Landrat's page of the business
on baselland.talus.ch (13090's `geschaeft_id` is talus's `gid`); `source_url`
is the dataset link the licence asks for. A vote's act comes through its
`geschaeft_id` (this run's rows, the store, or one look-up in 13090).

First live read (13 October 2026, scratch database, never the store): 650
businesses, 16 on our ground (among them the interpellation on the
conversion-practices ban 2026/6529, palliative care 2026/7052, sex work
2026/4870); votes from the start of the 2023-2027 legislature (first vote 31
August 2023) to 24 September 2026: 1,076 votes, 96,786 members' votes, every
one tied to its business, in 1 minute 46 seconds (14 quarterly exports, 3 s
apart). Later weekly runs re-read from the newest stored vote day: one export.
The vote dataset reaches 2018; earlier legislatures are not read.

## Basel-Stadt: the Grand Council's own exports (13 October 2026, branch `bs-gribs`)

**The offer.** On 13 October 2026 Peter Frankenbach, IT lead and webmaster
of the Parlamentsdienst des Grossen Rates Basel-Stadt, wrote that
`data.bs.ch`'s robots.txt is outside his control and offered instead the
Grand Council's own raw data exports of its business system (GRIBS):

- <https://grosserrat.bs.ch/component/gribs/?chosentable=ges&view=exporter&Itemid=105&format=csv>
- <https://grosserrat.bs.ch/component/gribs/?chosentable=ges&view=exporter&Itemid=105&format=json>

and said there are further export links matching the portal's datasets (we
asked him for the votes, documents/status and members links). Chris:
"temporarily switch to his exports and then find something else for
ongoing builds and data if needed". `grosserrat.bs.ch`'s robots.txt allows
`/component/` for `*` (it disallows `/administrator/`, `/api/`, system
folders, and GPTBot, ChatGPT-User, Google-Extended, CCBot and PerplexityBot
by name); our agent is allowed, so the per-run guard asks robots.txt and no
exemption or permission entry is needed. (The URL with `/gribs/?` answers a
302 to `/gribs?`; the collector asks the canonical form.)

**What the Geschäfte export contains (live, 13 October 2026).** The whole
table, every business since 1988: **21,197 rows** (998 pending, `status`
B; 20,199 closed, A), 7.8 MB as JSON, 4.2 MB as CSV, the same rows in both.
Fields: `idnr`, `beginn` (epoch seconds at midnight UTC; business lodged
for the next sitting is dated that sitting, e.g. 14 October), `ende` (0 or
epoch seconds, some with a time), `laufnr` (the business system's running
number, which the other tables refer to), `signatur` (the business number,
e.g. 26.5228, the same key as data.bs.ch's `signatur_ges`), `status` (A/B),
`titel` (the full title, author included: "Anzug Andrea Strahm und Marina
Schai betreffend ..."), `bempublic` (empty), `ga_rr_gr` (the type:
Interpellation 4,830, Anzug 4,511, Schriftliche Anfrage 2,652, Bericht,
Ratschlag, Wahl, Motion, Kleine Anfrage, Petition, ...; empty for 377
rows), `departement`, `geseigner` (always Parlamentsdienst), `gr_urheber`
(the author's member number), `gr_urheber_name` (surname and first name run
together, "ThüringJoël": not used; the author is read from the title). No
party, no co-authors.

**Other tables (task: probe politely, at most ten requests; eight were
sent).** The exporter's own form (`/component/gribs?view=exporter&Itemid=105`,
one request) lists its tables: `ges` Geschäfte, `dok` Dokumente, `vor`
Vorgänge, `zuw` Zuweisungen, `kon` Konsorten, `adr` Personen / Adressen,
`gre` Gremien, `mit` Mitgliedschaften, `intr` Interessenbindungen, `par`
Parteien, `siz` Sitzungen, `unt` Unterlagen, `gr_sitzung` Sessionen,
`gr_tagesordnung` Tagesordnungen, `gr_tagesordnung_pos`
Tagesordnungs-Traktanden. **There is no votes table.** Fetched once each:
`dok` (56,858 documents, 11 MB: `dok_nr`, `ges_laufnr`, `titel`, `url` of
the PDF, `datum` dd.mm.yyyy, `signatur`), `vor` (45,159 Grosser Rat steps,
12 MB: `ges_laufnr`, `siz_nr`, `vermerk` the decision in the Council's
words, `beschlnr`, `titel`), `siz` (1,287 sittings, 65 KB: `siz_nr`,
`datum`). The requests were: the two `/gribs/?` forms (302), `ges` JSON,
`ges` CSV, the exporter form, `vor`, `dok`, `siz`. Not fetched: `adr`,
`mit`, `kon` and the rest (the collector has no use for members' addresses;
members' names and Fraktion come with each vote). Guessed names such as
`abstimmungen`, `abs` or `sta` were not tried: the form lists every table.

**Wired.** `tools/ch_cantons.py fetch_baselstadt_gribs`: `ges` is the
primary Basel-Stadt business list (JSON; the CSV of the same table if the
JSON fails), `dok` and `vor` + `siz` give each business its newest dated
document or step, exactly as data.bs.ch 100313/100314 did (the fixtures'
seven businesses come out with the same statuses and dates from both).
One request per table per run (4 a week, about 31 MB, 3 s apart, not
archived under `data/raw`). The rows are diffed against the store: only
business begun, ended or touched (document or step) in the last 45 days,
or closed since we stored it open, is kept (326 of 21,197 in the first live
read, the same 326 the API gave: 0 new, 0 moved against the API rows
already in the scratch store). Votes stay on data.bs.ch 100186 (the
exporter has none). Edition: Basel-Stadt business items link to the Grand
Council's page of the business (`https://grosserrat.bs.ch/?gnr=<number>`,
the "Source:" line names grosserrat.bs.ch); votes keep the data.bs.ch
dataset link, as its CC BY licence requires; the coverage line links the
four exports and names Frankenbach's offer.

### Further exports: committee assignments and members (15 October 2026)

**The permission.** Peter Frankenbach (email of 13 October 2026) gave
further exports and allowed a **daily** download (the exports are rebuilt
nightly around 03:00): `zuw` (Zuweisungen an Gremien), `dok` (already read)
and `adr` (Ratsmitglieder), at
`https://grosserrat.bs.ch/component/gribs/?chosentable={zuw|dok|adr}&view=exporter&Itemid=105&format={csv|json}`.
Recorded in docs/robots-runtime.md ("Written permissions", Basel-Stadt daily
downloads). No `Permission` entry: robots.txt allows `/component/` and is
still asked every run.

**Measured live, 15 October 2026.** `zuw` JSON: 25,620 assignments (4.9 MB):
`ges_laufnr` (the business), `uni_nr_an` (the body it is assigned to),
`titel` (the assignment's words: "Überweisung", "Überweisung RA", "Zum
Bericht"), `status` (A done, B open, F, X), `termin` (deadline), `erledigt`
(completed); no date of assignment. The body numbers are not in `adr`; the
exporter's public form also lists `gre` (Gremien, 90 rows, 16 KB: number,
short name, name, type), which names them (811 Gesundheits- und
Sozialkommission, 795 BKK, 842 UVEK ...). The Regierungsrat and the plenary,
the commonest recipients, are not Gremien there and are not treated as
committees. `adr` JSON: 439 people (224 KB): members past and present and
some officials, with number, name, party (`partei_kname`) and, besides,
addresses, phone numbers and e-mail addresses. Only number, name and party
are read, in memory; nothing from `adr` is stored as such and the exports
are not archived.

**Wired** (`fetch_baselstadt_gribs`, branch `almg-bs-extra`): each business's
`committee` is the Gremium its open assignment names (else the last one it
was assigned to); an assignment completed in the window is a step ("Zuweisung
an Gesundheits- und Sozialkommission (Überweisung): erledigt"); the first
author (`ges.gr_urheber`) gets name and party from `adr`; every member's vote
from data.bs.ch 100186 gets the member's party from `adr`
(`ch_canton_votes.party`, beside the Fraktion at the vote, which is kept as
printed). Three more requests a week (about 5 MB), read weekly in
jobs/ch-weekly.sh, inside the daily allowance. If `adr` or `zuw`/`gre`
fails, a gap line says so and the business is read without it.

**Dataset links** (15 October 2026): data.bs.ch and data.bl.ch now answer
`/explore/dataset/<id>/` with a 302 to `/explore/assets/<id>/`. Every
Source line and the coverage line link the assets page directly (the item
filter in the form the portal redirects to, `?refine=signatur_ges%3A<nr>`);
rows stored earlier are shown the same way (`src/editions/ch.direct_url`).

### Ongoing source plan for Basel-Stadt

1. **Primary: the Grand Council's own exports** (`grosserrat.bs.ch/component/gribs`,
   offered by the Parlamentsdienst, 13 October 2026; robots.txt allows
   them): business (`ges`), documents (`dok`), steps (`vor` + `siz`),
   committee assignments (`zuw`, named by `gre`) and members (`adr`). When
   Frankenbach sends a votes export, it replaces data.bs.ch 100186 here.
2. **Secondary: `data.bs.ch`'s API under the Statistisches Amt's written
   permission** (Orhan Saeedi, 13 October 2026, `src/robots_guard.PERMISSIONS`):
   votes with every member's vote (100186) now; business, documents and
   steps (100311, 100313, 100314) when an export fails (a gap line says
   which).
3. **Last: the Grand Council's pages** (`/ratsbetrieb/neue-vorstoesse`,
   `/ratsbetrieb/neue-berichte-und-schreiben`), if both of the above fail.

Both permissions are recorded: the data.bs.ch permission in
`src/robots_guard.PERMISSIONS` and docs/robots-runtime.md ("Written
permissions"); the Grand Council's offer here and in docs/robots-runtime.md
(it needs no entry: robots.txt allows the exports). Waiting on
Frankenbach's reply for a votes export and the exact links he meant.

### Contacts (Waiting on Chris: write to them, nothing was sent)

| Canton | Best address | Second | Source |
|---|---|---|---|
| Basel-Stadt | opendata@bs.ch (Open Data Basel-Stadt) | parlamentsdienst@bs.ch | data.bs.ch home page; grosserrat.bs.ch footer |
| Basel-Landschaft | daten@bl.ch (Amt für Daten und Statistik, OGD office) | landeskanzlei@bl.ch | search results only (baselland.ch answered 403); the portal itself offers a form |
| St. Gallen | statistik@sg.ch (Amt für Daten und Statistik) | parlamentsdienste@sg.ch | sg.ch statistics and Parlamentsdienste pages |
| Thurgau | ogd@tg.ch (Koordinationsstelle OGD) | grossrat.sk@tg.ch | data.tg.ch start page; parlament.tg.ch / grgeko.tg.ch footer |
| Aargau | parlamentsdienst@ag.ch | info@ag.ch | www.ag.ch/grossrat footer (seen by a person's search, not fetched by the collector) |

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
2023.RRGR.109 (sex education, "Aufklärung"). **Terms, APPLIED 13 October
2026** (Chris, 13 October 2026: "Accept the watchlists, apply the terms after measuring"; taxonomy-atch v0.3, taxonomy-fr v0.3): German
`Geschlechtsänderung*` (area 3, tier 2) and `Genderstern*` (area 5, tier 2);
French `transition de genre` (area 3, tier 2) and the stem `réassignation*`
(area 3, tier 2), which reads the slash form. Measured on a scratch read of
the cantons (2,643 acts) and the federal, Austrian, French and Belgian stores:
Bern 2023.RRGR.193 and 2024.RRGR.225 and Geneva M 3137 and M 3087 gain their
areas (M 3010 and PL 13324 had them), nothing else matches, 0 false
positives. All shared, none canton-specific. The five watchlist entries stay
(accepted the same day); 2023.RRGR.109 still needs its key.

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
2. **CH7b:** Basel-Stadt and Thurgau from their open data, with members'
   votes: **built 13 October 2026** (written permissions, above).
   Basel-Landschaft with member votes: **built 13 October 2026**
   (`ch-bl-ods`, written permission). St. Gallen: waiting on its reply.
3. **CH7c:** Lucerne (the search form's JSON) and Valais (the Sitrox
   backend), both undocumented backends behind web pages, so robots.txt is
   asked first (both allow today); then Solothurn, Fribourg, Neuchâtel,
   Zug, Schwyz, Graubünden.
4. **CH7d:** Zürich votes (the Kantonsrat records electronic votes; no open
   source found yet) and Geneva's roll calls (published as PDFs, "vote
   nominal", per object in each session's documents).

## Waiting on Chris

0. **(13 October 2026)** The four Opendatasoft cantons and Aargau are now
   read from other official hosts (above); the emails in "Contacts" would
   still unlock what those routes lack (Basel-Landschaft's member votes,
   Thurgau's votes and speeches, Basel-Stadt's full business data, the
   Aargau Grosser Rat's business). Nothing was sent.
1. **The four Opendatasoft cantons.** (13 October 2026: Basel-Stadt and
   Thurgau granted written permission and are read from their APIs;
   Basel-Landschaft too, later the same day; St. Gallen has not replied.) Basel-Stadt, Basel-Landschaft,
   St. Gallen and Thurgau publish exactly what we want as open government
   data, listed on opendata.swiss, but their portals' robots.txt disallows
   `/api/` to every agent but Googlebot. Options: leave them; write to the
   cantons' open-data offices asking for permission or an exemption for our
   agent; or decide that a listed OGD dataset counts as a documented API
   (the `DOCUMENTED_APIS` route in `src/robots_guard.py`, which the regional
   collectors do not use). Nothing is read until you decide.
2. ~~Review the five seeded `cantons` watchlist entries and the proposed
   terms~~: accepted and applied 13 October 2026 (above).
3. **Aargau** disallows its whole parliament section; ask its Parlamentsdienst
   or leave it?

## Shared files touched

`src/ch_store.py` (two tables, `canton_watchlist`, additive), `src/db.py`
(two names in `TABLES`), `src/editions/ch.py` (the Cantons section and
`extra_sections`), `jobs/ch-weekly.sh` (one step, one reclassify line, the
federal budget's third argument), `tools/coverage.py` (two freshness rows,
two `AWAITING_STEP_UNTIL` entries), `config/watchlist-ch.yaml` (the
`cantons` section), `docs/country-parity-handover.md`, `docs/mac-mini.md`,
`docs/robots-runtime.md`. 13 October 2026 (`permissions-1013`):
`src/robots_guard.py` (`PERMISSIONS`), `src/ch_store.py` (`ch_canton_votes`,
`source_url`, `counts_from`), `src/db.py` (one name in `TABLES`).
13 October 2026 (`bs-gribs`): `src/editions/ch.py` (`OWN_EXPORTS`,
`OWN_SOURCES`, the Basel-Stadt source line).

## Forward agenda (regional_agenda, 16 October 2026)

Branch `regional-agenda`: `src/regional_agendas/ch.py`, read by
`tools/regional_agenda.py ch` into `regional_agenda` (src/regional_agenda.py).
Not wired into `jobs/ch-weekly.sh` yet. Region codes are `tools/ch_cantons.py`'s
(lower-case canton abbreviations). Probed live on 16 October 2026, robots.txt
read first, honest user agent, low volume.

**The finding: OpenParlData.ch covers sixteen cantons in three requests.**
`api.openparldata.ch/v1` (the opendata.ch association's harmonised API of
Swiss parliaments, beta, CC BY 4.0, attribution "Source: OpenParlData.ch";
robots.txt allows `/v1/`) has `meetings` (booked sittings, sessions and their
half-day sittings, some committees) and `agendas` (the order of business, with
the business number and language). One read per run is shared by every
OpenParlData canton (cached on the run's ctx): meetings of the sixteen cantons
newest first (`sort_by=-begin_date`, 500 a page, the API ignores date filters),
the agenda items of the meetings in the window (`meeting_id=<ids>`), the names
of their bodies (`groups`). If the API fails, all sixteen are gaps and keep
their rows; the failure is not retried per canton. **For Chris / the lead:**
OpenParlData republishes data some cantons keep behind robots.txt on their own
hosts (Aargau's `www.ag.ch/grossrat`, the Opendatasoft `/api/` portals). We
read OpenParlData's host, whose robots.txt allows us; this is the "official
open data elsewhere" pattern, but it is a third party, not the canton: worth a
yes/no, and worth a courtesy note to info@openparldata.ch.

**Lead's decision (16 October 2026): Aargau is left out of the OpenParlData
read** (fifteen cantons, not sixteen) and is `blocked` until Chris decides
whether to ask its Parlamentsdienst: its own host refuses the whole Grosser
Rat section, and reading it through a republisher would step round that
refusal. The Opendatasoft cantons are different: Basel-Stadt,
Basel-Landschaft and Thurgau granted written permission, and St. Gallen is
already read from its own allowed host (`www.ratsinfo.sg.ch`).

**Chris's decision (16 October 2026): OpenParlData.ch is approved** for every
canton it covers other than Aargau (CC BY 4.0, robots.txt allows us; no
courtesy note). Aargau stays `blocked`. Attribution travels with the data:
each row stores "OpenParlData.ch meetings + agendas (CC BY 4.0, Source:
OpenParlData.ch)" as its source, and the Switzerland countdown prints
"Cantonal agendas marked <cantons>: Source: OpenParlData.ch
(https://openparldata.ch), CC BY 4.0." in its coverage notes whenever a table
shows one of those rows (src/country_countdown.ATTRIBUTIONS). Count: the
reader takes fifteen cantons through OpenParlData (the table below; Chris's
note said fourteen, the code lists fifteen without Aargau).

| Canton | Route | Format | Reaches (live run) | robots.txt | Status |
|---|---|---|---|---|---|
| Zürich | `parlzhcdws.cmicloud.ch/parlzh3/cdws/Index/SITZUNGENDETAIL/searchdetails?q=datum_start >= "<today> 00:00:00" and datum_start <= "<until> 23:59:59"` (the index kantonsrat.zh.ch's own calendar asks) | XML; committee Traktanden structured, the Kantonsrat's from the Traktandenliste document's full text in the same reply | every Kantonsrat and committee sitting to 10 Dec; 19 Oct Traktandenliste (144 points, the whole pending list as published); committee agendas for the next week | 404 (no rules) | reader |
| Bern, Luzern, Uri, Schwyz, Obwalden, Nidwalden, Glarus, Solothurn, Basel-Stadt, Basel-Landschaft, Appenzell AR, Appenzell IR, St. Gallen, Graubünden, Thurgau (Aargau left out, above) | OpenParlData `meetings` + `agendas` + `groups` | JSON | sessions to Dec 2026; agendas: BE winter session (116 business, de/fr paired), BS 21 Oct (108), BL 22 Oct (72), SO 3 Nov (34), SG winter session (26), GR Oct (23, de/it/rm paired), GL, SZ, AI, AR, TG; LU, UR, OW, NW dates only (TBA) | allows | reader (shared) |
| Genève | `ge.ch/grandconseil/sessions/seances/<year>/` (sessions, sitting days, order-of-the-day link) + `/grandconseil/sessions/seances-odj-lion/<n>/?session=<n>` | HTML | the 29 Oct to 6 Nov session's order of the day (146 points with object numbers); November and December sittings TBA | none (no rules) | reader |
| Vaud | `www.vd.ch/gc/seances-du-grand-conseil` (sittings list) + `/detail-seance/seance-gc/<id>` | HTML | a sitting appears when its order of the day is out; none listed for the window on 16 Oct; the calendar is a PDF (not read) | allowed | reader (0 rows today) |
| Ticino | `www4.ti.ch/poteri/gc/attivita/ordine-del-giorno/` + `.../calendario-delle-sedute` | HTML | 26 Oct order of the day (19 points), later sessions TBA | allowed (the acts search stays disallowed, not used) | reader |
| Valais | `parlement.vs.ch/api/fe/v1/parl_sessions?...&limit=3` + `parl_session?id=<id>` (the JSON its app loads) | JSON | November session dates (TBA; its sittings programme is empty until published) | empty (no rules) | reader |
| Zug | `kr-geschaefte.zug.ch/gast/traktandenlisten` + `/gast/traktandenlisten/<id>` | HTML | a Traktandenliste dated in the window; none yet on 16 Oct; the sitting calendar is a PDF | allowed | reader (0 rows today) |
| Fribourg | `www.fr.ch/de/gr` allowed, but `www.fr.ch/fr/...`, and `www.parlinfo.fr.ch/de/sessionen/sitzung/` (redirects to `www.fr.ch/node/1374236`) are disallowed | | | disallows `/fr/`, `/search/`, `?page`, `/node/` | blocked; OpenParlData has no Fribourg meetings |
| Neuchâtel | `www.ne.ch/autorites/grand-conseil/ordres-du-jour` | PDFs only (ODJ, session plan) | | allowed | no-route (a PDF reader would do it) |
| Jura | `www.jura.ch/fr/Autorites/PLT/Calendrier-des-seances-plenieres/...` | nested archive pages, no list of coming sittings found | | allowed | no-route |
| Schaffhausen | `sh.ch` Kantonsrat pages answered 404 (and 500 on 13 Oct) | | | allowed | no-route |

**Live run, 16 October 2026** (scratch DB, 56 days, 26 s wall time): 22 of 26
read, 877 items, 90 to be announced (68 of them Zürich committee sittings),
23 on our ground, among them Zürich's "Standesinitiative: Konversionsmassnahmen
wirksam verbieten" (19 Oct, KR-Nr. 376/2026), Geneva's popular initiative "Pour
une contraception gratuite" and a bill amending its asylum implementing law
(LaLAsi), Bern's motions on femicide monitoring and palliative care
funding, Basel-Stadt's sex-work and trafficking motions, Graubünden's domestic
violence law. Throttles: 1.5 s for api.openparldata.ch, ge.ch and
parlement.vs.ch.

**Next steps worth doing:** a PDF reader (pypdf is used elsewhere) would add
Neuchâtel's orders of the day and the Vaud, Zug, Tirol-style calendars;
Basel-Stadt's own GRIBS exports list `gr_sitzung`, `gr_tagesordnung` and
`gr_tagesordnung_pos` (offered by the Parlamentsdienst) as an official fallback
for OpenParlData; Luzern's session pages on www.lu.ch for its Traktanden.
