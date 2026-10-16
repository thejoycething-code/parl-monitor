# Germany: the sixteen Landtage

Until 16 October 2026 the Länder were covered votes-only: abgeordnetenwatch's
open API serves recorded votes for all sixteen Land parliaments
(tools/de_rollcalls.py, `--all`), and docs/germany-scope.md item 3 records
that there is no shared document system for them (DIP is federal). No
Landtag had a collector of its own; the region codes below (ISO 3166-2:DE
without the prefix) are new and used by `regional_agenda`.

| Code | Landtag | Host |
|---|---|---|
| BW | Landtag von Baden-Württemberg | www.landtag-bw.de |
| BY | Bayerischer Landtag | www.bayern.landtag.de |
| BE | Abgeordnetenhaus von Berlin | www.parlament-berlin.de |
| BB | Landtag Brandenburg | www.landtag.brandenburg.de |
| HB | Bremische Bürgerschaft | www.bremische-buergerschaft.de, sd.bremische-buergerschaft.de |
| HH | Hamburgische Bürgerschaft | www.hamburgische-buergerschaft.de |
| HE | Hessischer Landtag | hessischer-landtag.de |
| MV | Landtag Mecklenburg-Vorpommern | www.landtag-mv.de |
| NI | Niedersächsischer Landtag | www.landtag-niedersachsen.de |
| NW | Landtag Nordrhein-Westfalen | www.landtag.nrw.de |
| RP | Landtag Rheinland-Pfalz | landtag-rlp.de, api.landtag-rlp.de |
| SL | Landtag des Saarlandes | www.landtag-saar.de |
| SN | Sächsischer Landtag | www.landtag.sachsen.de |
| ST | Landtag von Sachsen-Anhalt | www.landtag.sachsen-anhalt.de |
| SH | Schleswig-Holsteinischer Landtag | www.landtag.ltsh.de |
| TH | Thüringer Landtag | www.thueringer-landtag.de |

No two Landtage share a platform, so each has its own reader. Elections in
autumn 2026 (Berlin, Mecklenburg-Vorpommern, Sachsen-Anhalt) mean those three
had only constituent sittings and few committee dates on the day of the
survey; their readers will fill as the new committees are set up.

## Forward agenda (regional_agenda, 16 October 2026)

`src/regional_agendas/de.py`, run by `tools/regional_agenda.py de`. Every
reader does the same thing: a calendar of booked sittings (iCal, RSS, a JSON
calendar or an HTML list) gives each plenary sitting and committee meeting in
the window; a sitting whose Tagesordnung is published (usually a week ahead,
Bremen a fortnight) becomes one row per agenda point, every other sitting one
'to be announced' row. Agendas are HTML where the Landtag publishes HTML,
otherwise PDF read with pypdf (src/de_btp.extract_text); one splitter
(`split_tops`) reads the numbered points of both, switches day on a
'Mittwoch, 11. November 2026' heading, and cuts private persons' names
(election objectors, petitioners) from the text. Every host was checked with
`src.robots_guard.probe_refusal` before a reader was built; all routes below
are allowed unless said otherwise. Probing used a handful of requests per
host, at least 1 s apart, with the monitor's honest User-Agent.

Live run on 16 October 2026 (56-day window, to 11 December): about 3 minutes
wall time, 15 of 16 Landtage read. The per-region numbers are in the lead's
report; the horizon each reaches is set by the calendar, the agenda depth by
how early each Landtag publishes.

**NW Nordrhein-Westfalen** (reader). Calendar: the Kalender's own XHR,
`/cms/render/live/de/sites/landtag-r20/home/aktuelles/termine-und-veranstaltungen/kalender/contentArea/kalender.R20.xhr?jahr=Y&monat=M`
(one per month, marks the days with sittings), then per day
`terminanzeige-fur-den-kalender.html.ajax?view=ajax&von_datum=YYYYMMDD&bis_datum=YYYYMMDD`
(the range is ignored beyond the first day, so one request per sitting day).
Each meeting links its Tagesordnung as HTML,
`/home/der-landtag/tagesordnungen/WP18/<n>/E18-<nr>.html` (committees) and
`PT18-<nr>.html` (plenary): Word HTML, one table row per point. Reaches the
whole window (plenary days are booked a year ahead on
/home/aktuelles/termine-und-veranstaltungen/plenarsitzungen.html too).
robots.txt: allowed (disallows only old MM documents, the document search and
videos).

**BY Bayern** (reader). `/aktuelles/tagesordnungen/` lists every published
Tagesordnung (Gremium, Sitzung number, date, Nachtrag) from the current week
on; the page's PDF buttons are JSF postbacks, but the Sitzungen page links the
same PDFs as plain GETs,
`/webangebot3/views/tagesordnungdirektanzeige/tagesordnungdirektanzeige.xhtml?gremium=<code>&sitzungsdatum=DD.MM.YYYY&sitzungsnr=<n>&nachtragsnr=<k>&typ=pdf&wp=19`,
and the Gremium codes are the list page's own select box. Reaches about a week
ahead (agendas only; there is no machine-readable calendar of later sittings:
the Sitzungsplan PDFs are graphical and the digital Sitzungsplan loads its
data by script). `typ=html` answers 404. robots.txt: allowed (disallows
/webangebot2/Vorgangsmappe, /service/suche, eID).

**BW Baden-Württemberg** (reader). `/resource/calendar/501552/download/terminkalender.ics`
(plenary days and the Finanzausschuss blocks, into 2027) plus
`/de/aktuelles/tagesordnungen` (the plenary agenda PDF, and committee agendas
when any are posted). Reaches the window for dates; agendas for the next
plenary week. robots.txt: allows everything.

**NI Niedersachsen** (reader). `/fileadmin/calendar_abo/jahrestermine-YYYY.ics`
(every plenary and committee date of the year; SUMMARY is the committee's
abbreviation, expanded from the Jahreskalender legend) plus the RSS feeds
`/rss/tagesordnungen_plenarsitzungen.xml` and `/rss/tagesordnungen_ausschuesse.xml`
(agenda PDFs; committee dates in the file name, plenary dates in the title).
Reaches the window for dates, about two weeks for agendas. robots.txt:
allowed.

**HE Hessen** (reader). `/termine/veranstaltungs_kategorie/plenarsitzungen-7?page=N`
and `.../ausschusssitzungen-10?page=N` (ten per page from today on), each
entry a Termin page that carries the Tagesordnung as HTML once published
(with PDF Einladung). Termin pages are read for sittings within 21 days; later
sittings are 'to be announced'. robots.txt: allowed.

**SN Sachsen** (reader, sittings only). `/de/aktuelles/plenarsitzungen/index.cshtml`
and `/de/aktuelles/ausschusssitzungen/index.cshtml` list sittings with number
and date; the agendas sit behind `/de/aktuelles/sitzungskalender/sitzung/<id>`
and the iCal behind `/de/aktuelles/sitzungskalender/ics/<id>`, both under
`Disallow: /de/aktuelles/sitzungskalender`; EDAS (edas.landtag.sachsen.de)
disallows every robot. So future sittings are stored as 'to be announced'
and the note says why. The Wandkalender 2027 PDF has dates for 2027 only.

**BE Berlin** (reader, sittings only). `/termine/ical/appointmentsOfPlenar` and
`/termine/ical/appointmentsOfCommittees` (the homepage calendar's own
subscription links). The new Abgeordnetenhaus (elected September 2026) has its
plenary dates booked to December; its committees were not yet constituted, so
the committee feed was empty. Agendas: the Plenarunterlagen and committee
Einladungen are a JavaScript app whose data service is not documented (PARDOK
and /opendata/ are disallowed in robots.txt), so none are read.

**BB Brandenburg** (reader). RSS `/cms/detail.php?template=lt_rss_tagesordnung_d`
(plenary, booked to 2029) and `..._ausschuss_d` (committees), the pubDate being
the sitting; a published agenda shows in the item's description (truncated)
and in full on the Termin page `/sixcms/detail.php?id=brandenburg_01.c.<id>.de`.
robots.txt: allows everything.

**HB Bremen** (reader). SD.NET (sitzungsdienst.net) at
sd.bremische-buergerschaft.de: `/termine/ics/SD.NET_RIM.ics` (every body, all
years, about 480 KB) for dates, and each sitting's `tops/?__=<token>` page for
the Tagesordnung as an HTML table, read within 21 days. City bodies
(Stadtbürgerschaft, städtische Deputationen, '(Stadt)' committees) are left
out. The JSON calendar `/termine/json/Sitzungstermine/` answers 403 and is not
used; `*.pdf` is disallowed on sd. (robots.txt), so the Einladung PDFs are
never fetched. The main site's robots.txt asks for a 5 s Crawl-delay; the
reader does not use that host.

**HH Hamburg** (reader). `/aktuelles/termine/1042880!search?hitsPerPage=100&state=<s>`,
where `state` is the listing's own gzip+base64 JSON (date-sorted, no
constraint) that the page itself carries; the teaser gives day, month,
body, kind, time and a 'Tagesordnung' PDF under `/resource/blob/...` when
published. Non-public and cancelled ('entfällt') sittings are skipped. 100
entries reach into January. robots.txt: allowed.

**MV Mecklenburg-Vorpommern** (reader). `/plenum-und-ausschuesse/plenum/aktuelle-plenarwoche`
links the current plenary week's Tagesordnung PDF
(`/fileadmin/1.Abteilung_P/.../Tagesordnung/*.pdf`). After the September
election only the constituent sitting of 20 October was booked; the
Zeitplan PDFs (2026, 2027 draft) are graphical. robots.txt: allowed.

**RP Rheinland-Pfalz** (reader). The site's own meeting API,
`https://api.landtag-rlp.de/api/meeting/filteredList?from=<ms>&to=<ms>&useOR=true&sortOrder=asc&amount=10000`
(the apiUrl the page declares; robots.txt on that host answers 404, so
allowed): every plenary and committee meeting with an HTML note that links the
Einladung PDF on dokumente.landtag.rlp.de about a week ahead. That host's
robots.txt redirects (302, twice) to the Landtag's HTML home page. Until 16
October 2026 src/robots_guard treated that as unreachable and the PDFs were
refused; Chris then approved reading it as no rules (RFC 9309), so the
Einladung PDFs are read and their TOPs listed (first live run: the Rechtsausschuss
Einladung of 22 October, three items; meetings without an Einladung yet stay
'to be announced').

**ST Sachsen-Anhalt** (reader, plenary dates only). `/service/terminuebersichten`
lists 'Landtagssitzungstermine' for the year. Agendas are PDFs at
`/fileadmin/files/to_plenum/wp9/to<nnn>sp.pdf` announced in news articles, and
committee dates only in weekly PDF overviews (`/fileadmin/Downloads/Wochenuebersicht/9WP_2026_wo<kw>.pdf`);
neither has an index to read, so neither is guessed at. robots.txt: allowed.

**SH Schleswig-Holstein** (reader). The calendar's own JSON,
`/system/modules/de.planetic.opencms.contentelements.kalender/templates/dayMonthKalenderGetter.jsp?locale=de`
(every entry with its category; committees under /11/, plenary under /2/),
plus `/infothek/wahl20/plenum/tagesordnung_seite/` (plenary agenda PDF per
Tagung, published about four weeks ahead). Committee agendas are not linked.
robots.txt: allowed.

**TH Thüringen** (reader). `/fileadmin/calendar_abo/Thueringer-Landtag-Terminkalender.ics`
(plenary and committee dates into 2027) plus the Einladung PDFs linked on
`/plenum/sitzungstermine/` (`/uploads/tx_tltcalendar/invitations/Pe*.pdf`),
read when the sitting falls in the window. robots.txt: allowed.

**SL Saarland** (no route). www.landtag-saar.de (134.96.9.204, hosted at the
university of Saarland) did not answer at all on 16 October 2026: robots.txt
and the home page timed out on every try (three probes over about an hour), so robots.txt could
not be read and nothing was fetched. No other official host publishes the
Landtag's calendar or agendas. Retry when the host answers; the module then
needs a reader (the site is TYPO3 like most others).

What would widen coverage later: Berlin's agenda service (ask the
Abgeordnetenhaus for a documented feed), RP's documents host (core: treat a
robots.txt redirect to HTML as 'no rules'), Sachsen (ask the Landtag about
the sitzungskalender disallow), committee agendas in SH and ST.
