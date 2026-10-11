"""Argentina: the national government's public consultations.

Probed 11 October 2026. consultapublica.argentina.gob.ar (DemocracyOS; no
robots.txt) answers GET /api/forum/all with every consultation (20): its
slug, title, the office that runs it (extra.owner), when it opened and when
it closes (extra.closingAt). Few a year, mostly from the Transport
Secretariat, none open on 11 October; those closing today or later, or
closed in the last month, are stored.

Not covered: neither chamber of Congress publishes petitions or a public
vote that could be listed.
"""

from __future__ import annotations

import datetime
import html as htmlmod
import re

from src import petitions as P

CC = "ar"
LIST = "https://consultapublica.argentina.gob.ar/api/forum/all"
ITEM = "https://consultapublica.argentina.gob.ar/{0}"
GRACE_DAYS = 30


def parse(rows, today):
    cut = (datetime.date.fromisoformat(today) - datetime.timedelta(days=GRACE_DAYS)).isoformat()
    out = []
    for r in rows or []:
        extra = r.get("extra") or {}
        if extra.get("hidden"):
            continue
        closes = (extra.get("closingAt") or "")[:10] or None
        if not closes or closes < cut:
            continue
        summary = P.one_line(htmlmod.unescape(re.sub(r"<[^>]+>", " ", extra.get("richSummary")
                                                     or r.get("summary") or "")))
        out.append(P.entry("cp", r.get("name") or r.get("id"), r.get("title"),
                           kind="consultation", summary=summary[:P.SUMMARY_CAP] or None,
                           text=summary or None,
                           status="abierta" if closes >= today else "cerrada",
                           opened=(r.get("createdAt") or "")[:10], closes=closes,
                           body=extra.get("owner"), url=ITEM.format(r.get("name"))))
    return out


def fetch(client, today, log=print):
    try:
        rows = client.get_json(LIST, "ar-petitions", "forums")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["consultapublica unreadable: {0}".format(str(exc)[:140])])
    got = parse(rows, today)
    return P.fetched(got, note="{0} consultations on the site, {1} open or just closed".format(
        len(rows or []), len(got)))


SOURCES = (
    P.Source(code="cp", name="national public consultations (consultapublica)",
             kind="consultation", fetch=fetch),
)
