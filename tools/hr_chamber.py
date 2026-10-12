#!/usr/bin/env python3
"""Croatia: what was said in the Hrvatski sabor, speech by speech.

    python3 tools/hr_chamber.py                      # the last three weeks
    python3 tools/hr_chamber.py --since 2026-09-01 --budget-seconds 600
    python3 tools/hr_chamber.py --dry-run
    python3 tools/hr_chamber.py --reclassify

Remaining speech coverage (11 October 2026, branch gaps-speeches), on the
shared chamber layer (src/chamber_store.py). The source is the one the
profiles' party history already reads (tools/hr_party_history.py, X6): the
Sabor's e-Doc transcripts, edoc.sabor.hr/Views/FonogramView.aspx?tdrid=<id>,
keyless; robots.txt on edoc.sabor.hr is absent (404, measured 10 and 11
October 2026) and www.sabor.hr's disallows none of it.

THE SOURCE, measured 11 October 2026. One transcript per agenda item (or
per joint debate of several items, "20; 21"): the item's title, then the
day's date ("24.09.2026."), then each contribution headed "Surname, Name
(PARTY)" (a state secretary or guest has no party: "Nekić, Darko"),
followed by its paragraphs. The House's and the chair's interruptions are
printed inline as "…/Upadica predsjednik: Hvala kolega …/…" and are cut
before matching: they are someone else's words. A page is about 1.1 MB
(mostly page furniture) and answers in about a second. The newest transcript
on 11 October 2026 was of 29 September: the record follows the sitting by
days, so Croatia is not a same-day source (no live read).

THE CHAIR. The transcript does not label the presiding officer, who opens,
calls each speaker and rules on points of order. The chair is told by the
shape of the record: the presiding officer's turns alternate with everyone
else's (X, chair, Y, chair, Z), so a turn whose speaker also holds the turn
two places before or after it, around someone else's, is the chair's when
that speaker does so in at least half their turns, around at least two
different people who are not themselves chairs (a member answering back and
forth around the chair holds turns around the chair only), or, where only
two people speak, when theirs are the short turns (chair_turns). A vice-president who later speaks from the floor between
other chairs' turns is kept: that turn is not sandwiched.

WHICH TRANSCRIPTS. Ids are one sequence across e-Doc, numbered when an item
is put on the agenda, not when it is debated. Each run reads ids from just
above the newest known (the list page's frontier, or the newest
hr_transcripts row) down SPAN ids, skipping a transcript already read whose
last day is a week old, and one tools/hr_party_history.py has read with a
last day before --since. A transcript whose last day is under a week old is
read again (a debate can continue). Each page read is also handed to the
party history's own store (hr_transcripts, hr_party_seen), so the profiles'
walk never fetches it twice; this step runs before it in the weekly.

ROLES. A speaker matched to exactly one hr_members name of the 11th Sabor is
a member, with that slug as person_id; a member whose mandate is on hold
('U mirovanju': a minister, as a rule) is 'Government (mandate on hold)', and
a speaker with no party heading is 'Government or guest'.
"""

from __future__ import annotations

import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import chamber_store as cs  # noqa: E402
from src.http import FetchError  # noqa: E402
import hr_party_history as hph  # noqa: E402

CC = "hr"
FEED = hph.FEED                     # the same feed and slugs: one raw archive
HOST = hph.HOST
SPAN = 150                          # ids read below the newest, each run
LOOKAHEAD = 10
SETTLED_DAYS = 7                    # a transcript whose last day is older is not re-read

_HEAD = re.compile(r"^(?P<name>[A-ZČĆŽŠĐ][\w'’.-]+(?:[ -][A-ZČĆŽŠĐ][\w'’.-]+)*,"
                   r"\s*[A-ZČĆŽŠĐ][\w'’.-]+(?:\s+[A-ZČĆŽŠĐ][\w'’.-]+){0,2})"
                   r"(?:\s*\((?P<party>[^()\n<>]{1,40})\))?$")
_UPADICA = re.compile(r"…?\s*/\s*Upadica\b[^/]*/\s*…?")
_ITEMS = re.compile(r"^\d+(?:\s*;\s*\d+)*$")


def turns_of(page):
    """{'saziv', 'session_no', 'titles', 'turns': [{'speaker', 'party', 'date',
    'text'}]} from one transcript page, or None when it holds no transcript."""
    m = hph._SAZIV.search(page or "")
    if not m:
        return None
    lines = hph.lines_of(page)
    titles, turns, day, cur, started = [], [], None, None, False
    head = "Svi govornici" in lines
    after = not head
    for ln in lines:
        d = hph._DAY.match(ln)
        if d:
            try:
                day = datetime.date(int(d.group(3)), int(d.group(2)),
                                    int(d.group(1))).isoformat()
            except ValueError:
                pass
            started = True
            continue
        if not started:
            # The item's title follows the "Svi govornici" link (and the item
            # numbers of a joint debate, "20; 21"): "Aktualno prijepodne" is
            # question time.
            if ln == "Svi govornici":
                after = True
            elif after and ln not in ("-", "PDF") and not _ITEMS.match(ln) and (
                    head or (len(ln) > 25 and not ln.startswith(("Saziv", "Rasprave",
                                                                  "Povratak", ".")))):
                titles.append(ln)
            continue
        if ln in ("PDF", "Učitavanje"):
            continue
        h = _HEAD.match(ln)
        if h and len(ln) <= 90:
            cur = {"speaker": " ".join(h.group("name").split()),
                   "party": (h.group("party") or "").strip() or None, "date": day,
                   "lines": []}
            turns.append(cur)
            continue
        if cur is None:
            continue
        text = _UPADICA.sub(" ", ln).strip(" …")
        if text:
            cur["lines"].append(text)
    for t in turns:
        t["text"] = "\n".join(t.pop("lines"))
    return {"saziv": m.group(1), "session_no": m.group(2), "titles": titles, "turns": turns}


def chair_turns(turns):
    """Indexes of the presiding officer's turns (module docstring, THE CHAIR)."""
    names = [t["speaker"] for t in turns]
    sandwich, around = set(), {}
    for i, who in enumerate(names):
        for j in (i - 2, i + 2):
            mid = (i + j) // 2
            if 0 <= j < len(names) and names[j] == who and names[mid] != who:
                sandwich.add(i)
                around.setdefault(who, set()).add(names[mid])
    count, held, size = {}, {}, {}
    for i, who in enumerate(names):
        count[who] = count.get(who, 0) + 1
        size[who] = size.get(who, 0) + len(turns[i]["text"])
        if i in sandwich:
            held[who] = held.get(who, 0) + 1
    able = [w for w, n in held.items() if n >= 2 and n * 2 >= count[w]]
    # A member answering back and forth (A, chair, A, chair, A) also holds
    # turns around someone: the chair holds them around SEVERAL people. A
    # member who answers two chairs in turn holds turns around two people,
    # both of them chairs, so the chairs (who hold the most) come first.
    # Peeled in order of turns held: the chairs found so far are discounted.
    chairs = set()
    for w in sorted(able, key=lambda x: (-held[x], x)):
        if len(around.get(w, set()) - chairs) >= 2:
            chairs.add(w)
    if not chairs and able:
        # Two speakers only: the chair is the one whose turns are short.
        w = min(able, key=lambda x: size[x] / count[x])
        if size[w] / count[w] < 400:
            chairs = {w}
    return {i for i in sandwich if names[i] in chairs}


def roster(conn):
    """{folded 'Surname, Name': (slug, mandate)} of the 11th Sabor; a shared
    name maps to None."""
    out = {}
    try:
        rows = conn.execute("SELECT slug, name, mandate FROM hr_members WHERE saziv = ?",
                            (hph.SAZIV_NO,)).fetchall()
    except Exception:                               # noqa: BLE001
        return {}
    for slug, name, mandate in rows:
        k = hph.fold(name)
        out[k] = None if k in out else (slug, mandate)
    return out


def role_of(turn, member):
    if member and (member[1] or "").startswith("U mirovanju"):
        return "Government (mandate on hold)"
    if not turn["party"]:
        return "Government or guest"
    return "member"


def candidates(run, newest):
    """[(tdrid, why)] to read this run, newest first."""
    known = {r[0]: (r[1], r[2]) for r in run.conn.execute(
        "SELECT tdrid, saziv, last_date FROM hr_transcripts WHERE tdrid >= ?",
        (hph.START,)).fetchall()}
    found = [t for t, (s, _d) in known.items() if s]
    top = max([hph.START] + found + ([newest] if newest else []))
    settled = (datetime.date.fromisoformat(run.today)
               - datetime.timedelta(days=SETTLED_DAYS)).isoformat()
    out = []
    for t in range(top + LOOKAHEAD, max(hph.START, top - SPAN) - 1, -1):
        saziv, last = known.get(t, (None, None))
        ver, status = cs.read_state(run.conn, CC, "tdrid-{0}".format(t))
        if saziv and last and last < run.since:
            if status and not run.dry_run:
                cs.seen(run.conn, CC, "tdrid-{0}".format(t), run.today)
            continue
        if status == "read" and ver and ver.split("|")[0] < settled:
            if not run.dry_run:
                cs.seen(run.conn, CC, "tdrid-{0}".format(t), run.today)
            continue
        if t in known and not saziv and t < top - 40:
            continue                                # an item never debated; the walk rechecks it
        out.append(t)
    return out


def speeches(run):
    run.client.enable_gzip(HOST)
    members = roster(run.conn)
    party_roster = hph.members(run.conn) if members else {}
    try:
        newest = hph.frontier(run.client.get_text(hph.LIST, FEED, "fonogrami"))
    except FetchError as exc:
        if getattr(exc, "host_skipped", False):
            # robots.txt unreachable (src/robots_guard): one gap, no walk.
            run.gap("edoc.sabor.hr not read: {0}".format(exc))
            return
        run.log("  [hr-chamber] transcript list unreadable ({0}); walking from the newest id "
                "read".format(str(exc)[:80]))
        newest = None
    todo = candidates(run, newest)
    run.log("  [fonogrami] {0} transcript id(s) to read (newest {1})".format(len(todo), newest))
    fetched = 0
    for tdrid in todo:
        if run.out_of_time("transcripts", fetched):
            return
        try:
            page = run.client.get_text(hph.VIEW.format(tdrid), FEED, "fonogram-{0}".format(tdrid))
        except FetchError as exc:
            if cs.not_found(exc):
                continue
            run.gap("transcript {0} unreadable: {1}".format(tdrid, str(exc)[:100]))
            if getattr(exc, "host_skipped", False):
                return
            continue
        fetched += 1
        if not run.dry_run and party_roster:
            hph.store(run.conn, tdrid, hph.parse(page), party_roster, run.today)
        got = turns_of(page)
        if got is None or got["saziv"] != hph.SAZIV or not got["turns"]:
            continue
        process(run, tdrid, got, members)


def process(run, tdrid, got, members):
    """Classify and store one transcript's speeches; mark it read."""
    turns = got["turns"]
    days = sorted({t["date"] for t in turns if t["date"]})
    debate = " / ".join(got["titles"]) or "(agenda item {0})".format(tdrid)
    title = cs.classify_title(run.taxes, debate)
    chair = chair_turns(turns)
    url = hph.VIEW.format(tdrid)
    doc_id = "tdrid-{0}".format(tdrid)
    keep, matched, chars = [], 0, 0
    for i, t in enumerate(turns):
        if i in chair:
            continue
        chars += len(t["text"])
        m = cs.classify_speech(run.taxes, t["text"], title)
        if not m:
            continue
        member = members.get(hph.fold(t["speaker"]))
        # Keyed on the words, not the page: a joint debate is printed whole
        # under each of its items' ids (2017599 to 2017602, measured), and
        # must be stored once.
        sid = "{0}#{1}".format(t["date"], cs.short_id(t["speaker"], t["text"][:400]))
        keep.append(sid)
        matched += 1
        run.speech({"speech_id": sid, "doc_id": doc_id, "date": t["date"], "chamber": None,
                    "debate_id": cs.short_id(debate), "debate": debate, "speaker": t["speaker"],
                    "party": t["party"], "role": role_of(t, member),
                    "person_id": member[0] if member else None, "text": t["text"],
                    "url": url, "title_areas": title.areas}, m)
    if not run.dry_run:
        cs.forget_speeches(run.conn, CC, doc_id, keep)
    run.read(doc_id, "speeches", days[-1] if days else None,
             "{0}|{1}".format(days[-1] if days else "", len(turns)), len(turns) - len(chair),
             matched, chars)
    run.log("  [fonogram] {0} ({1}): {2} speech(es), {3} chair turn(s) left out, {4} on our "
            "ground".format(tdrid, days[-1] if days else "?", len(turns) - len(chair), len(chair),
                            matched))


if __name__ == "__main__":
    sys.exit(cs.main(CC, {"speeches": speeches}, doc=__doc__))
