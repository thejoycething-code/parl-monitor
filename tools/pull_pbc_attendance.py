"""Collect Public Bill Committee attendance from the sitting rosters.

    python3 tools/pull_pbc_attendance.py

Hansard prints, at the head of every PBC sitting, the committee roster with
a dagger by each member who attended that day -- the legend line underneath
reads "(dagger) attended the Committee". That roster is the only official
attendance record a bill committee has: the Committees API covers select
committees and knows nothing of bill committees, which is why TheyWorkForYou
parses these same transcripts.

This walks the sittings of each bill named under `pbc_attendance` in
config/vote_tracker.yaml (found in the raw archive's sweep metadata, so a
sitting nobody spoke in about our issues would be missed -- across 29
sittings of the Terminally Ill Adults Bill, none was), fetches each sitting's
transcript once, parses the roster, resolves the printed names against the
members table, and records one row per person per sitting.

COLLECTED BUT NOT DISPLAYED (Christopher, 2026-08-31): no page reads
committee_attendance yet. A name that cannot be resolved to a member id is
stored with member_id NULL and PRINTED -- never silently dropped.

Idempotent: a sitting whose rows are already stored is not refetched, so the
weekly re-run costs nothing once a bill's committee has finished.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, quotes
from src.http import HttpClient
from src.ingest.hansard import HANSARD_API

CONFIG = os.path.join(ROOT, "config", "vote_tracker.yaml")

ROSTER_START = "consisted of the following Members"
ROSTER_END = "attended the Committee"
DAGGER = "†"

# "Kruger, Danny" printed surname-first, with honourifics loose in either
# half: "Opher, Dr Simon", "Gale, Sir Roger". Same list initials() uses in
# the page template, plus the compounds Hansard prints.
HONOURIFIC = re.compile(
    r"\b(?:Mr|Ms|Mrs|Miss|Dr|Sir|Dame|Rt Hon\.?|The Reverend|Rev)\.?\s+")
TAG = re.compile(r"<[^>]+>")
EM = re.compile(r"<em>\s*\((?P<inside>[^)]*)\)\s*</em>")
# The party sits OUTSIDE the <em>: "... </em> (Lab/Co-op)". Matched after
# tag-stripping instead, on the LAST parenthetical of the line.
ROW = re.compile(r"^(?P<dagger>†\s*)?(?P<sur>[^,(]+),\s*(?P<rest>.+)$")


def norm(text):
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(HONOURIFIC.sub(" ", text).lower().split())


def sittings_from_archive(raw, bill):
    """{debate_id: (date, sitting_label)} for one bill's PBC sittings."""
    out = {}
    for meta in raw.meta.values():
        title = meta.get("debate") or ""
        hit = re.match(re.escape(bill) + r"\s*\((?P<n>[^)]*sitting)\)\s*$",
                       title, re.IGNORECASE)
        if hit and meta.get("debate_id"):
            out[meta["debate_id"]] = (meta.get("date") or "", hit.group("n"))
    return out


def parse_roster(items):
    """[(name_as_printed, role, attended)] from a sitting's opening items.

    The roster block runs from "The Committee consisted of the following
    Members:" to the dagger legend. Inside it: one line of chairs, one row
    per member, and a clerks line that names no member. A minister's row
    carries their OFFICE where everyone else has a constituency -- both are
    ignored here, because the name is the record and the office changes.
    """
    rows, inside = [], False
    for item in items:
        value = item.get("Value") or ""
        text = " ".join(TAG.sub(" ", value).split())
        if not inside:
            if ROSTER_START in text:
                inside = True
            continue
        if ROSTER_END in text:
            return rows
        if not text or "Committee Clerk" in text:
            continue
        if re.match(r"^\s*(?:<em>)?\s*Chairs?:", value.strip()):
            after = re.sub(r"^.*?Chairs?:\s*(?:</em>)?", "", value)
            for part in TAG.sub(" ", after).split(","):
                name = part.strip()
                if not name:
                    continue
                rows.append((name.lstrip(DAGGER).strip(), "chair",
                             DAGGER in name))
            continue
        hit = ROW.match(text)
        if not hit:
            continue          # a stray column marker; the roster forgives it
        # Drop the constituency/office and party parentheticals: everything
        # from the first "(" onward is annotation, not name.
        rest = hit.group("rest").split("(")[0].strip()
        name = "{0} {1}".format(rest, hit.group("sur").strip()).strip()
        rows.append((name, "member", bool(hit.group("dagger"))))
    return rows if inside else None


def resolve(conn, prefer_current=False):
    """{normalised name: member_id}, ambiguous names resolved to None.

    prefer_current=True breaks a tie in favour of the one SITTING member of
    that name -- right for a source that can only name sitting members,
    like the current APPG register (its "Paul Holmes" is the Hamble Valley
    Conservative, not the Chesterfield Lib Dem who left in 2010). It stays
    OFF for the PBC rosters: a 2025 roster names members current THEN, and
    one who has since left must not resolve to a current namesake.
    """
    index = {}
    current = {}
    for row in conn.execute(
            "SELECT id, name, list_as, "
            "COALESCE(current_mp, 0) + COALESCE(current_peer, 0) AS sitting "
            "FROM members"):
        for form in (row["name"], row["list_as"]):
            if not form:
                continue
            if "," in form:      # 'Kruger, Danny' -> 'Danny Kruger'
                sur, _, first = form.partition(",")
                form = "{0} {1}".format(first.strip(), sur.strip())
            key = norm(form)
            if key in index and index[key] != row["id"]:
                index[key] = None          # two members, one name: no claim
            else:
                index[key] = row["id"]
            if row["sitting"]:
                if key in current and current[key] != row["id"]:
                    current[key] = None    # two SITTING members share it
                else:
                    current[key] = row["id"]
    if prefer_current:
        for key, val in index.items():
            if val is None and current.get(key) is not None:
                index[key] = current[key]
    return index


def main():
    import yaml
    with open(CONFIG, encoding="utf-8") as handle:
        bills = (yaml.safe_load(handle) or {}).get("pbc_attendance") or []
    if not bills:
        print("no bills under pbc_attendance in config/vote_tracker.yaml")
        return 0

    conn = db.init_db(db.connect(os.path.join(ROOT, "data", "parl-monitor.db")))
    raw = quotes.RawHansard(ROOT)
    names = resolve(conn)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    unresolved = set()

    for bill in bills:
        sittings = sittings_from_archive(raw, bill)
        if not sittings:
            db.record_gap(conn, "pbc-attendance",
                          "no sittings of '{0}' in the raw archive".format(bill))
            continue
        stored = fetched = rows_written = 0
        for debate_id, (date, label) in sorted(sittings.items(),
                                               key=lambda kv: kv[1]):
            have = conn.execute(
                "SELECT COUNT(*) FROM committee_attendance WHERE debate_id = ?",
                (debate_id,)).fetchone()[0]
            if have:
                stored += 1
                continue
            try:
                payload = client.get_json(
                    "{0}/debates/debate/{1}.json".format(HANSARD_API, debate_id),
                    "hansard", "debate-{0}".format(debate_id))
            except Exception as exc:
                db.record_gap(conn, "pbc-attendance",
                              "{0} ({1}): {2}".format(label, date, exc))
                continue
            roster = parse_roster(payload.get("Items") or [])
            if not roster:
                db.record_gap(conn, "pbc-attendance",
                              "{0} ({1}): no roster block in the transcript"
                              .format(label, date))
                continue
            fetched += 1
            for name, role, attended in roster:
                member_id = names.get(norm(name))
                if member_id is None:
                    unresolved.add(name)
                conn.execute(
                    "INSERT OR REPLACE INTO committee_attendance "
                    "(bill, debate_id, sitting, date, member_id, name, role, "
                    "attended) VALUES (?,?,?,?,?,?,?,?)",
                    (bill, debate_id, label,
                     date or (payload.get("Overview") or {}).get("Date", "")[:10],
                     member_id, name, role, 1 if attended else 0))
                rows_written += 1
        conn.commit()
        total, people = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT name) FROM committee_attendance "
            "WHERE bill = ?", (bill,)).fetchone()
        print("{0}: {1} sittings ({2} already stored, {3} fetched), "
              "{4} rows this run; {5} rows / {6} people held in total".format(
                  bill, len(sittings), stored, fetched, rows_written,
                  total, people))

    if unresolved:
        # Printed, never suppressed: a name the members table cannot claim
        # is stored with member_id NULL and must be visible so someone can
        # decide whether the roster or the roster-reader is wrong.
        print("  {0} name(s) not resolved to a member id: {1}".format(
            len(unresolved), "; ".join(sorted(unresolved))))
    gaps = conn.execute(
        "SELECT COUNT(*) FROM gaps WHERE feed = 'pbc-attendance'").fetchone()[0]
    print("{0} gap(s) on record for this feed".format(gaps))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
