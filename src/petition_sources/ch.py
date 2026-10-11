"""Switzerland: Vernehmlassungen, Petitionen to the Federal Assembly, and
federal popular initiatives collecting signatures.

Probed 11 October 2026.

VERNEHMLASSUNGEN (federal consultations, the Swiss Begutachtung: anyone may
send a response before the deadline): the fedlex SPARQL endpoint
(fedlex.data.admin.ch/sparqlendpoint, keyless; robots.txt blocks only
/filestore/). Each jolux:Consultation with status 2 ('laufend') has an
eventId (proj/2026/43/cons_1, the stable id), a German title, and a
ConsultationPhase subtask with its start and end date: the end is the
deadline. 28 running on 11 October.

PETITIONEN: Curia Vista's OData service (ws.parlament.ch/odata.svc, the
host tools/ch_rollcalls.py reads), Business with BusinessType 10, the last
year's submissions in German. No signature counts, no closing date: a
Swiss petition goes to a committee and stays there. About 50 a year.

VOLKSINITIATIVEN: the Bundeskanzlei's list of initiatives in collection
only embeds a chart whose data API robots.txt disallows, so the Federal
Gazette notices are read instead, through the same SPARQL endpoint: an
initiative's collection starts with its "Vorprüfung" notice and ends with
"Zustandekommen", "Nichtzustandekommen", "Rückzug" or "Fristablauf". An
initiative with a Vorprüfung and no ending notice is collecting; its
deadline is 18 months after the Vorprüfung's publication (Art. 71 BPR,
our reading of the law, not a published date). 100,000 valid signatures
bring a popular vote. No counts are published while signatures are
collected.
"""

from __future__ import annotations

import datetime
import json
import re
import urllib.parse

from src import petitions as P

CC = "ch"
SPARQL = ("https://fedlex.data.admin.ch/sparqlendpoint?query={0}"
          "&format=application%2Fsparql-results%2Bjson")
ODATA = ("https://ws.parlament.ch/odata.svc/Business?$filter=Language eq 'DE' and BusinessType "
         "eq 10 and SubmissionDate ge datetime'{0}T00:00:00'&$orderby=SubmissionDate desc"
         "&$top=200&$select=ID,BusinessShortNumber,Title,SubmittedBy,SubmissionDate,"
         "BusinessStatusText,SubmittedText,Description&$format=json")
AFFAIR = "https://www.parlament.ch/de/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={0}"
PETITION_DAYS = 365
VI_MONTHS = 18
VI_THRESHOLDS = ((100000, "valid signatures bring a popular vote"),)

Q_CONSULT = """PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?c ?eventId ?title ?start ?end WHERE {
  ?c a jolux:Consultation ; jolux:eventId ?eventId ;
     jolux:consultationStatus <https://fedlex.data.admin.ch/vocabulary/consultation-status/2> ;
     jolux:eventTitle ?title .
  FILTER(lang(?title) = "de")
  OPTIONAL { ?c jolux:hasSubTask ?o . ?o a jolux:ConsultationPhase .
             OPTIONAL { ?o jolux:eventStartDate ?start }
             OPTIONAL { ?o jolux:eventEndDate ?end } }
} ORDER BY ?end"""

Q_INITIATIVES = """PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?act ?date ?title WHERE {
  ?act jolux:publicationDate ?date ; jolux:isRealizedBy ?e .
  ?e jolux:language <http://publications.europa.eu/resource/authority/language/DEU> ;
     jolux:title ?title .
  FILTER(?date >= "%s"^^<http://www.w3.org/2001/XMLSchema#date>)
  FILTER(STRSTARTS(STR(?act), "https://fedlex.data.admin.ch/eli/fga/"))
  FILTER(CONTAINS(?title, "Volksinitiative"))
} ORDER BY ?date"""

ENDS = ("Zustandekommen", "Nichtzustandekommen", "Nicht-Zustandekommen", "Rückzug",
        "Fristablauf")


def _val(b, k):
    return (b.get(k) or {}).get("value")


def parse_consultations(reply):
    out, seen = [], set()
    for b in reply.get("results", {}).get("bindings", []):
        eid = _val(b, "eventId")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        out.append(P.entry("vl", eid, _val(b, "title"), kind="consultation",
                           status="Vernehmlassung läuft", opened=_val(b, "start"),
                           closes=_val(b, "end"), body="Bundesverwaltung",
                           url="https://www.fedlex.admin.ch/eli/dl/{0}/de".format(eid)))
    return out


def odata_date(value):
    m = re.search(r"/Date\((-?\d+)", str(value or ""))
    if not m:
        return None
    return datetime.datetime.utcfromtimestamp(int(m.group(1)) / 1000).date().isoformat()


def parse_petitions(reply):
    out = []
    d = reply.get("d") or {}
    for r in (d if isinstance(d, list) else d.get("results") or []):
        num = r.get("BusinessShortNumber") or str(r.get("ID"))
        text = P.one_line(re.sub(r"<[^>]+>", " ", r.get("SubmittedText") or r.get("Description")
                                 or "")) or None
        out.append(P.entry("pet", num, r.get("Title"), kind="petition",
                           summary=text, status=r.get("BusinessStatusText"),
                           opened=odata_date(r.get("SubmissionDate")), author=r.get("SubmittedBy"),
                           thresholds=(), body="Bundesversammlung",
                           url=AFFAIR.format(r.get("ID"))))
    return out


def _initiative_name(title):
    m = re.search(r"«([^»]+)»", title or "")
    return m.group(1).strip() if m else None


def add_months(iso_date, months):
    d = datetime.date.fromisoformat(iso_date)
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    import calendar
    return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1])).isoformat()


def parse_initiatives(reply, today):
    """[entry] for initiatives whose collection is open (a Vorprüfung, no end)."""
    starts, ended = {}, set()
    for b in reply.get("results", {}).get("bindings", []):
        title, date, act = _val(b, "title") or "", (_val(b, "date") or "")[:10], _val(b, "act")
        name = _initiative_name(title)
        if not name:
            continue
        if title.rstrip(". ").endswith("Vorprüfung"):
            starts[name] = (date, act, title)
        elif any(e in title for e in ENDS):
            ended.add(name)
    out = []
    for name, (date, act, title) in sorted(starts.items(), key=lambda kv: kv[1][0]):
        if name in ended:
            continue
        closes = add_months(date, VI_MONTHS)
        if closes < today:
            continue
        out.append(P.entry("vi", act.rsplit("/eli/", 1)[-1], name, kind="referendum",
                           status="Unterschriftensammlung (Frist berechnet)", opened=date,
                           closes=closes, thresholds=VI_THRESHOLDS, body="Bundeskanzlei",
                           url=act + "/de"))
    return out


def _sparql(client, query, slug):
    return client.get_json(SPARQL.format(urllib.parse.quote(query)), "ch-petitions", slug)


def fetch_consultations(client, today, log=print):
    try:
        reply = _sparql(client, Q_CONSULT, "vernehmlassungen")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["fedlex consultations unreadable: {0}".format(str(exc)[:140])])
    return P.fetched(parse_consultations(reply), note="running Vernehmlassungen")


def fetch_petitions(client, today, log=print):
    since = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=PETITION_DAYS)).isoformat()
    url = ODATA.format(since).replace(" ", "%20")
    try:
        reply = client.get_json(url, "ch-petitions", "curia-petitions")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["Curia Vista petitions unreadable: {0}".format(str(exc)[:140])])
    return P.fetched(parse_petitions(reply), note="petitions submitted in the last year")


def fetch_initiatives(client, today, log=print):
    since = add_months(today, -(VI_MONTHS + 6))
    try:
        reply = _sparql(client, Q_INITIATIVES % since, "volksinitiativen")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["Federal Gazette notices unreadable: {0}".format(
            str(exc)[:140])])
    return P.fetched(parse_initiatives(reply, today),
                     note="collecting; deadline 18 months after the Vorprüfung, no counts published")


SOURCES = (
    P.Source(code="vl", name="Vernehmlassungen (fedlex)", kind="consultation",
             fetch=fetch_consultations),
    P.Source(code="pet", name="Petitionen (Curia Vista)", kind="petition",
             fetch=fetch_petitions),
    P.Source(code="vi", name="Volksinitiativen in collection (Federal Gazette)",
             kind="referendum", fetch=fetch_initiatives, thresholds=VI_THRESHOLDS),
)
