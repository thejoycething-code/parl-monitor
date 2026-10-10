"""Poland: the Sejm's sittings and their agendas from its API.

`/sejm/term10/proceedings` lists every sitting of the term with its days
and, once the Marshal has set it, its agenda as HTML ('Porządek dzienny'),
plus the PLANNED sittings to September 2027 (number 0, dates only).
Measured 9 October 2026: 89 entries; sitting 67 (20 to 23 October) already
carried a 41-point agenda. The agenda does not say which day a point is
taken, so a point is dated to the sitting's first day and the body names
the sitting's days.

Refs: every 'druk nr' as a print key ('10/3183') and the process the
agenda links (PrzebiegProc.xsp?nr=3086, '10/3086'); `resolve` maps prints
to their process through pl_prints. Process keys are what pl_processes and
config/watchlist-pl.yaml use.

The API did not answer the laptop on 10 October 2026 (40 s timeouts); the
weekly job runs on the Mini, which reads it for the vote collector.
"""

from __future__ import annotations

import datetime
import html
import re

from src import agenda
from src.http import FetchError

CC = "pl"
SOURCE = "the Sejm API's proceedings, with planned sittings"
BILLS = ("pl_processes", "process_key", "title")
FEED = "pl-agenda"
TERM = 10
PROCEEDINGS = "https://api.sejm.gov.pl/sejm/term{0}/proceedings".format(TERM)
WEB = "https://www.sejm.gov.pl/sejm{0}.nsf/porzadek.xsp?posiedzenie={1}"

LI = re.compile(r"(?s)<li[^>]*>(.*?)</li>")
# Each <ol> with the text before it: the first is the agenda as set; one
# after "Porządek dzienny może być uzupełniony o:" lists possible additions.
OL = re.compile(r"(?s)((?:(?!<ol).)*)<ol[^>]*>(.*?)</ol>")
PROCESS = re.compile(r"PrzebiegProc\.xsp\?nr=(\d+)")
DRUK = re.compile(r"druk(?:i|u|ów)?\s+nr\s+((?:[\d]+(?:-[A-Z])?[\s,i]*)+)", re.I)
NUM = re.compile(r"\d+(?:-[A-Z])?")
REPORTER = re.compile(r"\s*-\s*sprawozdawc\w*\s.*$|\s*-\s*uzasadnia\s.*$", re.I)


def text_of(fragment):
    t = re.sub(r"<br\s*/?>", " ", fragment or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(html.unescape(t).replace(" ", " ").split())


def refs_of(fragment):
    refs = ["{0}/{1}".format(TERM, n) for n in PROCESS.findall(fragment or "")]
    for group in DRUK.findall(text_of(fragment)):
        refs += ["{0}/{1}".format(TERM, n) for n in NUM.findall(group)]
    return refs


def short(iso):
    d = datetime.date.fromisoformat(iso)
    return "{0} {1}".format(d.day, d.strftime("%b"))


def parse_agenda(sitting):
    """Points from one sitting's agenda HTML."""
    dates = sorted(sitting.get("dates") or [])
    if not dates or not sitting.get("agenda"):
        return []
    number = sitting.get("number")
    body = "Plenary, sitting {0}{1}".format(
        number, " ({0} days, to {1})".format(len(dates), short(dates[-1])) if len(dates) > 1
        else "")
    out, i, status = [], 0, None
    for lead, block in OL.findall(sitting["agenda"]):
        lead = text_of(lead).lower()
        if "uzupełnion" in lead:
            status = "May be added to the agenda"
        elif "uchwał" in lead and "senatu" in lead:
            status = "Senate resolutions, if any"
        for li in LI.findall(block):
            full = text_of(li)
            if not full:
                continue
            i += 1
            title = REPORTER.sub("", full).strip() or full
            out.append(agenda.point("{0}-{1}".format(number, i), dates[0], title, body,
                                    "plenary", detail=full if full != title else None,
                                    refs=refs_of(li), url=WEB.format(TERM, number),
                                    status=status))
    return out


def parse(reply, today):
    """(points, next sitting) from the proceedings list: every sitting with
    a day on or after `today`."""
    points, upcoming = [], []
    for s in reply or []:
        dates = sorted(s.get("dates") or [])
        if not dates or dates[-1] < today:
            continue
        upcoming.append(dates[0] if dates[0] >= today else today)
        points += parse_agenda(s)
    return points, (min(upcoming) if upcoming else None)


def resolve(conn, refs):
    """Print keys to their process keys (pl_prints.process_key)."""
    out = []
    for r in refs:
        try:
            got = conn.execute("SELECT process_key FROM pl_prints WHERE print_key = ?",
                               (r,)).fetchone()
        except Exception:                          # noqa: BLE001 - table missing
            return out
        if got and got[0]:
            out.append(got[0])
    return out


def fetch(client, today, days, log=print):
    try:
        reply = client.get_json(PROCEEDINGS, FEED, "proceedings-term{0}".format(TERM),
                                timeout=120)
    except (FetchError, ValueError) as exc:
        return agenda.fetched([], gaps=["proceedings unreadable: {0}".format(str(exc)[:120])])
    points, nxt = parse(reply, today)
    note = None if points else "No agenda is published yet for the next sitting"
    # A point is dated to its sitting's first day; the agenda reaches the last.
    ends = [max(s.get("dates")) for s in reply or []
            if s.get("agenda") and s.get("dates") and max(s["dates"]) >= today]
    return agenda.fetched(points, horizon=max(ends) if ends else None, next_sitting=nxt,
                          note=note)
