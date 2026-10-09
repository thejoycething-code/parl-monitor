# Croatia: scoping the Sabor monitor

Probed live on 9 October 2026, from the laptop, with the project's User-Agent
(`CitizenGO-ParlMonitor/1.0`) at one request a second. Every number below was
measured, not estimated. Raw responses are archived under
`data/raw/2026-10-09/` (feeds `hr-rollcalls`, `hr-agenda`, `hr-item`,
`hr-probe`); the probe scripts themselves were scratch work and are not in the
repo. The national parliament only: the Hrvatski sabor is unicameral (151
seats).

## Decisions already taken (Chris)

- **Own edition**, delivered to Chris alone (Slack DM), as for the US.
- **Shared taxonomy concept, Croatian terms of its own.** No existing taxonomy
  file is edited. The Croatian term list is PROPOSED below; Chris approves it
  before `config/taxonomy-hr.yaml` is generated.
- **National parliament first.**
- **Mac Mini first, GitHub Actions as the backup** (the Australia pattern).
  No new paid services. Nothing is ever posted publicly.

## Phase 1: built, 9 October 2026

`tools/hr_rollcalls.py` into `hr_members`, `hr_items`, `hr_divisions` and
`hr_votes` (schema in `src/hr_store.py`, declared in `db.TABLES`), scheduled
by `jobs/hr-weekly.sh` (Mini, Saturdays 01:30 London) with
`.github/workflows/hr-weekly.yml` as the backup behind the `HR_WEEKLY` mini
check. Tests: `tests/test_hr_rollcalls.py`, on real responses saved in
`tests/fixtures/hr/`. Live run into a scratch database, not the store:

| | Read | On our ground (proposed terms) |
|---|---|---|
| Agenda appearances, 12 sessions | 2,139 | 108 |
| Distinct agenda titles | 1,177 | 33 |
| Bills (distinct numbers) | 350 | |
| Items with status "vote held" | 1,034 | |
| Recorded votes, with positions | 790 | 22 |
| Member positions | 96,008 | |
| Member records (11th Sabor) | 209, of whom 178 have voted | |

The whole of the 11th Sabor, 16 May 2024 to 25 September 2026, in 30
minutes, with no gap and no failed request. "On our ground" is the draft
Croatian terms run over the scratch store (`--reclassify` with the draft
file, not committed); the store itself carries no areas yet.

- **Every position is stored.** The vote service returns every member who
  voted in the same response as the totals, so keeping them costs nothing.
- **Nothing is classified yet.** Until `taxonomy-hr` exists, areas come only
  from `config/watchlist-hr.yaml` (eight draft entries, by key) and are
  otherwise NULL ("not classified", distinct from "classified, none").
  `--reclassify` fills them offline the day the file lands.
- **The first scheduled run fits its budget.** The backfill took 30 minutes
  against a 45-minute budget. Should the site slow down, the collector
  fetches votes newest first and discloses the rest, which drain on the
  following Saturdays. A normal week is the agenda index, two agenda pages,
  the member list (5 pages), the week's votes and an item page for each
  vote on our ground.
- **"Za" is not always "for the bill"** (next section but one). Every vote on
  our ground has its item page read once for the result sentence, stored as
  `outcome`, with `yes_means_reject` set when the vote was on a conclusion
  not to accept.

## The finding that shapes everything

**The English taxonomy is blind to Croatian, completely.** Run over every
distinct agenda title of the 11th Sabor (1,177 titles across 2,139 agenda
appearances, May 2024 to October 2026), `config/taxonomy.yaml` matched
**0**. Not one false positive to throw away: nothing at all. Germany's
English run at least matched "Migration"; Croatian shares no spelling with
any English term.

The proposed Croatian terms (below), run over the same 1,177 titles, find
**33 titles on our ground, 22 of which reached a recorded vote**, plus 9 on
migration (area 11, collated only). By area: abortion 1, sex-based rights and
gender 7, parental rights and education 14, free speech and online 5,
marriage and family 6, surrogacy and embryology 1. Every one was read by
hand; the list is in "What the proposed terms find" below.

That is the ceiling for TITLE matching, and the Sabor's titles are honest
but short. Two kinds of bill on our ground cannot be seen from a title at
all, and they are the reason a document layer (phase 3) matters:

- **Criminal Code amendments** ("Prijedlog zakona o izmjenama i dopunama
  Kaznenog zakona"). Seven distinct ones in this Sabor (P.Z.E. 186 and 343;
  P.Z. 11, 16, 241, 251, and the SDP's urgent one). The title names the code,
  never the offence. The government's P.Z.E. 186 PDF (444 pages, text
  extractable with pypdf) matches nine areas in its body, femicide, gender
  identity, social networks and "pravo na život" among them: the omnibus
  problem from the US, in Croatian.
- **Opposition and private members' bills are SCANNED.** All four sampled
  (P.Z. 11, 59, 160, 241) are image-only PDFs from a Canon scanner
  ("Adobe PSL for Canon"), 2 to 6 pages, with no text layer at all. A body
  match is impossible without OCR. P.Z. 59 (Mozemo!, an amendment to the
  Health Care Act) is a case in point: on the agenda of ten sessions, never
  debated, and nothing in its record says what it changes.

## What the Sabor publishes

There is **no API and no open dataset**. The Sabor's organisation on the
national open-data portal exists and holds **0 datasets** (`data.gov.hr`
CKAN API, `organization_show?id=hrvatski-sabor`); a search for `glasovanje`
returns 0, and the seven datasets that mention "sabor" are election results
(the State Electoral Commission) and public-body registers. So everything
below is the Sabor's own website, read the way its own pages read it.

### Session agendas: works today, open, no key

`www.sabor.hr/hr/sjednice/pregled-dnevnih-redova?field_saziv_target_id=144982&field_plenarna_sjednica_target_id=<session>`

- One session's **whole agenda on one page**, no pagination: 57 to 254
  items. 2,139 appearances across the 11th Sabor's 12 sessions (one of them
  extraordinary, 4 items). 1,034 of them carry status 8 ("Glasovanje
  provedeno", vote held).
- Each item: its `tid` (the key everything else uses), its node `t`, a
  parent for grouped items (435 of 2,139), a **status** (6 not debated, 7 in
  debate, 8 voted, 9 debate closed, 10 withdrawn) and the full title, which
  carries the bill number: "P.Z.E. br. 328".
- The page declares its own count ("Ukupno rezultata: 209"); the collector
  checks every parse against it and records a gap on a mismatch. The search
  form's status filter is ignored by the server (it returned all 209 when
  asked for status 8), so the collector filters itself.
- The session list is the search form's own `<select>`, newest first.
  Saziv node ids: 11th 144982, 10th 117053, 9th 170 (back to the 4th, 2000).
- **Slow:** 4 to 10 seconds a page; the 13 pages of a first run take about two minutes.

**Quirk: bills are carried over, not re-numbered.** A bill not reached is
put on the next session's agenda with a NEW tid. 97 titles sit on five or
more agendas, and 69 of those were never voted; the Istanbul Convention
withdrawal bill (P.Z. 41) is on every agenda from the 2nd session to the
12th, undebated. The edition must fold appearances by `bill_key`, never by
tid and never by title.

**Bill numbers.** PZ and PZE ("E" for EU-harmonising) share ONE sequence,
restarting with each saziv: 350 distinct numbers in the 11th Sabor (1 to
351), and only one printed with both markers. So the key is
`<saziv>/<number>` ("11/328") and the marker is stored beside it. The
printing is loose: "P.Z.E br. 344" (no full stop) appears; the parser
allows it.

### Recorded votes with every member's position: works today, open, no key

`www.sabor.hr/hr/rezultati-glasovanja-servis/<tid>/` returns JSON, the call
the item page's own script makes for its "Rezultati glasovanja" pop-up:

```
{"title": "...P.Z.E. br. 328...", "time": "25.09.2026. 12:22",
 "for_count": 81, "against_count": 2, "abstained_count": 41, "total_count": 124,
 "votes": "<div class=\"votes\"><div class=\"export-row vote-row for\">...",
 "session": "...12. sjednica Hrvatskoga sabora..."}
```

- `votes` is HTML: one row per member who voted, with their sabor.hr slug
  (`ackar-kresimir-11-saziv`), name and position (`for` / `against` /
  `abstained`). **Absent members are not listed**; there is no "not voting"
  row, so nothing is inferred for them.
- **No party in the vote.** Party comes from the member list (below), read
  in the same run, and is stored as `party_seen`, named for what it is.
- **Gotcha: an item with no recorded vote answers 200** with a zeroed record
  (`total_count: 0`, time `01.01.0001. 00:00`). Not an error, and not a
  division: stored as `vote_state='none'`.
- **Gotcha: status 8 does not guarantee a record.** Of the 1,034 items
  marked "vote held", **244 (24%) answer with the zeroed record**. They
  cluster early (1st session 43, 2nd 52, 5th 38, 6th 35; the 12th only 2).
  The two sampled were unanimous ("jednoglasno, 107 glasova za" on the item
  page). For those, the totals exist only as text, on the item page and in
  e-Doc; there are no positions to store.
- One vote per agenda item. Two other endpoints exist in the same script:
  `/hr/rezultati-glasovanja/<tid>/` (item metadata, `glasovanje_id`) and
  `/hr/rezultati-glasovanja-parse-itv/<ids>/` for items voted in several
  parts, triggered by `?ID=` links in an item's status text. None of 14
  sampled item pages carried one; not built.
- About a second a response; the 1,034 requests of the backfill took about
  25 minutes at one a second.
- **When the Sabor votes:** 628 of the 790 votes (79%) on a Friday, and 708
  (90%) between 12:00 and 13:59, on 42 voting days in 29 months. 285 were
  unanimous (no Protiv, no Suzdržan); 171 had ten or more against.
- **Grouped votes.** The chair often puts several items to one vote ("ostalih
  12 točaka da glasujemo objedinjeno"). The service then returns the same
  record for each item: 25 sets of identical time and totals cover 75 stored
  votes. Each is kept as its own division, keyed by its item; an edition
  should fold them.

### "Za" is not always "for the bill"

An opposition or private member's bill at first reading is usually disposed
of by a vote on a **conclusion not to accept it**: "donesen je zaključak da
se ne prihvaća Prijedlog zakona (76 glasova "za", 44 "protiv")". The
government majority votes **Za to kill the bill**. The vote service never
says which question was put; only the item page's status sentence does.
Of the 22 votes on our ground, **5 were such conclusions**: the Gender
Equality Act amendment, the Digital Protection of Children Act, the Family
Act amendment and two Education Act amendments. Read naively, the record
would say the HDZ majority voted for the Digital Protection of Children Act;
it voted to reject it. So the collector reads the item page once for every
vote on our ground (`pull_outcomes`; `--all-outcomes` for every vote) and
sets `yes_means_reject`. This is the Croatian form of the rule that a
division's meaning is signed by hand, never from the totals.

### Members: works today, open, no key

`www.sabor.hr/hr/zastupnici?field_saziv_target_id_all=144982&field_status_mandata_target_id=&page=<n>`,
50 a page: **209 member records for 151 seats** (150 active, 41 resting
their mandate, mostly ministers and mayors, 18 ended), each with slug,
name, party, constituency and mandate status. Parties: HDZ 86 records, SDP
43, Mozemo! 14, DP 13, NZ 12, Most 8, and 14 smaller. The status filter must
be sent empty or only the 150 active members come back.
`/hr/zastupnici-po-sazivu/<saziv>` gives the same names as `<option>` HTML
with numeric ids, which nothing else uses.

### e-Doc (edoc.sabor.hr): works, open, awkward

The Sabor's legislative database, ASP.NET WebForms with DevExpress grids.
**Listing pages paginate by postback** (`__VIEWSTATE`), so a collector would
have to replay form state. Detail pages are plain GETs by id:

- **Acts:** `Views/AktView.aspx?id=<id>`. 1,404 acts in the 11th Sabor (486
  laws, 491 decisions, 278 reports; 756 passed, 112 rejected, 156 pending).
  Each gives proposer, session, debate dates, vote date, method
  ("jednoglasno"), **totals only** (115/0/0), status, signature and the
  Narodne novine (official gazette) issue. No member positions. Ids are
  sequential (2031641 to 2031654 on the first page).
- **Questions:** `ZastupnickaPitanja.aspx`, **1,118 questions** in this
  Sabor, the latest dated 2 October 2026, each with asker, party, addressee,
  date, written or oral, and policy fields. Detail:
  `Views/ZastupnickoPitanjeKarticaView.aspx?id=<id>` (sequential, 15211 to
  15215 on page one); its text is loaded by script and was not reached.
- **Transcripts:** `Views/FonogramView.aspx?tdrid=<id>&type=HTML`, plain
  HTML, every contribution headed "Surname, Name (PARTY)". This is the
  Hansard equivalent for debate packs; the item page links each item's
  `tdrid`.

### Item pages: works, open

`www.sabor.hr/hr/sjednice-sabora/<slug>?t=<t>&tid=<tid>`: dates (entered
procedure, urgent procedure, debate opened and closed, voted), a status
sentence with the result ("Zakon je donesen na 12. sjednici, 25. rujna
2026. (81 glas "za", 2 "protiv", 41 "suzdržan")"), the committees that gave
opinions, the bill PDF and every **amendment PDF by its author** (e.g.
"AMANDMAN_Klub_SDP_PZE_328.pdf"). Amendments are not voted by roll call in
the service; they appear only as PDFs and in the transcript.

### Rate limits, keys and robots

No key anywhere. No rate limiting seen across about 1,300 requests at one a
second: no 429, no 5xx. The site is Drupal on Apache (`cache-control:
no-cache`). `robots.txt` disallows `/search/`, `/admin/`, `/user/*` and
Drupal internals; nothing this collector reads. The plenary votes in a
noon block (the chair says so on the record: "u 12 sati glasovanje").

## What the proposed terms find (titles, 11th Sabor)

Read by hand. "Voted" means at least one appearance has status 8.

| Area | Item | Voted |
|---|---|---|
| 1 | Interpellation on the Government's record on women's reproductive rights (16 members) | no |
| 5 | **Withdrawal from the Istanbul Convention**, P.Z. 41 (Pavlicek), never debated | no |
| 5 | Inquiry into institutional failures over violence against women "resulting in a large number of femicides" | yes |
| 5 | Gender Equality Act amendment, P.Z. 169 | yes |
| 5 | Gender Equality Ombudsperson's annual reports, 2022 to 2025 (four) | yes |
| 6 | **Digital Protection of Children Act**, P.Z. 213 (Mozemo!) | yes |
| 6 | Primary and Secondary Education Act amendments, P.Z. 10, 173, 236 | yes (10, 236) |
| 6 | Preschool Education Act amendment, P.Z. 211 | yes |
| 6 | Textbooks Act amendment, P.Z. 153 | yes |
| 6 | Children's Ombudsperson: annual reports 2022 to 2025, election, deputy | yes |
| 7 | Digital Services Act implementation, Regulation (EU) 2022/2065, and its amendment | yes |
| 7 | European Media Freedom Act implementation, Regulation (EU) 2024/1083 | yes |
| 9 | Family Act amendment, P.Z. 244 (SDP) | yes |
| 9 | Maternity and Parental Benefits Act, P.Z. 12 and P.Z.E. 119 | yes (119) |
| 9 | Child Benefit Act amendment, P.Z. 32 (Most) | yes |
| 9 | National Adoptive Parents' Day | yes |
| 10 | Medically Assisted Reproduction Act amendment, P.Z. 214 | no |

**Noise the draft already removes**, measured on the first pass: `obitelj*`
(family) matched 22 titles, 16 of them noise (the Croatian Defenders and
their Families Act, the Defenders' Fund, committee appointments to the
Committee on Family, Youth and Sport, a minister's confidence vote), and
"ravnopravnost spolova" matched 7 committee appointments. Both now carry
vetoes. One spelling lesson: "Konvencija ... o **sprječavanju**" is how the
Istanbul Convention is usually written, but the withdrawal bill's title has
"**sprečavanju**". The draft term is written `spr*čavanju` to take both.

**Also missed, and a scope question rather than a vocabulary one:**

- **Declaration rejecting any WHO agreement that would erode sovereignty
  over Croatian health care** (Miletic, DOMiNO), on ten agendas, never
  debated. CitizenGO campaigns on the pandemic treaty, but it is in none of
  the 13 areas.
- **Trade Act amendments** (P.Z. 160, 259, and the government's P.Z. 303,
  voted at the 10th session). The 2023 Trade Act limited Sunday opening;
  whether these bills touch Sunday rest cannot be read from the title (and
  the two opposition ones are scans).
- **Criminal Code and Health Care Act bills**, above: title-blind.

## Proposed Croatian terms (for Chris to approve)

Same 13 areas as `config/taxonomy.yaml`. Croatian is heavily inflected
(seven cases, adjectives agreeing in gender, number and case), so almost
every term is a stem: `pobačaj*` takes pobačaja, pobačaju, pobačajem;
`rodn* ideologij*` takes rodna ideologija, rodne ideologije, rodnoj
ideologiji, rodnu ideologiju. A `*` inside a phrase means "this word
inflects" (`src/filter.py` supports it since 26 September). Matching is
case-insensitive; agenda titles are in capitals and Python lower-cases Č, Ć,
Đ, Š and Ž correctly. Acronyms in capitals match case-sensitively.

This is a drafting job for a native reader, as German was. The list below
was measured against the Sabor's own titles but has not been read by a
Croatian campaigner.

### 1. Abortion (pobačaj)
- Tier 1: `pobačaj*`, `abortus*`, `prekid* trudnoće`, `prekidanj* trudnoće`,
  `slobodno odlučivanje o rađanju`, `slobodnom odlučivanju o rađanju` (the
  1978 law is still named this way), `nerođen*`, `pravo na život`,
  `prav* na život od začeća`, `zaštit* nerođen*`, `začeć*`,
  `Hod za život`, `40 dana za život`, `mifepriston*`, `tablet* za pobačaj`,
  `pilul* za pobačaj`
- Tier 2: `reproduktivn* zdravlj*`, `reproduktivn* prav*`,
  `spoln* i reproduktivn*`, `kontracepcij*` (contraception is area 1, as
  decided for the US), `trudnic*`, `trudnoć*`, `priziv* savjesti`
  (conscientious objection, the live Croatian abortion-access fight; also
  area 8), `prenatal*`, `mrtvorođen*`

### 2. Assisted dying
- Tier 1: `eutanazij*`, `potpomognut* samoubojstv*`,
  `asistiran* samoubojstv*`, `potpomognut* umiranj*`,
  `usmrćenj* na zahtjev` (Criminal Code art. 112, killing on request),
  `dostojanstven* smrt*`, `dostojanstven* umiranj*`
- Tier 2: `palijativ*`, `hospicij*`, `kraj* život*`, `anticipirane naredbe`,
  `obvezujuć* izjav* volje`

### 3. Gender medicine and children
- Tier 1: `blokator* pubertet*`, `promjen* spola`, `prilagodb* spola`,
  `uskla* spola`, `rodn* disforij*`, `spoln* disforij*`, `rodn* nesklad*`,
  `detranzicij*`
- Tier 2: `hormonsk* terapij*` with `djec*` / `maloljet*` / `spol*`;
  `tranzicij*` with `spol*` / `rod*` / `maloljet*` (unguarded, "tranzicija"
  is the economic transition of the 1990s)

### 4. Conversion practices
- Tier 1: `konverzijsk* terapij*`, `terapij* konverzije`,
  `reparativn* terapij*`, `konverzijsk* praks*`

### 5. Sex-based rights and gender ideology
- Tier 1: `rodn* ideologij*`, `rodn* identitet*`, `Istanbulsk* konvencij*`,
  `Konvencij* Vijeća Europe o spr*čavanju i borbi protiv nasilja nad ženama`,
  `rodno uvjetovan* nasilj*`, `femicid*`, `transrodn*`, `transseksual*`,
  `nebinarn*`, `LGBT`, `LGBTI`, `LGBTIQ`, `LGBTQ`
- Tier 2: `spoln* orijentacij*`, `ravnopravnost* spolova` (without
  `Odbor* za izbor`, `Odbor* za ravnopravnost spolova`),
  `rodn* ravnopravnost*`, `rodno osjetljiv*`, `suzbijanj* diskriminacij*`,
  `nasilj* nad ženama`, `interspoln*`, `državn* maticama` (the civil
  registry law, where a change of registered sex is made)

### 6. Parental rights and education
- Tier 1: `zdravstven* odgoj*` (health education, the 2013 sex-education
  curriculum fight), `spoln* odgoj*`, `seksualn* odgoj*`,
  `građansk* odgoj*`, `prav* roditelja`, `roditeljsk* prav*`,
  `kućn* školovanj*`, `školovanj* kod kuće`, `obrazovanj* kod kuće`,
  `nastav* kod kuće`, `digitaln* zaštit* djece`
- Tier 2: `kurikul*` with `spol*` / `zdravstven*` / `građansk*` / `rod*` /
  `vjeronauk*`; `društven* mrež*` with `djec*` / `maloljet*` / `škol*`;
  `mobitel*` with `škol*` / `učenik*`; `zaštit* djece na internetu`,
  `roditeljsk* skrb*`, `osnovnoškolsk* odgoj*`, `pravobranitel* za djecu`,
  `odgoj* i obrazovanj* u osnovnoj i srednjoj školi`, `udžbenic*`,
  `predškolsk* odgoj*`

### 7. Free speech and online safety
- Tier 1: `slobod* govora`, `slobod* izražavanj*`, `slobod* mišljenja`,
  `govor* mržnje`, `cenzur*`, `Akt o digitalnim uslugama`,
  `Digital Services Act`, `Uredbe (EU) 2022/2065`, `SLAPP`,
  `otkrivanj* sadržaja izvida` and `sadržaja izvida` (the 2024 offence of
  leaking investigation material, "Lex AP", which journalists fought),
  `Lex AP`, `slobod* medija`, `Europsk* akt* o slobodi medija`,
  `Uredbe (EU) 2024/1083`
- Tier 2: `dezinformacij*`, `lažn* vijest*`, `elektroničkim medijima`,
  `medijima`, `klevet*`, `uvred*`, `poticanj* na nasilje i mržnju`
  (Criminal Code art. 325), `zadržavanj* podataka`,
  `nadzor* komunikacij*`, `tajn* nadzor*`

### 8. Freedom of religion
- Tier 1: `vjersk* slobod*`, `slobod* vjeroispovijesti`, `slobod* savjesti`,
  `vjeronauk*` (Catholic religious education in schools, set by treaty),
  `Svet* Stolic*` (the four treaties with the Holy See), `progon* kršćana`,
  `blasfemij*`, `vjersk* osjećaj*`
- Tier 2: `vjersk* zajednic*`, `Katoličk* Crkv*`, `kršćan*`, `crkv*`,
  `nedjelj*` with `rad*` / `trgovin*` / `neradn*` (Sunday rest),
  `pravnom položaju vjerskih zajednica`

### 9. Marriage and family
- Tier 1: `brak*`, `bračn*`, `životn* partnerstv*` (the 2014 Life
  Partnership Act), `istospoln*`, `osob* istog spola`, `Obiteljsk* zakon*`,
  `roditelj* odgojitelj*` (the stay-at-home parent status, a standing
  conservative ask), `obiteljsk* politik*`, `pronatal*`
- Tier 2: `demograf*`, `rodiljn*`, `roditeljsk* potpor*`,
  `doplat* za djecu`, `posvojenj*`, `posvojitelj*`, `udomitelj*`,
  `udomljavanj*`, `obitelj*` (without `branitelj*`, `Odbor* za izbor`,
  `Odbor* za obitelj`, `ministr*`), `alimentacij*`, `uzdržavanj* djece`

### 10. Surrogacy and embryology
- Tier 1: `surogat*`, `zamjensk* majčinstv*`,
  `medicinski pomognut* oplodnj*` (the statute's own name),
  `potpomognut* oplodnj*`, `zametak`, `zametk*`, `embrij*`, `kloniranj*`
- Tier 2: `matičn* stanic*`, `neplodnost*`, `biomedicin*`,
  `genetsk* testiranj*`

### 11. Migration (collated, never campaigned)
- Tier 1: `migracij*`, `migrant*`, `azil*`, `međunarodn* zaštit*`,
  `strancima`, `stranaca` (the Aliens Act), `nezakonit* prelask*`
- Tier 2: `strani radnici`, `stranih radnika`, `radn* dozvol*`, `granic*`

### 12. Prostitution and trafficking
- Tier 1: `prostitucij*`, `trgovanj* ljudima`, `trgovin* ljudima`,
  `trgovac ljudima`, `pornograf*`, `seksualn* iskorištavanj*`,
  `spoln* iskorištavanj*`, `spoln* zlostavljanj*`,
  `seksualn* zlostavljanj*`
- Tier 2: `zlostavljanj* djece`, `iskorištavanj* djece`, `dob* pristanka`,
  `provjer* dobi`, `dječj* pornograf*`

### 13. Organ donation
- Tier 1: `presađivanj*`, `transplantacij*`, `darivanj* organa`,
  `doniranj* organa`, `darivatelj* organa`
- Tier 2: `darivanj* krvi`, `tkiva i stanica`

Not included, on purpose: bare `život` (life: in every pensions and
"quality of life" title), bare `spol` (sex: in every equality-body title),
`zaštita` (protection: everywhere), `antisemitiz*` (out of scope, as decided
for the US).

**One filter caveat to fix before the file goes live.** `src/filter.py`
draws word boundaries with ASCII classes (`[a-z0-9]`), so a letter with a
diacritic does not count as part of a word: a term could match after Č, Ć,
Đ, Š or Ž inside a longer word. It did not bite in this measurement (every
match was read), but it is a one-line change in a shared file (`\w` with
Unicode in place of `[a-z0-9]`) that should be made, with a test, when
`taxonomy-hr` is generated, and it would help any other non-English
edition.

## Phase plan

1. **Phase 1, built:** agendas, recorded votes with every position, members;
   weekly on the Mini; watchlist by key. No areas beyond the watchlist.
2. **Phase 2, the blocker (Chris):** approve the terms; then write
   `docs/keyword-taxonomy-hr.md` as the master, add `"hr"` to `MASTERS` in
   `tools/generate_taxonomy.py` (a shared file), generate
   `config/taxonomy-hr.yaml`, fix the filter boundary, and run
   `hr_rollcalls.py --reclassify`. Then a judge pass (as `tools/us_triage.py`)
   once there are classified items to score.
3. **Phase 3, documents:** bill PDFs from item pages. Government bills have a
   text layer (pypdf, already pinned by the Canada workflows); opposition bills are scans and
   need OCR. Body matching per passage as `src/eudoc.py` does, with the
   omnibus caution the Criminal Code bill shows.
4. **Phase 4, the rest of e-Doc:** questions (1,118, detail pages by
   sequential id), transcripts (`FonogramView`, speaker and party on every
   contribution) for debate packs, and act records for gazette references.
5. **Phase 5:** the Croatian edition and a 5CA, delivered to Chris alone.

## Files touched outside Croatia's own

Kept minimal for the 13-branch merge. Everything else is new and `hr_`
prefixed.

- `src/db.py` (+8 lines): the four `hr_*` names in `TABLES`, and
  `hr_store.ensure_schema(conn)` at the end of `init_db`.
- `tools/coverage.py` (+18 lines): `"Croatia weekly"` in `PIPELINES`,
  `PIPELINE_FEEDS` and `AWAITING_FIRST_RUN`; `hr_members` and `hr_items` in
  `FEEDS`; `hr_divisions` in `ONCE_EVER`.
- `.github/workflows/alert.yml` (+1 line): `"Croatia weekly"` in the
  watched workflows.

New files: `src/hr_store.py`, `tools/hr_rollcalls.py`,
`config/watchlist-hr.yaml`, `tests/test_hr_rollcalls.py`,
`tests/fixtures/hr/` (seven real responses, 80 KB gzipped), `jobs/hr-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.hr-weekly.plist`,
`.github/workflows/hr-weekly.yml`, this document.

## Waiting on Chris

1. **Approve or amend the Croatian terms above**, ideally with a native
   Croatian reader (a CitizenGO Croatia campaigner). Nothing is classified
   by taxonomy until then.
2. **Scope calls:** the WHO-sovereignty declaration (no area today); Sunday
   trading (area 8 or out); whether the Children's and Gender Equality
   Ombudspersons' annual reports are our ground or noise; textbooks and
   preschool law (area 6 tier 2, or out).
3. **Review the eight draft watchlist entries** (`config/watchlist-hr.yaml`).
4. **OCR for scanned bills (phase 3):** may the Mini run Tesseract, free and
   local, with the Croatian language pack? It is the only way to read
   opposition bills, and it adds a system dependency the repo does not
   have today.
5. **Mini install** when the branch is merged: copy the plist to
   `~/Library/LaunchAgents` and bootstrap it, and (optional) create
   `HC_HR_WEEKLY` in `~/runner/env`. Until the branch is on main neither the
   Mini job nor the GitHub backup runs.
6. **Cron slot:** Saturday 03:00 and 05:00 UTC are claimed here, clear of
   everything on main. The other country branches may claim the same slots;
   worth a glance at merge time. At the countries merge (10 October 2026)
   Austria kept them and Croatia moved to 01:30 and 03:30.
7. **Party at the vote:** the service prints no party, so `party_seen` is
   the party in the member list the week the vote is collected. Exact for
   weekly runs, approximate for the backfill. Acceptable, or should phase 4
   read party from the transcripts' "(HDZ)" headings instead?

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (HR1, HR2 WHO declaration, HR3 Sunday trading area 8, HR4 ombudsperson reports); `config/taxonomy-hr.yaml` generated.
- Weekly moved to Saturday 01:30/03:30 UTC (Austria holds 03:00/05:00).

Later phases and items for Chris (not built at the merge):

- X6: source party history before relying on party at the vote.
- Phase (X7): Tesseract OCR on the Mini for scanned records.
