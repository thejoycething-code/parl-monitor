"""Load a Looker campaign export into the store, for RF#1 baselines.

    python3 tools/load_looker_campaigns.py                    # load the export
    python3 tools/load_looker_campaigns.py --show             # what is held
    python3 tools/load_looker_campaigns.py path/to/other.tsv

WHY A FILE AND NOT AN API CALL. There is no Looker credential in this repo --
the Looker connection is an MCP tool available to Claude in session, not to a
scheduled script. So the export is pulled by hand and committed, exactly as
tools/log_campaign_performance.py parses Max's Slack replies. The query and
its filters live in the export header and in docs/campaign-benchmarks.md, so a
refresh is reproducible by whoever next has the MCP open.

WHY A SEPARATE TABLE FROM campaign_performance. They are not the same metric
and pooling them would be wrong:

  * campaign_performance holds LIFETIME PETITION totals for EN GB, from Max.
  * looker_campaigns holds signatures ATTRIBUTED TO AN EMAIL CAMPAIGN, per
    program, across every list.

The same campaign appears in both with different numbers -- "Protect Christian
Teaching in NI Schools" is 129,007 lifetime and 100,521 campaign-attributed.
Averaging those two would produce a figure that describes nothing.

AREAS COME FROM THE PETITION ID, not from the campaign name. The name in this
export is a truncated program SLUG -- "Support NHS nurses in their fi",
"Stand for Stornoway Sa", "Guide with Pride  Withdraw the" -- cut mid-word by
the program string, with punctuation flattened to underscores. Keyword-matching
that slug loses campaigns whose distinguishing word was the part cut off, and
it re-derives from a mangled string what campaign_performance already holds
correctly: the full name AND a curated area mapping. So the program's petition
id is joined to campaign_performance.petition_id -- an exact key -- and that
row's areas are used. On the widened export this resolved 49 of 58 previously
unmapped rows, 30 of them to areas already recorded locally.

The ids are NOT perfectly aligned between the two systems ("Justice for
Jennifer" is 15124 in Looker and 15129 locally), and six programs carry no
usable id at all (`-NA-` or an empty segment), so keyword matching on the slug
remains the documented fallback and area_source records which route was taken.

Looker's own `topic` is NOT used for our areas. It is blank on most EN_GB rows
(the program's own topic code reads NA), and where present it is five coarse
buckets. Areas come from log_campaign_performance.areas_for(), the explicit
keyword table that already maps campaign names and never guesses -- so a
campaign matching nothing is stored unmapped and listed, rather than filed
under a wrong topic.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db
import log_campaign_performance as lcp

DEFAULT_EXPORT = os.path.join(ROOT, "data", "looker", "en_gb_campaigns.tsv")

SCHEMA = """
CREATE TABLE IF NOT EXISTS looker_campaigns (
  program TEXT PRIMARY KEY,       -- the Looker campaign key
  list_name TEXT,                 -- EN_GB, DE, HO ...: the leading segment
  campaign_name TEXT,             -- recovered from the program string
  bound TEXT,                     -- Local | Global | International
  looker_topic TEXT,              -- Looker's own coarse topic; often blank
  start_date TEXT,
  signatures INTEGER, new_members INTEGER,
  otd_eur REAL, md_eur REAL, sent_emails INTEGER,
  areas TEXT,                     -- OUR taxonomy areas
  area_source TEXT,               -- how they were resolved; see resolve_areas
  logged_at TEXT NOT NULL
);
"""

# The campaign name is the tail of the program string, after the list, date,
# bound, topic code, owner initials and petition id. Two naming formats exist
# in the table and only the dash-date one carries real campaigns -- the
# underscore-date format is warm-ups and tests ("TEST_WARM_UP", "Warmup", "L1")
# and every one of those rows has zero signatures. Parsing is therefore
# deliberately strict: a program that does not match is stored with an empty
# name rather than mis-parsed, and shows up in --show as unnamed.
_PROGRAM = re.compile(
    r"^(?P<list>[A-Z]{2}(?:_[A-Z]{2,3})?)-"
    r"(?P<date>\d{4}-\d{2}-\d{2})-"
    r"(?P<bound>Local|Global|International)-"
    # The topic code is two OR THREE letters -- both FM and FAM occur. When
    # this demanded exactly two, "Demand BBC Children In Need CEO Resigns!"
    # (14,583 signatures) failed to parse and was dropped as unnamed.
    r"(?P<code>[A-Z]{2,3})-"
    r"(?P<owner>[A-Z]{3})-"
    r"(?P<pid>\w*)-"
    r"(?P<name>.*)$")


def parse_program(program):
    """(list_name, campaign_name) from a program key. Never raises."""
    m = _PROGRAM.match(program or "")
    if not m:
        head = (program or "").split("-", 1)[0]
        return head, ""
    name = m.group("name").replace("_", " ").strip()
    # Trailing duplication is common: "Paris_Olympics-Paris_Olympics".
    halves = name.split("-")
    if len(halves) == 2 and halves[0].strip() == halves[1].strip():
        name = halves[0].strip()
    return m.group("list"), name


def local_areas(conn):
    """{petition_id: [areas]} from campaign_performance, for the exact join."""
    try:
        rows = conn.execute("SELECT petition_id, areas FROM "
                            "campaign_performance").fetchall()
    except Exception:
        return {}
    return {r["petition_id"]: json.loads(r["areas"] or "[]") for r in rows}


def resolve_areas(program, name, by_pid):
    """([areas], source). The petition id wins; the slug is the fallback."""
    m = _PROGRAM.match(program or "")
    pid = m.group("pid") if m else ""
    if pid.isdigit() and int(pid) in by_pid:
        areas = by_pid[int(pid)]
        # A local row with no areas is still an ANSWER -- the curated sweep
        # looked at it and left it out of the taxonomy. Falling through to
        # keywords there would quietly overrule that decision.
        return areas, "petition-id join ({0})".format(pid)
    if not name:
        return [], "unresolved: no petition id and no parseable name"
    return lcp.areas_for(name), "keywords on the program slug"


def read_export(path):
    """[dict] from the TSV. Comment lines and blanks are skipped."""
    rows, header = [], None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if header is None:
                header = parts
                continue
            rows.append(dict(zip(header, parts)))
    return rows


def _num(value, cast=int):
    text = (value or "").strip()
    if not text:
        return None
    try:
        return cast(float(text))
    except ValueError:
        return None


def load(conn, rows, today):
    stored = unmapped = 0
    unnamed = []
    by_pid = local_areas(conn)
    for r in rows:
        program = (r.get("program") or "").strip()
        if not program:
            continue
        list_name, name = parse_program(program)
        if not name:
            unnamed.append(program)
        areas, source = resolve_areas(program, name, by_pid)
        if not areas:
            unmapped += 1
        conn.execute(
            "INSERT OR REPLACE INTO looker_campaigns (program, list_name, "
            "campaign_name, bound, looker_topic, start_date, signatures, "
            "new_members, otd_eur, md_eur, sent_emails, areas, area_source, "
            "logged_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (program, list_name, name, (r.get("bound") or "").strip(),
             (r.get("looker_topic") or "").strip(),
             (r.get("start_date") or "").strip(),
             _num(r.get("signatures")), _num(r.get("new_members")),
             _num(r.get("otd_eur"), float), _num(r.get("md_eur"), float),
             _num(r.get("sent_emails")), json.dumps(areas), source, today))
        stored += 1
    conn.commit()
    return stored, unmapped, unnamed


def show(conn):
    import statistics
    rows = conn.execute(
        "SELECT campaign_name, signatures, new_members, otd_eur, areas "
        "FROM looker_campaigns ORDER BY signatures DESC").fetchall()
    print("{0} campaign(s) held.".format(len(rows)))
    per = {}
    for r in rows:
        for a in json.loads(r["areas"] or "[]"):
            per.setdefault(a, []).append(r)
    print("\narea  n   median sigs  median new  median OTD EUR")
    for a in sorted(per):
        group = per[a]
        sigs = [x["signatures"] for x in group if x["signatures"]]
        new = [x["new_members"] for x in group if x["new_members"] is not None]
        otd = [x["otd_eur"] for x in group if x["otd_eur"] is not None]
        print("{0:<5} {1:<3} {2:>11} {3:>11} {4:>15}".format(
            a, len(group),
            int(statistics.median(sigs)) if sigs else "-",
            int(statistics.median(new)) if new else "-",
            int(statistics.median(otd)) if otd else "-"))
    un = [r for r in rows if not json.loads(r["areas"] or "[]")]
    if un:
        print("\n{0} campaign(s) map to NO area -- add a keyword to "
              "log_campaign_performance.KEYWORD_AREAS if any belong to us:"
              .format(len(un)))
        for r in un[:12]:
            print("   {0}".format((r["campaign_name"] or "(unnamed)")[:66]))
        if len(un) > 12:
            print("   ...and {0} more".format(len(un) - 12))


def main():
    import datetime
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else DEFAULT_EXPORT
    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    conn.executescript(SCHEMA)
    if "--show" in sys.argv:
        show(conn)
        conn.close()
        return 0
    if not os.path.exists(path):
        print("no export at {0} -- see docs/campaign-benchmarks.md for the "
              "query to re-run.".format(os.path.relpath(path, ROOT)))
        conn.close()
        return 1
    cols = [c[1] for c in conn.execute("PRAGMA table_info(looker_campaigns)")]
    if "area_source" not in cols:
        conn.execute("ALTER TABLE looker_campaigns ADD COLUMN area_source TEXT")
    rows = read_export(path)
    stored, unmapped, unnamed = load(
        conn, rows, datetime.date.today().isoformat())
    print("{0} row(s) loaded from {1}.".format(
        stored, os.path.relpath(path, ROOT)))
    print("{0} mapped to no taxonomy area (kept, listed by --show)."
          .format(unmapped))
    if unnamed:
        print("{0} program(s) could not be parsed for a campaign name: {1}"
              .format(len(unnamed), unnamed[0][:60]))
    show(conn)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
