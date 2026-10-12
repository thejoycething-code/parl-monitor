"""Austria: the Nationalrat's and Bundesrat's Termine with their
Tagesordnungen.

The Parliament's Termine list (`/Filter/api/filter/data/600`, POST, the
body naming the bodies and a date range) gives every plenary sitting and
committee meeting with a link to its Tagesordnung (an HTML document,
`/dokument/<GP>/<...>/TO_<n>.html`). Measured 10 October 2026: 36 entries
for 10 to 31 October; the 103rd Nationalrat sitting's agenda already had
nine points. Each point is a table row ('1.)', the Betreff) and prints the
documents it takes: '(620 d.B.)', 'Antrag 985/A(E)', 'III-393', which are
item keys here ('XXVIII/I/620', 'XXVIII/A/985', 'XXVIII/III/393'), the keys
of at_items and config/watchlist-at.yaml. An Ausschussbericht has its own
d.B. number, so a report point yields both the report's and the bill's key.

robots.txt disallows some /dokument/ paths (privacy requests); every
agenda document is checked against it first, as tools/at_rollcalls.py
does for history pages.
"""

from __future__ import annotations

import datetime
import html
import json
import re
import urllib.robotparser

from src import agenda
from src.http import FetchError

CC = "at"
SOURCE = "the Parliament's Termine and Tagesordnungen"
BILLS = ("at_items", "item_key", "title")
FEED = "at-agenda"
HOST = "https://www.parlament.gv.at"
TERMINE = HOST + "/Filter/api/filter/data/600?js=eval&showAll=true"
ROBOTS = HOST + "/robots.txt"
GREMIEN = ["Nationalrat", "Bundesrat"]
MAX_DOCS = 40

TO_LINK = re.compile(r'href="(/dokument/([A-Z]+)/[^"]*TO_[^"]+\.html)"')
TR = re.compile(r"(?s)<tr[^>]*>(.*?)</tr>")
TD = re.compile(r"(?s)<td[^>]*>(.*?)</td>")
TOP = re.compile(r"^(\d+)\.\)$")
DB = re.compile(r"(\d+)\s*d\.\s*B\.")
SLASH = re.compile(r"\b(\d+)/(A|J|BI|PET|AB|M|BA|E)(?:\(E\))?(?![A-Za-z])")
ROMAN = re.compile(r"\b(III|II)-(\d+)\b")


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    t = html.unescape(t).replace("­", "").replace(" ", " ")
    return " ".join(t.split())


def refs_of(text, gp):
    refs = ["{0}/I/{1}".format(gp, n) for n in DB.findall(text)]
    refs += ["{0}/{1}/{2}".format(gp, kind, n) for n, kind in SLASH.findall(text)]
    refs += ["{0}/{1}/{2}".format(gp, kind, n) for kind, n in ROMAN.findall(text)]
    return refs


def parse_termine(reply):
    """[{date, time, title, type, gremium, path, to_path, gp}] from the list."""
    header = [h.get("label") for h in (reply or {}).get("header") or []]
    out = []
    for row in (reply or {}).get("rows") or []:
        if len(row) < 16:
            continue
        rec = dict(zip(range(len(row)), row))
        link2 = rec.get(7) or ""
        m = TO_LINK.search(link2)
        start = rec.get(15) or ""
        out.append({"date": start[:10] or None,
                    "time": start[11:16] if start[11:16] not in ("", "00:00") else None,
                    "title": text_of(rec.get(3)), "type": rec.get(5),
                    "gremium": rec.get(10), "path": rec.get(4),
                    "to_path": m.group(1) if m else None,
                    "gp": m.group(2) if m else None})
    return out if "Bezeichnung" in header else []


def parse_to(page, entry):
    """Points from one Tagesordnung document."""
    plenary = (entry.get("type") or "").startswith("Plenar")
    body = entry["title"] if not plenary else "{0}, plenary".format(entry.get("gremium") or "Nationalrat")
    out = []
    for tr in TR.findall(page or ""):
        cells = [text_of(td) for td in TD.findall(tr)]
        if len(cells) < 2 or not TOP.match(cells[0]):
            continue
        n = TOP.match(cells[0]).group(1)
        text = cells[1]
        title = re.sub(r"\s*Berichterstatter\w*(?::in)?:.*$", "", text).strip() or text
        # 'NRSITZ/101 TOP 3': the sitting or committee path, without the GP and the file
        where = re.sub(r"^/dokument/[A-Z]+/|/TO_[^/]+$", "", entry["to_path"])
        out.append(agenda.point("{0} TOP {1}".format(where, n), entry["date"], title,
                                body, "plenary" if plenary else "committee", entry["time"],
                                refs=refs_of(text, entry.get("gp") or "XXVIII"),
                                url=HOST + entry["to_path"]))
    return out


def robots(client):
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(client.get_text(ROBOTS, FEED, "robots", archive=False).splitlines())
    except FetchError:
        return None
    return rp


def fetch(client, today, days, log=print):
    end = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    body = json.dumps({"GREMIUM": GREMIEN, "DATERANGE": [today, end]})
    try:
        entries = parse_termine(client.post_json(TERMINE, body, FEED,
                                                 "termine-{0}".format(today), timeout=120))
    except (FetchError, ValueError) as exc:
        return agenda.fetched([], gaps=["Termine unreadable: {0}".format(str(exc)[:120])])
    rp = robots(client)
    points, gaps, read = [], [], 0
    sittings = sorted(e["date"] for e in entries
                      if (e.get("type") or "").startswith("Plenar") and e["date"])
    for e in entries:
        if not e["to_path"] or not e["date"] or not (today <= e["date"] <= end):
            continue
        if rp is not None and not rp.can_fetch(client.user_agent, HOST + e["to_path"]):
            log("  robots.txt disallows {0}; skipped".format(e["to_path"]))
            continue
        if read >= MAX_DOCS:
            gaps.append("Tagesordnungen: stopped after {0}".format(MAX_DOCS))
            break
        read += 1
        try:
            page = client.get_text(HOST + e["to_path"], FEED, "to-" + e["to_path"])
        except FetchError as exc:
            gaps.append("{0} unreadable: {1}".format(e["to_path"], str(exc)[:80]))
            continue
        points += parse_to(page, e)
    no_to = sum(1 for e in entries if not e["to_path"])
    note = ("{0} of {1} meeting(s) have no Tagesordnung published yet".format(no_to, len(entries))
            if no_to else None)
    return agenda.fetched(points, next_sitting=sittings[0] if sittings else None, note=note,
                          gaps=gaps)
