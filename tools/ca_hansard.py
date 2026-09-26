#!/usr/bin/env python3
"""Who said what in the House of Commons of Canada, on our issues.

    python3 tools/ca_hansard.py                     # the next unread sittings
    python3 tools/ca_hansard.py --from 140 --limit 5
    python3 tools/ca_hansard.py --session 44-1 --from 1 --limit 20
    python3 tools/ca_hansard.py --dry-run           # parse and count, store nothing
    python3 tools/ca_hansard.py --db /tmp/ca.db

GROUNDWORK, phase 2 (26 September 2026). Nothing schedules this.

THE SOURCE. One XML per sitting, keyless:
ourcommons.ca/Content/House/<parl><session>/Debates/<nnn>/HAN<nnn>-E.XML.
Sitting 45-1/144 is 300 KB with 191 interventions. Sittings are numbered
consecutively, so the collector resumes at the highest sitting it has READ
plus one, and stops at the first number the House has not published (a 404
through a redirect to its error page). The frontier is not a gap.

WHAT A SPEECH IS. Each <Intervention>, in document order, under the
OrderOfBusiness (the rubric: Government Orders, Oral Questions, Routine
Proceedings...) and SubjectOfBusiness (the debate title) it sits in. Its
time is the last <Timestamp> before it: the House stamps every five minutes,
so a time here is good to five minutes, and the German protocol has none.
Petitions presented in Routine Proceedings arrive here too, as speeches
under the "Petitions" subject, each MP summarising what they present.

WHO SPOKE. The speaker is an <Affiliation DbId=...> whose id is a member IN
A ROLE, not the member: none of 191 matched a PersonId on sitting 144. The
label carries the riding the first time a member speaks in a debate --
"Gabriel Hardy (Montmorency—Charlevoix, CPC)" -- and ridings are unique, so
the RIDING resolves the person against the current roster, a unique name is
the fallback, and the DbId is remembered in ca_speaker_roles so a later bare
"Gabriel Hardy" or "Minister of Finance" resolves too. A label that resolves
by none of these is stored with person_id NULL and counted per sitting.
Never guessed: a wrong attribution in a 5CA is worse than a blank.

THE CHAIR IS COUNTED AND NOT STORED, as in the German collector. ONLY
SPEECHES ON OUR GROUND ARE STORED; every sitting read gets a ca_sittings row
with its totals regardless. Classification is per passage
(src/filter.match_passages) against the English taxonomy plus
config/watchlist-ca.yaml; the debate title counts as a passage.

A BACKFILL (--from 1 over a whole session: 144 sittings, ~40 MB) runs from
CI, paced, and is announced -- the Bundestag IP block of 24 September 2026.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "ca-hansard"
CURRENT_SESSION = "45-1"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy.yaml")
WATCHLIST = os.path.join(ROOT, "config", "watchlist-ca.yaml")
SITTING = "https://www.ourcommons.ca/Content/House/{0}{1}/Debates/{2:03d}/HAN{2:03d}-E.XML"
ROSTER = "https://www.ourcommons.ca/members/en/search/xml?parliament={0}"
DEFAULT_LIMIT = 10          # a sitting week is four days; ten covers a missed week
HIDDEN_AREAS = (11,)        # migration: collated, never campaigned

PARTIES = {"CPC": "Conservative", "Lib.": "Liberal", "BQ": "Bloc Québécois",
           "NDP": "NDP", "GP": "Green Party", "Ind.": "Independent"}
HONORIFICS = re.compile(r"^(?:(?:Right\s+)?Hon\.|Mr\.|Mrs\.|Ms\.|Dr\.)\s+", re.I)
LABEL = re.compile(r"^(?P<name>[^()]*?)\s*\((?P<inner>.*)\)\s*:?\s*$", re.S)
BILL = re.compile(r"\b([CS])[\-‐‑–](\d{1,4})\b")


def parse_session(code):
    hit = re.match(r"^(\d{1,2})-(\d)$", (code or "").strip())
    if not hit:
        raise ValueError("session must look like 45-1, not {0!r}".format(code))
    return int(hit.group(1)), int(hit.group(2))


def fold(text):
    """Casefolded, accent-free, dash-normalised, single-spaced."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[‐-―\-]", "-", text)
    return " ".join(text.casefold().split())


def is_chair(label):
    lab = (label or "").strip()
    return lab.startswith("The ") and ("Speaker" in lab or "Chair" in lab)


def parse_label(label):
    """(name, riding_or_role, party) from a Hansard speaker label.

    "Gabriel Hardy (Montmorency—Charlevoix, CPC)" -> (Gabriel Hardy,
    Montmorency—Charlevoix, Conservative). The bracket holds a riding or a
    role, then the party abbreviation; a bare label holds only a name or a
    role, and both come back in `name`."""
    label = " ".join((label or "").replace(":", " ").split())
    hit = LABEL.match(label)
    if not hit:
        return HONORIFICS.sub("", label).strip() or None, None, None
    name = HONORIFICS.sub("", hit.group("name")).strip() or None
    inner = hit.group("inner").strip()
    head, _, tail = inner.rpartition(",")
    party = PARTIES.get(tail.strip())
    if party is None:
        return name, inner or None, None
    return name, head.strip() or None, party


class Roster:
    """Members by riding and by name, from ca_members."""

    def __init__(self, conn):
        self.by_riding, self.by_name = {}, {}
        for pid, name, riding in conn.execute(
                "SELECT person_id, name, constituency FROM ca_members"):
            if riding:
                self.by_riding.setdefault(fold(riding), set()).add(pid)
            if name:
                self.by_name.setdefault(fold(name), set()).add(pid)

    def resolve(self, name, riding):
        """(person_id, how) or (None, None). Only a UNIQUE hit resolves."""
        if riding:
            hits = self.by_riding.get(fold(riding)) or set()
            if len(hits) == 1:
                return next(iter(hits)), "riding"
        if name:
            hits = self.by_name.get(fold(name)) or set()
            if len(hits) == 1:
                return next(iter(hits)), "name"
        return None, None


def load_roster(conn, client, parliament, today):
    """Refresh ca_members from the House's roster for one Parliament."""
    text = client.get_text(ROSTER.format(parliament), FEED,
                           "roster-{0}".format(parliament), archive=False)
    n = 0
    for m in ET.fromstring(text):
        pid = (m.findtext("PersonId") or "").strip()
        if not pid:
            continue
        name = " ".join(x for x in ((m.findtext("PersonOfficialFirstName") or "").strip(),
                                    (m.findtext("PersonOfficialLastName") or "").strip()) if x)
        conn.execute(
            "INSERT INTO ca_members (person_id, name, party, constituency, "
            "province, first_seen, last_seen) VALUES (?,?,?,?,?,?,?) "
            # A roster row never overwrites the party a division recorded:
            # it fills what is missing and moves last_seen.
            "ON CONFLICT(person_id) DO UPDATE SET "
            "name=COALESCE(ca_members.name, excluded.name), "
            "constituency=COALESCE(ca_members.constituency, excluded.constituency), "
            "province=COALESCE(ca_members.province, excluded.province), "
            "party=COALESCE(ca_members.party, excluded.party), "
            "last_seen=excluded.last_seen",
            (pid, name or None, (m.findtext("CaucusShortName") or "").strip() or None,
             (m.findtext("ConstituencyName") or "").strip() or None,
             (m.findtext("ConstituencyProvinceTerritoryName") or "").strip() or None,
             today, today))
        n += 1
    conn.commit()
    return n


def _all_text(el):
    return " ".join("".join(el.itertext()).split())


def sitting_date(root):
    items = {i.get("Name"): (i.text or "").strip() for i in root.iter("ExtractedItem")}
    try:
        return datetime.date(int(items["MetaDateNumYear"]), int(items["MetaDateNumMonth"]),
                             int(items["MetaDateNumDay"])).isoformat()
    except (KeyError, ValueError):
        return None


def subject_bill(sob):
    """The bill a SubjectOfBusiness is about, read from its title and the
    procedural text BEFORE its first intervention -- never from a speech,
    which can cite any bill it likes."""
    parts = [sob.findtext("SubjectOfBusinessTitle") or ""]
    content = sob.find("SubjectOfBusinessContent")
    for child in (list(content) if content is not None else []):
        if child.tag == "Intervention":
            break
        if child.tag in ("ParaText", "ProceduralText"):
            parts.append(_all_text(child))
    hit = BILL.search(" ".join(parts))
    return "{0}-{1}".format(hit.group(1), hit.group(2)) if hit else None


def parse_sitting(xml_text):
    """(date, [intervention dicts]) in document order."""
    root = ET.fromstring(xml_text)
    out = []
    state = {"rubric": None, "subject": None, "bill": None, "time": None}

    def walk(el):
        tag = el.tag
        if tag == "Timestamp":
            if el.get("Hr") is not None:
                state["time"] = "{0:02d}:{1:02d}".format(int(el.get("Hr")), int(el.get("Mn") or 0))
            return
        if tag == "OrderOfBusiness":
            state.update(rubric=(el.findtext("OrderOfBusinessTitle") or "").strip() or None,
                         subject=None, bill=None, title=None)
        elif tag == "SubjectOfBusiness":
            # Only the FIRST subject of a run carries a title: the petitions
            # presented on 24 September 2026 were one "Petitions" title and
            # then a string of subjects with only a qualifier ("Medical
            # Assistance in Dying"). An untitled subject inherits the last
            # title in its rubric, and the qualifier is appended.
            title = (el.findtext("SubjectOfBusinessTitle") or "").strip() or None
            if title:
                state["title"] = title
            qualifier = (el.findtext("SubjectOfBusinessQualifier") or "").strip() or None
            base = title or state.get("title")
            state.update(subject=(" — ".join(x for x in (base, qualifier) if x) or None),
                         bill=subject_bill(el))
        elif tag == "Intervention":
            aff = el.find("PersonSpeaking/Affiliation")
            label = _all_text(aff) if aff is not None else None
            paras = [_all_text(p) for p in el.iter("ParaText")]
            out.append({"id": el.get("id"), "kind": el.get("Type"),
                        "db_id": aff.get("DbId") if aff is not None else None,
                        "label": label, "text": "\n".join(p for p in paras if p),
                        "rubric": state["rubric"], "subject": state["subject"],
                        "bill": state["bill"], "time": state["time"]})
            # Timestamps INSIDE a long speech still move the clock for the next.
            for t in el.iter("Timestamp"):
                if t.get("Hr") is not None:
                    state["time"] = "{0:02d}:{1:02d}".format(int(t.get("Hr")), int(t.get("Mn") or 0))
            return
        for child in el:
            walk(child)

    body = root.find("HansardBody")
    walk(body if body is not None else root)
    return sitting_date(root), out


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def known_roles(conn):
    return {r[0]: r[1] for r in conn.execute("SELECT db_id, person_id FROM ca_speaker_roles")}


def attribute(conn, roster, roles, iv, today):
    """(person_id, party) for one intervention. Learns the DbId when a label
    carrying a riding resolves it."""
    name, riding, party = parse_label(iv["label"])
    db_id = iv["db_id"]
    if db_id and db_id in roles:
        return roles[db_id], party
    pid, how = roster.resolve(name, riding)
    if pid and db_id:
        roles[db_id] = pid
        conn.execute("INSERT OR IGNORE INTO ca_speaker_roles (db_id, person_id, "
                     "label, how, first_seen) VALUES (?,?,?,?,?)",
                     (db_id, pid, iv["label"], how, today))
    return pid, party


def store_sitting(conn, key, parl, sess, number, date, ivs, tax, wl, today, roster=None):
    """Store one sitting's speeches on our ground. Returns the totals row."""
    roster = roster or Roster(conn)
    roles = known_roles(conn)
    by_title = bills_by_title(conn, parl, sess)
    chair = stored = unresolved = chars = 0
    # Learn every DbId in the sitting first: a member's bare second label
    # ("Gabriel Hardy") often precedes nothing, but a minister's bare role
    # label can come BEFORE the riding-bearing one in document order.
    for iv in ivs:
        if not is_chair(iv["label"]):
            attribute(conn, roster, roles, iv, today)
    for iv in ivs:
        chars += len(iv["text"] or "")
        if is_chair(iv["label"]):
            chair += 1
            continue
        matches = filt.match_passages(tax, wl, iv["text"] or "", title=iv["subject"])
        areas, terms, excerpt = filt.aggregate_passages(matches)
        if not on_our_ground(areas):
            continue
        pid, party = attribute(conn, roster, roles, iv, today)
        if not iv["bill"] and iv["subject"]:
            # A resumed debate prints only the short title ("Protecting Young
            # Persons from Exposure to Pornography Act"), never "Bill S-209".
            iv["bill"] = by_title.get(fold(iv["subject"]))
        if pid is None:
            unresolved += 1
        conn.execute(
            "INSERT INTO ca_speeches (speech_id, sitting_key, date, time, rubric, "
            "subject, bill_number, kind, db_id, person_id, speaker, party, text, "
            "areas, matched_terms, excerpt, first_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(speech_id) DO UPDATE SET text=excluded.text, "
            "person_id=COALESCE(excluded.person_id, ca_speeches.person_id), "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, "
            "excerpt=excluded.excerpt",
            (iv["id"], key, date, iv["time"], iv["rubric"], iv["subject"], iv["bill"],
             iv["kind"], iv["db_id"], pid, iv["label"], party, iv["text"],
             json.dumps(areas), json.dumps(terms), excerpt, today))
        stored += 1
    conn.execute(
        "INSERT OR REPLACE INTO ca_sittings (sitting_key, parliament, session, "
        "number, date, interventions, chair, stored, unresolved, chars, read_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (key, parl, sess, number, date, len(ivs), chair, stored, unresolved, chars, today))
    conn.commit()
    return {"interventions": len(ivs), "chair": chair, "stored": stored,
            "unresolved": unresolved}


def bills_by_title(conn, parl, sess):
    """{folded short or long title: bill number} for one session, from
    ca_bills. Empty when tools/ca_rollcalls.py has not run -- then a
    resumed debate simply carries no bill number."""
    out = {}
    for number, short, long_ in conn.execute(
            "SELECT number, short_title, long_title FROM ca_bills "
            "WHERE parliament=? AND session=?", (parl, sess)):
        for t in (short, long_):
            if t:
                out.setdefault(fold(t), number)
    return out


def is_missing(exc):
    return getattr(getattr(exc, "cause", None), "code", None) == 404


def next_sitting(conn, parl, sess):
    row = conn.execute("SELECT MAX(number) FROM ca_sittings WHERE parliament=? "
                       "AND session=?", (parl, sess)).fetchone()
    return (row[0] or 0) + 1


def pull(conn, client, today, session=CURRENT_SESSION, start=None,
         limit=DEFAULT_LIMIT, tax=None, wl=None, log=print, budget=None,
         dry_run=False):
    """Read sittings from `start` (default: the next unread). Returns
    (read, stored, gaps, frontier) where frontier is the first unpublished number."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else filt.load_watchlist(WATCHLIST)
    parl, sess = parse_session(session)
    number = start or next_sitting(conn, parl, sess)
    read = stored = gaps = 0
    roster = Roster(conn)
    frontier = None
    while limit is None or read < limit:
        if budget is not None and budget.exhausted():
            log(budget.disclose("sittings", read))
            break
        key = "{0}-{1}-{2}".format(parl, sess, number)
        try:
            text = client.get_text(SITTING.format(parl, sess, number), FEED,
                                   "sitting-" + key, archive=False)
            date, ivs = parse_sitting(text)
        except FetchError as exc:
            if is_missing(exc):
                frontier = number
                break
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                         (today, FEED, "{0}: {1}".format(key, exc)))
            log("  [gap] sitting {0}: {1}".format(key, str(exc)[:70]))
            gaps += 1
            break   # sittings are read in order; never skip one and move on
        except ET.ParseError as exc:
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                         (today, FEED, "{0}: unparseable ({1})".format(key, exc)))
            log("  [gap] sitting {0} did not parse: {1}".format(key, exc))
            gaps += 1
            break
        if dry_run:
            log("  {0} {1}: {2} interventions".format(key, date, len(ivs)))
        else:
            t = store_sitting(conn, key, parl, sess, number, date, ivs, tax, wl, today, roster)
            stored += t["stored"]
            log("  {0} {1}: {2} interventions, {3} chair, {4} on our ground{5}".format(
                key, date, t["interventions"], t["chair"], t["stored"],
                ", {0} unattributed".format(t["unresolved"]) if t["unresolved"] else ""))
        read += 1
        number += 1
    return read, stored, gaps, frontier


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=CURRENT_SESSION)
    ap.add_argument("--from", dest="start", type=int, help="first sitting number to read")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="sittings per run")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--budget-seconds", type=float, default=drain.DEFAULT_S)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    parl, sess = parse_session(args.session)
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    today = datetime.date.today().isoformat()
    if args.dry_run:
        conn = ca_store.ensure_schema(db.init_db(db.connect(":memory:")))
    else:
        conn = ca_store.ensure_schema(db.init_db(db.connect(args.db)))
    members = load_roster(conn, client, parl, today)
    print("ca-hansard: {0}, roster of {1} member(s)".format(args.session, members))
    read, stored, gaps, frontier = pull(
        conn, client, today, session=args.session, start=args.start, limit=args.limit,
        budget=drain.Budget(args.budget_seconds), dry_run=args.dry_run)
    print("ca-hansard: {0} sitting(s) read, {1} speech(es) on our ground, {2} gap(s){3}.".format(
        read, stored, gaps,
        "; sitting {0} is not published yet".format(frontier) if frontier else ""))
    if not args.dry_run:
        n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        print("  store: {0} sitting(s) read, {1} speech(es), {2} unattributed, "
              "{3} speaker role(s) learned".format(
                  n("SELECT COUNT(*) FROM ca_sittings"), n("SELECT COUNT(*) FROM ca_speeches"),
                  n("SELECT COUNT(*) FROM ca_speeches WHERE person_id IS NULL"),
                  n("SELECT COUNT(*) FROM ca_speaker_roles")))
    conn.close()
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
