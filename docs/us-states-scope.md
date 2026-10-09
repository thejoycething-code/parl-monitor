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

(The weekly read described here, API first with the bulk files as fallback,
was replaced the same evening by bulk files first and an API top-up of the
last day: see "No paid tier" below. The measurements stand.)

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

## No paid tier (measured 9 October 2026)

Open States quoted Christopher $2,900 a year for 1,000 requests a day and
$7,900 for 10,000. Christopher: "upgrading tiers costs a huge amount, so we
may need to explore other methods." There is no budget, so the route below
works on the free key (250 a day) and would work, but for the last day of
each week, with no key beyond the two-request session list.

**Recommendation: bulk files for the whole week, the free key for the last
day only.** Built in `tools/us_states.py`. A weekly run spends **2 keyed
requests** for the session list plus a **top-up of 68 to 90** in a sitting
week (a handful in recess), never more than 150 a run or 225 a UTC day
across all runs (a ledger in the store, `uss_api_ledger`). No daily Mini job
is needed: see "Why not spread it over the week" below.

### 1. How often the bulk files are regenerated

- **The exporter writes a new file, under a new random name, for every
  session with a bill changed in the window, nightly.** Read in its source
  (`openstates/openstates.org`, `bulk/management/commands/bulk_export.py`):
  `export_all_states(--with-updates-days)` picks sessions with a bill whose
  `updated_at` is recent, and each export is `<ST>_<session>_csv_<random>.zip`
  uploaded beside the old ones (old URLs keep answering: a 2022 Minnesota
  file still does). Open States re-stamps `updated_at` whenever a scraper
  re-runs, so a sitting legislature gets a new file every night.
- **Measured now (recess):** of the 66 current sessions, **25 were stamped
  8 October between 23:02 and 23:21 UTC** (one nightly pass, alphabetical,
  AK to WI), 26 within the week (1,111 MB), the rest when they last changed
  (Texas 89R: 5 August 2025, after its last action). S3 `Last-Modified`
  equals the stamp the API lists.
- **Measured in session (the Wayback Machine's copies of the old listing
  page, openstates.org/data/session-csv/, which printed every file's
  "updated" date):** 27 January 2023, **48 of 50** sessions of 2023 stamped
  26 January; 19 April 2023, **48 of 53** stamped that day; 1 February 2022,
  43 of 44 stamped 31 January (on 19 January 2022 they were monthly, 1
  January: the daily cadence dates from the end of January 2022). The
  bucket itself cannot be listed (403), and the listing page now needs a
  login, so the URLs come from the API's jurisdiction list: **2 keyed
  requests a run**.
- **The file lags the API by about a day.** Pennsylvania's file of 8 October
  23:18 UTC holds actions to 7 October; the API (read at 13:00 the next day)
  had 187 bills with an action since 5 October against the file's 183: the
  difference is five resolutions acted on 8 October and scraped at 02:10 to
  02:26 UTC on the 9th (plus one bill the file had and the API page not).
  New Jersey's file of 8 October holds actions to 5 October; two bills acted
  on 8 October were in the API only. New York matched exactly (6 and 6). So
  a Friday 09:00 UTC run has, from the files, the week to Wednesday or
  Thursday, and `data_through` is the stamp's day less one.
- **Conditional GET works but does not matter.** `If-None-Match` and
  `If-Modified-Since` on an unchanged file answer 304 with no body; but a
  changed file has a new URL, so the collector compares the listed stamp
  with the one it read and never downloads an unchanged file at all.
- **Sizes and times (laptop, home connection, about 8 MB/s):** New York
  2025-2026 184 MB in 23 s, California 162 MB in 26 s, Texas 89R 145 MB in
  19 s, Pennsylvania 88 MB in 11 s, Massachusetts 45 MB in 10 s, New Jersey
  20 MB in 3 s; all 66 current files 2,175 MB. Reading a file for a week's
  bills: New York and California under 3 s in recess; Texas for a sitting
  stretch of 2025 (491 bills on our ground kept) 28 s, New Jersey 12 s,
  Massachusetts 41 s (its votes). In January to June 2027 most legislatures
  start new sessions, whose files begin small and grow: about 1 to 2 GB and
  10 to 15 minutes a week, inside the Mini's 30 minutes. GitHub's 10
  minutes may not finish in a sitting week; the rotation carries the rest.

### 2. The free key, used only where the files cannot reach

- **Busy days are too big for `action_since` by state.** From the files:
  Texas had 1,690 bills with an action on 14 March 2025 (85 pages of 20),
  New York 15,331 on 7 January 2026, Massachusetts 8,248 on 27 February 2025;
  a sitting week costs 687 to 949 pages across the fifty.
- **So the top-up asks by bill number.** `/bills` takes `session`,
  `action_since` and **up to 20 identifiers a request** (the API's own cap,
  read in `openstates/api-v3`, `api/bills.py`; tried live: Pennsylvania SR
  387 and SR 393 back, the four quiet bills not). It asks only for bills on
  our ground in the store that moved in the last 30 days, since the file's
  `data_through`. Measured from the stored actions: **860 such bills in 43
  sessions for the 30 days to 17 April 2026 (68 requests) and 1,251 in 46
  sessions to 3 March 2026 (90 requests)**; 161 of them moved on Thursday 5
  March alone, in 38 states. Asking every bill on our ground would be 256
  requests; the 30-day rule is what makes it fit.
- **States in order of salience:** a file more than three days behind (an
  export missed) first, then most live bills on our ground, then most tier-1
  bills. A run stops at its time or request budget and says which states it
  did not reach; the next file covers them.
- **Live test (laptop, scratch copy of the store, 9 October):** Pennsylvania,
  New Jersey, New York and Texas, files unchanged since read, so nothing
  downloaded; top-up 3 requests (NJ 11 live bills, PA 7, NY 3; Texas none
  live), one Pennsylvania bill refreshed with its vote; 5 keyed requests in
  all, 27 s.
- **The ledger.** `uss_api_ledger` counts keyed requests per UTC day in the
  store, written before each request is sent (a refused request still
  counts), checked before each. Defaults: 150 a run, 225 a day (25 kept for
  a hand probe). A 429 for the day closes the ledger to 250 for every later
  run that day. The Mini and GitHub's backup both fetch the store first, so
  a backup run the same day sees what the Mini spent; a run that crashes
  before publishing leaves the day uncounted for the other runner, which
  is why a run's own budget (150) is also capped and why the day refusal is
  handled.
- **Why not spread it over the week.** The edition is weekly and the files
  are a day behind whatever day they are read, so reading them daily does
  not make Friday's edition fresher; only the last day needs the API, and
  that is about 90 requests in session, a third of one day. A daily job
  would download every changed file seven times a week (7 to 14 GB from
  Open States' bucket) for nothing the edition prints. If daily alerts on
  state bills are wanted later, the same collector with `--no-people` run
  each morning on the Mini, under the same ledger, is the way: about 2 + 30
  keyed requests a day.
- **Zips only is a flag away:** `--no-topup` spends the 2 list requests and
  nothing else; the edition is then good to Wednesday or Thursday.

### 3. Running Open States' own scrapers (measured 9 October 2026)

Measured in a scratch directory on the laptop; nothing installed in the repo.

- **Licence:** openstates-scrapers is GPL v3, openstates-core MIT. Running
  them internally is fine; copyleft bites only if a modified version is
  redistributed.
- **Weight:** a shallow clone is 6.5 MB; it needs Python 3.13 (the Mini and
  laptop ship 3.9, so a separate `uv` venv), 121 packages (Django 3.2, boto3,
  pandas, pymupdf...), a 397 MB venv, 40 s to install. Scraping writes JSON
  and needs no Postgres. The Docker image is 890 MB and amd64-only, so it
  would run emulated on the Mini: the venv is the better route.
- **Per state, the bills scraper:**

| State | Source | Extra | Cost of a run |
|---|---|---|---|
| Texas | State FTP, one XML per bill, plus a capitol.texas.gov page for companions | none | No incremental mode. Measured: 146 requests and 118 bills in 10 minutes (about 4.8 s a bill); a 10-11k-bill regular session is **about 14-15 hours a run** |
| New York | NY Senate Open Legislation API plus one Assembly vote page per bill | a free NY key (not requested) | Incremental `window=7d`: 1 API call + 2 per changed bill |
| California | `pubinfo_2025.zip`, **1.29 GB**, loaded into a local MySQL | a MySQL server | one large download a run |
| New Jersey | The Legislature's own bulk zips (CSV tables + 6 vote zips) | none | about 7 requests: cheap |
| Massachusetts | JSON list, then an HTML crawl per bill with roll-call PDFs | none | about 35k requests, about 10 hours at 60 a minute |

**Verdict:** free and easy to install, but cheap only for New Jersey (and
New York with a free key). Texas and Massachusetts are long full crawls and
California needs MySQL and a 1.3 GB download every run. Not adopted: the
bulk-plus-top-up route above already keeps these states current a day
behind, for at most 150 keyed requests a run. If one state ever matters
enough to be same-day, New Jersey's bulk zips or New York's API
(`window=7d`) are the ones to self-run.

### 4. LegiScan's free tier (measured from what is reachable, 9 October 2026)

- **legiscan.com** (its API page, terms, datasets) answers a Cloudflare
  challenge to our client: recorded, not bypassed. **api.legiscan.com is not
  behind it**: the API manual (v1.91, revision 20250317) downloads from there.
- **Limit:** "Public service keys have a monthly limit of 30,000 queries"
  (the manual).
- **Change detection:** load each session's dataset (getDatasetList /
  getDataset: a base64 ZIP of every bill, vote and person, rebuilt weekly),
  then `getMasterListRaw` per state compares an MD5 `change_hash` per bill,
  and `getBill` fetches only the changed ones. Minimum refresh: master list
  hourly, bill 3 hours, datasets weekly.
- **Budget:** a daily master-list check for 50 states is about 1,500 queries
  a month; with changed bills and weekly datasets, well under 30,000.
- **Licence:** search snippets of legiscan.com say CC BY 4.0, but the wording
  could not be read through Cloudflare. **Christopher reads
  https://legiscan.com/legiscan and /terms-of-service in a normal browser**
  before we rely on it.
- **Key:** a free OneVote account at legiscan.com, then the API form at
  https://legiscan.com/legiscan. Christopher does this himself; questions to
  api@legiscan.com.
- **Verdict:** the best free route to same-day data for all 50 states, if the
  licence suits. Not needed for the route above, which is a day behind.

### 5. The states' own sources (measured from the UK, 9 October 2026)

| State | Source | Key | From the UK | What it gives | Verdict |
|---|---|---|---|---|---|
| Texas | anonymous FTP `ftp.legis.state.tx.us/bills/<session>/billhistory/` | no | answers (FTP only; https times out) | one XML per bill (actions with times, sponsors, subjects, committees, versions), rebuilt nightly at 02:00 in session; **no member roll calls**; the Acceptable Use notice asks data users to use the FTP | easy |
| California | `downloads.leginfo.legislature.ca.gov` | no | answers | full session 1.2 GB; nightly change files of 2 KB to 1.2 MB (about 21:20 Pacific), with votes per member | moderate (one load, then daily deltas) |
| New York | `legislation.nysenate.gov/api/3` | free key | **times out** | bills, updates since a time, per-member votes for both houses | easy once keyed, but needs a US runner |
| New Jersey | `pub.njleg.gov/leg-databases/` | no (expected) | **times out** | bills, actions, votes, sponsors (not measured) | needs a US runner to measure |
| Massachusetts | `malegislature.gov/api` | no (inferred) | **refused** | document list; history and roll calls need HTML | moderate to hard, needs a US runner |

New York, New Jersey and Massachusetts look closed to non-US addresses, so
any direct collector for them would run on GitHub's runners, not the Mini.

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
2. **The tier.** No paid tier (no budget). The free key's 250 a day carries
   the "No paid tier" route with room to spare; the options that need
   Christopher are listed there (keys to request, nothing to buy).
3. **Taxonomy terms** for the state names above (women's bill of rights,
   end-of-life options, born alive infant, Riley Gaines, gender transition
   for minors, reproductive freedom, legally protected health care, drag
   shows, given name). Until then the 46 watchlist entries stand in.
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
