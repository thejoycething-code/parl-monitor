"""Belgium: petitions to the Chamber of Representatives.

Probed 11 October 2026. The Chamber's petition platform
(dekamer.mijnopinie.belgium.be, also lachambre.monopinion.belgium.be, which
redirects) is a Decidim site whose GraphQL API answers at /api on the Dutch
host (robots.txt empty). The list query gives every petition (447) with its
id, state ('published' is open for signatures: 122 on 11 October), the
online and paper signature counts and the title in French and Dutch
('56_2025-2026/169 - ...'). Asking for the signature dates in the list
breaks the whole query (they are typed non-null and some are null), so the
dates of the open petitions are read in aliased batches,
{ i1428: initiative(id:1428) { signatureStartDate signatureEndDate } ... }.
Only open petitions, and those closed under a month ago, are stored.

THRESHOLD (the Chamber's petition rules): 25,000 signatures, with at least
14,500 from Flanders, 8,000 from Wallonia and 2,500 from Brussels, give the
petitioner a hearing in committee. The regional split is not published, so
the count shown is the total.
"""

from __future__ import annotations

import datetime
import json
import re

from src import petitions as P

CC = "be"
API = "https://dekamer.mijnopinie.belgium.be/api"
ITEM = "https://dekamer.mijnopinie.belgium.be/initiatives/i-{0}"
BATCH = 40
GRACE_DAYS = 30
THRESHOLDS = ((25000, "a hearing in committee (with 14,500 from Flanders, 8,000 from "
                      "Wallonia and 2,500 from Brussels)"),)
STATES = {"published": "open for signatures", "debatted": "debated",
          "intermediate_answer": "intermediate answer", "examinated": "examined",
          "rejected": "rejected", "classified": "closed"}

Q_LIST = ('{ initiatives { id slug state publishedAt onlineVotes offlineVotes '
          'title { translation(locale:"fr") translations { locale text } } } }')


def q_dates(ids):
    return "{ " + " ".join("i{0}: initiative(id:{0}) {{ id signatureStartDate signatureEndDate }}"
                           .format(i) for i in ids) + " }"


def _title(r):
    t = r.get("title") or {}
    fr = t.get("translation")
    nl = None
    for tr in t.get("translations") or []:
        if tr.get("locale") == "nl" and tr.get("text"):
            nl = tr["text"]
        if tr.get("locale") == "fr" and tr.get("text") and not fr:
            fr = tr["text"]
    return fr or nl, nl


def _strip_ref(title):
    return re.sub(r"^\d+_\d{4}-\d{4}/\d+\s*-\s*", "", title or "").strip()


def parse_list(reply):
    """[(id, row)] of every initiative."""
    return [(r.get("id"), r) for r in ((reply.get("data") or {}).get("initiatives") or [])]


def parse_dates(reply):
    out = {}
    for v in (reply.get("data") or {}).values():
        if v and v.get("id"):
            out[str(v["id"])] = (v.get("signatureStartDate"), v.get("signatureEndDate"))
    return out


def entries(rows, dates, today):
    cut = (datetime.date.fromisoformat(today) - datetime.timedelta(days=GRACE_DAYS)).isoformat()
    out = []
    for pid, r in rows:
        start, end = dates.get(str(pid), (None, None))
        if r.get("state") != "published" and not (end and end >= cut):
            continue
        fr, nl = _title(r)
        sigs = (r.get("onlineVotes") or 0) + (r.get("offlineVotes") or 0)
        out.append(P.entry("chambre", "i-{0}".format(pid), _strip_ref(fr), kind="petition",
                           summary=_strip_ref(nl) if nl and nl != fr else None,
                           status=STATES.get(r.get("state"), r.get("state")),
                           opened=start or (r.get("publishedAt") or "")[:10], closes=end,
                           signatures=sigs, body="Chambre des représentants",
                           url=ITEM.format(pid)))
    return out


def fetch(client, today, log=print):
    try:
        reply = client.post_json(API, json.dumps({"query": Q_LIST}), "be-petitions", "list")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["petition list unreadable: {0}".format(str(exc)[:140])])
    rows = parse_list(reply)
    want = [pid for pid, r in rows if r.get("state") == "published"]
    dates, gaps = {}, []
    for i in range(0, len(want), BATCH):
        chunk = want[i:i + BATCH]
        try:
            dates.update(parse_dates(client.post_json(
                API, json.dumps({"query": q_dates(chunk)}), "be-petitions",
                "dates-{0}".format(i // BATCH))))
        except Exception as exc:                    # noqa: BLE001
            gaps.append("dates of {0} petitions unreadable: {1}".format(len(chunk), str(exc)[:100]))
    return P.fetched(entries(rows, dates, today), gaps=gaps,
                     note="{0} petitions on the platform, {1} open".format(len(rows), len(want)))


SOURCES = (
    P.Source(code="chambre", name="Chamber petitions (mijnopinie / monopinion)",
             kind="petition", fetch=fetch, thresholds=THRESHOLDS),
)
