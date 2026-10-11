"""Colombia: draft regulations open for comment on SUCOP.

Probed 11 October 2026. The Sistema Único de Consulta Pública
(www.sucop.gov.co; robots.txt disallows only SharePoint's internals) is a
SharePoint list readable anonymously through its REST API: the 'Procesos
SUCOP' list, newest first, 200 rows a page, each a draft decree or
resolution (title nombreProyecto, summary Objeto, comment window
FechaInicioComentarios and FechaFinComentarios, state estadoView such as
'En consulta pública', the comment count Mensajes, and its page under the
ministry's own path in MostrarLink). The list also holds the drafts'
documents, which have no nombreProyecto and are skipped, as are the site's
test rows. A filter on the end date answers 500 (the list is over
SharePoint's threshold), so the newest PAGES pages are read and filtered
here: drafts whose comment window ends today or later, or ended in the
last month. About 24 new drafts in ten days; 14 open on 11 October.

The window's end is stored as the Bogotá date (the API gives 04:59:59 UTC,
the last second of the day in Bogotá).

No edition of its own: Colombia is in the monthly Latam edition
(src/latam.py PETITIONS), and these rows are classified with taxonomy-es
for Colombia, as tools/co_rollcalls.py classifies bills.
"""

from __future__ import annotations

import datetime
import re

from src import petitions as P

CC = "co"
TAXONOMIES = (("taxonomy-es.yaml", "co"),)
LIST = ("https://www.sucop.gov.co/formulacion_/_api/web/lists/getbytitle(%27Procesos%20SUCOP%27)"
        "/items?$top=200&$orderby=Id%20desc&$select=Id,Title,nombreProyecto,"
        "FechaInicioComentarios,FechaFinComentarios,Mensajes,estadoView,Created,MostrarLink,Objeto")
PAGES = 3
GRACE_DAYS = 30
TEST = re.compile(r"(?i)\bprueba\b|entidad ejemplo")


def bogota_date(stamp):
    if not stamp:
        return None
    try:
        t = datetime.datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return P.iso(stamp)
    return (t - datetime.timedelta(hours=5)).date().isoformat()


def ministry(url):
    m = re.search(r"/entidades/([^/]+)/", url or "")
    return m.group(1) if m else None


def parse(reply, today):
    cut = (datetime.date.fromisoformat(today) - datetime.timedelta(days=GRACE_DAYS)).isoformat()
    out = []
    for r in reply.get("value") or []:
        name = r.get("nombreProyecto")
        if not name or TEST.search(name) or TEST.search(r.get("Title") or ""):
            continue
        end = bogota_date(r.get("FechaFinComentarios"))
        if not end or end < cut:
            continue
        link = (r.get("MostrarLink") or {}).get("Url")
        status = r.get("estadoView") or ""
        if r.get("Mensajes"):
            status += "; {0} comentarios".format(r["Mensajes"])
        out.append(P.entry("sucop", r.get("Title") or r.get("Id"), name.strip().strip('"'),
                           kind="consultation", summary=r.get("Objeto"), status=status,
                           opened=bogota_date(r.get("FechaInicioComentarios")), closes=end,
                           body=ministry(link), url=link))
    return out


def fetch(client, today, log=print):
    entries, gaps, url = [], [], LIST
    for page in range(PAGES):
        try:
            reply = client.get_json(url, "co-petitions", "sucop-{0}".format(page))
        except Exception as exc:                    # noqa: BLE001
            gaps.append("SUCOP page {0} unreadable: {1}".format(page, str(exc)[:120]))
            break
        entries += parse(reply, today)
        url = reply.get("odata.nextLink")
        if not url:
            break
    return P.fetched(entries, gaps=gaps, note="the newest {0} pages of the list".format(PAGES))


SOURCES = (
    P.Source(code="sucop", name="SUCOP draft regulations", kind="consultation", fetch=fetch),
)
