# United States: the fifty state legislatures

Decided by Christopher on 9 October 2026: all 50 state legislatures, after
Congress, through Open States; the US edition goes to him alone. Probed and
built the same day, from the laptop, with the team's Open States key. Every
number below was measured, not estimated. Live runs went into a scratch
database (`/tmp`), never the store, with the raw archive under `/tmp` too.

Built: `src/us_states_store.py` (tables `uss_*`, declared in `db.TABLES`),
`tools/us_states.py` (the collector), `config/watchlist-us-states.yaml`
(named misses, by key), a **States** section in `tools/us_monitor.py`, state
bills in `tools/us_triage.py`, a step in `jobs/us-weekly.sh`, entries in
`tools/coverage.py`, and `tests/test_us_states.py` on trimmed real files.

## The key and its limits

- **Tier: `default`. 10 requests a minute, 250 a day** (UTC day). Measured,
  not guessed: v3.openstates.org sends **no rate-limit headers at all** (the
  only headers are Date, Content-Type, Content-Length, Connection and
  `server: uvicorn`), so the limit was read from a refusal. Eleven requests
  0.2 s apart; the eleventh came back 429 with the body
  `{"detail":"exceeded limit of 10/min: 11"}`, and the API's published
  source (`openstates/api-v3`, `api/auth.py`) defines the tiers:
  default 10/min and 250/day, bronze 40/min and 1,000/day, silver 80/min and
  50,000/day. The account page that names the tier needs a login.
- A request refused for the minute still counts towards the day.
- `per_page` is capped at **20** for bills ("invalid per_page, must be in
  [1, 20]").
- The key goes only in the `X-API-KEY` header (the API also accepts
  `?apikey=`, which we never use): never in a URL, a log, a gap row or the
  archive. `src/http.py` keeps keyed replies out of its own archive; the
  collector archives the API's JSON bodies itself (they never carry the key)
  and does not archive the bulk files (the URL and generation stamp, kept in
  `uss_sessions`, are the provenance, as for the Holyrood year dumps).
- Two runners share one key (the Mini, and GitHub as its backup), but only
  one of them runs a given Friday.

## The finding that shapes everything: two routes

**The per-session bulk files are open.** The API's jurisdiction list (two
keyed requests) names, for every session, a CSV zip on
`data.openstates.org/csv/latest/` with its generation stamp. Those files
answer **without a key and without a rate limit** (S3 behind CloudFront):
bills, abstracts, titles, actions with their chamber, sponsorships, sources,
votes, vote counts and **every legislator's position**. The scope note of
9 October said bulk downloads sit behind a login: that is the listing page
on open.pluralpolicy.com, not the files.

| | Requests | Time (laptop) | Size |
|---|---|---|---|
| **First read**, all fifty (66 current sessions) | **2 keyed** + 66 bulk files + 50 people files (keyless) | **945 s** | about 2.2 GB downloaded |
| **Weekly read**, week to 9 October 2026 (recess) | **65 keyed** (2 + one or more pages per state) + 50 people files | **410 s** (6.5 s spacing) | under 1 MB of JSON |
| Weekly read in session, estimated from the bulk actions | 687 to 949 keyed by API alone | | |

The in-session estimate counts, from the bulk files' own actions, the bills
with an action in a sitting week: **18,392 in the week of 2 March 2026** (949
pages of 20, 28 states over ten pages) and **13,083 in the week of 13 April
2026** (687 pages, 18 states over ten). That is three to four days of the
key's quota in one week. So the weekly read caps each state at ten pages and
the run at 200 requests; a state past either cap reads its **bulk file**
instead, only for bills with an action in the window. With the cap, a
sitting week costs about **130 keyed requests**, with 18 to 28 states read
from bulk files that Open States regenerates daily for active sessions
(most were stamped 8 October).

**The weekly read uses `action_since`, never `updated_since`.** Open States
re-stamps `updated_at` whenever its scrapers re-run: in the week to 9 October
**3,746 bills were "updated" (200 pages) and 622 had an action (75 requests
counting one per state)**. Vermont's H 951, last acted on in May, was
"updated" on 7 October.

### The proposed rotation

Every state every week, inside the step's clock (`--budget-seconds`: 600 s on
GitHub, 1,800 s on the Mini). States never read go first, then the longest
unread; a run cut short says so and the rest go first next week. A first
read of all fifty takes about 16 minutes on the laptop, so on GitHub alone it
would spread over two or three weeks; the Mini does it in one. No block
rotation is needed for the API: a recess week is 65 requests, a sitting week
about 130 with the bulk fallback, both under 250.

## What Open States gives, per state

Most recent full session of each state (the latest non-special session that
has begun), read whole from its bulk file on 9 October 2026, run through the
shared taxonomy (v1.19) on the title, the state's subject terms and its
abstract. "On our ground" excludes migration (area 11), as everywhere.
"Positions linked" is the share of recorded positions tied to an Open States
person ID. The last column is bills with an action in the week to 9 October.

| State | Session read | Bills | On our ground | Of those signed | Votes | Positions linked | Abstracts | Subjects | Action in week to 9 Oct |
|---|---|---|---|---|---|---|---|---|---|
| Alabama | 2026rs | 1,507 | 31 | 7 | **none** | | 100% | 100% | 0 |
| Alaska | 34 | 857 | 20 | 2 | 1,076 | **no positions** | 0% | 99% | 0 |
| Arizona | 57th-2nd-regular | 2,190 | 56 | 2 | 3,463 | 99% | 0% | 0% | 0 |
| Arkansas | 2025 | 1,928 | 41 | 22 | **none** | | 0% | 0% | 0 |
| California | 20252026 | 5,041 | 253 | 125 | 21,527 | 99% | 94% | 94% | 0 |
| Colorado | 2026A | 714 | 26 | 14 | 3,770 | **18%** | 88% | 95% | 0 |
| Connecticut | 2026 | 1,283 | 26 | 12 | 753 | 99% | 0% | 99% | 0 |
| Delaware | 153 | 1,297 | 56 | 26 | 2,035 | 99% | 99% | 0% | 4 |
| Florida | 2026 | 1,931 | 47 | 5 | 2,131 | 99% | 100% | 98% | 0 |
| Georgia | 2025_26 | 5,480 | 53 | 10 | 2,517 | 86% | 100% | 39% | 11 |
| Hawaii | 2026 | 6,728 | 114 | 4 | 8,897 | 95% | 78% | 100% | 0 |
| Idaho | 2026 | 817 | 23 | 8 | 853 | 93% | 0% | 100% | 0 |
| Illinois | 104th | 12,820 | 109 | 13 | 10,095 | 96% | 0% | 0% | 23 |
| Indiana | 2026 | 935 | 33 | 8 | 689 | 98% | 99% | 94% | 0 |
| Iowa | 2025-2026 | 4,370 | 124 | 15 | 1,411 | 97% | 0% | 96% | 7 |
| Kansas | 2025-2026 | 1,483 | 43 | 2 | **none** | | 0% | 88% | 0 |
| Kentucky | 2026RS | 1,737 | 85 | 5 | 886 | 99% | 98% | 98% | 0 |
| Louisiana | 2026 | 2,616 | 40 | 21 | 3,172 | 96% | 0% | 0% | 0 |
| Maine | 132 | 2,451 | 57 | 15 | 1,575 | 88% | 0% | 91% | 0 |
| Maryland | 2026 | 2,677 | 56 | 9 | 2,599 | 98% | 0% | 2% | 0 |
| Massachusetts | 194th | 19,057 | 215 | 0 | 329 | 96% | 64% | 0% | 46 |
| Michigan | 2025-2026 | 4,211 | 108 | 2 | 1,277 | 99% | 0% | 87% | 30 |
| Minnesota | 2025-2026 | 10,590 | 151 | 3 | 453 | 99% | 0% | 98% | 2 |
| Mississippi | 2026 | 4,116 | 69 | 5 | 1,826 | 92% | 0% | 100% | 0 |
| Missouri | 2026 | 3,177 | 134 | 6 | 1,478 | **no positions** | 33% | 61% | 0 |
| Montana | 2025 | 6,159 | 90 | 14 | 8,713 | 100% | 0% | 100% | 0 |
| Nebraska | 109 | 1,847 | 32 | 6 | 1,772 | 98% | 0% | 0% | 1 |
| Nevada | 83 | 1,210 | 32 | 9 | 1,333 | 95% | 0% | 0% | 0 |
| New Hampshire | 2026 | 1,394 | 32 | 1 | 403 | **56%** | 0% | 0% | 36 |
| New Jersey | 222 | 11,130 | 233 | 0 | **none** | | 0% | 0% | 223 |
| New Mexico | 2026 | 812 | 8 | 1 | 266 | 93% | 0% | 89% | 0 |
| New York | 2025-2026 | 25,516 | 425 | 20 | 10,553 | 99% | 84% | 0% | 10 |
| North Carolina | 2025 | 2,338 | 87 | 14 | 774 | 99% | 0% | 100% | 5 |
| North Dakota | 69 | 1,106 | 25 | 9 | 2,169 | 98% | 86% | 0% | 0 |
| Ohio | 136 | 2,581 | 59 | 2 | 1,088 | 99% | 100% | 61% | 18 |
| Oklahoma | 2026 | 6,006 | 117 | 17 | 8,767 | 96% | 0% | 0% | 0 |
| Oregon | 2026R1 | 304 | 7 | 4 | 724 | 98% | 100% | 0% | 0 |
| Pennsylvania | 2025-2026 | 5,153 | 94 | 2 | 5,538 | 99% | 0% | 0% | 199 |
| Rhode Island | 2026 | 3,020 | 47 | 2 | 1,106 | 97% | 86% | 0% | 0 |
| South Carolina | 2025-2026 | 4,050 | 125 | 11 | 2,055 | 92% | 100% | 0% | 0 |
| South Dakota | 2026 | 666 | 14 | 7 | 1,512 | 83% | 0% | 92% | 0 |
| Tennessee | 114 | 9,092 | 162 | 40 | 16,782 | 99% | 0% | 100% | 0 |
| Texas | 89R | 11,503 | 538 | 70 | 6,471 | 94% | 0% | 100% | 0 |
| Utah | 2026 | 1,016 | 25 | 13 | 1,907 | 100% | 0% | 100% | 0 |
| Vermont | 2025-2026 | 1,718 | 23 | 0 | 149 | 93% | 0% | 0% | 0 |
| Virginia | 2026 | 3,637 | 75 | 16 | 11,228 | 92% | 100% | 0% | 5 |
| Washington | 2025-2026 | 3,413 | 38 | 8 | 2,306 | 100% | 0% | 0% | 0 |
| West Virginia | 2026 | 2,975 | 63 | 4 | 1,146 | 99% | 0% | 93% | 1 |
| Wisconsin | 2025 | 2,749 | 87 | 4 | 2,309 | 99% | 0% | 0% | 1 |
| Wyoming | 2026 | 335 | 10 | 3 | 1,254 | 100% | 100% | 0% | 0 |
| **All fifty** | | **209,743** | **4,418** | **627** | **163,137** | **96%** (7.3 of 7.6 million) | 35% | 42% | **622** |

The collector's own first read covers more than this table: every current
session (66, specials and Virginia's 2027 pre-filing included), 215,543
bills, and the watchlist: **4,570 bills on our ground, 1,853 of them on a
tier-1 term**, 626 signed into law.

**By area** (collector's first read, every current session): abortion 972,
assisted dying 255, gender medicine 138, conversion practices 47, sex-based
rights 314, parental rights and education 1,414, free speech and civil
liberties 458, freedom of religion 194, marriage and family 82, surrogacy and
embryology 143, prostitution and trafficking 663, organ donation 106.
Tier 1 alone: abortion 622, parental rights 475, free speech 271, sex-based
rights 129, surrogacy 112, organ donation 106, gender medicine 74.

**Noise, measured.** Area 6 is inflated by tier-2 child-welfare terms that
state subject indexes use everywhere: "foster care" (475 bills) and "child
protection" (289; Texas files every Department of Family and Protective
Services bill under it, which is why Texas has 303 bills in area 6). Area 12
by "human trafficking" (518), mostly awareness signs and training bills. Area
1 catches Down syndrome awareness resolutions ("Down syndrome", 37). The
States section therefore orders each state's bills by step, then score, then
tier, and shows eight per state; the judge (below) is what should sort them.

## American naming, again: what the taxonomy missed

State titles differ from Congress's. The latest session of all fifty was
searched for the American names; "missed" means a bill whose title, subjects
and abstract carry the phrase and matched no area.

| Name | Bills carrying it | Missed | The misses |
|---|---|---|---|
| Women's Bill of Rights | 4 | **4** | MN SF 1651, HF 700; KY HB 334, SB 179 ("sex-based classifications") |
| Given Name Act | 2 | **2** | OH HB 190 Given Name Act; WA SB 5136 (students' given names) |
| SAFE Act (Save Adolescents from Experimentation) | 14 | 13 | all 13 misses are gun-safe, school-safety and surveillance acts: the name cannot be a term |
| heartbeat | 14 | 0 | |
| medical aid in dying / end-of-life options | 38 | **9** | Illinois's End-of-Life Options Act (HB 1328, SB 9 and three amending bills); MA SD 1665 |
| chemical abortion / abortion pill | 81 | 1 | NH HB 1702 ("chemical abortions", plural) |
| bathroom / restroom / changing facilities / locker room | 154 | 130 | almost all genuinely off our ground (park restrooms, recording devices); on it: AL HB 478 Restroom Access Act, MN SF 2294 |
| drag | 23 | 22 | 20 are drag racing; on our ground: AZ HB 2589, IA HSB 158 (minors at drag shows) |
| parental rights in education / parents' bill of rights | 186 | 5 | AZ SB 1328, HB 2661; WA SB 5181; OH HB 327 (PRIDE Act, the other side) |
| divisive concepts | 2 | 1 | GA HB 293 (repeal of the Protect Students First Act) |
| women's / girls' sports, Riley Gaines | 35 | **8** | GA HB 267 Riley Gaines Act; TN SB 468, HB 571 (Riley Gaines Women's Safety and Protection Act, enacted); MN SF 3979 Preserving Girls Sports Act, SF 2294 |
| gender transition / help not harm | 152 | **29** | AZ SB 1095, HB 2085, SB 1177; KS HB 2071, SB 63 Help Not Harm Act; the rest appropriations |
| born alive (as "born alive infant") | 34 | **9** | IL HB 2618, HB 1335, HB 2622; MA HD 3554, H 2428 |
| reproductive freedom / legally protected health care (shield laws) | 116 | 16 | GA SB 246, HB 598 Reproductive Freedom Act; DE SB 5; CT SB 295; CA AB 1854 |
| biological sex / human biological sexes | 84 | 5 | SC H 3506; WA HB 1629; NY A 5478, S 1049 |
| harmful to minors / obscenity in libraries | 209 | 96 | AR HB 1028; FL SB 1692; many are plain obscenity offences |
| DEI / diversity, equity and inclusion | 141 | 134 | by decision DEI is not a term (caught only where it meets our areas) |
| critical race theory | 11 | 10 | Iowa's DEI and CRT bills; out of scope with DEI |
| pronoun | 64 | 40 | mostly statutory pronoun clean-ups (death certificates, licensing) |
| ten commandments, chaplain, surrogacy, IVF, pregnancy centres, conversion therapy, RFRA | 296 | 0 | |

**46 of these are in `config/watchlist-us-states.yaml`**, keyed
`<ST>/<session>/<identifier>` (all 46 checked against the bulk files). The
lasting fix is terms, Christopher's call (the taxonomy is generated from
docs/keyword-taxonomy.md, never hand-edited). Candidates, each measured
above: "women's bill of rights", "sex-based classification*", "given name"
guarded by school or student company, "end-of-life option*", "born alive
infant" (or "born alive" unguarded), "Riley Gaines", "girls' sports" and
"female athletic*", "gender transition*" guarded to minors, "help not harm",
"reproductive freedom", "legally protected health care", "chemical
abortions", "drag show*" and "drag performance*", "restroom access" and
"multiple-occupancy" guarded by sex, "human biological sex*", "harmful to
minors" guarded by library or school. Not candidates: "SAFE Act" (13 of 14
are other acts), "drag" alone (20 of 23 are drag racing), "bathroom" alone.

**Done at taxonomy v1.20** (Christopher, 9 October 2026: "Add the state
keyword and other candidates to the taxonomy"). Measured against v1.19 over
all 66 current sessions read whole from the bulk files (215,543 bills; the
watchlist applied, so a bill already keyed does not count): 117 state bills
gain an area, 91 of them newly on our ground. Adopted: "women's bill of
rights", "sex-based classification*", "human biological sex*" (tier 1, area
5); "Riley Gaines", "girls sports", "female athletic*", and "restroom access"
and "multiple-occupancy" guarded by sex company (tier 2, area 5); "Given Name
Act" (tier 1) and "given name*" guarded by school, student, pupil or pronoun
(tier 2, area 6); "End of Life Options" and "End-of-Life Option* Act" (tier 1,
area 2); "born alive infant*", "reproductive freedom" and "legally protected
health care" (tier 1, area 1), and "shield law*" vetoed by press company (tier
2); "abortions" (tier 1), which covers "chemical abortions" and was the larger
find (the plural never matched); "gender transition*" guarded by minors
company (tier 1) and bare (tier 2), and "help not harm" (tier 1, area 3);
"drag show*", "drag performance*" and "harmful to minors" bare (tier 2, area
6). The library guard on "harmful to minors" caught 6 bills against 29 bare,
and the rest are age verification for adult sites and library materials, so
the term is bare and tier 2. By term, bills gaining: harmful to minors 29,
gender transition 17, abortions 16, reproductive freedom 9, online safety 8,
drag 8, trafficking in persons 5, blasphemy 5, Equality Act 4 (Hawaii's
resolutions), End of Life Options 3, Riley Gaines 3, legally protected health
care 3, born alive infant 2, restroom access 2, multiple-occupancy 2, women's
bill of rights 1, shield law 1. Terms that today catch only watchlisted bills
(sex-based classification, human biological sex, Given Name Act, help not
harm) were kept because a key is one session's bill and the names come back
in the next. The 46 watchlist entries stay. Still not terms: "SAFE Act", bare
"drag", "bathroom", bare "born alive" (two Rhode Island criminal-code bills),
and bare "gender identity" (232 state bills would gain area 5, nearly all
anti-discrimination boilerplate). Stored bills are re-derived by
`--reclassify`, which narrows only; a session's bills the old net missed are
picked up by `--full` (a bulk re-read), see Gotchas.

## Sessions in October 2026

By Open States' dates, seven legislatures have a session open on 9 October:
California (to 30 November, though it adjourned in August), Georgia (a
special session), and the full-time Michigan, New Jersey, New York, Ohio and
Pennsylvania. North Carolina's extra session sat on 7 and 8 October.
Massachusetts (formal sessions ended 31 July) and Wisconsin still act. 17
states had a bill with an action in the week to 9 October (622 bills), 33
had none. Texas meets
in odd years only: 89R (2025) and its two called sessions are the latest,
and the 90th convenes in January 2027. Virginia's 2027 session already has a
bulk file (pre-filed bills) and is read.

## Gotchas

- **Session dates are not reliable.** Mississippi's 2026 regular session is
  dated 6 January to 5 April **2025**; Alaska's two-year 34th Legislature
  "ends" 21 May 2025; Illinois's 104th General Assembly "ends" May 2025.
  `classification` is blank for a third of sessions and "primary" for some
  specials (Mississippi 20261E, Minnesota 2025s1, Missouri's extraordinary
  sessions). The collector's rule: the latest non-special session that has
  begun, any session begun in the last year or ending in the last month,
  any future session with a bulk file, and any session whose bulk file was
  regenerated in the last 45 days (which is what catches Mississippi 2026).
  It read 66 sessions.
- **`updated_since` is not movement** (above): `action_since` is.
- **Positions do not always match the tally.** 991 of the 6,196 votes
  stored (16%) list a different number of positions from their own counts:
  Texas 319 (both ways), Colorado 150, Wisconsin and South Carolina 73 to
  77, Iowa 73. Wyoming's House (62 members) lists 63 positions on three
  floor votes. Stored as given with `positions_ok = 0`, never "fixed".
- **Unlinked voters.** Colorado links 18% of positions to a person, New
  Hampshire 56%; the name is kept and the person left NULL, never guessed.
  **Alaska and Missouri give vote totals with no positions; Alabama,
  Arkansas, Kansas and New Jersey give no votes at all.**
- **Abstracts and subjects are thin.** 35% of bills have an abstract and 42%
  subject terms; in 13 states (Arizona, Arkansas, Illinois, Louisiana,
  Nebraska, Nevada, New Hampshire, New Jersey, Oklahoma, Pennsylvania,
  Vermont, Washington, Wisconsin) the title is all there is.
- **Action dates can be the session's, not the day's.** Vermont dates the
  governor's signature of H 951 to 29 May while its text says 16 June.
- **The official link is not always a bill page.** Alabama's source is the
  site's search page; Vermont lists a roll-call JSON endpoint first, so the
  collector prefers a page that is not a data endpoint and carries the
  bill's number.
- **Resolutions "become law" in California** (chaptered by the Secretary of
  State): the edition says "adopted", never "signed into law", for any
  resolution.
- **The API timed out once** (a Florida page, "The read operation timed
  out"): a timeout or 5xx is tried once more, then the state is a gap and its
  bulk file stands in.
- **Store size.** All fifty's first read is about **100 MB** in SQLite, of
  which every position (287,019) and its indexes are 67 MB. The store was 963
  MB on 9 October against the release asset's 2 GB ceiling, so only bills on
  our ground are stored (with the bills already stored); everything else is
  counted per session. Storing every bill and every position would be some
  7.6 million rows and would not fit. A taxonomy change that widens the net
  is applied by `--full` (bulk re-read), not `--reclassify` (which narrows).
- **DC and Puerto Rico** are in Open States and not read (the decision is the
  fifty states).

## Schema (`src/us_states_store.py`)

- `uss_sessions` (state, session): name, dates as listed, bulk URL and its
  stamp, the stamp last read, `read_via` ('bulk' / 'api'), `data_through`,
  bills read and on our ground at the last full read.
- `uss_bills` (`bill_id` = 'ocd-bill/...'): `bill_key` 'TX/89R/HB229',
  state, session, identifier, title, classification, subjects, abstract,
  chamber of origin, the state's URL, introduced, latest action, first
  passage in each chamber, signed (became-law or executive signature),
  vetoed, sponsor, areas, matched terms, tier, judge's score and why-line.
- `uss_actions` (bill, order), `uss_sponsors` (bill, seq; person ID or
  NULL), `uss_votes` ('ocd-vote/...'; counts, `positions`, `positions_ok`),
  `uss_vote_people` (vote, seq; name, person ID or NULL, option),
  `uss_people` ('ocd-person/...'; from the open per-state CSV).

## The edition

**The states**, after the Supreme Court: what moved on our ground this week,
by state, with the furthest step each bill took (signed into law, vetoed,
passed in the Senate, passed in the Assembly or House of Delegates as the
state names it, introduced), linked to the state's page; eight per state,
the rest counted. A quiet week says so, with how many legislatures were read
and which have a session open. A top line counts laws signed; the DM has one
line. Week to 9 October 2026: four bills introduced, all New Jersey. Week to
17 April 2026 (from the stored first read): 20 signed, 44 passed a chamber,
9 introduced, in 22 states.

**The judge** takes state bills only once they have an action in the last
30 days: 107 on 9 October, about $0.25 by `tools/us_triage.py --dry-run`.
Not run: spend needs a yes, and `US_JUDGE` decides it in the weekly.

## Schedule and coverage

`jobs/us-weekly.sh` runs `tools/us_states.py` after the Supreme Court and
before the judge: 600 s on GitHub (the step budgets then total about 6,700 s
of the 120 minutes), 1,800 s on the Mini (inside its three hours).
`OPENSTATES_API_KEY` is passed from an Actions secret; without it the step
logs one [gap] and skips. `tools/coverage.py` watches `uss_sessions` (weekly:
every run re-stamps every listed session), `uss_people` (weekly, a week's
grace for the rotation), and `uss_bills` and `uss_votes` a month plus a
month's grace (a bill is re-stamped only when it moves; the full-time
legislatures move all year). A step heartbeat, "US states", excuses the
empty tables until the first run.

## Open questions for Christopher

1. **The Actions secret and the Mini.** `OPENSTATES_API_KEY` must be added as
   a repository secret and to `~/runner/env` on the Mini; until then the step
   is one [gap] a week.
2. **The tier.** Default (250 a day) works with the bulk fallback. Bronze
   (1,000 a day) would let the sitting-season weeks run by API alone; it is
   a request to Open States, not a purchase we can make from here.
3. ~~Taxonomy terms~~ for the state names above: adopted at v1.20
   (9 October 2026), above. The 46 watchlist entries stay.
4. **Noise in area 6 and 12** from "foster care", "child protection" and
   "human trafficking" in state subject indexes: guard them for the states,
   or leave them to the judge?
5. **The judge for states** (107 items, about $0.25 now; perhaps $2 to $4 a
   week in session). Yes or no?
6. **Store size.** Positions for bills on our ground add about 67 MB a
   session cycle. Keep every position, or only votes on tier-1 bills?
7. **Which states first in the edition.** All fifty are printed by state
   alphabetically; a salience order (states with live fights first) is a
   one-line change if wanted.
