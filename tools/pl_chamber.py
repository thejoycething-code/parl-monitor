#!/usr/bin/env python3
"""Poland: the Sejm's interpellations and written questions.

    python3 tools/pl_chamber.py                      # the last three weeks
    python3 tools/pl_chamber.py --since 2026-09-01
    python3 tools/pl_chamber.py --dry-run
    python3 tools/pl_chamber.py --reclassify

Parity layer 5 (docs/country-parity-handover.md), 10 October 2026. From the
Sejm's open API (api.sejm.gov.pl, keyless; the source tools/pl_rollcalls.py
reads); the rest is src/chamber_store.py.

QUESTIONS. Interpelacje (/sejm/term10/interpellations, about 600 a month)
and zapytania poselskie (/writtenQuestions), each with its number, the date
received, the title ("Interpelacja w sprawie ..."), the deputies who signed
it (`from`, API member ids) and the minister asked (`to`), and the replies
received. Read newest first (`sort_by=-receiptDate`, honoured on questions),
a page at a time, until a page reaches back past --since. Classified on the
title alone; the deputies' clubs come from pl_members (the Polish weekly's
own roster) when it holds them. A reply's arrival is recorded as the date
answered; its text is never read.

THE API IS SLOW on these lists: 2.8 seconds for a page of interpellations
but 80 seconds for two written questions on 10 October 2026 (the list
endpoint sorts the whole term). The timeout here is two and a half minutes
a page; a list that does not answer is a gap and the next run's three-week
lookback reads it again.

SPEECHES ARE NOT COLLECTED. The transcripts endpoint
(/sejm/term10/proceedings/<n>/<date>/transcripts) gave no answer within 30
seconds on two tries on 9 October 2026 and within 45 seconds on two more on
10 October (the proceedings list itself answered 502 Proxy Error that day).
Given up cleanly, as asked: no collector is built on a source that has never
answered. To retry by hand: the probe line in docs/poland-scope.md.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402

CC = "pl"
FEED = "pl-chamber"
API = "https://api.sejm.gov.pl/sejm"
TERM = 10
PAGE = 200
MAX_PAGES = 10
TIMEOUT = 150
LISTS = (("interpellation", "interpellations"), ("written", "writtenQuestions"))


def members(conn):
    """{api id: (name, club)} from pl_members, the weekly's roster; {} without it."""
    try:
        return {str(r[0]): (r[1], r[2]) for r in conn.execute(
            "SELECT mp_id, name, club FROM pl_members WHERE term=?", (TERM,))}
    except Exception:                               # noqa: BLE001
        return {}


def parse(rec, kind, roster):
    signers = [str(int(x)) if str(x).isdigit() else str(x) for x in rec.get("from") or []]
    first = roster.get(signers[0]) if signers else None
    asker = first[0] if first else ("deputy {0}".format(signers[0]) if signers else None)
    if asker and len(signers) > 1:
        asker = "{0} and {1} other(s)".format(asker, len(signers) - 1)
    replies = [r for r in rec.get("replies") or [] if r.get("receiptDate")]
    link = next((l.get("href") for l in rec.get("links") or []
                 if l.get("rel") == "web-description"), None)
    return {"question_id": "{0} {1}/{2}".format("I" if kind == "interpellation" else "Z",
                                                TERM, rec.get("num")),
            "kind": kind, "date": (rec.get("receiptDate") or "")[:10],
            "title": rec.get("title") or "", "text": None, "asker": asker,
            "party": first[1] if first else None,
            "addressee": "; ".join(rec.get("to") or []) or None,
            "answered": min(r["receiptDate"][:10] for r in replies) if replies else None,
            "url": link}


def questions(run):
    roster = members(run.conn)
    for kind, path in LISTS:
        listed, page, done = [], 0, False
        while page < MAX_PAGES and not done:
            url = "{0}/term{1}/{2}?limit={3}&offset={4}&sort_by=-receiptDate".format(
                API, TERM, path, PAGE, page * PAGE)
            try:
                got = run.client.get_json(url, FEED, "{0}-{1}-p{2}".format(path, run.since, page),
                                          timeout=TIMEOUT)
            except (FetchError, ValueError) as exc:
                run.gap("{0} since {1}, page {2}: {3}".format(path, run.since, page,
                                                              str(exc)[:100]))
                break
            for rec in got or []:
                if (rec.get("receiptDate") or "")[:10] <= run.since:
                    done = True
                    continue
                listed.append(rec)
            if len(got or []) < PAGE:
                done = True
            page += 1
        matched = 0
        for rec in listed:
            q = parse(rec, kind, roster)
            m = cs.classify_question(run.taxes, q["title"])
            if not m:
                continue
            matched += 1
            run.question(q, m)
        run.read("{0}:{1}:{2}".format(path, run.since, run.today), "questions", run.today, None,
                 len(listed), matched, 0)
        run.log("  [{0}] {1} received since {2}, {3} on our ground".format(
            path, len(listed), run.since, matched))
        if run.out_of_time("question lists", len(listed)):
            return


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"questions": questions}, doc=__doc__))
