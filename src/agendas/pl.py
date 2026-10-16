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

COMMITTEES (11 October 2026, additive). `/committees/sittings/<date>` lists
each day's committee and subcommittee sittings, planned ones included
(status PLANNED), with the agenda as HTML; `/committees` names them. One
request a day of the window plus one for the names. Measured 11 October
2026: one sitting on 15 October (a recess week), 35 on 8 October. One
point per sitting, titled by the agenda's first line; its prints ('druk nr
3150') are refs as for the plenary, so a committee's reading of a watched
bill is found by number.
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
COMMITTEES = "https://api.sejm.gov.pl/sejm/term{0}/committees".format(TERM)
COMMITTEE_DAY = "https://api.sejm.gov.pl/sejm/term{0}/committees/sittings/{{0}}".format(TERM)
COMMITTEE_WEB = ("https://www.sejm.gov.pl/Sejm{0}.nsf/agent.xsp?symbol=KOMISJAST&NrKadencji={0}"
                 "&KodKom={{0}}".format(TERM))
DIV = re.compile(r"(?s)<div[^>]*>(.*?)</div>")

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


def committee_names(reply):
    """{code: name} for committees and their subcommittees."""
    out = {}
    for c in reply or []:
        out[c.get("code")] = c.get("name")
        for sub in c.get("subCommittees") or []:
            if isinstance(sub, dict) and sub.get("code"):
                out[sub["code"]] = sub.get("name") or "{0}, subcommittee".format(c.get("name"))
            elif isinstance(sub, str):
                out.setdefault(sub, "{0}, subcommittee".format(c.get("name")))
    return out


def parse_committee_day(reply, names=None):
    """Points from one day's committee sittings."""
    out = []
    for s in reply or []:
        if (s.get("status") or "").upper() in ("CANCELLED", "CANCELED"):
            continue
        lines = [text_of(d) for d in DIV.findall(s.get("agenda") or "")]
        lines = [x for x in lines if x] or [text_of(s.get("agenda"))]
        if not lines or not lines[0]:
            continue
        code = s.get("code") or ""
        body = (names or {}).get(code) or (names or {}).get(code[:3]) or "Committee {0}".format(code)
        start = s.get("startDateTime") or ""
        title = REPORTER.sub("", lines[0]).strip() or lines[0]
        rest = lines[1:]
        if len(title) < 25 and rest:                 # 'Sprawy bieżące.': the business follows
            title, rest = rest[0], [lines[0]] + rest[1:]
        detail = " ".join(rest)[:1500] or None
        out.append(agenda.point("kom-{0}-{1}".format(code, s.get("num")), s.get("date"), title,
                                body, "committee", start[11:16] or None, detail,
                                refs=refs_of(s.get("agenda")),
                                url=COMMITTEE_WEB.format(code[:3]),
                                status="closed sitting" if s.get("closed") else None))
    return out


COMMITTEE_DAYS = 28


def fetch_committees(client, today, days):
    """(points, gaps) for the committee sittings of each day of the window."""
    points, gaps = [], []
    try:
        names = committee_names(client.get_json(COMMITTEES, FEED, "committees-term{0}".format(
            TERM), timeout=120))
    except (FetchError, ValueError) as exc:
        names = {}
        gaps.append("committee names unreadable: {0}".format(str(exc)[:80]))
    d = datetime.date.fromisoformat(today)
    # One request per day: capped (16 October 2026), as the Sejm books
    # committee sittings a few weeks ahead at most; the plenary proceedings
    # (one request) are read to whatever date they publish.
    for i in range(min(days, COMMITTEE_DAYS) + 1):
        day = (d + datetime.timedelta(days=i)).isoformat()
        try:
            reply = client.get_json(COMMITTEE_DAY.format(day), FEED, "committees-" + day,
                                    timeout=120)
        except (FetchError, ValueError) as exc:
            gaps.append("committee sittings of {0} unreadable: {1}".format(day, str(exc)[:60]))
            continue
        points += parse_committee_day(reply, names)
    return points, gaps


def fetch(client, today, days, log=print):
    try:
        reply = client.get_json(PROCEEDINGS, FEED, "proceedings-term{0}".format(TERM),
                                timeout=120)
    except (FetchError, ValueError) as exc:
        return agenda.fetched([], gaps=["proceedings unreadable: {0}".format(str(exc)[:120])])
    points, nxt = parse(reply, today)
    note = None if points else "No agenda is published yet for the next sitting"
    committee, gaps = fetch_committees(client, today, days)
    # A point is dated to its sitting's first day; the agenda reaches the last.
    ends = [max(s.get("dates")) for s in reply or []
            if s.get("agenda") and s.get("dates") and max(s["dates"]) >= today]
    ends += [p["date"] for p in committee if p["date"]]
    return agenda.fetched(points + committee, horizon=max(ends) if ends else None,
                          next_sitting=nxt, note=note, gaps=gaps)
