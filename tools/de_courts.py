#!/usr/bin/env python3
"""What the Bundesverfassungsgericht has listed for decision.

    python3 tools/de_courts.py
    python3 tools/de_courts.py --dry-run

Christopher, 23 September 2026: build BVerfG judgments. Westminster's edition
has a courts section and Germany had none -- which matters more here than in
London, because the Federal Constitutional Court rules directly on abortion,
religious freedom, family law and speech, and its judgments BIND the
legislature rather than merely informing it. A German monitor that watches the
Bundestag and not Karlsruhe is watching the wrong half on several of our
issues.

THE SOURCE, and what it is not. "Geplante Entscheidungen" -- the cases each
Senate has listed to decide:

  /DE/Aktuelles/GeplanteEntscheidungen/geplante-Entscheidungen_node.html

Probed 23 September 2026: 40 BvR, 23 BvL and 17 BvE case numbers, in tables
under one accordion per Senate, columns Nr. / Aktenzeichen / Informationen zum
Verfahren / Stand des Verfahrens. The court's main decisions page is a landing
page carrying no case numbers at all, and there is no RSS anywhere on the
site, so this list is the machine-readable seam.

IT IS FORWARD-LOOKING AND UNDATED. The court publishes a STAGE, never a
judgment date. So this collector can say what is coming and cannot say when,
and nothing here may imply a date the court has not given. That is the whole
reason the stage is stored verbatim.

CLASSIFIED ON THE SUBJECT COLUMN, which is where the substance is -- a case
number classifies nothing and a Senate name would match everything or nothing.

NO VERDICTS AND NO PREDICTIONS. What the court is going to decide is recorded.
What it will hold, and what that means for us, is not this file's business.

ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import argparse
import datetime
import html as htmllib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

PAGE = ("https://www.bundesverfassungsgericht.de/DE/Aktuelles/"
        "GeplanteEntscheidungen/geplante-Entscheidungen_node.html")

# '1 BvR 2490/24'. The court wraps the register letters in <abbr>, so this
# only ever runs over tag-stripped text -- matching the raw HTML finds
# nothing, which is what made the first probe look like an empty page.
CASE = re.compile(r"\b(\d\s*Bv[RLEFGQK]\s*\d+/\d+)\b")
SENAT = re.compile(r"(Erster|Zweiter)\s+Senat")
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
CAPTION = re.compile(r"<caption[^>]*>(.*?)</caption>", re.S | re.I)
TABLE = re.compile(r"<table[^>]*>(.*?)</table>", re.S | re.I)


def flat(fragment):
    return htmllib.unescape(
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment or ""))).strip()


def parse(page_html):
    """[{case_no, senat, rapporteur, subject, stage}] for every listed case.

    The Senate comes from the accordion heading BEFORE each table, so the
    page is walked in order rather than table by table: a case attributed to
    the wrong Senate would be wrong about which five judges decide it.
    """
    out = []
    # Which Senate is in force at each offset.
    marks = [(m.start(), m.group(0)) for m in SENAT.finditer(page_html)]

    def senat_at(pos):
        cur = None
        for start, label in marks:
            if start <= pos:
                cur = label
            else:
                break
        return cur

    for tm in TABLE.finditer(page_html):
        body = tm.group(1)
        cap = CAPTION.search(body)
        rapporteur = None
        if cap:
            text = flat(cap.group(1))
            rapporteur = text.split(":", 1)[1].strip() if ":" in text else text
        senat = senat_at(tm.start())
        for rm in ROW.finditer(body):
            cells = [flat(c) for c in CELL.findall(rm.group(1))]
            if len(cells) < 4:
                continue
            case = CASE.search(cells[1])
            if not case:
                continue        # the header row, or a layout row
            out.append({
                "case_no": re.sub(r"\s+", " ", case.group(1)).strip(),
                "senat": senat,
                "rapporteur": rapporteur,
                "subject": cells[2] or None,
                "stage": cells[3] or None,
            })
    return out


def pull(conn, client, today, tax, wl, log=print):
    try:
        raw = client.get_text(PAGE, "de-courts", "geplante", archive=False)
    except (FetchError, ValueError) as exc:
        log("  [gap] de-courts: page unreadable ({0})".format(str(exc)[:80]))
        db.record_gap(conn, "de-courts",
                      "Geplante Entscheidungen unreadable: {0}".format(
                          str(exc)[:110]), today)
        return 0, 0, 0
    cases = parse(raw)
    if not cases:
        # A PARSE that finds nothing is not the same as a court with nothing
        # listed, and the page is markup we do not control. Say so loudly.
        log("  [gap] de-courts: the page loaded but no case parsed -- the "
            "table markup has probably changed")
        db.record_gap(conn, "de-courts",
                      "Geplante Entscheidungen parsed to zero cases; markup "
                      "may have changed", today)
        return 0, 0, 0
    seen = new = matched = 0
    for c in cases:
        seen += 1
        res = filt.filter_item(tax, wl, c["subject"] or "", c["case_no"])
        areas = res.issue_areas or []
        if areas:
            matched += 1
            log("  [bverfg] {0} {1}: {2}".format(
                c["case_no"], areas, (c["subject"] or "")[:60]))
        before = conn.execute("SELECT 1 FROM de_judgments WHERE case_no = ?",
                              (c["case_no"],)).fetchone()
        if not before:
            new += 1
        conn.execute(
            "INSERT INTO de_judgments (case_no, senat, rapporteur, subject, "
            "stage, url, areas, matched_terms, tier, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(case_no) DO UPDATE SET "
            "senat=excluded.senat, rapporteur=excluded.rapporteur, "
            "subject=excluded.subject, stage=excluded.stage, "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "tier=excluded.tier, last_seen=excluded.last_seen",
            (c["case_no"], c["senat"], c["rapporteur"], c["subject"],
             c["stage"], PAGE, json.dumps(sorted(set(areas))),
             json.dumps(sorted(set(res.matched_terms or []))), res.tier,
             today, today))
    conn.commit()
    return seen, new, matched


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and report, store nothing")
    args = ap.parse_args()

    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy-de.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-de.yaml"))

    if args.dry_run:
        raw = client.get_text(PAGE, "de-courts", "geplante", archive=False)
        cases = parse(raw)
        print("de-courts: {0} case(s) listed for decision. Nothing "
              "stored.".format(len(cases)))
        for c in cases[:6]:
            print("  {0}  {1}  {2}".format(
                c["case_no"], (c["senat"] or "?"),
                (c["subject"] or "")[:70]))
        conn.close()
        return 0

    seen, new, matched = pull(conn, client, today, tax, wl)
    print("de-courts: {0} case(s) listed for decision, {1} new, {2} on our "
          "ground. The court publishes a stage, never a judgment date."
          .format(seen, new, matched))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
