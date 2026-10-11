"""Italy: popular-initiative bills and referendums collecting signatures on
the Ministry of Justice's platform, and the government's consultations.

Probed 11 October 2026.

FIRMEREFERENDUM (firmereferendum.giustizia.it, the public signature
platform since 2021): GET /referendum/api-portal/iniziativa/public returns
every initiative in one JSON reply (87 on 11 October, although it reports a
page size of 10), each with its title, short description, collection dates
(dataInizioRaccolta, dataFineRaccolta; 9999-12-31 for open-ended), the
signature count so far (sostenitori), the quorum it needs (50,000 for a
popular bill, art. 71 of the Constitution; 500,000 for an abrogative
referendum, art. 75), its type and status ('IN RACCOLTA FIRME', 'CHIUSA',
'MESSA A DISPOSIZIONE'). Only those still collecting, or closed under a
month ago, are stored. robots.txt answers 403 (no rules published).

PARTECIPA (partecipa.gov.it, the government's consultation platform, a
Decidim site): POST /api GraphQL for the participatory processes with
their start and end dates. Few are open at a time (3 of 60 on 11 October);
only those ending today or later are stored. robots.txt is empty.

The Camera's and the Senato's own petition lists were not readable (503
and 403 from here), so parliamentary petitions are not covered.
"""

from __future__ import annotations

import datetime
import json

from src import petitions as P

CC = "it"
FIRME = "https://firmereferendum.giustizia.it/referendum/api-portal/iniziativa/public"
FIRME_PAGE = "https://firmereferendum.giustizia.it/referendum/open/dettaglio-open/{0}"
PARTECIPA = "https://partecipa.gov.it/api"
GRACE_DAYS = 30

QUORUM_NOTE = {
    50000: "signatures to file the bill in Parliament (art. 71)",
    500000: "signatures to call the referendum (art. 75)",
}


def parse_firme(reply, today):
    cutoff = (datetime.date.fromisoformat(today)
              - datetime.timedelta(days=GRACE_DAYS)).isoformat()
    out = []
    for r in reply.get("content") or []:
        end = (r.get("dataFineRaccolta") or "")[:10]
        status = ((r.get("idDecStatoIniziativa") or {}).get("nome") or "").strip()
        collecting = status == "IN RACCOLTA FIRME"
        if not collecting and not (end and cutoff <= end):
            continue
        quorum = r.get("quorum")
        kind_name = ((r.get("idDecTipoIniziativa") or {}).get("nome") or "").strip()
        thresholds = [[quorum, QUORUM_NOTE.get(quorum, "signatures required")]] if quorum else []
        out.append(P.entry("firme", r.get("id"), r.get("titolo") or r.get("titoloLeggeCostituzionale"),
                           kind="referendum", summary=r.get("descrizioneBreve"),
                           text=r.get("descrizione"), status=status,
                           opened=r.get("dataInizioRaccolta") or r.get("dataApertura"),
                           closes=None if end.startswith("9999") else end,
                           signatures=r.get("sostenitori"), thresholds=thresholds,
                           body=kind_name, url=FIRME_PAGE.format(r.get("id"))))
    return out


Q_PROCESSES = ('{ participatoryProcesses { id slug title { translation(locale:"it") } '
               'subtitle { translation(locale:"it") } startDate endDate } }')


def parse_processes(reply, today):
    out = []
    for r in ((reply.get("data") or {}).get("participatoryProcesses") or []):
        end = r.get("endDate")
        if not end or end < today:
            continue
        out.append(P.entry("partecipa", r.get("slug") or r.get("id"),
                           (r.get("title") or {}).get("translation"), kind="consultation",
                           summary=(r.get("subtitle") or {}).get("translation"),
                           status="aperta", opened=r.get("startDate"), closes=end,
                           body="Governo (ParteciPa)",
                           url="https://partecipa.gov.it/processes/{0}".format(r.get("slug"))))
    return out


def fetch_firme(client, today, log=print):
    try:
        reply = client.get_json(FIRME, "it-petitions", "firmereferendum")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["firmereferendum unreadable: {0}".format(str(exc)[:140])])
    got = parse_firme(reply, today)
    return P.fetched(got, note="{0} initiatives on the platform, {1} collecting or just closed"
                     .format(len(reply.get("content") or []), len(got)))


def fetch_partecipa(client, today, log=print):
    try:
        reply = client.post_json(PARTECIPA, json.dumps({"query": Q_PROCESSES}), "it-petitions",
                                 "partecipa")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["ParteciPa unreadable: {0}".format(str(exc)[:140])])
    return P.fetched(parse_processes(reply, today), note="open consultations")


SOURCES = (
    P.Source(code="firme", name="popular initiatives and referendums (firmereferendum)",
             kind="referendum", fetch=fetch_firme),
    P.Source(code="partecipa", name="government consultations (ParteciPa)",
             kind="consultation", fetch=fetch_partecipa),
)
