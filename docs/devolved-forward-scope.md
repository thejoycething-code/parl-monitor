# Devolved forward business: Holyrood and the Senedd (15 October 2026)

What the UK weekly edition can show about the next eight weeks at the
Scottish Parliament and the Senedd, where it comes from, and what was tried.
NI already has this (`ni_agenda`, `tools/ni_pull.py`, NI Assembly weekly).

## What was built

| | Holyrood | Senedd |
|---|---|---|
| Table | `sp_agenda` | `sd_agenda` |
| Collector | `tools/sp_agenda.py` (`src/ingest/holyrood_agenda.py`) | `tools/sd_agenda.py` (`src/ingest/senedd_agenda.py`) |
| Weekly step | `jobs/sp-weekly.sh` (Mini, Fridays 07:00) and `.github/workflows/sp-weekly.yml` (backup), after `sp_committees.py` | `jobs/sd-weekly.sh` (Mini, Thursdays 07:00) and `.github/workflows/sd-weekly.yml`, after `sd_committees.py` |
| Primary source | parliament.scot What's on, per weekday | ModernGov web service, business.senedd.wales/mgWebService.asmx |
| Fallback | data.parliament.scot Business Programme motions (API) | none needed (see below) |
| Horizon | Chamber: the agreed programme, 2-3 sitting weeks; the day strip runs ~4 weeks; committee agendas ~1 week ahead | Sittings listed to mid-December; Plenary agendas ~1 week ahead, committee draft agendas 1-2 weeks ahead |

Both collectors read from today to today + 56 days (`--from/--to/--days`,
`--db` for any store). One row per agenda item: `key` (stable), `dated`,
`item_time`, `body` (Chamber / Plenary or the committee), `item_order`,
`business` (title), `detail` (the motion text, the oral questions lodged, the
committee's description; witness lists dropped), `item_type`, `reference`
(S7M-/NDM motion), `meeting_id`, `url` (official), `source`, `areas`,
`matched_terms` (English taxonomy, business first), `first_seen`,
`last_seen`. Schema comment in `src/db.py`.

`item_type`: procedural, questions, statement, debate, members' business,
bill stage, legislative consent, subordinate legislation, petition, committee
evidence, committee business, chamber business, and **to be announced** for a
booked slot with no subject yet ("Scottish Government Business", "Reform UK
Business", a bare "Members' Business"). An edition should say "subject to be
announced" for those rather than show the placeholder as business.

A forward agenda changes, so a day (Holyrood) or meeting (Senedd) read in full
replaces its rows: an item no longer listed is deleted, so a placeholder does
not linger beside the debate that replaced it. A day or meeting that could not
be read keeps its rows and writes a gap (feeds `sp-agenda`, `sd-agenda`):
nothing is ever emptied by a failed read, and a run that read no source at all
exits 1. A Senedd meeting whose agenda is not published yet is counted, not
stored (there is no business to classify).

Coverage (`tools/coverage.py`): both tables are watched feeds (last_seen, 7
days) and excused while empty until 31 October 2026 (first Mini runs).

## Routes tried (laptop, 15 October 2026, UA "CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)")

### Holyrood

| Route | robots.txt | Result | Used |
|---|---|---|---|
| www.parliament.scot/chamber-and-committees/business-bulletin (and /future-business, /business-programme, /todays-business, /whats-on, /meeting-of-the-parliament) | allowed | **301 to webarchive.nrscotland.gov.uk**: the new site's catch-all for any path it does not know. Not followed (the collector's redirect guard refuses any hop off parliament.scot) | no |
| www.parliament.scot/chamber-and-committees/whats-on-and-watch-live/whats-on?dateFrom=YYYY-MM-DD | allowed (disallows only /sitecore, /temp/, /upload/, /xsl/, app folders) | **200**. The Business Bulletin per day: Chamber items (title, time; members' business motion text; oral questions lodged) and every committee meeting's numbered agenda with the committee page link. `dateFrom` also takes M/D/YYYY. "There are no meetings today" past the programme; "Information will be published when available" for committee agendas not out yet | **yes, primary** |
| www.parliament.scot/-/media/files/whats-on-bb/.../bbYYYYMMDD.pdf | allowed | 200 PDF (linked from What's on). Same content as What's on, as PDF | no (What's on is the same text, parseable) |
| data.parliament.scot/api/MotionsQuestionsAnswersMotionsBusiness?motionfilter=programme | 404 (no rules) | **200 JSON**, 1,631 Business Programme motions since 1999 (3.6 MB). The newest (S7M-01505, 6 Oct) programmes 27 Oct to 5 Nov | **yes, fallback** for a day whose page fails or is not shown yet |
| data.parliament.scot/api/events | 404 | exhibitions history, no future rows (probed 21 Aug, docs/api-notes.md) | no |
| data.parliament.scot/api/apilist | 404 | no agenda, committee-meeting or bulletin endpoint; Orscommitteemeeting is the Official Report (past) | no |
| Committee pages (/chamber-and-committees/committees/...) | allowed | the agenda is the same text What's on carries | no (What's on covers every committee in one page per day) |
| Scottish Government consultations (consult.gov.scot) | | already collected by `tools/dg_consultations.py --nation scotland` into `dg_consultations` | unchanged |

### Senedd

| Route | robots.txt | Result | Used |
|---|---|---|---|
| business.senedd.wales calendar (mgCalendarMonthView/WeekView), agenda pages (ieListDocuments.aspx?MId=), host root | the WAF's 403 page | **403** "Service unavailable" (Azure WAF) to our UA, as since 28 August. The 403 WebFetch saw was this WAF, not a WebFetch quirk | no |
| business.senedd.wales/mgWebService.asmx (ModernGov web service; the .asmx lists 21 operations) | the WAF's 403 page (a 4xx: no rules, RFC 9309) | **200 XML to our identified UA**, no browser UA, cookie or key. `GetCommittees` (210 bodies, expired flag), `GetMeetings?lCommitteeId=&sFromDate=DD/MM/YYYY&sToDate=` (ISO dates are misread), `GetMeeting?lMeetingId=` (numbered agenda items, agenda text, NDM motion text, agendapublished) | **yes**. The client removes the browser UA src/http.py keeps for this host's web pages and sends ours |
| business.senedd.wales/mgRss.aspx | | 200 RSS: "What's new" (minutes, petitions published), backwards-looking | no |
| senedd.wales "Business Statement and Announcement" (the Trefnydd's three-week look, Tuesdays) | /search disallowed | the Plenary agenda item carries no link; the only route on senedd.wales is /search, which robots.txt disallows | no. ModernGov gives each sitting's date and its agenda once published |
| senedd.wales/senedd-business/plenary/, /senedd-timetable/ | allowed | static pages; the timetable links the blocked ModernGov calendar | no |
| record.senedd.wales | allows all | the Record: what was said (sd_committees, sd_divisions). OrderPaper/OralQuestions/DD-MM-YYYY/ (200) has the oral questions for a sitting | no (not needed for the item list) |

Welsh: the web service answers in English (`agendaitemtitle`); a bilingual
"Welsh / English" title is read in English (`senedd_agenda.english`).

## What the first read found (scratch copy of the store, 19 October to 13 December 2026)

See the PR for the counts and items on our ground from the one scratch run.
Highlights at the time of writing: Holyrood, 7 October members' business on
Baby Loss Awareness Week (S7M-00815) matched `baby loss` (dev capture); the
Senedd Legislation Committee's 19 October papers matched the Immigration and
Asylum Bill.

## Not done / open

- Holyrood committee agendas appear about a week ahead and Senedd Plenary
  agendas about a week ahead, so the eight-week view is mostly dates and
  booked slots beyond the next fortnight. Neither parliament publishes
  subjects further out in a machine form we may read.
- The Senedd web service has not been tried from GitHub's runners; the
  backup workflow will record a gap if the WAF refuses them.
- The edition renderer (another branch) reads these tables; nothing here
  renders them.
