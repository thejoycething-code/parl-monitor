"""The Netherlands: petitions handed to the Tweede Kamer.

Probed 11 October 2026. The Tweede Kamer's open data (the OData service
tools/nl_rollcalls.py reads; its robots.txt answers 500) has no Zaak of the
kind 'Petitie' or 'Burgerinitiatief'. A petition appears instead as an
Activiteit of the kind 'Petitie': the appointment at which a committee
receives it, with its subject (Onderwerp), date, status ('Gepland',
'Uitgevoerd') and the committee (Voortouwnaam). About 45 since 1 September.
No signature counts and no closing date: the date shown is the hand-over.
The window read is the last 60 days and everything scheduled.

NOT COVERED: internetconsultatie.nl, the government's consultation portal,
disallows every crawler but named search engines in robots.txt
(`User-agent: * Disallow: /`) and publishes no dataset, so Dutch government
consultations are not read. Burgerinitiatieven reach the store only as the
committee's reports.
"""

from __future__ import annotations

import datetime

from src import petitions as P

CC = "nl"
ODATA = ("https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Activiteit?$filter=Soort eq "
         "'Petitie' and Verwijderd eq false and Datum ge {0}&$orderby=Datum desc&$top=250"
         "&$select=Id,Nummer,Soort,Onderwerp,Datum,Status,Voortouwnaam")
ITEM = "https://www.tweedekamer.nl/debat_en_vergadering/commissievergaderingen/details?id={0}"
LOOKBACK_DAYS = 60


def parse(reply):
    out = []
    for r in reply.get("value") or []:
        num = r.get("Nummer") or r.get("Id")
        out.append(P.entry("tk", num, r.get("Onderwerp"), kind="petition",
                           status=r.get("Status"), opened=(r.get("Datum") or "")[:10],
                           body=r.get("Voortouwnaam"), thresholds=(),
                           url=ITEM.format(num)))
    return out


def fetch(client, today, log=print):
    since = (datetime.date.fromisoformat(today)
             - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    url = ODATA.format(since).replace(" ", "%20").replace("'", "%27")
    try:
        reply = client.get_json(url, "nl-petitions", "tk-petitie")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["Tweede Kamer petitions unreadable: {0}".format(
            str(exc)[:140])])
    return P.fetched(parse(reply), note="petition hand-overs, last {0} days and scheduled"
                     .format(LOOKBACK_DAYS))


SOURCES = (
    P.Source(code="tk", name="petitions handed to the Tweede Kamer", kind="petition",
             fetch=fetch),
)
