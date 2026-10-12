"""Netherlands: the Tweede Kamer's agenda from its Open Data Portaal.

`Activiteit` (a plenary debate, a committee debate, a procedure meeting, a
round table) with its `Agendapunt`s, each naming the zaken it takes and
their Kamerstuk dossiers. Measured 10 October 2026: 183 activities in the
three weeks from 10 October, paged by the portal at 250. One point per
agendapunt; an activity with none (a working visit) is one point itself.

Refs are zaaknummers ('2026Z18884') and dossier numbers ('36390',
'36800-XVI'), the keys config/watchlist-nl.yaml and nl_zaken use.
"""

from __future__ import annotations

import datetime
from urllib.parse import quote

from src import agenda
from src.http import FetchError

CC = "nl"
SOURCE = "the Tweede Kamer's open data, Activiteit and Agendapunt"
BILLS = ("nl_zaken", "zaak_nummer", "onderwerp")
FEED = "nl-agenda"
BASE = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
TZ = "+02:00"
ACTIVITIES = (
    "Activiteit?$filter=Verwijderd eq false and Datum ge {start}T00:00:00{tz} "
    "and Datum lt {end}T00:00:00{tz}&$orderby=Datum"
    "&$select=Id,Nummer,Soort,Onderwerp,Datum,Aanvangstijd,Status,Besloten,"
    "Voortouwnaam,Voortouwafkorting"
    "&$expand=Agendapunt($filter=Verwijderd eq false;$select=Id,Nummer,Onderwerp,Volgorde;"
    "$expand=Zaak($select=Nummer,Soort,Onderwerp;"
    "$expand=Kamerstukdossier($select=Nummer,Toevoeging)))")
PLENARY = ("Plenair debat", "Stemmingen", "Vragenuur", "Hamerstukken", "Regeling van werkzaamheden")
HEARING = ("Rondetafelgesprek", "Hoorzitting", "Technische briefing", "Gesprek")
PAGE_LIMIT = 40
# Cancelled and moved activities are left out: a moved one reappears under
# its new date as its own activity.
SKIP_STATUS = ("Geannuleerd", "Verplaatst")
WEB = "https://www.tweedekamer.nl/debat_en_vergadering/commissievergaderingen/details?id={0}"


def url(path):
    return BASE + quote(path, safe="$(),=;/?&:'-")


def dossier_key(k):
    if not k or k.get("Nummer") is None:
        return None
    extra = (k.get("Toevoeging") or "").strip()
    return "{0}-{1}".format(k["Nummer"], extra) if extra else str(k["Nummer"])


def kind_of(soort):
    s = soort or ""
    if s in PLENARY or s.startswith("Plenair"):
        return "plenary"
    if s in HEARING:
        return "hearing"
    return "committee"


def parse(reply):
    """Points from one page of the portal's reply."""
    out = []
    for a in reply.get("value") or []:
        if a.get("Status") in SKIP_STATUS:
            continue
        date = (a.get("Datum") or "")[:10] or None
        start = a.get("Aanvangstijd") or ""
        time = start[11:16] if len(start) >= 16 else None
        soort = a.get("Soort") or ""
        kind = kind_of(soort)
        body = "Plenary" if kind == "plenary" else (a.get("Voortouwnaam") or soort or "Tweede Kamer")
        head = " ".join(x for x in (soort, "-", a.get("Onderwerp")) if x)
        status = a.get("Status")
        link = WEB.format(a.get("Id"))
        points = sorted(a.get("Agendapunt") or [], key=lambda p: p.get("Volgorde") or 0)
        if not points:
            out.append(agenda.point(a.get("Nummer") or a.get("Id"), date,
                                    a.get("Onderwerp") or soort, body, kind,
                                    time, soort, url=link, status=status))
            continue
        for p in points:
            refs = []
            for z in p.get("Zaak") or []:
                if z.get("Nummer"):
                    refs.append(z["Nummer"])
                for k in z.get("Kamerstukdossier") or []:
                    d = dossier_key(k)
                    if d:
                        refs.append(d)
            out.append(agenda.point(p.get("Nummer") or p.get("Id"), date,
                                    p.get("Onderwerp") or a.get("Onderwerp"),
                                    body, kind, time, head, refs=refs, url=link, status=status))
    return out


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    nxt = url(ACTIVITIES.format(start=today, end=end, tz=TZ))
    points, gaps, page = [], [], 0
    while nxt and page < PAGE_LIMIT:
        page += 1
        try:
            reply = client.get_json(nxt, FEED, "activiteit-{0}-p{1}".format(today, page))
        except (FetchError, ValueError) as exc:
            gaps.append("Activiteit page {0} unreadable: {1}".format(page, str(exc)[:120]))
            break
        points += parse(reply)
        nxt = reply.get("@odata.nextLink")
    if nxt and page >= PAGE_LIMIT:
        gaps.append("Activiteit: stopped after {0} pages".format(PAGE_LIMIT))
    plenary = sorted(p["date"] for p in points if p["kind"] == "plenary" and p["date"])
    return agenda.fetched(points, next_sitting=plenary[0] if plenary else None, gaps=gaps)
