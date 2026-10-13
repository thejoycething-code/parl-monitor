# Australia: the six states and two territories

Probed and built on 13 October 2026 (branch `states-au`), from the laptop,
with the honest user agent (`CitizenGO-ParlMonitor/1.0 (contact:
cjoyce@citizengo.net)`) through `src/http.py`, robots.txt read first through
`src/robots_guard.py`, raw replies archived under `data/raw/2026-10-13/`
(feeds `aus-probe` and `au-states`). Live runs went into a scratch database
inside the worktree, never the store. Every number below was measured unless
it says otherwise.

The federal edition (`docs/australia-scope.md`) stays as it is; this is the
state layer, which the Australian edition now carries in a section of its
own ("States and territories"), from `tools/au_states.py`, a step of the
Australia weekly.

## The finding that shapes everything: the parliaments refuse, the registers answer

Six of the eight parliaments' own websites answer our honest user agent with
a bot challenge, which is never solved or bypassed:

| Host | Answer (13 October 2026) |
|---|---|
| www.parliament.nsw.gov.au, legislation.nsw.gov.au | 403, Cloudflare "Just a moment" |
| www.parliament.qld.gov.au, documents.parliament.qld.gov.au | 403, Azure WAF |
| www.parliament.wa.gov.au | 403, Azure WAF |
| www.parliament.tas.gov.au | 403, Cloudflare |
| www.parliament.act.gov.au | 403, Cloudflare |
| parliament.nt.gov.au | 403, Cloudflare |
| www.legislation.sa.gov.au | 403, Cloudflare |
| hansardsearch.parliament.sa.gov.au | Azure WAF JavaScript challenge |

What does answer, in every state, is a second official channel: a
Parliament's own API or search engine on another host, or the Parliamentary
Counsel's legislation register, which lists bills and the Acts they become.
The layer reads those, and only those.

## State by state

Ranked by CitizenGO relevance (population, and what is moving on our ground:
voluntary assisted dying, abortion, conversion practices, gender
self-identification, parental rights, religious exemptions, speech,
surrogacy), then by source quality.

| State | Source read | Format | robots.txt | What it gives |
|---|---|---|---|---|
| **New South Wales** (8.5 m) | `api.parliament.nsw.gov.au/api/hansard/search/`: `year/YYYY`, `daily/tableofcontents/<id>`, `daily/fragment/<uid>` | JSON and XML | 404 (no rules) | every sitting day's contents per House: bills by the Parliament's ID, each stage taken, every speaker (member ID, name, electorate) and **every division with each member's ID** (ayes, noes, pairs); the question and result in the fragment |
| **Victoria** (7 m) | `www.legislation.vic.gov.au/api/tide/elasticsearch/content-legislation-vic-gov-au__production__sapi_node/_search` (the register's "Bills in Parliament" listing backend; the Parliament's own bills page sends readers there) | JSON (POST) | Crawl-delay 2; `/api/` allowed | every bill with its stage in the register's words ("Council - second reading (passed Assembly)", "Passed and Assented to", "Defeated"), introducer, node ID, last-changed date |
| **Queensland** (5.6 m) | `www.legislation.qld.gov.au/projectdata` (the register's browse backend), bills as introduced (`PrintType=bill.first` or `bill.firstnongovintro`, `ParliamentNo=58`) and Acts as passed (`PrintType=act.new`) | JSON | `/admin/`, `/view/pdf/`, `/view/html/compare/` disallowed; `/projectdata` allowed | every bill of the 58th Parliament (government or private member's), and every Act; a bill reads "introduced" until an Act of its name appears |
| **Western Australia** (3 m) | `www.legislation.wa.gov.au/legislation/statutes.nsf/aspassed.atom` | Atom | 404 (no rules) | Acts as passed (200 in the feed), no bills in passage |
| **South Australia** (1.9 m) | the Legislative Tracking system's backend, `prod-internet-salt-functionapp.azurewebsites.net/api/` (`GetSessions`, `Search/?parliamentSession=56th/1st`, `GetMembersforSession`), behind `salt.parliament.sa.gov.au`, which the Parliament's own site embeds | JSON | 404 (no rules) | every bill of the session with its status ("Adj 2nd Reading", "Passed in LC with amendments", "Negatived in HA", "Assented"), house, introducer and ID, in one request; the session's members |
| **Tasmania** (0.6 m) | `search.parliament.tas.gov.au/search/quicksearch/<year>/Bills` (the Parliament's own search engine, on its own host); `www.legislation.tas.gov.au/feed?id=act-year` | HTML, Atom | 404 (no rules); `/admin/` only | the year's bill titles as named in the Hansard, **with no stage or ID**; the year's royal assents, which settle a bill's passage |
| **ACT** (0.5 m) | `www.legislation.act.gov.au/WhatsNew/Index` | HTML | Crawl-delay 10; `/results` (where the bill lists live) disallowed | what the register added in the last seven days: Acts notified and bills presented, when there are any |
| **Northern Territory** (0.25 m) | `legislation.nt.gov.au/en/LegislationPortal/Bills/By-Session` | HTML (2.4 MB) | only two Siteimprove bots disallowed | the current Assembly's every bill: serial number, introduced and passed dates, amended, remarks |

### Not read, and why

- **The parliaments' own sites** (table above): challenges, never bypassed.
- **South Australia's motions**: the tracking search answered bills only for
  the session (60); its motion records need a motion type the public search
  does not default to. Phase 2.
- **The ACT's bill lists**: under `/results`, which robots.txt disallows. The
  register's What's new is read instead, so an ACT bill is seen only in the
  week it is presented.
- **Tasmania's Votes and Proceedings**: the search engine lists no Votes
  database (`/search/quicksearch/<year>/Votes` answers 404); its Hansard
  carries every division, and is read instead (below).
- **Victoria's Hansard** (`hansard.parliament.vic.gov.au`, an ISYS search
  engine that answers us) carries divisions in the daily PDFs; the Votes and
  Proceedings and Minutes carry the same divisions in a cleaner form and
  are read instead (below).
- **Divisions in Queensland, Western Australia and the Northern
  Territory.** Every record of them (Hansard, Votes and Proceedings,
  Minutes) is behind the challenges, from GitHub's runners too; see
  "Divisions: the alternative routes" below for every route tried. Victoria,
  South Australia, Tasmania and the ACT are read since 13 October 2026.
- **AustLII** (which mirrors every state's bills) was not probed: it is not
  an official source, and the official channels above cover what it would.

## What the first live run found

Every source, 13 October 2026, into a scratch database (`--db
scratch-ausp/aus.db`):

| Source | Read | On our ground |
|---|---|---|
| NSW Hansard, 2025 and 2026 (172 House sitting days) | 256 bills, 708 divisions with 37,744 member votes, 137 members named (every voter) | 8 bills, 45 divisions |
| Victoria | 141 bills (46 before Parliament, 93 assented, 2 defeated) | 3 (two assisted dying, one abortion) |
| Queensland | 70 bills, 56 Acts; 50 bills settled by their Act | 0 |
| South Australia | 60 bills, 47 members | 4 (two abortion, one gender medicine, one child protection) |
| Western Australia | 200 Acts as passed | 4 (surrogacy, abortion, safe access zones, transplant) |
| Tasmania | 59 bill titles (2025 and 2026), 34 Acts; 23 titles settled | 0 |
| ACT | 0 Acts, 0 bills in the last seven days (the Assembly had not sat) | 0 |
| Northern Territory | 78 bills (69 passed) | 0 by the taxonomy |

Everything in one run took about two minutes for the seven list sources; the
NSW backfill is the slow part (172 House sitting days took under 20 minutes,
a few seconds each, plus one fragment per topic with a division on our
ground), so on the Mini it drains newest first under the step's five-minute
budget over three or four weekly runs; then a sitting week is six documents.

**On our ground, as the edition shows it**: in New South Wales, the
Abortion Law Reform Amendment (Health Care Access) Bill 2025 (18 divisions
across both Houses, assented 24 June 2025), the Voluntary Assisted Dying
Amendment (Residential Facilities) Bill 2025 (second reading negatived in the
Council, 19 November 2025, 16 to 23), the Crimes Amendment (Places of
Worship) Bill 2025 and the Law Enforcement (Powers and Responsibilities)
Amendment (Places of Worship) Bill (area 8, both assented), and Council
motions on special religious education and the school choice movement; NSW's Abortion Law Reform
Amendment (Sex Selection Prohibition) Bill 2025, second reading negatived in
the Legislative Council on 16 September 2026, 16 to 21, every member's vote
stored; NSW's Education Legislation Amendment (Parental Rights) Bill 2026
(second reading speech, 3 June 2026); Victoria's Voluntary Assisted Dying
Amendment (Equity and Access) Bill 2024 and Constitution Amendment
(Abortion) Bill 2024 (both at Council second reading); South Australia's two
Termination of Pregnancy (Restrictions on Terminations After 24 Weeks)
records (passed in the Legislative Council with amendments; negatived in the
House of Assembly) and a Health Practitioner Regulation bill on childhood
gender treatment (negatived in the Legislative Council); four NSW Council
motions for papers on hate speech legislation (area 7).

### What the taxonomy misses (config/watchlist-au-states.yaml)

Read title by title. Seven entries, by key, each with its "why", the texts
not read:

- `nt:EBD33A287B5F496FBF9D3DE24A9FD373`, the Northern Territory's **Rights of
  the Terminally Ill Bill 2026** (passed with amendments 27 August 2026):
  assisted dying, area 2. "Terminally ill" is not a taxonomy term.
- `sa:5631` and `sa:5640`, South Australia's **Births, Deaths and Marriages
  Registration (Birth Certificates) Amendment** (one record per House,
  assented): area 5, provisionally (the text may concern something else, such
  as early pregnancy loss certificates).
- `wa:A147447`, the **Births, Deaths and Marriages Registration Amendment
  (Sex or Gender Changes) Act 2024** (Western Australia): area 5.
- `vic:22623`, the **Health Safeguards for People Born with Variations in Sex
  Characteristics Bill 2025** (Victoria, assented): area 3, for Christopher
  to keep or drop.
- `wa:A147445`, the **Criminal Code Amendment (Prohibition on Display of
  Nazi Symbols or Gesture) Act 2024**: area 7, as the federal hate package.
- `nt:AF92C56CA0444E02854B67F968762F60`, the Territory's **Anti-Discrimination
  Amendment Bill 2025** (passed): area 8, provisionally.

### Proposed vocabulary (not added: `config/taxonomy.yaml` is generated)

For Christopher to approve into `docs/keyword-taxonomy.md`, all Australian
statute names a title would carry:

- area 2: "terminally ill" (with a guard such as "rights of the"), "end of
  life choices" (Tasmania's 2021 Act).
- area 5: "Births, Deaths and Marriages Registration" with "sex" or "gender"
  as a guard (the bare name also covers routine amendments).
- area 8: "religious exceptions", "religious educational institutions"
  (Victoria's and the Commonwealth's wording); "Equal Opportunity Amendment
  (Religious ...)" as a guarded form.
- area 1: "safe access zones" is matched already; "termination of pregnancy"
  is too.

## What was built

- `src/au_states_store.py`: `aus_bills` (bills, and South Australian motions
  if phase 2 adds them, with stage and status), `aus_bill_events` (each stage,
  dated by the Hansard sitting for NSW, by the read elsewhere), `aus_acts`,
  `aus_divisions` and `aus_votes` (NSW; Victoria, South Australia, Tasmania
  and the ACT since 13 October 2026), `aus_members` (NSW and SA, and every
  member those divisions name),
  `aus_hansard_days`, `aus_reads`. Declared in `db.TABLES`, created by
  `db.init_db`. Keys are `<state>:<the source's ID>`, never titles, except
  Tasmania's (`tas:<year>:<title slug>`), whose only reachable list has no ID.
- `tools/au_states.py`: the eight sources, robots.txt asked at run time
  (`GuardedClient`, no exemptions), one gap row per failure, exit 3 on gaps.
  A source's first read is a seed (not "new" unless introduced in the
  window). An Act whose folded title matches a stored bill settles it
  (`act_key`, status assented). A division takes its bills' areas;
  `own_areas` keeps its own words apart. A NSW bill whose second or third
  reading is negatived on division is marked defeated. `--reclassify` is
  offline.
- NSW division questions are matched to divisions by order within a topic
  (the last "The question is that ..." sentence before each "divided"); a
  division whose question is put in other words can carry its neighbour's
  question, so the edition shows the tally and stage beside it.
- `src/au_states_edition.py`, called by `tools/au_monitor.py`: "States and
  territories" (new this week, moved this week, NSW divisions, Acts made this
  week, before the state parliaments, state coverage) before the federal
  Coverage block, and one line in the DM.
- `jobs/au-weekly.sh`: a step after the debates, five-minute budget
  (`tools/collector_budget.sh 300`), the federal collector's reserve raised
  from 600 to 900 seconds; `AU_RECLASSIFY=true` re-derives the states too.
- `config/watchlist-au-states.yaml`, `tests/test_au_states.py` (fixtures in
  `tests/fixtures/au_states/`), `tools/coverage.py` (four tables watched,
  excused until the first Friday run).

Shared files touched: `src/db.py` (table names and one `ensure_schema`
call), `tools/au_monitor.py` (the section, the DM line, the Coverage line),
`jobs/au-weekly.sh`, `tools/coverage.py`, `docs/mac-mini.md`,
`docs/australia-scope.md`, `docs/country-parity-handover.md`. No new job, no
plist, nothing to install: the Mini picks the step up on its next pull.

## Divisions: the alternative routes (13 October 2026, branch `au-divisions-alt`)

Chris, 13 October 2026: "help explore alternate routes for Australia
divisions". The standing rule (`.claude/regions-brief.md`): when a source
blocks us, look for legitimate alternatives before recording a gap, and
never bypass the block. Every route below was asked from the laptop with
the honest user agent, robots.txt read first through `src/robots_guard.py`;
the challenged parliament hosts were asked again from a GitHub runner by
the read-only probe workflow (`.github/workflows/probe-hosts.yml`, run
38332141239: GET only, no store, no secrets). Nothing was solved, retried
with another user agent or worked around. Live reads went into a scratch
database, never the store.

### Every route tried, state by state

| State | Route | Outcome |
|---|---|---|
| **NSW** | `api.parliament.nsw.gov.au` Hansard API | already read: every division with member IDs |
| **Victoria** | `www.parliament.vic.gov.au` (robots.txt names only Facebook's crawlers): the House documents database's listing, `/api/search/house-papers/865788` (the JSON the "Minutes of the Houses" page itself loads), then each day's **Votes and Proceedings** (Assembly) and **Minutes of the Proceedings** (Council) as Word files | **works, built** (`vic-votes`): every division with every member's name, the question, the result. 2,420 documents back to 1996 |
| | `hansard.parliament.vic.gov.au` (ISYS, answers) | works, not needed: the same divisions in the daily Hansard PDFs |
| | `discover.data.vic.gov.au` CKAN API | robots.txt disallows `/api/`: not asked |
| **Queensland** | `www.parliament.qld.gov.au`, `documents.parliament.qld.gov.au` (Record of Proceedings, Votes and Proceedings), `data.parliament.qld.gov.au` | 403 Azure WAF from the laptop; from the runner robots.txt answers 403 (`www`) and the page 403 (`documents`): **blocked** |
| | `www.data.qld.gov.au` (CKAN) | the API disallowed by robots.txt; the dataset search answered an empty page: nothing parliamentary |
| | `www.legislation.qld.gov.au/projectdata`, `PrintType="bill.third"` (the register's bill-as-passed print, published when the Assembly amended a bill) | **works, built** into the `qld` source: passage dated before the Act appears (8 bills in 2026). No votes: the register records no division |
| **Western Australia** | `www.parliament.wa.gov.au` (Hansard, Votes and Proceedings, bill progress) | 403 Azure WAF from the laptop; robots.txt 403 from the runner: **blocked** |
| | `www.legislation.wa.gov.au` | answers; Acts as passed only (already read). No third-reading record with votes |
| **South Australia** | the Parliament's document library backend, `dynamic-content-api.parliament.sa.gov.au/api/` (`documentlibrary`, `GetFileDownloadLink`; robots.txt 404), behind `dynamic-content.parliament.sa.gov.au`, which the Parliament's own Votes and Proceedings and Minutes pages embed; each file comes through a short-lived read-only link the library hands every visitor (Azure blob storage) | **works, built** (`sa-votes`): the House of Assembly's Votes and Proceedings of the 56th Parliament (21 sitting days so far) and the Legislative Council's Minutes (its library has no 56th-Parliament folder yet, so its latest, the 55th, is read until one appears) |
| | `hansardsearch.parliament.sa.gov.au` | Azure WAF challenge from the laptop and the runner: **blocked** |
| **Tasmania** | `search.parliament.tas.gov.au` (the Parliament's own search engine, robots.txt 404): `/search/quicksearch/<year>/sittingdays.html`, then the Hansard search for each day, then each House's **Hansard** Word file | **works, built** (`tas-votes`): divisions are tables (Ayes, Noes, tellers, pairs) |
| | `www.parliament.tas.gov.au` | Cloudflare from the laptop; robots.txt 403 from the runner: **blocked** |
| | a Votes and Proceedings database in the search engine | none listed (`/quicksearch/<year>/Votes` 404) |
| **ACT** | `www.hansard.act.gov.au` (the Assembly's Hansard site; robots.txt `Allow: /`), `/hansard/11th-assembly/<year>/debates(PDF).htm`, then each day's Hansard PDF | **works, built** (`act-votes`): "The Assembly voted" with names in columns, read with x positions; 27 sitting days in 2026. The HTML edition for 2026 is not out yet (404) |
| | `www.parliament.act.gov.au` (Minutes of Proceedings) | Cloudflare from the laptop; robots.txt 403 from the runner: **blocked** |
| | `www.data.act.gov.au` | answered a page our probe flags as a challenge: not used |
| **Northern Territory** | `parliament.nt.gov.au` (Minutes of Proceedings, Parliamentary Record) | Cloudflare from the laptop; robots.txt 403 from the runner: **blocked** |
| | `territorystories.nt.gov.au` (the NT Library's archive, which holds the Assembly's records) | answers, but robots.txt disallows `/search/`, `/documents/` and every `.pdf`: not used |
| | `legislation.nt.gov.au` | bills by session (already read); no votes |
| **All** | They Vote For You (`theyvoteforyou.org.au`, OpenAustralia Foundation) | the Commonwealth Parliament only, no state data; and a 403 to our user agent from the laptop and the runner (`openaustralia.org.au` too). Nothing built, no account, no key needed |
| | state open-data portals (Victoria, Queensland, ACT above; SA, WA, NT not needed) | no parliamentary divisions dataset found |
| | official GitHub repositories | none of the eight parliaments publishes one |

### What the readers do (`src/au_states_votes.py`, `tools/au_states.py`)

- **Parsers** (pure, fixture-tested): Victoria's Word files (Ayes and Noes
  paragraphs, names split on semicolons or commas, the Council's "Recorded by
  Clerks-at-the-Table" note dropped, non-breaking hyphens kept); South
  Australia's PDFs (the Assembly's two side-by-side columns split at each
  honorific, the left column Ayes; the Council's one name a line);
  Tasmania's Word tables (left Ayes, right Noes, "(Teller)", pairs); the
  ACT's PDF pages with positions (`src/prov_fetch.pdf_rows`, a name's column
  told by the midpoint between the "Ayes" and "Noes" headings). Each
  division keeps its heading (the bill or motion), question and result.
- **Store:** the existing tables, additively: `aus_divisions` keyed
  `<state>:<date>:<house>:<n>`, `aus_votes` with `teller`, `aus_members`
  keyed `<state>:name:<the printed name folded>` (no IDs in these records),
  `aus_hansard_days` one row per record read (so each is read once; a
  Tasmanian House with no Hansard three weeks after a sitting day is marked
  read). A heading that folds to a stored bill's title links the bill and
  takes its areas; a bill whose second or third reading is negatived on a
  division is marked defeated, as for NSW.
- **Budget:** records newest first, capped per run (Victoria 30, South
  Australia 8 a House, Tasmania 8, the ACT 4), big files never archived;
  the step's budget went from 5 to 8 minutes (`jobs/au-weekly.sh`), the
  federal collector's reserve from 900 to 1,080 seconds. A plain run reads
  the list sources, then the four records sources, then NSW.
- **Edition:** the "Divisions" block now says which states (`Divisions this
  week (3: NSW 1, Vic 2)`), and a records division shows its heading before
  its question; the coverage line counts divisions by state.

### First live read (13 October 2026, scratch database)

Two runs of the four records sources (`--sources vic-votes,sa-votes,tas-votes,act-votes`),
after the list sources, into `--db` a scratch file:

| Source | Records read | Divisions | Votes named | On our ground |
|---|---|---|---|---|
| Victoria | 60 (30 a run, newest first; the backlog to 2025 continues) | 302 | every member, tellers marked | 6 |
| South Australia | 32 (the Assembly's 16 newest sitting days, the Council's 16 newest of the 55th Parliament) | 41 | every member | 3 |
| Tasmania | 24 (both Houses, newest sitting days) | 21 | every member, pairs | 0 |
| ACT | 8 | 6 (one printed as a tally only) | every member | 0 |

17,071 member votes and 322 members named in all. The second run's four
sources took 5 minutes 14 seconds (the Council of South Australia's minutes
are 900 KB PDFs); a sitting week afterwards is a handful of records. Every
stored division's names matched its printed tally but four: three Victorian
free votes printed "Tellers:" after the list (fixed and tested before the
merge) and one Tasmanian Assembly division with pairs in its table (17 of 18
Ayes named); the tally is the record's own either way.

**On our ground, measured:** Victoria's **Voluntary Assisted Dying
Amendment Bill 2025**: in the Assembly on 28 October 2025, the second
reading 67 to 16 and the third 67 to 14 (a free vote, tellers named); in
the Council on 12 November 2025, Gaelle Broad's reasoned amendment
negatived 16 to 24, the second and third readings 26 to 14. South
Australia's **Termination of Pregnancy (Restrictions on Terminations after
24 Weeks and 6 Days) Amendment Bill**: second reading negatived in the House
of Assembly on 17 June 2026, 9 to 36; and the Council's **22 Weeks and 6
Days** bill on 12 November 2025, second reading negatived 8 to 11 (and a
later division 2 to 16). Every member's vote is stored for each.

## Dates that matter

- **Victoria votes on 28 November 2026** (fixed term; background, not
  measured). Parliament is dissolved beforehand and every bill not passed
  lapses: the 46 before Parliament will read "lapsed" or vanish from the
  register's current list after the dissolution.
- **South Australia** began its 56th Parliament on 5 May 2026 (measured: the
  tracking system's sessions); **Tasmania** and the **ACT** sit to their own
  calendars, which are on the challenged sites.

## Phase list

1. **Built (13 October 2026):** above.
2. **Divisions beyond NSW: built 13 October 2026** for Victoria, South
   Australia, Tasmania and the ACT (above). Still to do: South Australian
   motions; Queensland, Western Australia and the Northern Territory if a
   parliament lets our user agent in.
3. **Member profiles and 5CA sheets for NSW:** every vote is stored with the
   member's ID; parties are not in the Hansard API and would come from the
   member pages, which are on the challenged site.
4. **The challenged sites** from the Mac Mini or GitHub's runners, honestly,
   once (as was done for aph.gov.au): if a host answers there, its bill
   progress and calendars come in.

## Waiting on Chris

1. **The watchlist** (seven entries above), especially the provisional ones
   (South Australia's birth certificates bill, Victoria's sex
   characteristics bill, the Territory's Anti-Discrimination Amendment).
2. **The proposed vocabulary** above, into `docs/keyword-taxonomy.md`.
3. **Whether to write to the parliaments** behind the challenges (NSW,
   Queensland, Western Australia, Tasmania, the ACT, the Northern Territory)
   asking for our user agent to be allowed, as was done for aph.gov.au.
   Queensland, Western Australia and the Northern Territory matter most now:
   they are the three with no division read at all (13 October 2026), and
   the challenge answers GitHub's runners as well as the laptop.
