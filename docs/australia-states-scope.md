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
- **Tasmania's Votes and Proceedings and Hansard documents** are in the same
  search engine (`IW_DATABASE=Hansard`), as PDFs and word-processor files.
  Phase 2.
- **Victoria's Hansard** (`hansard.parliament.vic.gov.au`, an ISYS search
  engine that answers us) carries divisions in the daily PDFs. Phase 2.
- **Divisions everywhere but New South Wales.** Queensland, Western
  Australia, the ACT and the Northern Territory publish them in Hansard or
  Votes and Proceedings behind the challenges; South Australia's Hansard
  search is challenged.
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
  `aus_divisions` and `aus_votes` (NSW), `aus_members` (NSW and SA),
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
2. **Divisions beyond NSW:** Victoria's Hansard PDFs through its ISYS engine
   (reachable), Tasmania's Votes and Proceedings (reachable, word-processor
   files). South Australian motions.
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
