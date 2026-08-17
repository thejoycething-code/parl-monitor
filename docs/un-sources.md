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
| OHCHR calls for input | 15 open consultations with deadlines | Listing only. **Detail pages return 403** to non-browser clients, so there is no description text to match on. |
| OHCHR HRC sessions page | Every HRC regular session with date range | Plain HTML, stable. |
| Treaty body master calendar | 49 reporting deadlines by country and committee | `MasterCalendar.aspx`. `SessionsList.aspx` is a Telerik postback grid that stays empty — that difference cost an hour. |
| UN Women CSW pages | CSW session ranges (CSW71: 8–19 March 2027) | The landing page has almost no dates; the **per-session pages** carry them in prose ("from 8 to 19 March 2027"). |
| UN GA session page | Session window (81st: 8 Sep 2026 – 7 Sep 2027) | Session number = year − 1945, derived not hardcoded. |
| docs.un.org | Draft resolutions by symbol (`A/C.3/81/L.7`, `A/HRC/63/L.4`) | Needs `?direct=true`. Existence is decided by **content type**, not status: a missing symbol answers 200 with an HTML page. Range requests honoured, so a check costs 64 bytes — but ~10s each, which is server latency not transfer. |
| UN Journal API | Third Committee meetings with times, official/informal | Base from `journal.un.org/assets/config.json`. `GlobalCalendar` is **POST** with `{locationValue, startDate, endDate, organs}` and **ISO datetimes** — plain dates return 400. Organ UUIDs from `AdvancedSearch/Organs` (3,495). |

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

## Legitimate routes to voting data, not yet taken

Ranked by how much work they are, not by preference:

1. **Ask the Dag Hammarskjöld Library.** They curate the voting data
   collection and are the people who would know whether an API or a bulk
   export exists. A single email, and the only route that gets *current* HRC
   and GA votes.
2. **Academic bulk datasets.** UN General Assembly plenary voting has been
   collated and published for decades in research archives, updated annually.
   Genuinely usable for state-position analysis, but historical rather than
   live, and GA plenary rather than Third Committee.
3. **Parse session report PDFs.** HRC session outcomes (`A/HRC/NN/2`) record
   each resolution's vote. Reliable and public, but PDF parsing, and only
   after a session closes.

## Two rules earned the hard way

**Read the client, not the page.** Treaty bodies, CSW, UPR sessions and the
Third Committee were all called impossible after fetching a landing page and
counting dates. Every one was reachable — via a different page, a POST, an
app bundle naming its own API, or a config file naming its base URL.

**Distinguish a block from a bug.** 404 means wrong URL. 403 with
`cf-mitigated` means a bot challenge — route around it, do not defeat it. 202
with an empty body means blocked while looking successful. 503 with
`Retry-After` means slow down, and is worth waiting for.
