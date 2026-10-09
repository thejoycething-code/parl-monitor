#!/usr/bin/env python3
"""Austria's Parliament: members, Verhandlungsgegenstände and Klub votes of
the Nationalrat and the Bundesrat.

    python3 tools/at_rollcalls.py                     # the current (XXVIII.) Gesetzgebungsperiode
    python3 tools/at_rollcalls.py --dry-run           # read both lists, store nothing
    python3 tools/at_rollcalls.py --reclassify        # re-derive areas, offline
    python3 tools/at_rollcalls.py --db /tmp/at.db     # anywhere but the store

PHASE 1 (9 October 2026). See docs/austria-scope.md. No edition reads these
tables yet. Every source is the Parliament's own Open Data offer (CC BY 4.0,
keyless), all on www.parlament.gv.at:

  * POST /Filter/api/filter/data/101 -- the Gegenstände filter. ONE request
    returns every item of a Gesetzgebungsperiode for one chamber (24,735
    Nationalrat rows in XXVIII, 15 s; 1,319 Bundesrat rows), each with its
    title, type, status, Klubs, Schlagworte, and for laws the third-reading
    vote by Klub.
  * GET /gegenstand/<gp>/<ityp>/<inr>?json=TRUE -- an item's history page.
    Every vote taken on the item, in committee and in either plenary, is a
    stage: "Unselbständiger Entschließungsantrag abgelehnt<br>Dafür: FPÖ,
    dagegen: ÖVP, SPÖ, NEOS, GRÜNE". Read only for items on our ground (and
    on the watchlist), and only when the list says the item moved.
  * POST /Filter/api/json/post?...WFW_002 / WFW_005 -- the sitting members
    of the Nationalrat (183) and the Bundesrat (60), with PAD and Klub.

KLUB VOTES, NOT MEMBER VOTES. Austria records who voted how by Klub; only a
namentliche Abstimmung names members (5 in the Nationalrat in XXVIII), and
those names are in the Stenographisches Protokoll, by surname. Phase 1b.

CLASSIFICATION is config/taxonomy-de.yaml, unchanged, on the item's title,
plus config/watchlist-at.yaml by item key. The Schlagworte are stored but not
matched: the Parliament's own tag "Familienpolitik" is a tier-1 term in
taxonomy-de and would put 49 items in area 9 where titles put 3 (measured).

ROBOTS. www.parlament.gv.at disallows a few hundred history pages by path
(privacy takedowns). They are skipped and logged, never fetched.

Separation guarantee: writes at_* tables and the shared gaps table only.
ONE WRITER AT A TIME on the store.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.robotparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import at_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402

FEED = "at-rollcalls"
TAXONOMY = os.path.join(ROOT, "config", "taxonomy-de.yaml")
HOST = "www.parlament.gv.at"
BASE = "https://" + HOST
ITEMS = BASE + "/Filter/api/filter/data/101?js=eval&showAll=true"
MEMBERS = {
    "NR": BASE + "/Filter/api/json/post?jsMode=EVAL&FBEZ=WFW_002&listeId=10002&showAll=true",
    "BR": BASE + "/Filter/api/json/post?jsMode=EVAL&FBEZ=WFW_005&listeId=10005&showAll=true",
}
# Both member filters return nothing for an empty body or {"FR": ["ALLE"]};
# asking for both sexes returns everyone (measured 9 October 2026).
MEMBERS_BODY = {"M": ["M"], "W": ["W"]}
DETAIL = BASE + "{0}?json=TRUE"
ROBOTS = BASE + "/robots.txt"
CURRENT_GP = "XXVIII"   # from 24 October 2024
CHAMBERS = ("NR", "BR")
# EU documents (EUSV, EUBM, EUPA under ityp EUBTG): 6,680 of the 24,735
# Nationalrat rows in XXVIII. The EU edition covers the EU's own record.
SKIP_ITYP = frozenset({"EUBTG"})
# Questions and answers are never voted on: no history page is read for them.
NO_VOTE_ARTS = frozenset({"J", "JPR", "AB", "ABPR", "J-BR", "AB-BR", "JPR-BR", "ABPR-BR"})
THROTTLE_S = 1.0
BUDGET_S = drain.DEFAULT_S
GAPS_EXIT = 3          # stored what it could, recorded gaps: jobs/at-weekly.sh publishes
HIDDEN_AREAS = (11,)   # migration is collated, never campaigned (src/partner.py)
TEXT_CHARS = 1200
QUESTION_CHARS = 300
# The labels the list header must carry; a renamed column is a gap, not a guess.
REQUIRED = ("GP_CODE", "ITYP", "INR", "Datum", "Art", "Betreff", "Nummer", "Status",
            "DOKTYP_LANG", "HIS_URL", "DATUM_VON", "Personen", "Fraktionen", "THEMEN",
            "SW", "EUROVOC", "Abstimmungstext", "Abstimmungskommentar")


def _gap(conn, today, detail):
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))


def on_our_ground(areas):
    return any(a not in HIDDEN_AREAS for a in (areas or []))


def strip_tags(text):
    """Tags out, <br> as a line break, entities decoded, spaces squashed."""
    text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[ \t\r\f\v\u00a0]+", " ", text)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


def iso_date(text):
    """'15.10.2025' or '2025-10-15T00:00:00' -> '2025-10-15'; else None."""
    text = (text or "").strip()
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})", text)
    if m:
        return "{2}-{1}-{0}".format(*m.groups())
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else None


def json_list(text):
    """The list packs its lists as JSON strings: '["32508"]'. Empty strings out."""
    if isinstance(text, list):
        values = text
    else:
        try:
            values = json.loads(text or "[]")
        except ValueError:
            return []
    return [v for v in (values or []) if v not in (None, "")]


def item_key(his_url):
    """'/gegenstand/XXVIII/I/525' -> 'XXVIII/I/525'; anything else None."""
    m = re.match(r"^/gegenstand/([^/?#]+/[^/?#]+/[^/?#]+)$", his_url or "")
    return m.group(1) if m else None


# --- the item lists -----------------------------------------------------------

def header_index(reply):
    labels = [h.get("label") for h in (reply or {}).get("header") or []]
    index = {}
    for i, label in enumerate(labels):
        index.setdefault(label, i)
    missing = [r for r in REQUIRED if r not in index]
    return index, missing


def parse_items(reply):
    """The filter reply -> (items, missing labels). EU documents dropped."""
    ix, missing = header_index(reply)
    if missing:
        return [], missing
    out = []
    for row in (reply or {}).get("rows") or []:
        get = lambda label: row[ix[label]] if ix[label] < len(row) else None  # noqa: E731
        if get("ITYP") in SKIP_ITYP:
            continue
        key = item_key(get("HIS_URL"))
        if not key:
            continue
        try:
            inr = int(get("INR"))
        except (TypeError, ValueError):
            inr = None
        try:
            status = int(get("Status"))
        except (TypeError, ValueError):
            status = None
        out.append({
            "item_key": key,
            "gp": get("GP_CODE"),
            "chamber": "BR" if key.startswith("BR/") else "NR",
            "ityp": get("ITYP"),
            "inr": inr,
            "art": get("Art"),
            "art_long": get("DOKTYP_LANG"),
            "title": (get("Betreff") or "").strip() or None,
            "citation": get("Nummer"),
            "status": status,
            "last_date": iso_date(get("Datum")),
            "introduced": iso_date(get("DATUM_VON")),
            "persons": json_list(get("Personen")),
            "klubs": json_list(get("Fraktionen")),
            "topics": json_list(get("THEMEN")),
            "headwords": json_list(get("SW")),
            "eurovoc": json_list(get("EUROVOC")),
            "vote_text": get("Abstimmungstext") or None,
            "vote_comment": (get("Abstimmungskommentar") or "").strip() or None,
        })
    return out, []


def classify_item(tax, wl, key, title, wl_path=None):
    res = filt.filter_item(tax, wl, title or "", title=title or "")
    return at_store.add_watch_areas(res, key, wl_path)


def empty_watchlist():
    """The AT watchlist is applied by item key (at_store.add_watch_areas), so
    the filter itself gets no title entities."""
    return filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def store_items(conn, items, tax, wl, today, wl_path=None):
    """Upsert every item; returns the number on our ground."""
    ours = 0
    d = at_store.dumps
    for it in items:
        res = classify_item(tax, wl, it["item_key"], it["title"], wl_path)
        ours += on_our_ground(res.issue_areas)
        conn.execute(
            "INSERT INTO at_items (item_key, gp, chamber, ityp, inr, art, art_long, title, "
            "citation, status, last_date, introduced, persons, klubs, topics, headwords, "
            "eurovoc, vote_text, vote_comment, areas, matched_terms, tier, first_seen, "
            "last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(item_key) DO UPDATE SET gp=excluded.gp, chamber=excluded.chamber, "
            "ityp=excluded.ityp, inr=excluded.inr, art=excluded.art, "
            "art_long=excluded.art_long, title=COALESCE(excluded.title, at_items.title), "
            "citation=excluded.citation, status=excluded.status, "
            "last_date=excluded.last_date, introduced=excluded.introduced, "
            "persons=excluded.persons, klubs=excluded.klubs, topics=excluded.topics, "
            "headwords=excluded.headwords, eurovoc=excluded.eurovoc, "
            "vote_text=COALESCE(excluded.vote_text, at_items.vote_text), "
            "vote_comment=COALESCE(excluded.vote_comment, at_items.vote_comment), "
            "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
            "last_seen=excluded.last_seen",
            (it["item_key"], it["gp"], it["chamber"], it["ityp"], it["inr"], it["art"],
             it["art_long"], it["title"], it["citation"], it["status"], it["last_date"],
             it["introduced"], d(it["persons"]), d(it["klubs"]), d(it["topics"]),
             d(it["headwords"]), d(it["eurovoc"]), it["vote_text"], it["vote_comment"],
             d(res.issue_areas), d((res.matched_terms or []) + (res.watchlist_hits or [])),
             res.tier, today, today))
    return ours


def pull_items(conn, client, today, gp=CURRENT_GP, tax=None, wl=None, log=print, wl_path=None):
    """Both chambers' lists. Returns (items stored, on our ground, gaps)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = wl if wl is not None else empty_watchlist()
    stored = ours = gaps = 0
    for chamber in CHAMBERS:
        body = json.dumps({"NRBR": [chamber], "GP_CODE": [gp]})
        try:
            reply = client.post_json(ITEMS, body, FEED, "items-{0}-{1}".format(chamber, gp),
                                     timeout=180)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "items {0} {1}: {2}".format(chamber, gp, exc))
            log("  [gap] items {0} {1}: {2}".format(chamber, gp, str(exc)[:80]))
            gaps += 1
            continue
        items, missing = parse_items(reply)
        if missing:
            _gap(conn, today, "items {0} {1}: header lacks {2}".format(chamber, gp, missing))
            log("  [gap] items {0} {1}: the list header lacks {2}".format(chamber, gp, missing))
            gaps += 1
            continue
        if not items:
            _gap(conn, today, "items {0} {1}: the list came back empty".format(chamber, gp))
            log("  [gap] items {0} {1}: the list came back empty".format(chamber, gp))
            gaps += 1
            continue
        n_ours = store_items(conn, items, tax, wl, today, wl_path)
        conn.commit()
        stored += len(items)
        ours += n_ours
        log("at-rollcalls: {0} {1}: {2} item(s) listed ({3} reported), {4} on our ground".format(
            chamber, gp, len(items), (reply or {}).get("count"), n_ours))
    return stored, ours, gaps


# --- members ------------------------------------------------------------------

def parse_members(reply, chamber):
    ix = {}
    for i, h in enumerate((reply or {}).get("header") or []):
        ix.setdefault(h.get("label"), i)
    klub_label = "Klub" if "Klub" in ix else "Fraktion"
    out = []
    for row in (reply or {}).get("rows") or []:
        get = lambda label: row[ix[label]] if label in ix and ix[label] < len(row) else None  # noqa: E731
        m = re.search(r"/person/(\d+)", get("link") or "")
        if not m:
            continue
        out.append({"pad": m.group(1), "name": strip_tags(get("Name")) or None,
                    "chamber": chamber, "klub": strip_tags(get(klub_label)) or None,
                    "wahlkreis": strip_tags(get("Wahlkreis")) or None,
                    "bundesland": strip_tags(get("Bundesland")) or None})
    return out


def pull_members(conn, client, today, log=print):
    """Returns (members stored, gaps)."""
    n = gaps = 0
    for chamber, url in MEMBERS.items():
        try:
            reply = client.post_json(url, json.dumps(MEMBERS_BODY), FEED, "members-" + chamber)
        except (FetchError, ValueError) as exc:
            _gap(conn, today, "members {0}: {1}".format(chamber, exc))
            log("  [gap] members {0}: {1}".format(chamber, str(exc)[:80]))
            gaps += 1
            continue
        members = parse_members(reply, chamber)
        if not members:
            _gap(conn, today, "members {0}: none listed".format(chamber))
            log("  [gap] members {0}: none listed".format(chamber))
            gaps += 1
            continue
        for m in members:
            conn.execute(
                "INSERT INTO at_members (pad, name, chamber, klub, wahlkreis, bundesland, "
                "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(pad) DO UPDATE SET "
                "name=excluded.name, chamber=excluded.chamber, klub=excluded.klub, "
                "wahlkreis=excluded.wahlkreis, bundesland=excluded.bundesland, "
                "last_seen=excluded.last_seen",
                (m["pad"], m["name"], m["chamber"], m["klub"], m["wahlkreis"], m["bundesland"],
                 today, today))
        conn.commit()
        n += len(members)
        log("at-rollcalls: {0} sitting member(s) of the {1}".format(len(members), chamber))
    return n, gaps


# --- history pages: the votes -------------------------------------------------

OUTCOME = re.compile(r"\b(angenommen|abgelehnt)\b")
POSITIONS = re.compile(r"Dafür:\s*([^\n]*?)\s*,\s*dagegen:\s*([^\n]*)", re.I)
ROLL_CALL = re.compile(r"Namentliche Abstimmung", re.I)
YES = re.compile(r"Ja-Stimmen:\s*(\d+)|(\d+)\s*Ja-Stimmen")
NO = re.compile(r"Nein-Stimmen:\s*(\d+)|(\d+)\s*Nein-Stimmen")
PLENARY_NR = re.compile(r"^\d+\.\s*Sitzung des Nationalrates\s*:?\s*")
PLENARY_BR = re.compile(r"^\d+\.\s*Sitzung\s*:?\s*")


def page_stages(content):
    """Every stage of a history page, in order. Two shapes are served: items
    with a procedure carry content.phase[].stages; an unselbständiger
    Entschließungsantrag carries content.stages directly (measured)."""
    stages = list((content or {}).get("stages") or [])
    for phase in (content or {}).get("phase") or []:
        stages.extend(phase.get("stages") or [])
    return stages


def klub_list(text):
    text = (text or "").strip().strip(".")
    if not text or text == "-":
        return []
    return [k.strip() for k in text.split(",") if k.strip() and k.strip() != "-"]


def parse_vote(stage, chamber):
    """A stage -> a vote dict, or None when the stage is not a recorded vote.
    A vote is an outcome word plus Klub positions, Einstimmig, or a
    namentliche Abstimmung; "Antrag auf Einholung einer Stellungnahme ...
    angenommen", with no Klubs named, is procedure and is left out."""
    text = strip_tags(stage.get("text"))
    flat = " ".join(text.split("\n"))
    outcome = OUTCOME.search(flat)
    if not outcome:
        return None
    pos = POSITIONS.search(text)
    unanimous = bool(re.search(r"\beinstimmig\b", flat, re.I))
    roll_call = bool(ROLL_CALL.search(flat))
    if not (pos or unanimous or roll_call):
        return None
    fsth = stage.get("fsth") or []
    sitting = rn = url = None
    body = None
    if fsth:
        pick = next((f for f in fsth if "Abstimmung" in (f.get("title") or "")), fsth[0])
        url = pick.get("url")
        gp = pick.get("gp_code")
        sid = pick.get("sitzung_id")
        if gp and sid is not None:
            sitting = "{0}/{1}/{2}".format(gp, "BRSITZ" if gp == "BR" else "NRSITZ", sid)
            body = "BR" if gp == "BR" else "NR"
        if url and "#" in url:
            rn = url.split("#", 1)[1]
    head = flat
    if PLENARY_NR.match(head):
        body = body or "NR"
        head = PLENARY_NR.sub("", head, count=1)
    elif PLENARY_BR.match(head):
        body = body or "BR"
        head = PLENARY_BR.sub("", head, count=1)
    elif ":" in head.split(outcome.group(1))[0]:
        committee, head = head.split(":", 1)
        body = body or committee.strip()
    body = body or chamber
    question = head.split(outcome.group(1))[0].strip(" :,")
    question = re.sub(r"^Abstimmung:\s*", "", question).strip(" :,") or None
    yes = YES.search(flat)
    no = NO.search(flat)
    return {
        "date": iso_date(stage.get("date")),
        "body": body,
        "sitting": sitting,
        "rn": rn,
        "question": (question or "")[:QUESTION_CHARS] or None,
        "outcome": outcome.group(1),
        "unanimous": int(unanimous),
        "roll_call": int(roll_call),
        "yes_count": int(next(g for g in yes.groups() if g)) if yes else None,
        "no_count": int(next(g for g in no.groups() if g)) if no else None,
        "for": klub_list(pos.group(1)) if pos else [],
        "against": klub_list(pos.group(2)) if pos else [],
        "text": flat[:TEXT_CHARS],
        "protocol_url": url,
    }


def division_keys(key, votes):
    """Stable keys. A plenary vote has its anchor in the Stenographisches
    Protokoll (RN/121.2), which never moves: '<item>@<sitting>#<rn>'. A
    committee vote has none, so it is keyed by body, date and its order that
    day: '<item>@<body>/<date>#<n>'."""
    keys, seen, nth = [], set(), {}
    for v in votes:
        if v["sitting"] and v["rn"]:
            k = "{0}@{1}#{2}".format(key, v["sitting"], v["rn"])
        else:
            slot = (v["body"], v["date"])
            nth[slot] = nth.get(slot, 0) + 1
            k = "{0}@{1}/{2}#{3}".format(key, v["body"], v["date"], nth[slot])
        base, n = k, 1
        while k in seen:
            n += 1
            k = "{0}+{1}".format(base, n)
        seen.add(k)
        keys.append(k)
    return keys


def store_page(conn, key, chamber, page, areas, today):
    """Store a history page's votes and long title. Returns divisions stored."""
    content = (page or {}).get("content")
    if not isinstance(content, dict):
        raise ValueError("no content object")
    description = strip_tags(content.get("description")) or None
    if description:
        conn.execute("UPDATE at_items SET description=? WHERE item_key=?", (description, key))
    votes = [v for v in (parse_vote(s, chamber) for s in page_stages(content)) if v]
    for k, v in zip(division_keys(key, votes), votes):
        conn.execute(
            "INSERT INTO at_divisions (division_key, item_key, date, body, sitting, question, "
            "outcome, unanimous, roll_call, yes_count, no_count, text, protocol_url, areas, "
            "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(division_key) DO UPDATE SET date=excluded.date, body=excluded.body, "
            "sitting=excluded.sitting, question=excluded.question, outcome=excluded.outcome, "
            "unanimous=excluded.unanimous, roll_call=excluded.roll_call, "
            "yes_count=excluded.yes_count, no_count=excluded.no_count, text=excluded.text, "
            "protocol_url=excluded.protocol_url, areas=excluded.areas, "
            "last_seen=excluded.last_seen",
            (k, key, v["date"], v["body"], v["sitting"], v["question"], v["outcome"],
             v["unanimous"], v["roll_call"], v["yes_count"], v["no_count"], v["text"],
             v["protocol_url"], areas, today, today))
        conn.execute("DELETE FROM at_votes WHERE division_key=?", (k,))
        for klub in v["for"]:
            conn.execute("INSERT OR REPLACE INTO at_votes (division_key, klub, position) "
                         "VALUES (?,?,?)", (k, klub, "Dafür"))
        for klub in v["against"]:
            conn.execute("INSERT OR REPLACE INTO at_votes (division_key, klub, position) "
                         "VALUES (?,?,?)", (k, klub, "Dagegen"))
    return len(votes)


def load_robots(client, log=print):
    """A RobotFileParser for the host, or None when robots.txt cannot be read
    (then nothing is skipped, and the run says so)."""
    try:
        text = client.get_text(ROBOTS, FEED, "robots", archive=False)
    except FetchError as exc:
        log("  robots.txt unreadable ({0}); no path skipped".format(str(exc)[:60]))
        return None
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    return rp


def due_for_detail(conn):
    """Items on our ground (or watched) that can carry a vote and whose list
    date moved since their history page was last read."""
    rows = conn.execute(
        "SELECT item_key, chamber, art, areas, matched_terms FROM at_items "
        "WHERE COALESCE(detail_date, '') != COALESCE(last_date, '') "
        "ORDER BY last_date DESC").fetchall()
    out = []
    for key, chamber, art, areas, terms in rows:
        if art in NO_VOTE_ARTS:
            continue
        watched = any(str(t).startswith("watch:") for t in json.loads(terms or "[]"))
        if on_our_ground(json.loads(areas or "[]")) or watched:
            out.append((key, chamber, areas))
    return out


def pull_details(conn, client, today, robots=None, log=print, limit=None, budget=None):
    """Read the history pages that are due. Returns (pages, divisions, skipped, gaps)."""
    pages = divisions = skipped = gaps = 0
    for key, chamber, areas in due_for_detail(conn):
        if limit is not None and pages >= limit:
            log("  fetch cap ({0}) reached; the rest lands on the next run "
                "-- disclosed, not silent".format(limit))
            break
        if budget is not None and budget.exhausted():
            log(budget.disclose("history pages", pages))
            break
        path = "/gegenstand/" + key
        url = DETAIL.format(path)
        if robots is not None and not robots.can_fetch(client.user_agent, BASE + path):
            log("  robots.txt disallows {0}; skipped".format(path))
            skipped += 1
            continue
        try:
            page = client.get_json(url, FEED, "detail-" + key)
            n = store_page(conn, key, chamber, page, areas, today)
        except (FetchError, ValueError, TypeError, AttributeError) as exc:
            _gap(conn, today, "{0}: {1}".format(key, exc))
            log("  [gap] {0}: {1}".format(key, str(exc)[:80]))
            gaps += 1
            continue
        conn.execute("UPDATE at_items SET detail_date=last_date WHERE item_key=?", (key,))
        conn.commit()
        pages += 1
        divisions += n
    return pages, divisions, skipped, gaps


# --- offline -------------------------------------------------------------------

def reclassify(conn, tax=None, log=print, wl_path=None):
    """Re-derive item areas, then the divisions' (which carry their item's)."""
    tax = tax if tax is not None else filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    changed = 0
    for key, title, areas in conn.execute(
            "SELECT item_key, title, areas FROM at_items").fetchall():
        res = classify_item(tax, wl, key, title, wl_path)
        new = at_store.dumps(res.issue_areas)
        if new != (areas or "[]"):
            changed += 1
            conn.execute("UPDATE at_items SET areas=?, matched_terms=?, tier=? WHERE item_key=?",
                         (new, at_store.dumps((res.matched_terms or []) + (res.watchlist_hits or [])),
                          res.tier, key))
    conn.execute("UPDATE at_divisions SET areas=(SELECT areas FROM at_items "
                 "WHERE at_items.item_key=at_divisions.item_key)")
    conn.commit()
    log("at-rollcalls: reclassified; {0} item(s) changed area".format(changed))
    return changed


def summary(conn, log=print):
    n = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    ours = lambda t: sum(on_our_ground(json.loads(a or "[]"))  # noqa: E731
                         for (a,) in conn.execute("SELECT areas FROM {0}".format(t)))
    log("  store: {0} item(s), {1} on our ground, {2} with a third-reading Klub vote; "
        "{3} division(s), {4} on our ground, {5} namentliche Abstimmung(en); "
        "{6} Klub position(s); {7} member(s)".format(
            n("SELECT COUNT(*) FROM at_items"), ours("at_items"),
            n("SELECT COUNT(*) FROM at_items WHERE vote_text IS NOT NULL"),
            n("SELECT COUNT(*) FROM at_divisions"), ours("at_divisions"),
            n("SELECT COUNT(*) FROM at_divisions WHERE roll_call=1"),
            n("SELECT COUNT(*) FROM at_votes"), n("SELECT COUNT(*) FROM at_members")))


def make_client():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    client.set_host_throttle(HOST, THROTTLE_S)
    return client


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gp", default=CURRENT_GP, help="Gesetzgebungsperiode, roman numerals")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--no-members", action="store_true")
    ap.add_argument("--no-details", action="store_true", help="skip the history pages")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-derive areas for stored items and divisions, offline")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--limit", type=int, help="stop after this many history pages")
    ap.add_argument("--dry-run", action="store_true",
                    help="read both chambers' lists, store nothing")
    args = ap.parse_args()
    client = make_client()
    today = datetime.date.today().isoformat()
    if args.dry_run:
        tax = filt.load_taxonomy(TAXONOMY)
        wl = empty_watchlist()
        for chamber in CHAMBERS:
            reply = client.post_json(ITEMS, json.dumps({"NRBR": [chamber], "GP_CODE": [args.gp]}),
                                     FEED, "dry-items-" + chamber, timeout=180)
            items, missing = parse_items(reply)
            if missing:
                print("at-rollcalls: {0}: LIST HEADER LACKS {1}".format(chamber, missing))
                continue
            ours = sum(on_our_ground(classify_item(tax, wl, it["item_key"], it["title"]).issue_areas)
                       for it in items)
            print("at-rollcalls: {0} {1}: {2} item(s), {3} on our ground, {4} with a "
                  "third-reading vote".format(chamber, args.gp, len(items), ours,
                                              sum(1 for it in items if it["vote_text"])))
        return 0
    conn = db.init_db(db.connect(args.db))
    if args.reclassify:
        reclassify(conn)
        summary(conn)
        conn.close()
        return 0
    tax = filt.load_taxonomy(TAXONOMY)
    wl = empty_watchlist()
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    if not args.no_members:
        _, g = pull_members(conn, client, today)
        gaps += g
    _, _, g = pull_items(conn, client, today, gp=args.gp, tax=tax, wl=wl)
    gaps += g
    if not args.no_details:
        robots = load_robots(client)
        pages, divs, skipped, g = pull_details(conn, client, today, robots=robots,
                                               limit=args.limit, budget=budget)
        gaps += g
        print("at-rollcalls: {0} history page(s) read, {1} vote(s) found, {2} skipped by "
              "robots.txt; {3} gap(s)".format(pages, divs, skipped, g))
    summary(conn)
    conn.close()
    return GAPS_EXIT if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
