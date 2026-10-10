# Slovakia: scoping the Národná rada monitor

Probed live on 9 October 2026, from the laptop, through `src/http.py` (the
honest CitizenGO User-Agent, throttled, every response archived under
`data/raw/2026-10-09/`). Every number below was measured, not estimated.
National parliament only: the Národná rada Slovenskej republiky (NR SR) is
unicameral, 150 seats, now in its 9th electoral term (volebné obdobie),
which began on 25 October 2023.

## Decisions already taken (Christopher)

- **Own edition**, delivered to Christopher alone by Slack DM, like the US.
- **Shared taxonomy concept, separate term list.** `config/taxonomy.yaml`
  is never edited. The Slovak terms are PROPOSED below; `config/taxonomy-sk.yaml`
  is generated only after Christopher approves them.
- **National parliament first.**
- **Mac Mini first, GitHub Actions as backup**, as for the Australia weekly.
  No new paid services. Nothing is ever posted publicly.

## The finding that shapes everything

**The English taxonomy is blind to Slovak, and Slovak titles hide the
subject behind a law number.** Run over all 1,551 parliamentary prints
(tlače) of the 9th term, `config/taxonomy.yaml` matched **one**: a
resolution on the European Citizens' Initiative "My Voice, My Choice",
caught only because the English campaign name sits in its Slovak title.
Over 4,606 recorded votes it matched one; over 358 interpellations, none.
Germany's lesson again, more sharply.

A Slovak print is titled by the act it amends, not by what it does:

> Návrh poslancov ... na vydanie zákona, ktorým sa mení zákon č. 73/1986 Zb.
> o umelom prerušení tehotenstva v znení neskorších predpisov

So the term list has to know two things: the words, as **stems** (Slovak
inflects: *prerušenie, prerušenia, prerušení*), and the **numbers of the
laws** that carry our ground (73/1986 on abortion, 36/2005 the Family Act,
308/1991 on religious freedom and the churches). Eleven of the prints on our
ground were found only by a law number.

The first draft wrote `umel* prerušeni* tehotenstva` and missed both
abortion bills of the term: *prerušení* ends in í, not i. A stem must stop
before the case ending (`preruš*`). The test suite now holds that case.

**And some prints say nothing at all.** The government's constitutional
amendment of 2025 (tlač 733: two sexes only, sovereignty on cultural and
ethical questions, parental consent for sex education, adoption for married
couples, a surrogacy ban; adopted 26 September 2025 by 90 votes to 7) is
titled only "Vládny návrh ústavného zákona, ktorým sa mení a dopĺňa Ústava
Slovenskej republiky", like 20 other prints this term. No term can find it.
That is what `config/watchlist-sk.yaml` is for, applied by print key, never
by title. Reading the bill documents (phase 2) is the lasting fix.

### How much touches CitizenGO ground (measured with the proposed terms)

Titles and vote labels only, 9th term to 9 October 2026, area 11
(migration) excluded as everywhere else:

| | Read | Any area | On our ground | Tier 1 on our ground |
|---|---|---|---|---|
| Prints (tlače), every type | 1,551 | 64 | 50 (+1 watchlist: 733) | 19 |
| Recorded votes | 4,606 | 180 | 144 (+13 on tlač 733) | 31 |
| Interpellations | 358 | 16 | 15 | 3 |

Votes on our ground fall on **36 prints**; joined to their print by number,
every one of the 145 is found (a vote's label nearly always repeats the
print's title, so the join adds little here, unlike the US).

By area, prints on our ground: parental rights and education 21, marriage
and family 11, abortion 6, sex-based rights 6, freedom of religion 5, free
speech 4 (migration 14, collated only). Votes: free speech 54 (almost all
on the 2025 NGO law, 213/1997, see "Waiting on Chris"), parental rights and
education 50, marriage and family 23, sex-based rights 8, freedom of
religion 7, abortion 4.

What it found, for flavour: both abortion bills (tlač 234, Bittó Cigániková
and Szalay; tlač 593, Záborská and Vašečka, rejected at first reading on
15 April 2025, 25 for, 41 against, 74 abstaining), two resolutions against
the European Parliament's push for an EU right to abortion (266, 285), the
"My Voice, My Choice" resolution (845), eight amendments to the Family Act,
the church-financing bills (370/2019), a resolution on opening a Holy See
mission (1363), a bill on protecting minors in the digital environment
(1367), and an interpellation on the administrative change of sex in the
civil registers.

The tier-2 net is loose on purpose (it goes to triage): "školský zákon"
(the Education Act) alone brings in 14 prints, most of them about school
meals, funding or calendars.

## What Slovakia publishes

### NR SR open data: works today, open, no key, JSON

`https://www.nrsr.sk/opendata/1/sk/<Controller>/<Action>?termNr=9`. It is
listed in the national open-data catalogue (data.slovensko.sk, publisher
"Kancelária Národnej rady SR", 14 datasets, found through the catalogue's
SPARQL endpoint `data.slovensko.sk/api/sparql`), but documented nowhere:
there is no help page, no Swagger, and `/opendata/` is a 404. The catalogue
lists members, meetings, programmes and prints; the vote and interpellation
endpoints were found by probing. Measured:

| Endpoint | Returns (term 9) | Size | Time |
|---|---|---|---|
| `General/ParliamentaryTerms` | 9 terms since 1994 | 1 KB | 0.3 s |
| `General/Meetings?termNr=9` | 64 meetings (schôdze), the latest the 63rd from 16 September 2026 | 10 KB | 0.6 s |
| `General/MeetingProgram?termNr=9&meetingNr=61` | the agenda, point by point, with print numbers | 173 KB | 0.7 s |
| `MP/MembersOfParliament?termNr=9` | 194 members (150 seats plus substitutes), with PoslanecID, list party, latest club | 153 KB | 0.6 s |
| `MP/Clubs?termNr=9` | 7 clubs, with member counts | 4 KB | 1.3 s |
| `Bill/Bills?termNr=9` | **1,551 prints, every type, in one call** | 387 KB | 0.6 s |
| `Bill/BillsOfType?termNr=9&typeId=1` | the same, one type (926 bills) | | 0.5 s |
| `Bill/BillTypes` | 6 types: bill, information, report, other, treaty, petition | | 0.2 s |
| `Voting/Votings?termNr=9` | **4,606 votes with totals, in one call**, newest 6 October 2026 | 3.0 MB | 1.5 to 6.5 s |
| `Interpellation/Interpellations?termNr=9` | 358 interpellations, with addressee, answer date, verdict | | 2.8 s |

Not found (404): any per-vote positions endpoint (twelve names tried, among
them `Voting/VotingResult`, `Voting/Votes`, `Voting/MPVotes`), a bill detail
endpoint, and `MP/Interpellations`. `Voting/Votings` ignores a `meetingNr`
parameter and always returns the whole term. No rate limiting seen across
about 30 calls; no `robots.txt` (404).

**Quirks, all measured:**

- **No positions.** The vote list carries totals only. Who voted how is on
  the web pages below.
- **`countNotPresent` is wrong on 568 of 4,570 open votes** (12%): present
  plus absent comes to 152, 149 or 148 seats instead of 150. Present always
  equals for + against + abstained + not voting, so those four are the check
  against the per-member page, never the absent count. On the 2025
  constitutional amendment the open data says 53 absent; the page shows 51.
- **`isConstitutionalLaw` is false on every vote of the term**, including the
  final vote on the constitutional amendment. Stored as published, never
  relied on.
- **Prints' open-data `id` is not the web MasterID** (tlač 1178 is id 11088
  in the open data and MasterID 10646 on the web). Link to a print by its
  number instead: `Default.aspx?sid=zakony/cpt&ZakZborID=13&CisObdobia=9&ID=<tlač>`.
- **Vote IDs are global** (51,426 to 58,451 in this term, not dense) and so
  make a safe key. 804 votes carry no print (procedure, elections, the
  roll-call "prezentácia"); 36 are secret ballots with no positions.
- Dates come as `2023-10-25T00:00:00`; votes carry a real time.

### NR SR web pages: works today, open, no key, HTML, SLOW

- **Positions:** `www.nrsr.sk/web/Default.aspx?sid=schodze/hlasovanie/hlasklub&ID=<vote id>`.
  One page per vote, about 93 KB, every member's position as a code
  (`[Z]` za, `[P]` proti, `[?]` zdržal sa, `[N]` nehlasoval, `[0]`
  neprítomný) with their PoslanecID, grouped by club. Club at the time of
  the vote comes free, as party does in Canada. Parsed and checked against
  the open-data totals: 150 positions on each fixture, totals agree.
- **Speed is the constraint.** The same kind of page took 10.8, 96, 63, 49,
  1.7 and 2.0 seconds at different times of the same morning; the print
  detail page took 70 seconds. During the live run (05:14 to 05:39 London)
  141 pages came in 1,500 seconds: median 3 seconds a page, one in ten over
  32 seconds, the slowest 183. It is the server, not throttling: no 429s, no
  errors, just slow first bytes. So the collector reads positions only for votes on our
  ground and stops at a clock budget; a full term (4,570 pages) is
  possible with `--positions all` but would take days and is not proposed.
- **Print detail:** `Default.aspx?sid=zakony/zakon&MasterID=<id>` gives the
  stage of the legislative process, the proposer, committees and the
  attached documents (`Dynamic/Download.aspx?DocID=<n>`: the bill text and
  the explanatory memorandum, PDF or Word). Phase 2.
- **Vote list per meeting:** `sid=schodze/hlasovanie/vyhladavanie_vysledok&...&CisSchodze=<n>`,
  paged by ASP.NET postback. Not needed: the open data has every vote.

### data.slovensko.sk (national catalogue)

The old CKAN API at data.gov.sk is gone (the host now serves a JavaScript
app). The catalogue's SPARQL endpoint works and is how the NR SR datasets
were found. Everything else NR SR-related in it is election results from the
Statistical Office. Nothing there that the parliament's own API lacks.

### Not probed yet

Debates (`sid=schodze/rozprava`, video and stenographic records), committee
pages (`sid=vybory/schodze`), the Question Time records, and EUROVOC tags on
prints (the site offers a EUROVOC search, `sid=zakony/eurovoc_search`; if
each print carries descriptors, they would play the part the CRS subject
terms play in the US). Phase 2.

## Phase 1: built, 9 October 2026

`tools/sk_rollcalls.py` into `sk_members`, `sk_bills`, `sk_divisions`,
`sk_votes` and `sk_interpellations` (schema in `src/sk_store.py`, declared in
`db.TABLES`). Keys: a member is the PoslanecID; a print is `'<term>/<tlač>'`
(`'9/733'`), because print numbers restart each term; a vote is the
parliament's own voting ID.

- **Five open-data calls** read every member, print, vote and
  interpellation of the term and re-stamp them, so all four tables move
  every week, recess included (coverage watches all four).
- **Votes inherit their print's areas**; `own_areas` keeps the vote's own
  match apart, as in the US.
- **Positions only on our ground**, newest first, until a 45-minute budget
  runs out; `positions_at` records what has been read, so the next run
  resumes. A reclassification that brings a vote onto our ground queues it.
- **Checked, not trusted:** a page whose positions disagree with the totals
  is stored and recorded as a gap; a page with no positions stores nothing
  and is a gap; a secret ballot is never fetched.
- **No taxonomy until approved.** Without `config/taxonomy-sk.yaml` the
  collector runs with no terms at all (never the English list): everything
  is stored, only watchlisted prints (tlač 733) are on our ground, and only
  their 13 votes get positions. `--taxonomy <file>` points it at a draft.
  After approval, a `--reclassify` (or the workflow's reclassify input)
  re-derives every area offline and the next run reads the new votes'
  positions.
- Exit code 3 means "stored what it could, recorded gaps"; the job still
  publishes on the Mini.

Live run into a scratch database with the proposed terms, 9 October 2026:


| | Stored | On our ground |
|---|---|---|
| Members | 194 | |
| Prints | 1,551 | 51 (50 by terms, 1 by watchlist) |
| Votes | 4,606 | 157 |
| Vote pages read | 141 of 157 in a 25-minute budget | |
| Positions | 21,150 | |
| Interpellations | 358 | 15 |

The five open-data calls took under 20 seconds together; everything else
was vote pages. **No gaps**: every page's positions agreed with the
open-data totals for, against, abstained and not voting. The remaining 16
pages drain on the next run. One example of what the club breakdown shows:
on the constitutional amendment's final vote, all 33 PS members were
recorded absent and SaS cast the only seven votes against.

Tests: `tests/test_sk_rollcalls.py`, 36 tests on real responses saved under
`tests/fixtures/sk/` (the open-data lists, cut to a few records each, and
two vote pages: the constitutional amendment's final vote and the 2025
abortion bill's first reading). A test-only term list sits beside them;
it is not the proposed taxonomy.

### The weekly job (Mini first)

| Job | Mini (launchd, London) | GitHub backup (UTC) | Gate |
|---|---|---|---|
| `sk-weekly` | Tuesdays 02:00 | Tuesdays 02:00, retry 04:00 | `MINI_LAST_SK_WEEKLY`, grace 200 minutes |

`jobs/sk-weekly.sh` (one script, two callers), `ops/launchd/net.citizengo.parlmonitor.sk-weekly.plist`,
`.github/workflows/sk-weekly.yml`, gated by `mini-check.yml` with
`SK_WEEKLY`. Copied from the Australia weekly, including its newer split:
on GitHub the script only collects (`SK_PUBLISH=false`) and the workflow
publishes in its own guarded steps. The Národná rada sits Tuesday to Friday
in its session weeks, so Tuesday before dawn reads a complete week. Tuesday
02:00 and 04:00 UTC collide with no workflow on main or on the other
country branches.

## Proposed Slovak term list (for approval)

Same thirteen areas and the same tier rules as `config/taxonomy.yaml`:
tier 1 auto-includes, tier 2 goes to triage. `*` ends a stem (`potrat*`
matches potrat, potratu, potratov, potratová); inside a phrase it means that
word inflects. Law numbers match as written in titles. Generated into
`config/taxonomy-sk.yaml` only after sign-off. Every term was run over the
term's prints, votes and interpellations; the counts above are this list.

**1. Abortion.** Tier 1: potrat\*, umel\* preruš\* tehotenstva, 73/1986
(the Abortion Act), interrupci\*, nenaroden\*, ochran\* nenaroden\*,
počat\* život\*, od počatia, potratov\* tabletk\*, mifepriston\*, Medabon,
ochran\* života od počatia, Pochod za život. Tier 2: reprodukčn\* zdravi\*,
reprodukčn\* práv\*, výhrad\* vo svedomí, výhrad\* svedomia, antikoncepci\*,
mŕtvo naroden\*, Down\* syndróm\*, tehotn\* žen\*, prenatáln\* diagnosti\*,
anonymn\* pôrod\*, hniezd\* záchrany (baby boxes).

**2. Assisted dying.** Tier 1: eutanázi\*, asistovan\* samovražd\*,
asistovan\* smr\*, asistovan\* umieran\*, dôstojn\* smr\*. Tier 2:
paliatív\*, hospic\*, nevyliečiteľn\* chor\*, konc\* život\*.

**3. Gender medicine and children.** Tier 1: blokátor\* puberty, zmen\*
pohlav\* (change of sex), rodov\* dysfóri\*, pohlavn\* dysfóri\*, prechod\*
pohlav\*, tranzíci\* pohlav\*. Tier 2: hormonáln\* liečb\*, tranzíci\*,
detranzíci\*, rodov\* tranzíci\*.

**4. Conversion practices.** Tier 1: konverzn\* terapi\*, konverzn\*
praktik\*, reparatívn\* terapi\*.

**5. Sex-based rights and gender ideology.** Tier 1: rodov\* ideológi\*,
genderov\* ideológi\*, Istanbulsk\* dohovor\*, rodov\* identit\*,
biologick\* pohlav\*, dv\* pohlav\* (the 2025 amendment's "two sexes"),
mužské a ženské, LGBT\* (case-sensitive), Stratégi\* rovnosti LGBTIQ.
Tier 2: rodov\* rovnos\*, rodov\* stereotyp\*, transrodov\*, transsexu\*,
násili\* na ženách, rodovo podmienen\* násili\*, genderov\*, sexuáln\*
orientáci\*, homosex\*, antidiskriminačn\* zákon\*, rovnak\* zaobchádzan\*,
154/1994 (civil registers, where a change of sex is recorded), 301/1995
(the birth number, which encodes sex), 365/2004 (the Anti-discrimination Act).

**6. Parental rights and education.** Tier 1: sexuáln\* výchov\*, výchov\*
k manželstvu a rodičovstvu, práv\* rodičov, informovan\* súhlas\* rodič\*,
súhlas\* zákonn\* zástupc\*, domác\* vzdelávan\*, nábožensk\* výchov\*,
telesn\* tresta\*. Tier 2: individuáln\* vzdelávan\*, etick\* výchov\*,
školsk\* zákon\*, obsah\* vzdelávania, vzdelávac\* program\*, ochran\* detí,
ochran\* maloletých, sociáln\* siet\*, sexuáln\* zneužívan\*, mimoškolsk\*
vzdelávan\*, cirkevn\* škol\*, sociálnoprávn\* ochran\*, 245/2008 (the
Education Act), 305/2005 (child protection).

**7. Free speech, online safety, health sovereignty.** Tier 1: slobod\*
prejavu, cenzúr\*, nenávistn\* prejav\*, overovan\* veku, overeni\* veku,
pandemick\* zmluv\*, pandemick\* dohod\*, Medzinárodn\* zdravotn\* predpis\*,
digitáln\* identit\*, digitáln\* eur\*, zahraničn\* agent\*. Tier 2:
dezinformáci\*, hoax\*, extrémizm\*, digitáln\* služb\*, pornografi\*,
Svetov\* zdravotníck\* organizáci\*, WHO, mimovládn\* neziskov\*
organizáci\*, slobod\* zhromažďovania, hanobeni\*, 213/1997 (the NGO Act).

**8. Freedom of religion.** Tier 1: slobod\* náboženstva, slobod\*
vierovyznania, nábožensk\* slobod\*, prenasledovan\* kresťanov, registráci\*
cirkví, financovan\* cirkví, Svät\* stolic\* (the Holy See), slobod\*
svedomia, postaveni\* cirkví, 308/1991 (religious freedom and the churches),
370/2019 (church financing). Tier 2: cirkv\*, cirkevn\*, nábožensk\*
spoločnos\*, duchovn\* služb\*, náboženstv\*, vierovyznan\*, kresťan\*.

**9. Marriage and family.** Tier 1: zväz\* muža a ženy, zväzok medzi mužom a
ženou, registrovan\* partnerstv\*, životn\* partnerstv\*, partnersk\* zväz\*,
36/2005 Z. z. (the Family Act), rovnakého pohlavia, spolužitie osôb. Tier 2:
manželstv\*, osvojeni\*, rozvod\*, rodinn\* politik\*, demografi\*,
pôrodnos\*, natalit\*, rodičovsk\* dôchod\*, rodičovsk\* príspev\*,
náhradn\* starostlivos\*, pestúnsk\*, o rodine.

**10. Surrogacy and embryology.** Tier 1: náhradn\* materstv\*, surogát\*,
umel\* oplodn\*, asistovan\* reprodukci\*, ľudsk\* embry\*, embryonáln\*
kmeňov\*, výskum\* na embryách. Tier 2: embry\*, darcovstv\* vajíčok,
darcovstv\* spermi\*, IVF, neplodnos\*, reprodukčn\* medicín\*.

**11. Migration (collated, never campaigned).** Tier 1: nelegáln\*
migráci\*, migračn\* pakt\*, Pakt o migrácii, nelegáln\* prisťahovalectv\*.
Tier 2: migráci\*, azyl\*, utečen\*, pobyt\* cudzincov, štátn\*
občianstv\*, prisťahovalectv\*.

**12. Prostitution and trafficking.** Tier 1: kupliarstv\*, nevestin\*,
sexuáln\* vykorisťovan\*, kúp\* sexuáln\* služ\*, nákup\* sexuáln\* služ\*,
obchodovan\* so ženami. Tier 2: prostitúci\*, obchodovan\* s ľuďmi,
sexuáln\* služ\*.

**13. Organ donation.** Tier 1: darcovstv\* orgánov, transplantáci\*,
darc\* orgánov, obchodovan\* s orgánmi, odber\* orgánov. Tier 2:
predpokladan\* súhlas\*, ľudsk\* tkan\*.

The machine-readable draft used for every count above is the same list in
the taxonomy YAML format; it will become `docs/keyword-taxonomy-sk.md` and
`config/taxonomy-sk.yaml` (through `tools/generate_taxonomy.py --lang sk`,
as for German) once approved.

## Phase plan

1. **Phase 1 (built):** members, prints, votes, positions on our ground,
   interpellations; weekly on the Mini. Waits only on the term list.
2. **Phase 1b:** generate `taxonomy-sk` after approval, reclassify, read the
   positions it queues (about 160 vote pages, one or two weekly runs at the
   speeds measured); a Slovak triage pass on the judge, as Germany has.
3. **Phase 2: bill documents.** Fetch the attached texts of prints on our
   ground and of prints whose title is only "amends the Constitution / Act
   No. X" (body matching as `src/eudoc.py` does), plus the legislative stage
   from the print detail page, so the board knows a print's status. Also
   probe EUROVOC descriptors.
4. **Phase 3: the edition.** A Slovak section in Christopher's DM edition:
   votes on our ground with club breakdowns, new prints, interpellations,
   and the week ahead from `General/MeetingProgram`.
5. Later: debates (rozprava) for quotes; committees.

## Waiting on Chris

1. **Approve, cut or extend the proposed term list** above, so
   `taxonomy-sk` can be generated. Specific calls:
   - **The NGO Act (213/1997, "mimovládne neziskové organizácie")**: the
     2025 amendment that brought 54 votes into area 7. Free speech and civil
     society, or out of scope?
   - **Contraception (antikoncepci\*)**: tier 2 in area 1, as for the US?
   - **The Education Act (245/2008) and "školský zákon"**: tier 2 brings in
     every school bill (14 prints). Keep as a net for triage, or drop and
     rely on the specific terms?
   - **Parental allowance and parental pension (rodičovsk\* príspev\*,
     rodičovsk\* dôchod\*)**: family policy for area 9, or benefits noise?
2. **Confirm the watchlist entry** for tlač 733 (the 2025 constitutional
   amendment, areas 5, 6, 9, 10) and name any other prints you know of whose
   titles hide our ground.
3. **Phase 2 go-ahead** for reading bill documents (the only way past
   "amends Act No. X" titles).
4. **Merge and install**, when you are ready: the branch adds one launchd
   job; it needs the plist copied on the Mini after the merge to main (see
   `docs/mac-mini.md`), and an `MINI_LAST_SK_WEEKLY` variable appears by
   itself after the first Mini run.
5. Nothing here needs a key, an account or a payment.

## Shared files touched (for the merge of the country branches)

Every edit outside Slovakia's own files, kept to added lines only:

- `src/db.py`: five `sk_*` names added to `TABLES`, and two lines in
  `init_db` calling `sk_store.ensure_schema`.
- `tools/coverage.py`: a "Slovakia weekly" entry in `PIPELINES`, four
  `sk_*` rows in `FEEDS`, one entry in `PIPELINE_FEEDS`, one in
  `AWAITING_FIRST_RUN`.
- `.github/workflows/alert.yml`: "Slovakia weekly" added to the watched
  workflows.
- `docs/mac-mini.md`: a "Slovakia weekly" section at the end (the runner
  migration list, `docs/mac-mini-runner.md`, is not on this branch).

Slovakia's own files: `docs/slovakia-scope.md`, `src/sk_store.py`,
`tools/sk_rollcalls.py`, `config/watchlist-sk.yaml`, `tests/test_sk_rollcalls.py`,
`tests/fixtures/sk/`, `jobs/sk-weekly.sh`,
`ops/launchd/net.citizengo.parlmonitor.sk-weekly.plist`,
`.github/workflows/sk-weekly.yml`.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (SK1, SK2 NGO Act, SK3 Education Act net, SK4 parental allowance area 9); `config/taxonomy-sk.yaml` generated.
- X15: `--positions all` is now the default, our ground first.

Later phases and items for Chris (not built at the merge):

- Phase 2: bill documents (SK6).

## Same-day vote briefs (built 10 October 2026, branch `parity-vote-briefs`)

Handover item 1: a brief for each watched or tier-1 vote, naming the members who voted against their group's majority, one DM to Chris per run, de-duplicated in `data/vote-briefs/sk.json` (`src/country_vote_brief.py`, step in `jobs/sk-weekly.sh`). Briefed after each weekly collection. See docs/mac-mini.md, "Vote briefs for the new countries".
