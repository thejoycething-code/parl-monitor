# Australia: scoping the Federal Parliament monitor

Probed live on 9 October 2026, from the laptop. Every number below was
measured, not estimated; where a sentence rests on background knowledge
rather than a measurement, it says so. Federal Parliament only (House of
Representatives and Senate); the states and territories are scoped briefly at
the end. Phase 1, the edition and the judge are built on the `australia`
branch and have run once into a scratch database. Nothing is merged,
scheduled for real or published.

## Decisions (Christopher, 9 October 2026)

Proposed on the US pattern and confirmed by Christopher on 9 October 2026.

- **Own edition.** Australia gets its own edition, not a section of another,
  and it **goes to Christopher alone** until it is good.
- **Shared English taxonomy.** `docs/keyword-taxonomy.md` and
  `config/taxonomy.yaml` are unchanged. Australian vocabulary the taxonomy
  lacks is proposed below for Christopher to approve; it has not been added.
  Named bills whose titles would miss are in `config/watchlist-au.yaml`,
  applied by bill ID.
- **Federal first.** House and Senate now; the six states and two territories
  later, where much of our ground actually sits (assisted dying, abortion,
  conversion practices, gender).

## Phase 1: built, 9 October 2026

`tools/au_rollcalls.py` into `au_members`, `au_offices`, `au_bills`,
`au_divisions`, `au_votes` and `au_hansard_files` (schema in
`src/au_store.py`, declared in `db.TABLES`, created by `db.init_db`). A live
run into a scratch database (`--db /tmp/au.db --raw-dir /tmp/au-raw`), the
whole of the 48th Parliament from its first sitting day, 22 July 2025, to
the last sitting before the probe, 17 September 2026:

| | Read | On our ground |
|---|---|---|
| Hansard day files (86 House, 72 Senate) | 158 | |
| Divisions (289 House, 996 Senate) | 1,285 | 73 (43 before the watchlist) |
| Member votes (41,540 Aye, 44,715 No, 8,496 Paired) | 94,751 | |
| Bills of the 48th named in the Hansard or the Register | 269 | 19 (6 before the watchlist) |
| Of those, became Acts (Federal Register of Legislation) | 144 | |
| Members of the 48th (150 House and 76 Senate sitting, 4 departed) | 230 | |

6.4 minutes, 31 MB of gzipped raw payloads, no gaps. Area 11 (migration) is
collated, never campaigned, and is not counted as our ground, as in the US.

- **Every vote is stored**, Aye, No or Paired, with the party of the office
  spell it was cast under. The positions come in the same file as the
  division, so there is no per-division fetch to save.
- **Votes inherit their bills' areas**; `own_areas` keeps the division's own
  match apart. 42 divisions on our ground matched on their own words only, 30
  only through a bill, and 1 both.
- **The APH's own member ID (PHID)** sits beside ours for 219 of the 226
  sitting members: the Parliamentary Handbook gave exactly one match on
  surname and electorate or state. The other 7 are left blank, never guessed.
- **The edition and the judge are built too** (below), and everything is
  **scheduled on the branch, not live.** `jobs/au-weekly.sh`, the Mini-gated
  `.github/workflows/au-weekly.yml` and the launchd plist are written; the
  workflow runs only once merged to main (see "The weekly schedule").

## The finding that shapes everything

**The Parliament's own website refuses the laptop, and the Hansard carries
everything phase 1 needs anyway.**

www.aph.gov.au and parlinfo.aph.gov.au answer every request, `robots.txt`
included, with an **Azure WAF block page (403)**, with our honest UA and with
curl's default alike. That is where Bills Search, the bills digests, the
explanatory memoranda, Votes and Proceedings, the Journals of the Senate,
committee inquiries and submissions, the e-petitions and the sitting calendar
all live. It was not worked around: bot detection is never worked around in
this repo. Whether GitHub's runners or the Mac Mini fare better is untested
(the US Senate refused the laptop and answered CI); a probe from either is
the first thing to try, and needs Christopher's go-ahead because it means
running a workflow.

The route that works is the **OpenAustralia Foundation's parse of the
official Hansard** (`data.openaustralia.org.au`, open, keyless, one XML file
per chamber per sitting day). It has three things the official Hansard XML
does not:

1. **Every division with every member's identity.** The official XML lists
   names only ("Aldred, M. R. (Teller)"); OpenAustralia resolves each to an
   office ID, each office to a person, and each office carries its party, so
   party at the vote comes free, as in Canada and the US.
2. **The Parliament's own bill ID on the debate** (`<bill id="r7532">`), so
   a division joins its bill by ID, never by title.
3. **Pairs**, which the Senate uses heavily (8,496 paired votes). The pairs
   list does not say which side each senator was on, so both are stored as
   Paired and no side is guessed.

### The taxonomy on Australian titles: it mostly misses

Bills are matched on their **titles only**: the explanatory memoranda and
bills digests are on the blocked site, and Australia has nothing like the
US CRS subject terms. `config/taxonomy.yaml`, unchanged, over the 269 bills
of the 48th Parliament: **6 on our ground** (area 11 aside). Every bill title
was then searched for some forty stems (sex, gender, relig, online, child,
hate, abort, surroga, dying, and so on) and every hit read by hand. That
found 13 more that are plainly ours and that no taxonomy term caught. They
are the watchlist:

| Bill | ID | Why the title missed |
|---|---|---|
| Human Rights (Children Born Alive Protection) Bill 2026 | r7511 | the term is the hyphenated "born-alive", on purpose |
| Sex Discrimination Amendment (Sex-based Rights) Bill 2026 | r7479 | "sex-based rights" names the area but is not a term |
| Sex Discrimination Amendment (Restoring Biological Definitions) Bill 2025 | s1463 | "biological definitions" |
| Anti-Discrimination Legislation Amendment (Sexual Orientation, Gender Identity and Sex Characteristics Discrimination Commissioner) Bill 2026 | s1499 | "gender identity" is not a term |
| Online Safety Amendment (Strengthening Enforcement for the Social Media Minimum Age) Bill 2026 | r7512 | "social media" is guarded and "minimum age" is not company |
| Social Media Minimum Age Repeal Bill 2025 | s1480 | as above |
| Criminal Code Amendment (Using Technology to Generate Child Abuse Material) Bill 2025 | r7347 | "child abuse material" is the Criminal Code's name for CSAM |
| Combatting Antisemitism, Hate and Extremism Bill 2026 | r7420 | "hate and extremism" |
| Combatting Antisemitism, Hate and Extremism (Criminal and Migration Laws) Bill 2026 | r7422 | matched only "migration" |
| Human Rights Bill 2026 | r7488 | a federal charter of rights |
| Online Safety Amendment (Broadening Adult Cyber Abuse Protections) Bill 2026 | s1487 | "Online Safety Amendment" |
| Online Safety Amendment (Fix Our Feeds) Bill 2026 | s1491 | as above |
| Online Safety and Other Legislation Amendment (My Face, My Rights) Bill 2025 | s1471 | as above |

Watchlist applied, the 19 bills on our ground by area (a bill can carry
two): free speech 9, sex-based rights 6, parental rights and children 4,
abortion 1, assisted dying 1, religion 1, organ donation 1.

The six the taxonomy did catch: the two National Higher Education Code
gender-based violence bills (s1459, s1460; area 5 on "gender-based
violence", tier 2, probably triage's to drop), Crimes Amendment (Mandatory
Minimum Sentences for Child Sexual Abuse) Bill 2025 (r7387), Sex
Discrimination Amendment (Restoring Common Sense and Recognising Biological
Sex) Bill 2026 (s1500), Criminal Code Amendment (Equal Access to Voluntary
Assisted Dying) Bill 2026 (s1505), and Migration Amendment (Overseas Organ
Transplant Disclosure) Bill 2026 (s1511).

### The names in the brief, checked

- **Religious Discrimination Bill**: no bill of that name in the 48th
  Parliament's Hansard. "Religious" appears in the motion text of 2
  divisions only.
- **Sex Discrimination amendments**: three in the 48th (s1463, s1500,
  r7479), plus the Commissioner bill s1499. Only s1500 matched, on
  "biological sex".
- **Online Safety (Social Media Minimum Age)**: that Act is the 47th
  Parliament's (background, not measured here). In the 48th the live bills
  are the enforcement bill r7512 (11 divisions, House 1 July and 10
  September, Senate 9 and 10 September 2026; one matched, on its motion
  text) and the repeal bill s1480.
- **Misinformation**: no bill title in the 48th. The word matched the motion
  text of 2 Senate divisions (an order for documents on internet content, and
  a motion on 15 September 2026).
- **Hate crimes / Criminal Code Amendment (Hate Crimes)**: no bill of that
  name in the 48th. The hate law of this Parliament is the Combatting
  Antisemitism, Hate and Extremism package, introduced at the recall sitting
  of 19 and 20 January 2026: three bills, 32 divisions on 20 January, 4
  March and 23 March 2026. The two that are ours (r7420, r7422) carried 20
  of them; the firearms bill (r7421, 14 divisions) is not our ground.
  Antisemitism is out of scope in the US decision; hate speech law is area
  7, so the package is in on that ground. Whether area 8 also applies (who
  may preach what) needs the bill's text, which is on the blocked site.
- **Surrogacy**: no bill title and no division text in the 48th.
- **Voluntary assisted dying**: s1505 (the carriage service offence that
  stops telehealth for VAD). Matched. No division on it yet.
- **Territories' right to legislate on VAD**: nothing in the 48th. (The
  Restoring Territory Rights Act is the 47th's, 2022: background.)
- **Abortion**: no division text in the 48th contains "abortion" or
  "unborn". The one abortion bill is r7511 (Born Alive), with no division.

### Proposed Australian vocabulary (for Christopher; NOT added)

Each would have caught a measured miss above. Tiers are suggestions:

- Area 1: "Born Alive Protection" (tier 1; the open "born alive" is
  obstetrics, as the taxonomy's own note says).
- Area 5: "sex-based rights" (tier 1); "Sex Discrimination Act" and "Sex
  Discrimination Amendment" (tier 2: most amendments are about harassment,
  some about the definition of sex); "gender identity" (tier 2);
  "sex characteristics" (tier 2).
- Area 6: "child abuse material" (tier 1; the Australian statutory term);
  "social media minimum age" (tier 1); "under-16 ban" (tier 2).
- Area 7: "Online Safety Amendment" (tier 2: every one touches the eSafety
  Commissioner's powers); "eSafety Commissioner" (tier 2); "vilification"
  (tier 2: the Australian legal word for hate speech, state and federal);
  "hate and extremism" (tier 2); "Human Rights Bill" / "Human Rights Act"
  (tier 2, guarded, because "human rights" alone is everywhere).
- Area 8: "Religious Discrimination" (tier 1).
- Area 4 (for the states): "change or suppression" practices, Victoria's
  statutory name for conversion practices (background).

### What it caught that it should not have

Of the 43 divisions that matched on their own words, about a dozen are
noise a triage pass would drop:

- **"coercion" (area 2)**: 4 divisions on the Select Committee on Corruption
  in the Construction Industry, whose terms of reference list "intimidation,
  coercion and misconduct".
- **"gender-based violence" (area 5)**: 6 divisions on Senate second reading
  amendments to the Draught Beer excise bills (1 April 2026), about alcohol
  and violence against women.
- **"Down syndrome" (area 1)**: 1 division on the NDIS bill.
- **Area 7 on terrorism and Islamophobia motions** ("Islamis*",
  "Islamophobia", "hate crime"): real area 7 vocabulary, but most are
  condolence and counter-terrorism business. Triage's call.

What own-text matching gets right is the Senate's business that carries no
bill, or none yet:

- the proposed referral of **gender dysphoria guidelines for minors** to the
  Community Affairs References Committee (31 March 2026, area 3; negatived
  19 to 41);
- Senator Babet's urgency motion on **age assurance** for search engines
  (29 July 2025; 38 to 25);
- orders for documents on the age assurance trial and on "cybersafety";
- Senator Cash's motion to introduce the **Biological Sex bill** (s1500,
  1 July 2026; negatived 21 to 30, so the Senate refused the bill a first
  reading) and her motion to restore it to the Notice Paper (15 September
  2026; negatived 22 to 32).

## How divisions join to bills

- **By the debate's bill tag.** 583 of the 1,285 divisions (210 House, 373
  Senate) carry at least one bill ID. The rest are motions, committee
  references, orders for documents, suspensions of standing orders and
  procedure, classified on their own words: the debate's headings, the
  Chair's question ("The question is that ...") and the nearest motion
  ("I move ..."), never the debate speeches, because a speech that mentions
  abortion in passing is not a vote on it.
- **Cognate debates tag several bills** (133 divisions). A division then
  inherits every tagged bill's areas: the hate package's 23 March vote
  carries r7420's area 7 even where the question was the firearms bill.
  The edition must say which bill a division was on, from the question.
- **Amendments: the US omnibus lesson, in a milder form.** Australia has no
  appropriations riders on our ground, but amendment votes are where the
  fight is, and their own text is thin:
  - Senate **second reading amendments** carry their full text in the
    Hansard ("At the end of the motion, add ', but the Senate calls on the
    Government to ...'"): 57 divisions, classifiable on their own words.
  - **Committee-stage amendments** (Senate "In Committee", 86 divisions;
    House consideration in detail) are moved by sheet number ("amendment
    (1) on sheet 4109") or put as "that item 65 of schedule 5 stand as
    printed". 258 divisions name a sheet or "stand as printed". The sheets'
    text is on ParlInfo, which refuses the laptop, so these inherit the
    bill's areas and say nothing of their own. This is phase 1b.
- **Procedure is a quarter of it.** 203 divisions are closures ("that the
  question be now put"), suspensions of standing orders or limitations of
  debate. The edition should fold them under the question they enabled.
- **The House question is sometimes missing.** 57 of 289 House divisions
  have no "The question is" sentence before them in the parse (the Chair's
  words were said earlier, or not transcribed).

### A bill ID trap: OpenAustralia tags some bills by title

The Parliament's bill IDs are a running series, not per Parliament (r7333 is
the 48th's first House bill, introduced on 23 July 2025). OpenAustralia
resolves some of its bill tags by title, and so pins **the lapsed bill of the
previous Parliament on the new one's debate**: the 48th's Appropriation Bill
(No. 1) 2025-2026 is r7354, and its debates also carry r7327, the 47th's
bill of the same name, which lapsed when the House was dissolved on 28 March
2025. Measured: **16 such IDs in 28 tags**, every one of the eight House IDs
from r7292 to r7329 with a 48th twin of the same title, plus three older
House IDs and five Senate IDs whose own title year (2018 to 2024) proves an
earlier Parliament. So
`FIRST_BILL_IDS` (below r7330 or s1431) stores such an ID under the earlier
Parliament and records each tag as a gap. The hard rule holds: the key is
the ID, and the title is only how the trap was found.

**Coverage of the bill series.** 207 of the 217 House IDs from r7333 to
r7549 and 62 of the 73 Senate IDs from s1446 to s1518 were named in the
Hansard. The other 21 were never named on a sitting day (or are not bills);
which, needs the blocked Bills Search.

## How bills lapse

When the House of Representatives is dissolved for an election, **every
bill before either House lapses**; a bill that comes back is a new bill with
a new ID (r7327 became r7354). The 48th first met on 22 July 2025, and the
House expires three years from its first meeting unless dissolved sooner
(background: section 28 of the Constitution), so the next mass lapse is due
by mid-2028. Between elections, a prorogation also lapses bills, and the Senate can
restore business to its Notice Paper by motion (background; the one attempt
measured here, for the Biological Sex bill on 15 September 2026, was
negatived). So `au_bills.parliament` is
what a board must read, as `us_bills.congress` is in the US, and the
watchlist must be re-keyed after every election.

## What Australia publishes

### Hansard with divisions: works today, open, no key

- `data.openaustralia.org.au/scrapedxml/{representatives,senate}_debates/<date>.xml`,
  one file per chamber per sitting day, 0.4 to 1.2 MB each; an Apache index
  lists every file with its last-modified stamp. 1,253 House and 1,042
  Senate days since February 2006; 86 and 72 in the 48th.
- **OpenAustralia re-parses old days**: all of June 2026 was rewritten on
  25 August. The collector keeps each file's listing stamp
  (`au_hansard_files`) and reads a day again only when its stamp moves.
- **Timing**: the parser runs daily at 09:05 Canberra time (the server's
  clock, measured against UTC); a sitting day appears the next morning.
- It is a volunteer service, as the US congress-legislators crosswalk is,
  but the words and the votes are the Parliament's own. Its listing pages
  carry a Cloudflare script but are served (200); `www.openaustralia.org.au`
  itself answers with a Cloudflare challenge, so only the data host is used.
- `origxml/` mirrors the official Hansard XML: names only in divisions, and
  a zero-byte file with status 200 for every non-sitting weekday (the trap
  the US Clerk's 200 error page was). Not used.

### Members: works today, open, no key

- OpenAustralia `members/people.xml`, `representatives.xml`, `senators.xml`:
  persons and office spells, one spell per party, so a floor-crosser has two
  (Barnaby Joyce: Independent from 27 November 2025, One Nation from 8
  December 2025). The chairs' spells carry the **role in the party field**
  ("PRES", "DPRES", "SPK"): 805 Senate votes were first stored under PRES. The
  collector resolves each to the person's last real party and keeps the role.
- **Parliamentary Handbook API** (`handbookapi.aph.gov.au/api/individuals`,
  OData, official, keyless): it answers, unlike the rest of aph.gov.au. 226
  current members, with PHID, party, electorate or state, service history.
  **It refuses `$top` over 100** (400, naming the limit), so it is paged.

### Acts: works today, open, no key

**Federal Register of Legislation API** (`api.prod.legislation.gov.au/v1`,
OData). Every Act carries `originatingBillUri`, a ParlInfo link holding the
bill ID: 144 Acts made in the 48th, all 144 with a bill ID, 143 joined to a
bill the Hansard named. Gotchas: `$top` is capped at 500; `year ge 2025`
fails with a 400 whose `text/text` body is "Exception has been thrown by the
target of an invocation" (`year eq` works, so the collector asks year by
year). No explanatory memorandum is attached to an Act (measured on
C2026A00005: the Act's own text only).

### Blocked from the laptop (Azure WAF), not worked around

Bills Search and bill homepages, bills digests, explanatory memoranda,
Votes and Proceedings, Journals of the Senate, the Senate's division
records, committee inquiries and submissions, Senate estimates, House and
Senate e-petitions, the sitting calendar, and every ParlInfo search and
download. All on www.aph.gov.au or parlinfo.aph.gov.au.

### Keyed, not needed for phase 1

- **TheyVoteForYou API**: 401, "You need a valid api key. Sign up for an
  account on They Vote For You to get one." The site itself answers with a
  Cloudflare challenge. It is built on the same OpenAustralia data; its
  value would be its policy groupings, not new votes.
- **OpenAustralia API** (`getDivisions` etc.): "No API key provided."
- Both keys are free and tied to an account. Christopher would have to
  create them; neither is needed while the open data host answers.

### High Court: unreachable from the laptop

`www.hcourt.gov.au` failed at the TLS layer (HTTP/2 stream error) and timed
out over plain HTTP; `eresources.hcourt.gov.au` answers with a redirect. Not
probed further.

## What an Australian edition would look like (proposal)

Westminster's sections map as follows: **bills** (Hansard-named bills and
their stages, Acts from the Register), **divisions** (House and Senate, with
pairs), **Senate motions and references** (the Senate's business on our
ground is often a motion or a committee referral with no bill: gender
dysphoria guidelines, age assurance, documents orders), and later
**debates** (the same Hansard files). No PQ equivalent is reachable
(questions on notice are on aph.gov.au); petitions likewise.

**The 5CA translates.** Every vote carries the member and the party of the
spell, Senate pairs are recorded, and second reading amendments name their
movers. Private senators' bills and motions are a strong signal in the Senate
(Cash's s1500 and its two divisions), much as US cosponsorship is.

## The edition (built 9 October 2026)

`tools/au_monitor.py --edition --dm` writes `editions/au-monitor-<date>.md`
and DMs a short summary to Christopher alone (U05LJP0BT61), modelled on the
US edition. Sections: top lines, dates that matter, divisions this week
(folded where the same question was put again; tally, pairs and the party
split, Paired shown by party; the last 30 days when Parliament did not sit),
bills that moved (a new stage in the Hansard, or assent), new bills, bills
before Parliament, Acts of this Parliament, and coverage, which says plainly
what aph.gov.au blocks. No verdicts: "agreed to" and "negatived" are ayes
against noes. Each division says whether its own words matched or only its
bill did. It renders with no scores at all. Speaks once a day: an edition
already committed for today is rewritten, not resent (as the US weekly).

Rendered from the scratch database for 9 October 2026: no sitting since 17
September, so the top line says so and the divisions section shows the last
30 days (13 divisions on our ground, nine of them the social media minimum
age enforcement bill's passage on 10 September); 15 bills before Parliament
and 4 Acts on our ground.

## The judge (built, NOT on)

`tools/au_triage.py`, modelled on `tools/us_triage.py`: the same judge and
rubric with an Australian frame (voluntary assisted dying, the Sex
Discrimination Act, "child abuse material", the eSafety Commissioner,
vilification; bills are given by title only, and the judge is told not to
invent contents). It judges bills of the current Parliament on our ground and
divisions whose own words matched. **It runs only when the repository
variable `AU_JUDGE` is `on`, and it is not on: SPEND NEEDS A YES.** Measured
by `--dry-run` on the scratch database: **62 items (19 bills, 43 divisions),
about 16 calls, roughly $0.15** for the whole backlog.

## The aph.gov.au probe (prepared, NOT run)

`.github/workflows/au-probe.yml` (workflow_dispatch only; no store, no
commit, no secrets) asks once from a GitHub runner, and `tools/au_probe.py`
asks the same from the Mac Mini by hand: Bills Search, a bill homepage
(r7512), the ParlInfo bill page and a Senate Hansard day, Votes and
Proceedings, the Journals of the Senate, the sitting calendar, committees,
Senate estimates and the High Court. Each answer's status and a short text
sample go to the step summary, and the replies to an artifact kept 7 days.
It uses `tools/probe_hosts.py`'s rules unchanged: robots.txt honoured, at
least 3 seconds between requests, and a challenge or 403 stops the host for
the run, never worked around. Christopher decides whether to run it.

## The weekly schedule

`.github/workflows/au-weekly.yml`: **Friday 02:00 UTC, retry 04:00 UTC**,
gated by `mini-check.yml` with job `AU_WEEKLY`; the Mac Mini runs it first,
Fridays 02:00 London (`ops/launchd/net.citizengo.parlmonitor.au-weekly.plist`,
`jobs/au-weekly.sh`, which collects, runs the judge when it is on, writes the
edition and sends the DM; its `# mini_run: commit editions` line makes the
Mini commit `editions/` beside `data/`). Canberra sits Monday to Thursday; 02:00 UTC Friday is
13:00 in Canberra (AEDT), after OpenAustralia's 09:05 parse has picked up
Thursday. The slot collides with no other workflow (every file in
`.github/workflows` was checked, and a test checks it) and stays clear of
Friday 06:00 to 14:00 UTC, which is kept for the Ireland weekly. The Mini runs
once for both slots, so the gate allows 200 minutes rather than 75: 02:00
London is 01:00 UTC in summer, three hours before the retry. Watched by the
failure alert and `tools/coverage.py` (members and bills weekly, because the
member lists and the Register's Acts are re-read every run; divisions a
month plus a month's grace, because Canberra sits in blocks). **It runs only
once merged to main.**

## Proposed phasing

1. **Phase 1 (built): divisions, bills, members** from the Hansard, the
   Handbook and the Register, as above.
2. **Phase 1b: amendment sheets and bill texts.** Needs ParlInfo or the
   APH bill homepages, which refuse the laptop. First step: one probe from
   GitHub's runners and one from the Mini (each needs Christopher's go-ahead).
   If both are refused, ask the Parliamentary Library or the Department of
   the House for access, as was done for PEI in Canada.
3. **Phase 2: debates and Senate motions in full** (the same Hansard files:
   speeches on our ground, the motion texts), and the weekly **sitting
   calendar** and Senate estimates (blocked today).
4. **Phase 3: the Australian 5CA** (votes, pairs, private bills, second
   reading amendments).
5. **Phase 4: states and territories**, in the order the open data allows
   (below).

## Dates that matter

- **No sitting day between 17 September and 9 October 2026** (measured: the
  OpenAustralia mirror's daily files are empty for every weekday since).
- **The sitting calendar for October to December 2026 and the dates of
  Senate estimates could not be read**: both are on aph.gov.au, which
  refuses the laptop. Background only: supplementary budget estimates are
  normally held in late October or early November, and both Houses
  normally sit into early December. Confirm from a network the APH answers.
- **Mid-2028 at the latest: the next election**, and with it every pending
  bill lapses at once (see "How bills lapse").

## States and territories (scoped, not built)

Much of our ground is state law. Background, not measured here: voluntary
assisted dying is legal in all six states and the ACT's law has passed;
abortion is state criminal law; conversion practices bans exist in
Victoria, Queensland, the ACT and NSW (Victoria calls them "change or
suppression practices"); birth certificate sex markers and puberty blockers
(Queensland's 2025 pause) are state matters.

Measured on 9 October 2026, homepage only, honest UA:

| Parliament | Answers the laptop? |
|---|---|
| Victoria (parliament.vic.gov.au) | yes (200); legislation.vic.gov.au too |
| South Australia (parliament.sa.gov.au) | yes (200) |
| New South Wales | no: Cloudflare challenge; legislation.nsw.gov.au 403 |
| Queensland | no: Azure WAF (legislation.qld.gov.au answers, 200) |
| Western Australia | no: Azure WAF |
| Tasmania, ACT, Northern Territory | no: Cloudflare challenge |

So Victoria and South Australia are the only two whose parliaments can be
probed from here; the rest need a CI or Mini probe first, and OpenAustralia
covers none of them. Which state has open division data with names was not
probed.

## Open questions for Christopher

1. ~~Confirm the assumed decisions~~: confirmed 9 October 2026.
2. **The proposed Australian vocabulary** (above): add to the shared
   taxonomy, keep in the watchlist, or drop, term by term.
3. **Scope**: the Combatting Antisemitism, Hate and Extremism package is in
   on area 7 (hate speech law) while antisemitism itself is out in the US
   decision. Should area 8 apply too? Is the Human Rights Bill ours? Are the
   Online Safety bills (adult cyber abuse, feeds, likeness) ours, or only
   the children's ones?
4. **Run the aph.gov.au probe?** Prepared (`au-probe.yml`, `tools/au_probe.py`),
   not run: it shows whether the WAF block is the laptop's network. Phase 1b
   depends on it.
5. **Keys**: TheyVoteForYou and OpenAustralia keys are free but need an
   account in your name or the team's. Not needed now.
6. **Which states first**, once you have decided; Victoria and South
   Australia are the only two that answer the laptop.
7. **Turn the judge on?** About $0.15 for the backlog (measured by --dry-run), then only new items each
   sitting week: set the repository variable `AU_JUDGE` to `on`.
