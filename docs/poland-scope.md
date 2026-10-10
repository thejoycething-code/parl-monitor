# Poland: scoping the Sejm monitor

Probed live on 9 October 2026 from Christopher's laptop with the repo's own
client (`src/http.py`: the CitizenGO User-Agent, one request a second for
bulk reads, retry with backoff). Every number below was measured, not
estimated. Raw replies are archived under `data/raw/2026-10-09/`
(`pl-probe_*` for the scoping probes); the collector's own test run went to
a scratch store and scratch archive, never the published ones.

## Decisions already taken (Chris)

- Poland is its own edition, delivered to Chris alone by Slack DM, like the US.
- Shared taxonomy concept, but no existing taxonomy file is edited. The Polish
  terms below are a PROPOSAL; `config/taxonomy-pl.yaml` is generated only
  after Chris approves them.
- National parliament first (the Sejm); the Senate and the regions are listed
  for later.
- The Mac Mini runs the job; GitHub Actions is the backup. No paid services.
  Nothing is ever posted publicly.

## Is an edition worth it? Yes

Poland is a working parliamentary democracy with a real opposition, close
votes and a President who vetoes. The ground CitizenGO cares about is
contested in the Sejm itself, in recorded votes, almost every sitting:
abortion decriminalisation failed by three votes on 12 July 2024 (215 to
218); the cohabitation-status law ("status osoby najbliższej") passed 230 to
198 on 29 May 2026 and went back to the Sejm at the President's request;
religion lessons, health education, hate-speech law and the EU migration pact
all reached the floor this term. And the data is the best of any parliament
scoped so far: one open JSON API, keyless, with every deputy's position on
every vote.

## Phase 1: built, 9 October 2026

`tools/pl_rollcalls.py` into `pl_members`, `pl_prints`, `pl_processes`,
`pl_divisions` and `pl_votes` (`src/pl_store.py`), weekly on the Mini
(`jobs/pl-weekly.sh`, Sundays 04:00 London) with GitHub as the backup
(`.github/workflows/pl-weekly.yml`, Sundays 04:00 and 07:00 UTC, gated by
`mini-check` with `PL_WEEKLY`). Tests: `tests/test_pl_rollcalls.py`, 25
tests on real replies trimmed into `tests/fixtures/pl/`.

What one run does, in order:

1. The term list (`/sejm/term`): which term is current and how many prints it
   declares.
2. Every deputy of the term (`/sejm/term10/MP`, one reply): 499 records for
   460 seats, 39 of them inactive (mandates given up for the European
   Parliament, the President's office and so on).
3. Every print (`/sejm/term10/prints`, one reply, 1.8 MB): 3,415, each with
   the process it belongs to.
4. Every legislative process (`/sejm/term10/processes`, four pages of 500):
   1,739, with title, the Sejm's own one-paragraph summary, type, start and
   closure dates, `passed`, and the ELI reference once published.
5. The stage list of every classified process whose `changeDate` moved
   (27 on the first run: the watchlist).
6. Vote headers for every sitting short of its count in the index, plus the
   newest two sittings always: title, topic, totals, majority, the prints it
   cites and, through them, its processes.
7. Every deputy's position on every vote not yet held, newest first, until
   the 45-minute budget runs out.

**First live run (scratch store, 9 October 2026, `--limit 40`):** 499
deputies, 3,415 prints, 1,739 processes, 27 process details, 4,875 vote
headers from 64 sittings, positions for the 40 newest votes (18,400 rows),
**2 gaps**: sittings 9 and 10 failed four times each with a TLS handshake
timeout, then answered in 0.2 seconds a few minutes later. Both are re-read
on the next run, because their stored count falls short of the index. 165
votes were classified with no taxonomy at all, through the 27 watched
processes. The run took 12.6 minutes, most of it in those retries.

**The backfill is spread over runs.** 4,941 vote details at a second each
plus latency is roughly 1.5 to 2 hours; the 45-minute budget cuts it, newest
first, so the whole term is held after two or three weekly runs. After that a
normal week is one sitting: about 150 vote details and a dozen other
requests.

**Store cost (measured).** The vote table is the big one: 460 rows a vote,
about 2.3 million for the term so far. As `WITHOUT ROWID` with a member index
it costs about 60 bytes a position on a scratch store (a rowid table cost
about 100): **some 135 MB for the 10th term, then about 50 MB a year**. The
raw archive adds about 5 KB gzipped per vote detail, some 25 MB for the
backfill. See "Waiting on Chris".

## The finding that shapes everything

**The English taxonomy is blind to Polish**, exactly as it was to German.
Run over the whole 10th term:

| Text matched | Rows | English taxonomy | Proposed Polish terms | of which tier 1 |
|---|---|---|---|---|
| Process titles and summaries (all) | 1,739 | 1 (`Frontex`) | 172 (9.9%) | 39 |
| of which bills (`BILL`) | 992 | 1 | 101 (10.2%) | 25 |
| Processes opened since 9 October 2025 | 627 | 1 | 55 (8.8%) | 11 |
| Vote titles and topics (all) | 4,941 | 0 | 377 (7.6%) | 78 |
| Votes since 9 October 2025 | 2,382 | 0 | 193 (8.1%) | 56 |
| Interpellation titles (latest 2,000, 3 July to 8 October 2026) | 2,000 | 2 (`SoHO`, `Digital Services Act`) | 112 (5.6%) | 28 |
| Print titles (all) | 3,415 | 0 | 240 (7.0%) | 37 |

By area, process titles and summaries (a row can carry two): abortion 13,
assisted dying 1, conversion practices 1, sex-based rights and gender 5,
parental rights and education 48, free speech 36, religion 10, marriage and
family 21, surrogacy and embryology 3, migration 43, prostitution 1.

**Read by hand, all 172 process hits:** 9 are plainly off our ground
(a road-transport bill matched on human trafficking, a tax bill matched on
"digital platforms", an environment bill matched on churches, a hunting bill
on parental consent, a shipping bill on citizenship, a VAT bill on the school
system, a capital-markets bill on equal treatment, a historical deportation
commemoration, an EU tax-reporting bill). About 20 more are routine tier-2
items a triage pass would drop (every bill that amends the education act in
passing, appointments to the state commission on child sexual abuse,
annual reports of the broadcasting council). That is the same shape as the
other languages: tier 1 is precise, tier 2 needs the judge.

**Votes inherit their process's areas.** A vote's own title is often only
"Pkt. 5 Sprawozdanie Komisji o rządowym projekcie ustawy o ..." and its topic
"poprawka 1". So the collector classifies the PROCESS (title plus the Sejm's
summary, which is where the subject is) and gives its areas to every vote
that cites one of its prints. 4,527 of the term's 4,941 votes cite at least
one print, and every cited print resolved to a process.

Until the taxonomy is approved, areas come only from `config/watchlist-pl.yaml`
(27 processes, keyed `10/<number>`), and every other row has `areas` NULL,
meaning "not classified". `--reclassify` fills them offline the day
`config/taxonomy-pl.yaml` lands.

## What the Sejm publishes

### api.sejm.gov.pl: works today, open, no key

JSON over HTTPS, no key, no account, no stated rate limit, no CAPTCHA, CORS
open. Our User-Agent is answered normally. Replies take 0.2 to 1.5 seconds;
the full print list takes 4 to 8.

| Endpoint | What | Measured |
|---|---|---|
| `/sejm/term` | every term, the current flag, print counts | 10 terms; 10th current since 13 November 2023 |
| `/sejm/term10/MP` | every deputy: club, district, voivodeship, active, inactive cause | 499 records, 460 active |
| `/sejm/term10/clubs` | clubs and circles with members and functions | 40 KB |
| `/sejm/term10/prints` | every print with `processPrint` | 3,415 in one reply; `limit`/`offset` ignored |
| `/sejm/term10/prints/{n}` | one print | |
| `/sejm/term10/processes` | processes, 50 a page by default | 1,739 with `limit=500` and offsets; `sort_by` ignored |
| `/sejm/term10/processes/{n}` | one process with every stage (committee referrals, readings, reports, Senate position, President) | |
| `/sejm/term10/proceedings` | every sitting with its days and agenda as HTML, including PLANNED sittings | 89 entries, 67 numbered; sitting 67 (20 to 23 October 2026) already has its agenda |
| `/sejm/term10/votings` | vote count per sitting day | 166 days, 4,941 votes |
| `/sejm/term10/votings/{sitting}` | every vote of a sitting with totals, title, topic | up to about 170 a sitting |
| `/sejm/term10/votings/{s}/{n}` | one vote with every deputy's position AND club | 460 positions, 45 KB |
| `/sejm/term10/interpellations`, `/writtenQuestions` | questions with `limit`, `offset`, `sort_by` honoured | 20,265 interpellations and 4,061 written questions this term |
| `/eli/acts/DU/{year}`, `/eli/acts/search` | the Journal of Laws (ELI) | 1,304 acts in Dz.U. 2026 so far |

### Quirks (observed, not documented)

- **A vote names prints, not a process.** Parse "druk nr 3162", "druku 3156",
  "druki nr 3030, 3080 i 3080-A" from title, topic and description; the
  print list maps each print to its process. Letter suffixes ("3080-A") are
  additional committee reports.
- **"Tak" is not always "for the bill".** Many votes are on a motion to
  reject ("wniosek o odrzucenie projektu w pierwszym czytaniu", "wniosek o
  odrzucenie w całości projektu"): YES there means AGAINST the bill. On the
  cohabitation bill, vote 58/54 (reject) went 197 to 230 and vote 58/62 (the
  whole bill) 230 to 198, the same split mirrored. Any stance or scorecard
  reading must read the topic. Amendment votes ("poprawka 1", "wnioski
  mniejszości nr 4-6") need the committee report to know what was changed.
- **Two kinds of vote.** `ELECTRONIC` (4,932 this term) gives YES, NO,
  ABSTAIN or ABSENT per deputy. `ON_LIST` (9 this term: Marshal, KRS
  members, data protection ombudsman and similar) gives `VOTE_VALID` and a
  `listVotes` map per candidate; the collector keeps that map. Quorum calls
  ("Głosowanie kworum") count in `present`, not in yes or no.
- **The club comes with each position**, so a deputy's club at the time of
  the vote is in the record itself. Clubs moved mid-term (Centrum and
  RozwojPlus formed in 2026); `pl_members.club` is only the latest.
- **Process list paging** is 50 by default; `limit` up to at least 500 works;
  `sort_by` is ignored on processes and prints but honoured on questions.
- **Planned sittings** appear in `/proceedings` with `number` 0 and dates
  through September 2027: a free week-ahead calendar.
- **Transient TLS handshake timeouts.** Two of 66 sitting requests failed
  four times running on 9 October 2026 and answered moments later; one
  later probe also stalled. Recorded as gaps and retried by the next run.
- **Debate transcripts did not answer.** `/sejm/term10/proceedings/66/2026-10-08/transcripts`
  gave no reply within 30 seconds on two tries (9 October 2026); not used in
  phase 1.
- **Citizens' bills carry over between terms** (numbered afresh): 10/25 and
  10/26 began in the 9th term. Other bills fall at the end of a term. Every
  key carries the term.

### The Senate (senat.gov.pl): blocked

Every page tried (`/`, `/prace/posiedzenia/`, `robots.txt`) answered **403
with a Cloudflare challenge** (`cf-mitigated: challenge`, "Just a moment...")
to our User-Agent. Under the house rule we neither solve nor spoof it. The
loss is small for phase 1: the Sejm's process stages already record the
Senate's position on every bill and the Sejm's votes on Senate amendments
("Sprawozdanie Komisji o uchwale Senatu", 2 votes in sitting 66 alone). The
Senate's own recorded votes are the gap. Whether senat.gov.pl answers the
Mini or GitHub's runners has not been tried.

### Courts, referendums, regions

- **The Constitutional Tribunal** (Trybunał Konstytucyjny) is a major channel:
  its 22 October 2020 ruling made the current abortion law, and its status is
  itself disputed. Not monitored in phase 1.
- **Citizens' legislative initiatives** (100,000 signatures) are frequent on
  our ground and arrive as ordinary processes ("Obywatelski projekt ustawy"):
  seven of the 27 watched processes are citizens' bills. Referendums are rare
  and not a channel.
- **Regions, later:** the 16 voivodeship assemblies (sejmiki województw) passed
  the 2019-20 "LGBT-free" and Family Charter resolutions that the EU later
  tied to funding; Warsaw city hall's 2024 order removing crosses from its
  offices is the municipal analogue. No source probed.

## Proposed Polish terms (for Chris to approve)

Conventions as the other languages: `*` is a stem wildcard, an internal `*`
inflects a word inside a phrase, matching is case-insensitive, and a term in
braces is guarded (`with`) or vetoed (`without`). **Polish is heavily
inflected and several stems alternate**, so a single stem is not always
enough: płeć / płci, Kościół / Kościoła, związek / związku, zarodek /
zarodka, ciąża / ciąży. Where the stem changes, both forms are listed.

Markers: **[PL]** is Polish law, institutions or politics, specific to this
edition. Unmarked terms are general Polish and can be shared with any other
Polish-language list.

### 1. Abortion (aborcja)

- Tier 1: aborcj\*, aborcyjn\*, przerywani\* ciąży, przerwani\* ciąży,
  przerywaniu ciąży, dopuszczalnoś\* przerywania ciąży, ochron\* płodu,
  ochron\* życia poczętego, dzieci\* poczęt\*, dziecka poczętego, życi\* poczęt\*,
  pigułk\* poronn\*, "planowaniu rodziny, ochronie płodu ludzkiego" **[PL]** (the
  1993 act's title), kompromis\* aborcyjn\* **[PL]**, "Trybunał\* Konstytucyjn\*
  z 22 października 2020" **[PL]**
- Tier 2: praw\* reprodukcyjn\*, zdrowi\* reprodukcyjn\*, zdrowi\* prokreacyjn\*,
  klauzul\* sumienia, antykoncepcj\*, pigułk\* dzień po, ellaOne, badani\*
  prenataln\*, diagnostyk\* prenataln\*, wad\* letaln\*, letalnie chor\*,
  poronieni\*, martw\* urodzeni\*, hospicj\* perinataln\*, okienk\* życia **[PL]**
- Dropped after measuring: bare ciąż\* (it tagged a pregnant workers' benefit
  bill and two unrelated bills).

### 2. Assisted dying

- Tier 1: eutanazj\*, wspomagan\* samobójstw\*, samobójstw\* wspomagan\*,
  pomoc\* w samobójstwie, pomoc\* w umieraniu, zabójstw\* eutanatyczn\*
- Tier 2: opiek\* paliatywn\*, hospicj\*, uporczyw\* terapi\*, oświadczeni\* pro
  futuro, testament\* biologiczn\*, medycyn\* paliatywn\*

### 3. Gender medicine and children

- Tier 1: bloker\* dojrzewania, blokowani\* dojrzewania, hormon\* płciow\*,
  tranzycj\*, dysfori\* płciow\*, zmian\* płci, korekt\* płci, uzgodnieni\*
  płci **[PL]** (the vetoed 2015 "ustawa o uzgodnieniu płci"), uzgadnianiu
  płci, terapi\* afirmując\*, chirurgi\* zmiany płci
- Tier 2: detranzycj\*, transpłciow\*, niebinarn\*, tożsamoś\* płciow\*

### 4. Conversion practices

- Tier 1: terapi\* konwersyjn\*, praktyk\* konwersyjn\*, terapi\* reparatywn\*
- Tier 2: {orientacj\* seksualn\*, with: terapi\*, zakaz\*, zmian\*}

### 5. Sex-based rights and gender ideology

- Tier 1: ideologi\* gender **[PL]**, ideologi\* LGBT **[PL]**, gender (in Polish
  political usage the bare English word is the ideology debate), LGBT\*,
  konwencj\* stambulsk\*, "Konwencj\* Rady Europy o zapobieganiu i zwalczaniu
  przemocy wobec kobiet", tożsamoś\* płciow\*, ekspresj\* płciow\*, płe\*
  kulturow\* and płc\* kulturow\*, płe\* biologiczn\* and płc\* biologiczn\*,
  płe\* metrykaln\* and płc\* metrykaln\*, strefy wolne od LGBT **[PL]**,
  kobiet\* trans\*, sport\* kobiet\*, neutralnoś\* pod względem płci **[PL]**
  (gender-neutral job adverts, Kodeks pracy), feminatyw\* **[PL]**
- Tier 2: orientacj\* seksualn\*, osob\* LGBT\*, mniejszoś\* seksualn\*, równoś\*
  płci, równego traktowania, przemoc\* ze względu na płeć, przemoc\* wobec
  kobiet, przemoc\* domow\*, parytet\*, homofobi\*, transfobi\*, pełnomocni\*
  rządu do spraw równego traktowania **[PL]**, pełnomocni\* rządu do spraw
  równości **[PL]**

### 6. Parental rights and education

- Tier 1: edukacj\* seksualn\*, edukacj\* zdrowotn\* **[PL]** (the 2025 school
  subject), wychowani\* do życia w rodzinie **[PL]** (the existing subject),
  religi\* w szkol\*, lekcj\* religii, nauczani\* religii, nauk\* religii,
  katechez\*, katechet\*, etyk\* w szkol\*, praw\* rodziców, prawa rodziców do
  wychowania, władz\* rodzicielsk\*, edukacj\* domow\*, lex Czarnek **[PL]**
- Tier 2: podstaw\* programow\*, organizacj\* w szkole, zgod\* rodzica, zgod\*
  rodziców, wykorzystani\* seksualn\* małoletnich, wykorzystaniu seksualnemu
  małoletnich, Rzecznik\* Praw Dziecka **[PL]**, praw\* dziecka, pieczy
  zastępcz\*, piecz\* zastępcz\*, kurator\* oświaty **[PL]**, prawo oświatowe
  **[PL]**, system\* oświaty **[PL]**, szkoł\* niepubliczn\*, ochron\*
  małoletnich, ochronie małoletnich, Standard\* Ochrony Małoletnich **[PL]**,
  smartfon\* w szkoł\*, telefon\* komórkow\* w szkoł\*, wychowani\*
  patriotyczn\*
- Noted: "prawo oświatowe" is the noisiest tier-2 term (15 bills, many
  amending the education act in passing). It stays at tier 2 for triage
  rather than out, because parental-rights fights do run through that act.

### 7. Free speech and online safety

- Tier 1: mow\* nienawiści, przestępstw\* z nienawiści, przestępstw\*
  motywowan\* uprzedzeniami, wolnoś\* słowa, wolnoś\* wypowiedzi, swobod\*
  wypowiedzi, cenzur\*, akt\* o usługach cyfrowych, usługach cyfrowych,
  weryfikacj\* wieku, {art. 256, with: Kodeks\* karn\*} **[PL]**, {art. 257,
  with: Kodeks\* karn\*} **[PL]**, znieważeni\* grupy, nawoływani\* do
  nienawiści, pandemi\* traktat\*, porozumieni\* pandemiczn\*, Międzynarodow\*
  Przepis\* Zdrowotn\*
- Tier 2: dezinformacj\*, pornograf\*, treści szkodliw\*, treści nielegaln\*,
  platform\* internetow\*, platform\* cyfrow\*, media społecznościow\*, mediów
  społecznościowych, szyfrowani\*, inwigilacj\*, Pegasus\* **[PL]**, kontrol\*
  operacyjn\* **[PL]**, radiofonii i telewizji, Krajow\* Rad\* Radiofonii
  **[PL]**, zniesławieni\*, Światow\* Organizacj\* Zdrowia, Europejsk\*
  Konwencj\* Praw Człowieka

### 8. Freedom of religion

- Tier 1: obraz\* uczuć religijnych, obrażani\* uczuć religijnych, {art. 196,
  with: Kodeks\* karn\*} **[PL]**, wolnoś\* religi\*, wolnoś\* sumienia,
  wolnoś\* wyznania, prześladowa\* chrześcijan, prześladowa\* religijn\*,
  Fundusz\* Kościeln\* **[PL]**, konkordat\* **[PL]**, symbol\* religijn\*,
  krzyż\* w urzęd\*, krzyż\* w szkol\*, krzyż\* w Sejmie **[PL]**,
  bluźnierstw\*, złośliwe przeszkadzanie, aktów religijnych, wyznawan\*
  religi\*
- Tier 2: Kościół, Kościoł\*, Kościel\* (not "Kości\*", which is also "bones"),
  związk\* wyznaniow\*, związków wyznaniowych, stosunku Państwa do **[PL]**,
  duchown\*, kapelan\*, miejsc\* kultu, chrześcijan\*, katolick\*, religijn\*,
  niedziel\* wolne od handlu **[PL]**, zakaz\* handlu w niedziel\* **[PL]**,
  handlu w niedziele **[PL]**, klauzul\* sumienia

### 9. Marriage and family

- Tier 1: małżeństw\* jednopłciow\*, związ\* jednopłciow\*, pary jednopłciow\*,
  par\* jednopłciow\*, związ\* partnersk\*, status\* osoby najbliższej **[PL]**,
  osob\* najbliższ\* **[PL]**, umow\* o wspólnym pożyciu **[PL]**, równoś\*
  małżeńsk\*, art. 18 Konstytucji **[PL]** (marriage as a man and a woman),
  definicj\* małżeństwa, rozwod\* pozasądow\* **[PL]**, rozwiązani\*
  małżeństwa
- Tier 2: rozwod\*, Kodeks\* rodzinn\* **[PL]**, utrudniani\* kontaktu,
  babciow\* **[PL]**, Aktywn\* rodzic\* **[PL]**, małżeńst\*, małżeńsk\*, rodzin\*
  wielodzietn\*, Karta Dużej Rodziny **[PL]**, Karty Dużej Rodziny **[PL]**,
  świadczeni\* wychowawcz\* **[PL]**, 800 plus **[PL]**, 800+ **[PL]**, Rodzin\*
  800 **[PL]**, rodzicielstw\*, macierzyńsk\*, ojcostw\*, dzietnoś\*,
  demograf\*, polityk\* rodzinn\*, alimen\*, urlop\* rodzicielsk\*, becikow\*
  **[PL]**, przemoc\* ekonomiczn\*

### 10. Surrogacy and embryology

- Tier 1: macierzyństw\* zastępcz\*, surogac\*, matk\* zastępcz\*, in vitro,
  zapłodnieni\* pozaustrojow\*, leczeni\* niepłodności, leczeniu niepłodności,
  embrion\*, zarodk\*, zarodek, adopcj\* zarodków, dawstw\* komórek
  rozrodczych, komórek rozrodczych
- Tier 2: niepłodnoś\*, naprotechnologi\*, medycznie wspomagan\* prokreacj\*,
  wspomagan\* rozrod\*, edycj\* genom\*, substancj\* pochodzenia ludzkiego,
  badani\* genetyczn\*

### 11. Migration (collated, never campaigned)

- Tier 1: pakt\* o migracji, pakt\* migracyjn\*, polityk\* migracyjn\*,
  zabezpieczeni\* granicy, zakaz\* wjazdu, relokacj\* migrant\*, nielegaln\*
  migracj\*, nielegaln\* imigrac\*, przekraczani\* granicy, granic\* z
  Białorusią **[PL]**, zawieszeni\* prawa do azylu **[PL]**, prawa do azylu,
  strefy buforowej **[PL]**, stref\* buforow\* **[PL]**, zobowiązani\* do
  powrotu, pushback\*
- Tier 2: deportac\*, migrac\* (not "migracj\*", which misses "migracyjn-"),
  obywateli państw trzecich, migrant\*, imigra\*, cudzoziem\*, {azyl\*,
  without: zwierząt} (the Central Animal Shelter is "Centralny Azyl dla
  Zwierząt"), uchodźc\*, ochron\* międzynarodow\*, {Straż\* Granicz\*, with:
  migra\*, cudzoziem\*, azyl\*, Białoru\*, nielegaln\*, uchodźc\*, granic\*
  państwow\*} **[PL]** (unguarded it tagged every uniformed-services pension
  bill), Frontex, obywatelstw\*, repatria\*, wizow\*, zezwoleni\* na pobyt,
  integracj\* cudzoziemców

### 12. Prostitution and trafficking

- Tier 1: prostytucj\*, nierząd\*, kupowani\* usług seksualnych, zakup\* usług
  seksualnych, sutener\*, stręczyc\*, kuplerstw\*, domów publicznych, dom\*
  publiczn\*, handl\* ludźmi w celu wykorzystania seksualnego, model\*
  nordyck\*
- Tier 2: handl\* ludźmi, handlu ludźmi, praca seksualn\*, pracy seksualnej,
  prac\* przymusow\*, niewolnictw\*

### 13. Organ donation

- Tier 1: przeszczep\*, transplantac\*, transplantolog\*, pobierani\*
  narządów, "pobieraniu, przechowywaniu i przeszczepianiu" **[PL]** (the act's
  title), pobranie narządów, dawc\* narządów, dawstw\* narządów, sprzeciw\*
  na pobranie, Centraln\* Rejestr\* Sprzeciwów **[PL]**, śmier\* mózg\*,
  handl\* narządami
- Tier 2: "komórek, tkanek i narządów", tkanek i narządów, krwiodawstw\*,
  dawc\* szpiku

### Global exclusions (never terms on their own)

rodzina, życie, prawo, dziecko, płeć, szkoła, ochrona, edukacja, przemoc,
wolność, migracja, kościół.

### One matcher caveat for when the file is generated

`src/filter.py` bounds a term with `[a-z0-9]`, so Polish letters (ą, ć, ę, ł,
ń, ó, ś, ź, ż) count as word boundaries. In practice this almost never
matters (a stem would have to follow a Polish letter inside a word), and no
false match was seen in the measurements above. The tidy fix is to add those
letters to the boundary class in `src/filter.py`, a shared file, so it is
Chris's call and is NOT made here.

## The watchlist (`config/watchlist-pl.yaml`)

27 processes, found by the proposed terms and read by hand, each with its
reason: the five abortion bills of this term (10/176, 10/177, 10/223,
10/224, 10/611); "Tak dla rodziny, nie dla gender" (10/25) and "Stop LGBT"
(10/26), both rejected at first reading on 22 February 2024; the hate-speech
amendment to the Criminal Code (10/876, passed); gender-neutral job adverts
(10/2623); civil partnerships (10/1457, 10/1458); the cohabitation-status
law and its implementing act (10/2110, 10/2111); parental contact (10/2212);
compulsory religion or ethics (10/1603, citizens'); child removal (10/1892);
online age verification (10/1006 citizens', 10/2697 government); the two DSA
implementation bills (10/1757, 10/2694); anti-SLAPP (10/2488); WHO withdrawal
(10/1114); protecting religious expression (10/29, citizens'); desecration of
a religious symbol (10/2145); state-funded IVF (10/31); and the migration
pact (10/1043, 10/2602). Keys must be redone when the 11th Sejm convenes
after the 2027 election.

## Phase plan

1. **Phase 1, built:** Sejm deputies, prints, processes, recorded votes with
   every position; watchlist classification; weekly on the Mini.
2. **Phase 1b, on approval:** generate `docs/keyword-taxonomy-pl.md` and
   `config/taxonomy-pl.yaml` from the list above, run `--reclassify`, then
   build the edition (`tools/pl_monitor.py` on the US pattern: the week's
   votes and new processes on our ground, Slack DM to Chris only), with the
   reject-motion reading of YES built in.
3. **Phase 2:** week ahead from `/proceedings` (planned sittings with their
   agendas, already published for 20 to 23 October; **Week ahead built 10 October 2026** (branch `parity-week-ahead`, `src/agendas/pl.py`, a step of the weekly job): sitting 67's 41 points, the druk 223 abortion bill among the possible additions, watched); interpellations and
   written questions (about 600 interpellations a month, 5.6% on our ground by
   title); process stages for the board (committee, readings, Senate,
   President, veto, ELI publication).
4. **Later:** the Senate's own votes if senat.gov.pl ever answers a runner
   without a challenge; Constitutional Tribunal rulings; the 16 voivodeship
   assemblies.

## Files touched outside Poland's own

- `src/db.py`: five table names in `TABLES`, and `pl_store.ensure_schema`
  called from `init_db` (9 lines).
- `tools/coverage.py`: the "Poland weekly" pipeline, four feeds (`pl_members`,
  `pl_prints`, `pl_processes`, `pl_divisions`), its `PIPELINE_FEEDS` entry and
  its `AWAITING_FIRST_RUN` entry.
- `.github/workflows/alert.yml`: "Poland weekly" in the watched workflows.
- `docs/mac-mini.md` is NOT edited (to keep the merge small); the install
  steps are in the plist's own header and below.

Poland's own: `tools/pl_rollcalls.py`, `src/pl_store.py`,
`config/watchlist-pl.yaml`, `tests/test_pl_rollcalls.py`,
`tests/fixtures/pl/`, `jobs/pl-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.pl-weekly.plist`,
`.github/workflows/pl-weekly.yml`, this file.

**Install on the Mini** (after the branch is merged to main, because
`mini_run.sh` records the slot only for main): `cp
ops/launchd/net.citizengo.parlmonitor.pl-weekly.plist ~/Library/LaunchAgents/`
then `launchctl bootstrap gui/$(id -u)
~/Library/LaunchAgents/net.citizengo.parlmonitor.pl-weekly.plist`. The repo
variable `MINI_LAST_PL_WEEKLY` is written by the Mini's first clean run.

### Chamber layer: debates, speeches and questions (parity layer 5, 10 October 2026)

Built: interpellations and written questions (`/interpellations`, `/writtenQuestions`, newest first), `tools/pl_chamber.py`, a step of the Polish weekly; the asker's club from pl_members. 212 interpellations and 38 written questions from 26 September to 9 October 2026, 7 on our ground. NOT built: debate transcripts. `/proceedings/66/2026-10-08/transcripts` gave no reply in 30 seconds twice on 9 October and in 45 seconds twice on 10 October (the proceedings list answered 502 that day); given up cleanly, to retry by hand.

## Waiting on Chris

1. **Approve, cut or extend the Polish terms above.** Nothing is classified
   by taxonomy until `config/taxonomy-pl.yaml` exists; the watchlist carries
   the edition until then.
2. **Store every position, or only on-ground votes?** Every position costs
   about 135 MB for the 10th term and 50 MB a year (measured). The
   alternative is positions only for votes on our ground, a few per cent of
   that, at the price of a second backfill whenever the taxonomy changes. As
   built: every position, like Spain and the US.
3. **The Senate is behind a Cloudflare challenge.** Accept the gap (the
   Sejm records the Senate's positions and the votes on its amendments), or
   ask for a one-off test of whether senat.gov.pl answers the Mini.
4. **The boundary fix in `src/filter.py`** for Polish letters, when the
   taxonomy is generated (a shared file).
5. **Review the 27-entry watchlist**, ideally with someone who campaigns in
   Poland: it was drafted from the Sejm's own summaries, not from campaign
   knowledge.
6. **Merge and install** the Mini job when ready; the first two or three
   runs are the backfill.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (PL1); `config/taxonomy-pl.yaml` generated.
- The Senate gap is accepted (PL2).

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/pl_stance.yaml` holds 21 bill direction(s) (Claude's drafts from the watchlist) and 185 vote reading(s): 24 with proposed values, 4 procedural, 157 need reading, 0 confirmed. Guide: `docs/5ca-pl-readings.md`; confirm with `python3 tools/country_5ca.py --cc pl --sign-from-doc --by NAME`. Sheets (`data/5ca/pl-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for Poland (`config/stance_signers.yaml`).
