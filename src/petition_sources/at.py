"""Austria: Ministerialentwürfe in Begutachtung, Petitionen and
Bürgerinitiativen before the Nationalrat, and registered Volksbegehren.

Probed 11 October 2026 (docs/austria-scope.md flagged the Begutachtung:
it is when CitizenGO can still send a Stellungnahme, before a bill reaches
the Nationalrat).

MINISTERIALENTWÜRFE: the Parliament's Filter list 81 (the ME list), POST
/Filter/api/filter/data/81?js=eval&showAll=true with {"GP_CODE":
["XXVIII"]}: every government draft of the period (142 on 11 October, 10 in
Begutachtung), positional rows with the ministry, the date it arrived, the
Begutachtungsfrist (the deadline for statements) and the count of
Stellungnahmen received. Only drafts still in Begutachtung, or whose
deadline is under a month past, are stored.

PETITIONEN AND BÜRGERINITIATIVEN: Filter list 143 (the /beteiligen page),
POST with {"AKTIV":["J"],"ITYP":["BI","PET"]}: the open ones (24 PET, 20 BI)
with their online support count (Unterstützungen) and statements. Neither
has a closing date: they stay open while the Petitionsausschuss handles
them. A Bürgerinitiative needs 500 signatures to be filed at all, so every
one listed has passed it; no further threshold applies.

VOLKSBEGEHREN: the interior ministry's list of registered popular
initiatives collecting support declarations (www.bmi.gv.at/411/, one table:
title and "registriert seit"; 40 on 11 October). 8,969 declarations (one
in a thousand of the population, as the page states) let the initiators
request a signing week; the page publishes no counts, so none are shown. The
text PDF's file name is the only stable id. robots.txt (the * group) allows
the page.

robots.txt on www.parlament.gv.at allows /Filter/.
"""

from __future__ import annotations

import datetime
import html as htmlmod
import json
import re

from src import petitions as P

CC = "at"
BASE = "https://www.parlament.gv.at"
FILTER = BASE + "/Filter/api/filter/data/{0}?js=eval&showAll=true"
GP = "XXVIII"
BMI = "https://www.bmi.gv.at/411/"
ME_GRACE_DAYS = 30
VB_THRESHOLDS = ((8969, "support declarations enough to request a signing week"),)

MONTHS = {"jänner": 1, "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
          "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
          "dezember": 12}


def _rows(reply):
    """[{header: value}] from a Filter reply."""
    head = [h.get("label") if isinstance(h, dict) else h for h in reply.get("header") or []]
    out = []
    for r in reply.get("rows") or []:
        d = {}
        for i, v in enumerate(r):
            if i < len(head) and head[i] not in d:
                d[head[i]] = v
        d["_raw"] = r
        out.append(d)
    return out


def _clean_betreff(text):
    return P.one_line(re.sub(r"\s*\(\d+/[A-Z]+\)\s*$", "", htmlmod.unescape(text or "")))


def parse_me(reply, today):
    """[entry] for the drafts in Begutachtung (or closed under a month ago)."""
    cutoff = (datetime.date.fromisoformat(today)
              - datetime.timedelta(days=ME_GRACE_DAYS)).isoformat()
    out = []
    for r in _rows(reply):
        frist = P.iso(r.get("Frist"))
        active = r.get("Begutachtung aktiv?") == "J"
        if not active and not (frist and frist >= cutoff):
            continue
        n = int(str(r.get("INR")).lstrip("0") or 0)
        stmts = r.get("Stellungnahmen")
        status = "Begutachtung {0}".format("läuft" if active else "beendet")
        if stmts is not None:
            status += "; {0} Stellungnahme{1}".format(stmts, "" if stmts == 1 else "n")
        out.append(P.entry("me", "{0}/ME/{1}".format(r.get("Gesetzgebungsperiode") or GP, n),
                           r.get("Betreff"), kind="consultation", status=status,
                           opened=r.get("Einlangen"), closes=r.get("Frist"),
                           body=r.get("Ministerium") or r.get("Ressort"),
                           url=BASE + (r.get("uri") or "/gegenstand/{0}/ME/{1}".format(GP, n))))
    return out


def parse_participations(reply):
    """[entry] for the open Petitionen and Bürgerinitiativen (list 143)."""
    out = []
    for r in _rows(reply):
        raw = r["_raw"]
        ityp = raw[1] if len(raw) > 1 else None
        if ityp not in ("PET", "BI"):
            continue
        n = int(str(raw[2]).lstrip("0") or 0)
        themes = []
        try:
            themes = json.loads(raw[16]) if len(raw) > 16 and raw[16] else []
        except (TypeError, ValueError):
            pass
        stmts = raw[19] if len(raw) > 19 else None
        status = (raw[5] if len(raw) > 5 else None) or ityp
        if stmts:
            status += "; {0} Stellungnahme{1}".format(stmts, "" if stmts == 1 else "n")
        out.append(P.entry("parl", "{0}/{1}/{2}".format(raw[0] or GP, ityp, n),
                           _clean_betreff(raw[6] if len(raw) > 6 else ""),
                           kind="initiative" if ityp == "BI" else "petition",
                           summary=", ".join(themes) or None, status=status, opened=raw[4],
                           signatures=raw[20] if len(raw) > 20 else None, thresholds=(),
                           body="Ausschuss für Petitionen und Bürgerinitiativen",
                           url=BASE + (raw[14] if len(raw) > 14 and raw[14]
                                       else "/gegenstand/{0}/{1}/{2}".format(GP, ityp, n))))
    return out


def german_date(text):
    m = re.search(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})", htmlmod.unescape(text or ""))
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return "{0}-{1:02d}-{2:02d}".format(int(m.group(3)), MONTHS[m.group(2).lower()],
                                        int(m.group(1)))


def parse_volksbegehren(page):
    out = []
    body = page.split("<tbody>", 1)[-1].split("</tbody>", 1)[0]
    for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        a = re.search(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', tr, re.S)
        tds = re.findall(r"<td>(.*?)</td>", tr, re.S)
        if not a or len(tds) < 2:
            continue
        href, title = a.group(1), P.one_line(htmlmod.unescape(re.sub(r"<[^>]+>", "", a.group(2))))
        vid = re.sub(r"\.pdf$", "", href.rsplit("/", 1)[-1])
        out.append(P.entry("vb", vid, title, kind="referendum", status="registriert",
                           opened=german_date(tds[1]), thresholds=VB_THRESHOLDS,
                           body="Bundesministerium für Inneres",
                           url=BMI + href if not href.startswith("http") else href))
    return out


def fetch_me(client, today, log=print):
    try:
        reply = client.post_json(FILTER.format(81), json.dumps({"GP_CODE": [GP]}),
                                 "at-petitions", "me-81")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["ME list unreadable: {0}".format(str(exc)[:140])])
    got = parse_me(reply, today)
    return P.fetched(got, note="{0} drafts in the period, {1} in or just past Begutachtung"
                     .format(len(reply.get("rows") or []), len(got)))


def fetch_participations(client, today, log=print):
    try:
        reply = client.post_json(FILTER.format(143),
                                 json.dumps({"AKTIV": ["J"], "ITYP": ["BI", "PET"]}),
                                 "at-petitions", "participations-143")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["participation list unreadable: {0}".format(str(exc)[:140])])
    return P.fetched(parse_participations(reply), note="open Petitionen and Bürgerinitiativen")


def fetch_volksbegehren(client, today, log=print):
    try:
        page = client.get_text(BMI, "at-petitions", "bmi-volksbegehren")
    except Exception as exc:                        # noqa: BLE001
        return P.fetched([], gaps=["Volksbegehren list unreadable: {0}".format(str(exc)[:140])])
    got = parse_volksbegehren(page)
    return P.fetched(got, note="registered, collecting declarations; no counts published",
                     gaps=[] if got else ["Volksbegehren table empty or changed"])


SOURCES = (
    P.Source(code="me", name="Ministerialentwürfe in Begutachtung", kind="consultation",
             fetch=fetch_me),
    P.Source(code="parl", name="Petitionen and Bürgerinitiativen", kind="petition",
             fetch=fetch_participations),
    P.Source(code="vb", name="registered Volksbegehren (BMI)", kind="referendum",
             fetch=fetch_volksbegehren, thresholds=VB_THRESHOLDS),
)
