# UN sources: what is machine-readable and what is not

**Probed 16–17 August 2026.** Written so nobody repeats the probing. Every
"no" below names the specific mechanism that blocks it, not a guess from a
symptom — four things were called impossible during this work and turned out
to be possible, always because a rendered page had been read instead of the
client code that fetches it.

## Working, and in the monitor

| Source | What it gives | Notes |
|---|---|---|
| UPR Info Uwazi API | 2,331 recommendations: who asked, who was asked, Supported/Noted | `upr-info-database.uwazi.io/api`. Issue filter values must be **full UUIDs** from `/api/thesauris`; an abbreviated id returns `totalRows=0` with HTTP 200. `searchTerm` needs **quoted phrases** or it matches everything. |
| UPR Info session list | UPR working group schedule to January 2031 | Month precision only. Used because OHCHR's own UPR pages are Cloudflare-challenged. |
| OHCHR calls for input | 15 open consultations with deadlines | Listing only. **Detail pages return 403** to non-browser clients, so there is no description text to match on. **Since 13 Oct 2026 the listing itself is Cloudflare-challenged; no alternative route found (below).** |
| ~~OHCHR HRC sessions page~~ HRC portal (13 Oct 2026) | Every HRC regular session from the 46th, with date range and a page per session | `hrcportal.ohchr.org/hrc-sessions-all` (`hrcmeetings.ohchr.org` now 301s there). Replaces `www.ohchr.org/en/hr-bodies/hrc/regular-sessions`, challenged since 13 Oct 2026, which stays as the fallback only. Drupal; robots.txt allows it, Crawl-delay 10 (one request a run). |
| Treaty body master calendar | 49 reporting deadlines by country and committee | `MasterCalendar.aspx`. `SessionsList.aspx` is a Telerik postback grid that stays empty — that difference cost an hour. **Not fetched since 13 Oct 2026: `tbinternet.ohchr.org/robots.txt` is `Disallow: /`** (checked on every run; it resumes if that changes). |
| Indico.UN treaty body sessions (13 Oct 2026) | CEDAW, CRC and CCPR plenary sessions about a year ahead, with the states under review where listed | `indico.un.org/category/{828,833,821}/events.ics`: UNOG's meeting registration system, its own calendar export. No robots.txt (404); requests still go through the robots guard. Sub-category working groups share the numbering, so plenaries are told apart by length (10 days or more) and CANCELLED events dropped. Sitting dates, **not** reporting deadlines. Replaces the master calendar in the check log (`Treaty bodies (Indico.UN; OHCHR)`). |
| UN Women CSW pages | CSW session ranges (CSW71: 8–19 March 2027) | The landing page has almost no dates; the **per-session pages** carry them in prose ("from 8 to 19 March 2027"). |
| UN GA session page | Session window (81st: 8 Sep 2026 – 7 Sep 2027) | Session number = year − 1945, derived not hardcoded. |
| docs.un.org | Draft resolutions by symbol (`A/C.3/81/L.7`, `A/HRC/63/L.4`) | Needs `?direct=true`. Existence is decided by **content type**, not status: a missing symbol answers 200 with an HTML page. Range requests honoured, so a check costs 64 bytes — but ~10s each, which is server latency not transfer. |
| UN Journal API | Third Committee meetings with times, official/informal | Base from `journal.un.org/assets/config.json`. `GlobalCalendar` is **POST** with `{locationValue, startDate, endDate, organs}` and **ISO datetimes** — plain dates return 400. Organ UUIDs from `AdvancedSearch/Organs` (3,495). |
| UN Journal API, GA plenaries (13 Oct 2026) | General Assembly plenaries and high-level meetings, with each meeting's agenda and draft symbols | `GlobalCalendar` with the General Assembly organ (`9615d07d-d53c-e711-84fb-0050569f00b6`). A plenary's title is only a number, so `GET officials/<meeting id>` (headers `location`, `language`) is read for the agenda ("Global health and foreign policy - Item 129: Draft resolution (A/81/L.6)") and programme notes (which PGA letters announced it). About a week ahead. |
| PGA letters (13 Oct 2026) | Every letter of the President of the General Assembly to member states, dated, with title, PDF and a summary page | `www.un.org/pga/81/documents/letters/` (the session number moves each September). Plain HTML; robots.txt allows it with Crawl-delay 10, honoured. Not challenged. Where plenary votes are announced first: the 7 October 2026 letter named the 12 October vote on the pandemic declaration. |
| docs.un.org, GA plenary drafts (13 Oct 2026) | `A/81/L.n`, the series political declarations are adopted from | Same walk and first-page parse as `A/C.3/81/L.n`. A President's draft has no sponsor list; its title follows "submitted by the President". |
| ~~docs.un.org~~ **refused since 13 Oct 2026** | | `?direct=true` now redirects to `documents.un.org/api/symbol/access`, which `documents.un.org/robots.txt` disallows. Every docs.un.org row in the check log says "could not read: robots.txt disallows (documents.un.org)". See the section at the end. |

## Not available, with the reason

**Draft resolutions and voting records.** The biggest gap and, unlike the
others, not solved. Five routes, each closed for a different reason:

- **Digital Library search** — returns HTTP 202 with an empty body, every
  time, on every query and format. A 202 that never resolves is a block
  dressed as a success.
- **Digital Library OAI-PMH** — works, and rate-limits politely with
  `Retry-After` (a two-day harvest succeeded on the seventh attempt). But
  `ListSets` exposes exactly one set, `sanctions`, and every record returned
  by an unset date-range harvest carries `setSpec: sanctions`. The feed is
  that one collection, so GA and HRC voting records are not in it.
- **HRC extranet** (`hrcmeetings.ohchr.org`) — session pages exist for each
  regular session but contain no `A/HRC/NN/L.n` references; draft resolutions
  sit behind the e-delegate login.
- **UN Journal daily list** — real and open, but it is a "documents issued"
  feed of 12–20 items a day and carries no committee L-documents.
- ~~**undocs.org / docs.un.org** — serve a ~4KB redirect shell~~ **WRONG,
  corrected the same day.** `docs.un.org/en/{symbol}?direct=true` serves the
  actual PDF. The `direct=true` is everything, and it was named in the
  Journal app's own config file (`undocsUrl`). `A/C.3/80/L.1` is a 256KB
  Third Committee draft resolution. Draft resolutions are now discoverable by
  symbol — see below.

**Third Committee agenda items — SOLVED, from an unexpected direction.** There
is no agenda endpoint: the meetings page chunk makes no HTTP calls of its own,
and the Journal archive PDF path is built from minified constants. But
`A/C.3/{session}/L.1` is not a draft resolution at all — it is the
Organization of Work note, and its annex is the committee's dated PROGRAMME OF
WORK, item by item ("Thursday, 9 October, 10 a.m. — Item 25 Social
development"). One document, fetched by symbol.

**Reading PDFs** needs pypdf, approved 2026-08-17. A stdlib attempt returned a
page of "en-GB": the body text uses subset fonts whose bytes need the embedded
ToUnicode map. With pypdf, every draft's first page yields its agenda item,
subject, date and type in a fixed order.

Note that resolution TITLES are a third distinct matching surface, after UPR
recommendation text and call-for-input titles. The annual omnibus resolutions
are called "Rights of the child" and "Advancement of women" — deliberately
generic, and matched nothing until those exact phrases were added to the UN
taxonomy as tier 2. Generic is the point: the omnibus is the vehicle CSE and
SRHR language gets inserted into.

**OHCHR UPR pages.** Cloudflare bot challenge (`cf-mitigated: challenge`,
"Just a moment..."). Note this is path-specific: the HRC branch of the same
host is not challenged, and a nonexistent OHCHR path returns 404, which is
how the 403 was confirmed as a real decision rather than a wrong URL.
Answered by using UPR Info instead.

## Voting records — SOLVED via session reports

Route 3 below was the one that worked, and it was reachable all along once
`?direct=true` and pypdf were in hand. `A/HRC/{session}/2` is the session
report: 219 pages for session 58, carrying 16 recorded votes in a fixed form.
Each vote is anchored to the nearest preceding draft symbol, and tallies are
counted from the name lists rather than read from prose, because the prose
form varies between sections while the lists are always there.

**The validator that proved the parse:** the Council has 47 members, so a
correct parse yields at most 47 names per vote and exactly 47 distinct states
across a session. The first version produced 48 — the 48th being
`A/HRC/58/2 GE.25-11364`, a page footer glued into a country list at a page
break. Tallies of 45 and 46 are legitimate: an absent member appears in none
of the three lists.

### Third Committee votes: not reachable, and why

The HRC route does not transfer. The Council publishes ONE session report
containing every vote; the Third Committee reports to the plenary once per
agenda item, in the `A/80/...` series that also carries every other
committee's output and hundreds of unrelated documents. Three routes tried,
17 August 2026:

- **Plenary verbatim records** (`A/80/PV.NN`) — the symbol form is right and
  works for session 79 (PV.40, 50, 60, 70 all served as PDFs), but **no
  session 80 record is published at all**, from PV.1 upward. Verbatim records
  lag by roughly a year. They also anchor votes on RESOLUTION numbers
  ("resolution 79/138") rather than draft symbols, so joining them to
  harvested drafts needs a draft-to-resolution mapping we do not have.
- **Committee reports** (`A/80/NNN`) — these DO cite draft symbols, which
  makes them the right source, but the series is 600+ documents and blind
  probing found none: A/80/460 is a one-page transmittal note, and A/80/520,
  560 and 600 are unrelated. At ~15-40s per probe this is not a search
  strategy, and the Digital Library search that would find them by title is
  the blocked 202.
- **Adopted resolutions** (`A/RES/80/N`) — served as PDFs, and each cites its
  Third Committee report symbol, so one of these would unlock the report. But
  the draft-to-resolution mapping is again missing, so finding the right one
  means enumerating.

**What would unlock it cheaply: one report symbol.** Any single Third
Committee report symbol for a session (visible in seconds on the UN's own
document index in a browser) gives the pattern, and the reports for other
items sit near it. That is a one-line answer from a human, not an hour of
enumeration, and it is why this is left undone rather than brute-forced.

Still open, if GA votes are ever wanted: **academic bulk datasets** collate GA
plenary voting going back decades, updated annually — historical rather than
live, and plenary rather than Third Committee. And the **Dag Hammarskjöld
Library** would know whether a bulk export exists, which is one email.

## Two rules earned the hard way

**Read the client, not the page.** Treaty bodies, CSW, UPR sessions and the
Third Committee were all called impossible after fetching a landing page and
counting dates. Every one was reachable — via a different page, a POST, an
app bundle naming its own API, or a config file naming its base URL.

**Distinguish a block from a bug.** 404 means wrong URL. 403 with
`cf-mitigated` means a bot challenge — route around it, do not defeat it. 202
with an empty body means blocked while looking successful. 503 with
`Retry-After` means slow down, and is worth waiting for.

## The 12 October 2026 miss, and the check log

The General Assembly voted on the political declaration on pandemic
prevention, preparedness and response on 12 October 2026 and the monitor
said nothing: the GA calendar held only the session window, nothing read PGA
letters, plenary drafts were never walked, the UN taxonomy lacked the
health-sovereignty terms the parliamentary one has carried since v0.6, and UN
output had been paused since 17 August. All four sources above now feed
`tools/un_forward.py` and the UN DM, with first signs on our ground at the
top (`src/un_signals.py`) and a check log on every run (`src/un_checks.py`):
each source "read OK", "read but empty" or "could not read", with its newest
item, so a source that could not be read is never mistaken for a quiet week.
`tools/un_backtest.py` replays the archived responses and shows the draft (5
October), the letter (7 October) and the plenary listing (8 October) leading
the output before the vote.


## OHCHR behind a Cloudflare challenge: routes tried (13 October 2026)

By 13 October `www.ohchr.org` answered the HRC sessions page and the
calls-for-input listing with `403`, `cf-mitigated: challenge` ("Just a
moment..."), from the laptop and from the Mac Mini alike. The standing rule:
look for a legitimate other route, never defeat the challenge (no browser
User-Agent, no challenge solver, no cache or proxy in between). Every request
below went out with the honest User-Agent, a few seconds apart.

| Tried | Result | Used? |
|---|---|---|
| `hrcmeetings.ohchr.org` | `301` to `hrcportal.ohchr.org` | via the portal |
| `hrcportal.ohchr.org/robots.txt` | allows all but `/admin`, `/search`, `/user/*`, core paths; `Crawl-delay: 10` for `*` | honoured |
| `hrcportal.ohchr.org/hrc-sessions-all` | `200`, 18 regular sessions (46th to 63rd) with dates and `/node/N` pages | **YES: HRC sessions, READ OK** |
| `hrcportal.ohchr.org/sitemap.xml` (167 URLs) | no calls-for-input listing anywhere on the portal | no |
| `www.ohchr.org/en/rss.xml` | `200`, not challenged, but it is the front-page node feed: ten topic pages, no calls | no |
| `www.ohchr.org/en/calls-for-input`, `/en/calls-for-input-listing/rss.xml`, `/sitemap.xml`, `/en` | all challenged | no |
| The same two pages from the Mac Mini | challenged too: not one address being throttled | no |
| `spinternet.ohchr.org` (Special Procedures) | `200`, but no calls listing | no |
| ReliefWeb API | `403` "not using an approved appname"; an appname must be requested (Chris's call), and ReliefWeb does not syndicate OHCHR calls in any case | no |
| `tbinternet.ohchr.org/robots.txt` | `User-agent: *` / `Disallow: /` | treaty body calendar and general comments no longer fetched (see below) |
| Wayback Machine or any other cache | not tried on purpose: it would route the challenged page through a third party | no |
| GitHub's runners | answered by the backup workflow's own check log: dispatch `un-calls-weekly.yml` with `dry_run` (stateless, sends nothing) | see the PR |

**So:** HRC sessions read OK again via the portal. Calls for input stay "could
not read" in the check log, with the reason, and the DM says the number of open
calls is unknown, never zero. Still worth asking, by a human: whether OHCHR
offers the calls listing as a feed to registered NGOs, or would allow-list an
identified monitor.


## Treaty bodies after tbinternet's `Disallow: /` (13 October 2026)

`tbinternet.ohchr.org/robots.txt` reads `User-agent: *` / `Disallow: /`. Both
things the monitor read there now go through the robots guard
(`src/robots_guard.GuardedClient`) and are refused before any request is sent:
the master calendar (`src/ingest/un_calendar.fetch_treaty_deadlines`, run by
the weekday UN job) and the general-comment search
(`src/ingest/treaty_comments.py`, run by hand as `tools/un_comments.py`, which
now prints `could not read: robots.txt disallows ...`, stores nothing and exits
2). Both resume by themselves if the robots.txt relents. Alternatives tried,
every request with the honest User-Agent, a few seconds apart:

| Tried | Result | Used? |
|---|---|---|
| `indico.un.org` (UNOG's Indico.UN) | no robots.txt (404). Category exports `/category/<id>/events.ics` (CEDAW 828, CRC 833, CCPR 821, under OHCHR 800) list every session to late 2027, e.g. CEDAW 94th 3-26 Feb 2027, CCPR 146th 19 Oct-6 Nov 2026 with the states under review | **YES: treaty body sessions** |
| UN Journal API, location Geneva (`journal-api.un.org`, robots.txt 404) | works: `GlobalCalendar` with the committee organ UUIDs gives every meeting with times, but only about three weeks ahead; meeting details are closed and carry no agenda | not wired (Indico is a year ahead); the fallback if Indico goes |
| `docs.un.org/<symbol>` for provisional agendas (`CEDAW/C/94/1`) and general comments (`CRC/C/GC/26`) | the page is a frame over, and `?direct=true` a 302 to, `documents.un.org/api/symbol/access`; `documents.un.org/robots.txt` disallows `/api`, `/doc`, `/access` (so do `daccess-ods.un.org`, `documents-dds-ny.un.org`) | no |
| `digitallibrary.un.org` | robots.txt disallows `/search` and `/rss`; records can only be found by search; the sitemap it names answers `202` with an empty body | no |
| `uhri.ohchr.org` (Universal Human Rights Index) | documented API and daily full export, but of recommendations (concluding observations, UPR), not general comments; API by arrangement (`uhrisupport@ohchr.org`) | no (a lead for concluding observations) |
| `www.ungeneva.org` calendar of major meetings | robots.txt allows; hand-kept, last updated 27 Feb 2026, stops in September, omits CEDAW 93rd and CCPR 146th; the biweekly press calendar lists no treaty bodies | no |
| `conf.unog.ch` | robots.txt `Disallow: /` (bar help and recordings) | no |
| Wayback Machine or any other cache | not tried on purpose | no |

**So:** treaty body SESSIONS read OK again, from Indico.UN, further ahead than
tbinternet ever gave. Reporting deadlines and general comments stay unread: no
legitimate route found. Calls for comments on draft general comments are listed
only on `www.ohchr.org` (Cloudflare challenge) and tbinternet (robots.txt).
Worth asking, by a human: whether OHCHR would allow an identified monitor on
tbinternet.

**Found while probing, fixed 13 October 2026 (below):** `docs.un.org/<symbol>?direct=true`,
the route the draft-resolution walks (`src/ingest/un_docs.py`) and the session
reports use, now answers `302` to `documents.un.org/api/symbol/access`, a path
`documents.un.org/robots.txt` disallows. The HTTP client followed the redirect
without a second robots check.


## docs.un.org redirects to a disallowed path (13 October 2026)

`docs.un.org/en/A/81/L.6?direct=true` answers `302` to
`documents.un.org/api/symbol/access?s=A/81/L.6&l=en&t=pdf`, and
`documents.un.org/robots.txt` reads `User-agent: *` / `Disallow: /doc`,
`/access`, `/api`. (`docs.un.org/robots.txt` itself answers the language picker
page: no rules.)

**The client fix, general, not UN only.** `src/http.HttpClient` now asks
robots.txt about EVERY hop of a redirect chain before requesting it
(`_RedirectHandler`; an opener a collector passes in has its redirect handler
wrapped the same way). Every robots-checked wrapper registers itself as a
redirect guard: `src/robots_guard.GuardedClient` and `guard()`, and
`src/prov_fetch.Context` (the provinces, US/AU/... state collectors). The
collectors with their own `urllib.robotparser` first-URL check register through
`robots_guard.check_redirects` (`src/member_service.fetch_at`,
`src/agendas/at.py`, `tools/at_rollcalls.py`); the urllib one-off probes open
through `robots_guard.probe_urlopen` (`tools/nic_probe.py`, `ve_probe.py`,
`ve_news_crawl.py`). A refused hop raises `RobotsRefused`
("robots.txt disallows <hop> (redirected from <first url>); not fetched"),
nothing is sent to the refused URL, and it is never served from the day's
archive. A robots.txt file is always fetchable; a hop under a documented API or
a written permission passes unasked, as a first URL does. Tests:
`tests/test_robots_redirects.py` (a real HttpClient over an in-memory web).

**The UN side.** Every `un_docs` fetch goes through the robots guard. A walk
stops at the first refusal (every symbol goes the same way) and the forward
look's check log says, for each docs.un.org row, `COULD NOT READ  robots.txt
disallows (documents.un.org): docs.un.org redirects to
https://documents.un.org/api/symbol/access`; the DM adds "new drafts are
unknown, not zero". `tools/un_drafts.py` and `tools/un_votes.py` print
`could not read: robots.txt disallows (documents.un.org)` and exit 2. The HRC
session reports (`A/HRC/NN/2`, the voting records) go the same way: no
alternative found yet.

### Alternative routes for GA and Third Committee drafts, tried 13 October 2026

Every request with the honest User-Agent, seconds apart.

| Tried | robots.txt | Result | Used? |
|---|---|---|---|
| PGA letters, `www.un.org/pga/81/documents/letters/` | allows, Crawl-delay 10 | a letter submitting a draft names it ("to be annexed to draft resolution A/81/L.6") and says what it is | **YES**: a draft named there is known by symbol, the letter's subject and date (`un_signals.drafts_named`) |
| UN Journal API, GA plenary agendas (`journal-api.un.org`) | 404 (no rules) | "Global health and foreign policy - Item 129: Draft resolution (A/81/L.6)" about a week ahead | **YES** (already read); now also a source of named drafts |
| UN Journal API, GA calendar, informal consultations | 404 | "Informal consultations on the draft resolution entitled ... (under agenda item 9) (convened by ...)": the draft's title before it has a symbol | **YES**: `un_calendar.parse_ga_consultations`, a CONSULT first sign when on our ground; same payload, no extra request |
| UN Journal API, Third Committee official meetings (`officials/<id>`) | 404 | the agenda names the item and, once action begins (late October), the `A/C.3/81/L.n` drafts acted on | **YES**: `un_calendar.fetch_committee_drafts`, the next 14 days, at most 15 requests |
| UN Journal, Third Committee informal consultations | 404 | the Journal only says the schedule "is available on iGov" | no |
| `igov.un.org` (iGov portal) | the path answers the app page (no rules) | the proposals list its own app loads (`igov/api/proposals/<session>/<committee>`) answers an empty list for sessions 80 and 81; not explored further | no; re-check once Third Committee action begins |
| `www.un.org/en/ga/info/draft/` | allows | a stale list of A/66/L.n | no |
| `www.un.org/en/ga/third/81/documentation.shtml` | allows | lists L.1 (organisation of work) only, linking to undocs.org | no |
| `press.un.org` meetings coverage | allows (not `/search/`) | names drafts and votes on the day of action: after the first sign | not wired |
| `digitallibrary.un.org` | disallows `/search`, `/rss` | records can be found only by search | no |
| `research.un.org` | allows `*` (Crawl-delay 10; AI crawlers named) | research guides linking to docs.un.org | no |
| `daccess-ods.un.org`, `documents-dds-ny.un.org` | disallow the document paths | | no |
| Wayback Machine or any other cache | not tried on purpose | | no |

**Backtest** (`tools/un_backtest.py`, replaying the archived responses through
the new route honestly; the old first-page fixture is kept for the parser's own
tests but is no longer a route): A/81/L.6 is flagged from **7 October** (named
by the PGA letter, area 7, due 12 October), with the 18th and 19th plenary
listings from 8 October. **5 and 6 October now show nothing**: the draft's own
PDF, dated 5 October, is out of reach, and nothing readable named it before
the letter. Two days of lead lost, five days still ahead of the vote.

Worth asking, by a human: whether the UN's Documents Management would allow an
identified monitor on `documents.un.org/api/symbol/access`, or publishes the
documents feed it serves to `docs.un.org`.
