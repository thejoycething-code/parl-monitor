"""The country debate pack: one debate on our ground, one folder, for the
new country editions (10 October 2026).

    python3 tools/country_debate_pack.py --country it --date 2026-10-14 --find "consenso informato"
    python3 tools/country_debate_pack.py --country pl --date 2026-10-15 --item "10/2110"

Handover item 7 (docs/country-parity-handover.md): "Debate packs, campaign
briefs, campaign targets: only once 5CA exists for a country". The 5CA layer
is merged (src/country5ca.py), so this generalises the Westminster and
German packs (src/debatepack.py, src/de_debatepack.py) to every new country
with a store, for a debate that is COMING UP or has just happened. A manual
command, like the UK and German ones: no scheduled job.

WHAT A PACK HOLDS (data/packs/<cc>-<date>-<slug>/):

  pack.md       in the country's language (src/debatepack_i18n.py): the item
                and its bill; the agenda slot; every recorded vote on the
                bill, with the tally and the split by group; the recent votes
                on the same topic; the 5CA placement (CONFIRMED readings only,
                otherwise "awaiting sign-off"); likely speakers (named by
                hand with --speakers, since no new country's source publishes
                a speakers' list ahead); the members to watch (those who
                broke with their group on the bill or topic); and every
                member's record on the bill and the topic, with a link to
                their profile when profiles/<cc>/ holds one.
  checklist.md  THE CHECK, in the country's language: the campaigner's tasks
                before the debate, then one ONSIDE: line per group and per
                member to watch. Nothing is treated as onside until a person
                has written yes.
  members.csv   the members table as a spreadsheet.
  pack.json     what was used (keys, divisions, confirmed readings), so a
                rebuild can be compared.
  README.md     in English, for whoever runs the tool.

WHERE EACH PART COMES FROM, all from the store, read-only:

  * The item: the country's own edition classification (src/editions/<cc>.py
    through country_edition.gather, or src/latam.py for the Latam
    countries), after the same noise rules, mutes and session-judge scores
    the edition applies. Never a raw keyword hit.
  * The bill and its votes: by ID, never by title (CLAUDE.md). A division
    is on the bill when one of its references (src/country5ca.py's
    Spec.refs) is one of the item's keys.
  * The agenda slot: the `country_agenda` table (src/agenda.py, the week
    ahead layer) when the store has it, matched by bill key or reference;
    the edition adapter's own week ahead otherwise (France, Croatia). Where
    neither exists the pack says so.
  * Members, positions and groups: src/country5ca.py's Specs (the same SQL
    the 5CA reads), positions verbatim, party-group countries' DERIVED rows
    (X5) marked with * and never counted as a member's own record.
  * Placement: src/country5ca.build_rows over the readings in
    config/<cc>_stance.yaml that a named person has CONFIRMED. Today none
    is, so every pack renders the "awaiting sign-off" state: no column, no
    target, no guess.

NO VERDICTS. Which way a vote cut for CitizenGO is a signed human judgement.
"Broke with their group" is arithmetic on the record, not a stance.

No network, no AI call, nothing posted.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import re
import sqlite3

from src import country5ca as c5
from src import debatepack_i18n as i18n
from src import readings5ca as r5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, "data", "packs")
PROFILES = os.path.join(ROOT, "profiles")

EDITIONS = ("es", "it", "fr", "nl", "be", "at", "ch", "pl", "pt", "hr", "sk", "hu", "br", "ar", "mx")
LATAM = ("co", "cl", "pe", "ec", "bo", "uy", "gt", "pa", "hn", "sv", "do")
COUNTRIES = EDITIONS + LATAM
HIDDEN_AREAS = (11,)             # migration: matched but never shown, as everywhere
DECISIVE = ("final", "reject", "inverted")
LOOKBACK_DAYS = 365
AHEAD_DAYS = 21
TOPIC_VOTES = 6
MAX_WATCH = 25
REBEL_MIN_GROUP = 3              # a group of two has no majority to break from
REBEL_MAJORITY = 0.6


def fold(text):
    return c5.fold(text)


def clean(text):
    return " ".join(str(text or "").split())


def clip(text, n):
    t = clean(text)
    return t if len(t) <= n else t[:n - 1].rstrip() + "..."


def name_of(cc):
    if cc in c5.SPECS:
        return c5.SPECS[cc].name
    from src import latam
    if cc in latam.NAMES:
        return latam.NAMES[cc]
    from src import country_edition as ce
    return ce.adapter(cc).name


def _plus(iso, days):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=days)).isoformat()


def _list(raw):
    return c5._json_list(raw)


# --- items on our ground --------------------------------------------------------------

def items_in(conn, cc, since, until, config_dir=None):
    """The country's items on our ground in (since, until], as its edition
    or the Latam monitor classifies them; [] when the store lacks them."""
    conn.row_factory = sqlite3.Row
    try:
        if cc in LATAM:
            from src import latam
            return latam.country_items(conn, cc, since, until, config_dir=config_dir)
        from src import country_edition as ce
        return ce.gather(conn, ce.adapter(cc), since, until, config_dir=config_dir)
    except sqlite3.OperationalError:
        return []


def agenda_points(conn, cc, start, end):
    """country_agenda rows for the country dated start..end, one per point
    (the latest sighting), or None when the store has no agenda table."""
    try:
        got = conn.execute(
            "SELECT * FROM country_agenda WHERE cc = ? AND date >= ? AND date <= ? "
            "ORDER BY date, time, item_id", (cc, start, end)).fetchall()
    except sqlite3.OperationalError:
        return None
    out = []
    for r in got:
        r = dict(r)
        r["refs"] = _list(r.get("refs"))
        r["bill_keys"] = _list(r.get("bill_keys"))
        r["watch_keys"] = _list(r.get("watch_keys"))
        r["areas"] = c5.areas_of(r.get("areas"))
        out.append(r)
    return out


def agenda_read(conn, cc):
    """True once the week-ahead collector has read this country's agenda
    (a country_agenda_runs row), so 'no point found' means what it says."""
    try:
        return conn.execute("SELECT 1 FROM country_agenda_runs WHERE cc = ? LIMIT 1",
                            (cc,)).fetchone() is not None
    except sqlite3.OperationalError:
        return False


def adapter_ahead(conn, cc, today, config_dir=None):
    """The edition adapter's own week ahead (France, Croatia on main), or None
    when it has none, or when its week ahead is the agenda table's
    (src/agenda.py) and that has not been read for this country."""
    if cc not in EDITIONS:
        return None
    from src import country_edition as ce
    country = ce.adapter(cc)
    if not country.week_ahead:
        return None
    if getattr(country.week_ahead, "__module__", "") == "src.agenda":
        return None
    conn.row_factory = sqlite3.Row
    try:
        return country.week_ahead(conn, today, ce.watchlist_of(country, config_dir)) or []
    except sqlite3.OperationalError:
        return []


def watchlist(cc, config_dir=None):
    if cc in LATAM:
        from src import latam
        return latam.watchlist(cc, config_dir)
    from src import country_edition as ce
    return ce.watchlist_of(ce.adapter(cc), config_dir)


def candidate(source, cc, key, date, title, areas, tier=None, watched=False, watch_key=None,
              refs=(), url=None, group=None, group_title=None, kind=None, extra=None):
    ids = [k for k in [key, watch_key, group] + list(refs) if k]
    return {"source": source, "cc": cc, "key": str(key), "date": str(date or "")[:10],
            "title": clean(title), "areas": [a for a in (areas or []) if a not in HIDDEN_AREAS],
            "tier": tier, "watched": bool(watched), "watch_key": watch_key,
            "refs": [str(r) for r in refs if r], "url": url, "group": group,
            "group_title": clean(group_title) or None, "kind": kind,
            "ids": list(dict.fromkeys(str(i) for i in ids)), "extra": extra or {}}


def from_item(it):
    return candidate("item", it["cc"], it["key"], it.get("date"), it.get("title"),
                     it.get("areas"), it.get("tier"), it.get("watched"),
                     it.get("watch_key") or (it["key"] if it.get("watched") else None),
                     it.get("refs") or [], it.get("url"), it.get("group"),
                     it.get("group_title"), it.get("kind"))


def from_agenda(cc, p):
    watched = p.get("watch_keys") or []
    return candidate("agenda", cc, "agenda:{0}".format(p["item_id"]), p.get("date"),
                     p.get("title"), p.get("areas"), p.get("tier"), bool(watched),
                     watched[0] if watched else None, (p.get("bill_keys") or []) + (p.get("refs") or []),
                     p.get("url"), kind="agenda", extra={"agenda": p})


def subject_of(c):
    """What a candidate is ABOUT: its watchlist key, its group (a vote's
    bill), its references, itself."""
    for k in [c.get("watch_key"), c.get("group")] + list(c.get("refs") or []):
        if k:
            return str(k)
    return c["key"]


def matches(c, find=None, item=None):
    if item:
        return str(item) in c["ids"] or str(item) == c["key"]
    if find:
        hay = fold(" ".join([c["title"], c.get("group_title") or "", c["key"]] + c["refs"]))
        return fold(find) in hay
    return True


def gather_candidates(conn, cc, date, since=None, config_dir=None, ahead=AHEAD_DAYS):
    """Every candidate around the debate date: items on our ground from
    `since` (default a year back) to `ahead` days on, and agenda points from
    a week back to `ahead` days on."""
    since = since or _plus(date, -LOOKBACK_DAYS)
    until = _plus(date, ahead)
    out = [from_item(it) for it in items_in(conn, cc, since, until, config_dir)]
    points = agenda_points(conn, cc, _plus(date, -7), until)
    for p in points or []:
        if p["areas"] or p["watch_keys"]:
            out.append(from_agenda(cc, p))
    return out


def subjects(cands):
    """Candidates merged by what they are about, most relevant first."""
    groups = {}
    for c in cands:
        s = subject_of(c)
        g = groups.setdefault(s, {"subject": s, "cands": [], "areas": set(), "watched": False,
                                  "title": None, "url": None, "dates": set(), "ids": set(),
                                  "tier": None})
        g["cands"].append(c)
        g["areas"].update(c["areas"])
        g["watched"] = g["watched"] or c["watched"]
        g["ids"].update(c["ids"])
        if c["date"]:
            g["dates"].add(c["date"])
        if c.get("tier") and (g["tier"] is None or c["tier"] < g["tier"]):
            g["tier"] = c["tier"]
    out = list(groups.values())
    for g in out:
        g["areas"] = sorted(g["areas"])
        g["title"] = subject_title(g["cands"])
        g["url"] = subject_url(g["cands"])
    out.sort(key=lambda g: (not g["watched"], g["tier"] or 9,
                            -_ordinal(max(g["dates"]) if g["dates"] else None)))
    return out


def _ordinal(iso):
    try:
        return datetime.date.fromisoformat(str(iso)[:10]).toordinal()
    except (TypeError, ValueError):
        return 0


TITLE_ORDER = ("new", "moved", "updated", "law", "report", "agenda")


def subject_url(cands):
    """The bill's own page before a vote's."""
    ranked = sorted(cands, key=lambda c: (c.get("kind") not in TITLE_ORDER, c["source"] != "item"))
    for c in ranked:
        if c.get("url"):
            return c["url"]
    return None


def is_key(text):
    """An identifier ('19/S.1735', '10/2110', '24.3456', 'PL 2665/2022'), not
    a title some adapters carry in `refs` (Poland's vote titles)."""
    t = str(text or "").strip()
    if not t or len(t) > 48 or t.count(" ") > 2:
        return False
    if " " not in t:
        return any(ch.isdigit() for ch in t)
    return bool(re.search(r"\d[/.:-]|[/.:-]\d", t))


def subject_title(cands):
    """The bill's own title where a candidate carries it: a bill item's title,
    then a vote's group title (a vote's own title is "Votazione finale"),
    then an agenda point's words, then whatever there is."""
    for kind in TITLE_ORDER:
        for c in cands:
            if c.get("kind") == kind and c["title"]:
                return c["title"]
    for c in cands:
        if c.get("group_title"):
            return c["group_title"]
    return cands[0]["title"] if cands else ""


def find_subjects(conn, cc, date, find=None, item=None, since=None, config_dir=None):
    cands = [c for c in gather_candidates(conn, cc, date, since, config_dir)
             if matches(c, find, item)]
    if not cands and item and cc in c5.SPECS:
        # A division or bill key the edition does not show (an old vote, a
        # bill whose votes are all outside the window): look in the store.
        spec = c5.SPECS[cc]
        for r in c5.divisions(conn, cc):
            refs = [str(x) for x in spec.refs(r) if x]
            if str(item) == r["key"] or str(item) in refs:
                cands.append(candidate("division", cc, r["key"], r["date"], r.get("question"),
                                       c5.areas_of(r.get("areas")), r.get("tier"), False, None,
                                       refs, None, group=refs[0] if refs else None,
                                       group_title=r.get("subject"), kind="vote"))
    return subjects(cands)


# --- votes -------------------------------------------------------------------------------

def bill_divisions(conn, cc, ids, wl=None):
    """Every division of the store on the subject, oldest first."""
    if cc not in c5.SPECS:
        return []
    spec = c5.SPECS[cc]
    ids = {str(i) for i in ids if i}
    out = []
    for r in c5.divisions(conn, cc):
        refs = {str(x) for x in spec.refs(r) if x}
        own = spec.extra_watched(r, wl or {}) if wl else None
        if r["key"] in ids or refs & ids or (own and own in ids):
            r["kind"] = c5.vote_kind(r.get("question"), spec.hint(r))[0]
            out.append(r)
    return out


def topic_divisions(conn, cc, areas, date, exclude, chamber=None, limit=TOPIC_VOTES, wl=None):
    """The latest watched or tier-1 votes on the same areas, on or before the
    debate date: decisive votes (final, reject) first, procedure never."""
    if cc not in c5.SPECS or not areas:
        return []
    spec = c5.SPECS[cc]
    got = []
    for r in c5.qualifying(conn, cc, wl):
        if r["key"] in exclude or (r.get("date") or "") > date:
            continue
        if chamber and str(r.get("chamber")) != str(chamber):
            continue
        if not set(c5.areas_of(r.get("areas"))) & set(areas):
            continue
        r["kind"] = c5.vote_kind(r.get("question"), spec.hint(r))[0]
        if r["kind"] == "procedural":
            continue
        got.append(r)
    got.sort(key=lambda r: (r["kind"] in DECISIVE, r.get("date") or "", r["key"]), reverse=True)
    picked = got[:limit]
    picked.sort(key=lambda r: (r.get("date") or "", r["key"]), reverse=True)
    return picked


def side_label(spec, lang, side):
    if side == "yea":
        return spec.labels[0]
    if side == "nay":
        return spec.labels[1]
    return i18n.text(lang, "abstain")


def tally(spec, lang, r, pos):
    """'Favorevole 80, Contrario 60, Astenuto 2' from the record's counts, or
    counted from the positions when the record has none."""
    yes, no, ab = r.get("yes"), r.get("no"), r.get("abstain")
    if yes is None and no is None and pos:
        sides = [spec.side(p["position"]) for p in pos]
        yes, no, ab = sides.count("yea"), sides.count("nay"), sides.count("abstain")
    if yes is None and no is None:
        return None
    bits = ["{0} {1}".format(spec.labels[0], yes if yes is not None else "?"),
            "{0} {1}".format(spec.labels[1], no if no is not None else "?")]
    if ab:
        bits.append("{0} {1}".format(i18n.text(lang, "abstain"), ab))
    return ", ".join(bits)


def group_split(spec, lang, pos):
    """'FdI: Favorevole 50; PD: Contrario 40, Astenuto 1' (largest group first)."""
    by = {}
    for p in pos:
        s = spec.side(p["position"])
        if s:
            g = by.setdefault(p.get("party") or "?", {"yea": 0, "nay": 0, "abstain": 0})
            g[s] += 1
    if not by:
        return None
    parts = []
    for party, n in sorted(by.items(), key=lambda kv: -sum(kv[1].values())):
        bits = ["{0} {1}".format(side_label(spec, lang, s), n[s])
                for s in ("yea", "nay", "abstain") if n[s]]
        parts.append("{0}: {1}".format(party, ", ".join(bits)))
    return "; ".join(parts)


def majorities(spec, pos):
    """{party: 'yea' | 'nay'} where a group of at least REBEL_MIN_GROUP voted
    one way by at least REBEL_MAJORITY; derived rows never count."""
    by = {}
    for p in pos:
        if p.get("derived"):
            continue
        s = spec.side(p["position"])
        if s in ("yea", "nay"):
            g = by.setdefault(p.get("party") or "?", {"yea": 0, "nay": 0})
            g[s] += 1
    out = {}
    for party, n in by.items():
        total = n["yea"] + n["nay"]
        if total < REBEL_MIN_GROUP:
            continue
        top = "yea" if n["yea"] >= n["nay"] else "nay"
        if n[top] / float(total) >= REBEL_MAJORITY:
            out[party] = top
    return out


# --- members ----------------------------------------------------------------------------

def roster(conn, cc):
    if cc not in c5.SPECS:
        return {}
    return {str(m["member_id"]): m for m in c5._rows(conn, c5.SPECS[cc].roster_sql)}


def member_records(conn, cc, bill_votes, topic_votes):
    """{member_id: record} over the decisive bill votes and the topic votes,
    with the members who broke with their group's majority."""
    spec = c5.SPECS[cc]
    ros = roster(conn, cc)
    recs = {}
    positions = {}

    def rec(p):
        mid = str(p["member_id"])
        m = ros.get(mid) or {}
        r = recs.setdefault(mid, {"member_id": mid, "name": m.get("name") or p.get("name") or mid,
                                  "party": p.get("party") or m.get("party"),
                                  "chamber": m.get("chamber"), "sitting": m.get("sitting"),
                                  "bill": [], "topic": [], "broke": [], "derived": False})
        r["party"] = p.get("party") or r["party"]
        r["derived"] = r["derived"] or bool(p.get("derived"))
        return r

    for which, divs in (("bill", bill_votes), ("topic", topic_votes)):
        for d in divs:
            pos = positions.get(d["key"])
            if pos is None:
                pos = positions[d["key"]] = c5.positions(conn, cc, d["key"])
            major = majorities(spec, pos)
            for p in pos:
                r = rec(p)
                r[which].append((d, p))
                s = spec.side(p["position"])
                party = p.get("party") or "?"
                if (not p.get("derived") and s in ("yea", "nay") and party in major
                        and major[party] != s):
                    r["broke"].append((d, p, major[party]))
    for r in recs.values():
        r["broke"].sort(key=lambda b: (b[0].get("date") or "", b[0]["key"]), reverse=True)
    return recs, positions


def topic_counts(spec, lang, rec):
    n = {"yea": 0, "nay": 0, "abstain": 0, "other": 0}
    for _d, p in rec["topic"]:
        n[spec.side(p["position"]) or "other"] += 1
    bits = ["{0} {1}".format(side_label(spec, lang, s), n[s]) for s in ("yea", "nay", "abstain") if n[s]]
    if n["other"]:
        bits.append("{0} {1}".format(i18n.text(lang, "no_record"), n["other"]))
    return ", ".join(bits)


def position_word(spec, lang, position):
    """A Yes, No or abstention in the chamber's own lobby words (the record's
    'aye' is Italy's 'Favorevole'); anything else (absent, on mission,
    present not voting) as the record has it."""
    s = spec.side(position) if spec else None
    return side_label(spec, lang, s) if s else (clean(position) or "?")


def bill_cell(rec, spec=None, lang="en"):
    """The member's position on the latest decisive bill vote, and how many
    decisive votes they have on the bill beyond it."""
    if not rec["bill"]:
        return ""
    d, p = sorted(rec["bill"], key=lambda dp: (dp[0].get("date") or "", dp[0]["key"]))[-1]
    star = "*" if p.get("derived") else ""
    more = " (+{0})".format(len(rec["bill"]) - 1) if len(rec["bill"]) > 1 else ""
    return "{0}{1} ({2}){3}".format(position_word(spec, lang, p.get("position")), star,
                                   d.get("date") or "?", more)


def placements(conn, cc, areas, config_dir=None, today=None):
    """({member_id: ['area: column']}, confirmed readings on these areas).
    Through src/country5ca.publishable_sheets, THE GATE the 5CA sheets and
    web pages share: only CONFIRMED readings place anyone, and with none
    confirmed nothing is computed and the pack renders 'awaiting sign-off'."""
    if cc not in c5.SPECS:
        return {}, 0
    entries = c5.load(cc, config_dir)[0]
    confirmed = [e for e in entries.values() if r5.status(e) == "confirmed"
                 and set(e.get("areas") or []) & set(areas)]
    if not confirmed:
        return {}, 0
    out = {}
    for sheet in c5.publishable_sheets(conn, cc, config_dir, today, entries):
        if sheet["area"] not in areas or not sheet["rows"]:
            continue
        for row in sheet["rows"]:
            if row.get("column") and row["column"] != "0":
                derived = " [DERIVED]" if "[DERIVED]" in (row.get("decision_maker") or "") else ""
                out.setdefault(str(row["person_id"]), []).append(
                    "{0}: {1}{2}".format(sheet["area"], row["column"], derived))
    return out, len(confirmed)


def profile_link(cc, member_id, name, profiles_dir=None):
    """profiles/<cc>/<file>.md when the member-profiles step has written one
    (src/member_profiles.py's filename rule), else None."""
    base = os.path.join(profiles_dir or PROFILES, cc)
    if not os.path.isdir(base):
        return None

    def slug(text, n):
        s = re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")
        return s[:n].strip("-") or "member"

    nm, key = slug(name, 50), slug(member_id, 40)
    for fn in (key + ".md", "{0}-{1}.md".format(nm, key)):
        if os.path.exists(os.path.join(base, fn)):
            return os.path.join(base, fn)
    return None


_PROFILE_VOTES = re.compile(r"^## .*\((\d+)\)\s*$")


def profile_votes(path):
    """The count in the profile's 'Votes on our ground (N)' heading, or None."""
    try:
        with open(path, encoding="utf-8") as h:
            for line in h:
                if line.startswith("## Votes"):
                    hit = _PROFILE_VOTES.match(line.strip())
                    return int(hit.group(1)) if hit else None
    except OSError:
        return None
    return None


def name_tokens(name):
    words = re.findall(r"[\w'-]+\.?", fold(name))
    return frozenset(w.strip("'-") for w in words if not w.endswith(".") and len(w.strip("'-")) > 1)


def match_speakers(conn, cc, names):
    """[(given name, roster member or None)] by folded name tokens."""
    ros = roster(conn, cc)
    out = []
    for given in names:
        want = name_tokens(given)
        hit = None
        if want:
            for m in ros.values():
                if want <= name_tokens(m.get("name")) and (hit is None or m.get("sitting")):
                    hit = m
        out.append((given, hit))
    return out


# --- assembling --------------------------------------------------------------------------

def assemble(conn, cc, date, subject, chamber=None, speakers=(), config_dir=None,
             today=None, topic_limit=TOPIC_VOTES, profiles_dir=None):
    """Everything a pack holds, as one dict (rendered by render_pack)."""
    today = today or datetime.date.today().isoformat()
    wl = watchlist(cc, config_dir) if cc in c5.SPECS else {}
    areas = [a for a in subject["areas"] if a not in HIDDEN_AREAS]
    ids = set(subject["ids"]) | {subject["subject"]}
    bill = bill_divisions(conn, cc, ids, wl)
    decisive = [d for d in bill if d["kind"] in DECISIVE] or bill
    if chamber is None and decisive:
        chamber = decisive[-1].get("chamber")
    topic = topic_divisions(conn, cc, areas, date, {d["key"] for d in bill}, chamber,
                            topic_limit, wl)
    bill_keys = [subject["subject"]]
    for c in subject["cands"]:
        for k in [c.get("watch_key")] + list(c.get("refs") or []):
            if k and is_key(k) and k not in bill_keys:
                bill_keys.append(k)
    pack = {"cc": cc, "country": name_of(cc), "bill_keys": bill_keys, "lang": i18n.lang_of(cc), "date": date,
            "today": today, "subject": subject["subject"], "title": subject["title"],
            "areas": areas, "watched": subject["watched"], "url": subject["url"],
            "ids": sorted(ids), "bill_votes": bill, "decisive": decisive, "topic_votes": topic,
            "chamber": chamber, "member_votes": cc in c5.SPECS,
            "derived": cc in c5.PARTY_GROUP}
    # The agenda slot: the agenda table by ID, then the adapter's own week ahead.
    points = agenda_points(conn, cc, _plus(date, -7), _plus(date, AHEAD_DAYS))
    slot = []
    if points is not None and agenda_read(conn, cc):
        pack["agenda_state"] = "collected"
        for p in points:
            if set(p["bill_keys"] + p["refs"] + p["watch_keys"]) & ids:
                slot.append(p)
    else:
        ahead = adapter_ahead(conn, cc, _plus(date, -7), config_dir)
        if ahead is None:
            pack["agenda_state"] = "uncollected"
        else:
            pack["agenda_state"] = "collected"
            for it in ahead:
                keys = {str(it.get("key")), str(it.get("watch_key") or "")} | set(it.get("refs") or [])
                if keys & ids:
                    slot.append({"date": it.get("date"), "time": None, "body": it.get("takeaway"),
                                 "title": it.get("title"), "status": it.get("status"),
                                 "url": it.get("url")})
    for c in subject["cands"]:
        if c["source"] == "agenda" and c["extra"].get("agenda") not in slot:
            slot.append(c["extra"]["agenda"])
    slot.sort(key=lambda p: (str(p.get("date") or ""), str(p.get("time") or "")))
    pack["agenda"] = slot
    # Members.
    recs, positions = ({}, {})
    if cc in c5.SPECS:
        recs, positions = member_records(conn, cc, decisive, topic)
    pack["positions"] = positions
    pack["members"] = recs
    place, n_confirmed = placements(conn, cc, areas, config_dir, today)
    pack["placements"], pack["confirmed"] = place, n_confirmed
    for r in recs.values():
        r["profile"] = profile_link(cc, r["member_id"], r["name"], profiles_dir)
        r["profile_votes"] = profile_votes(r["profile"]) if r["profile"] else None
    pack["speakers"] = match_speakers(conn, cc, speakers) if speakers else []
    watch = sorted((r for r in recs.values() if r["broke"]),
                   key=lambda r: (-len(r["broke"]), fold(r["name"])))
    pack["watch"] = watch
    return pack


# --- rendering ---------------------------------------------------------------------------

UMLAUT = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def slug(title, limit=44):
    low = (title or "").lower()
    for k, v in UMLAUT.items():
        low = low.replace(k, v)
    out = re.sub(r"[^a-z0-9]+", "-", fold(low)).strip("-")
    return out[:limit].rstrip("-") or "debate"


def pack_dir(cc, date, title, root=None):
    return os.path.join(root or PACKS, "{0}-{1}-{2}".format(cc, date, slug(title)))


def _areas_text(lang, areas):
    return ", ".join("{0} ({1})".format(a, i18n.area_label(lang, a)) for a in areas) or "-"


def _chamber(cc, chamber):
    spec = c5.SPECS.get(cc)
    if spec is None or chamber is None:
        return chamber or ""
    return spec.chambers.get(chamber) or spec.chambers.get(str(chamber)) or str(chamber)


def _cell(text):
    return clean(text).replace("|", "/")


def render_pack(pack, sample=False, folder=None):
    cc, lang = pack["cc"], pack["lang"]
    T = lambda key, **kw: i18n.text(lang, key, **kw)  # noqa: E731
    spec = c5.SPECS.get(cc)
    out = ["# {0}: {1}".format(T("title"), clip(pack["title"], 120)), ""]
    if sample:
        out += ["**{0}**".format(T("sample")), ""]
    out += ["*{0}*".format(T("built", today=pack["today"])), "",
            "**{0}:** {1}  ".format(T("debate_date"), pack["date"]),
            "**{0}**{1}".format(pack["country"], (", " + _chamber(cc, pack["chamber"]))
                                if pack.get("chamber") else ""), ""]

    # The item.
    out += ["## " + T("section_item"), "", "*{0}*".format(pack["title"]), "",
            "- {0}: {1}".format(T("bill"), ", ".join(pack["bill_keys"])),
            "- {0}: {1}".format(T("areas"), _areas_text(lang, pack["areas"]))]
    if pack["watched"]:
        out.append("- " + T("watched"))
    if pack.get("url"):
        out.append("- {0}: {1}".format(T("link"), pack["url"]))
    out.append("")

    # The agenda slot.
    out += ["## " + T("section_agenda"), ""]
    if pack["agenda"]:
        for p in pack["agenda"]:
            when = str(p.get("date") or "?") + (" {0}".format(p["time"]) if p.get("time") else "")
            line = "- {0}, {1}: *{2}*".format(when, clean(p.get("body")) or "-", clip(p.get("title"), 200))
            if p.get("status"):
                line += " ({0})".format(clean(p["status"]))
            if p.get("url"):
                line += " {0}".format(p["url"])
            out.append(line)
    elif pack["agenda_state"] == "uncollected":
        out.append(T("agenda_uncollected"))
    else:
        out.append(T("agenda_none", a=_plus(pack["date"], -7), b=_plus(pack["date"], AHEAD_DAYS)))
    out.append("")

    if not pack["member_votes"]:
        out += [T("no_member_votes"), ""]
        return "\n".join(out).rstrip() + "\n"

    # Votes on the bill.
    out += ["## " + T("section_bill_votes"), ""]
    if not pack["decisive"]:
        out += [T("bill_votes_none"), ""]
    for d in sorted(pack["decisive"], key=lambda d: (d.get("date") or "", d["key"]), reverse=True):
        pos = pack["positions"].get(d["key"]) or []
        out.append("### {0}, {1}: *{2}*".format(d.get("date") or "?", _chamber(cc, d.get("chamber")),
                                                clip(d.get("question"), 160)))
        if d.get("result"):
            out.append("- {0}".format(clip(d["result"], 120)))
        t = tally(spec, lang, d, pos)
        if t:
            out.append("- {0}".format(t))
        g = group_split(spec, lang, pos)
        if g:
            out.append("- {0}: {1}".format(T("by_group"), g))
        out.append("")
    others = len(pack["bill_votes"]) - len(pack["decisive"])
    if others > 0:
        out += ["*{0}*".format(T("other_votes", n=others)), ""]

    # Votes on the topic.
    out += ["## " + T("section_topic"), ""]
    if not pack["topic_votes"]:
        out.append(T("topic_none"))
    for d in pack["topic_votes"]:
        pos = pack["positions"].get(d["key"]) or []
        line = "- {0}, {1}: *{2}*".format(d.get("date") or "?", _chamber(cc, d.get("chamber")),
                                         clip(d.get("question"), 140))
        if d.get("subject") and clean(d["subject"]) != clean(d.get("question")):
            line += " (*{0}*)".format(clip(d["subject"], 120))
        t = tally(spec, lang, d, pos)
        if t:
            line += ": {0}".format(t)
        out.append(line)
    out.append("")

    # Placement: confirmed readings only.
    out += ["## " + T("section_place"), ""]
    if not pack["confirmed"]:
        out += [T("place_awaiting"), ""]
    out += [T("place_note", cc=cc, n=pack["confirmed"]), ""]

    # Likely speakers.
    out += ["## " + T("section_speakers"), ""]
    if pack["speakers"]:
        out.append("{0}:".format(T("speakers_given")))
        for given, m in pack["speakers"]:
            if m is None:
                out.append("- {0}: {1}".format(given, T("not_in_roster")))
                continue
            rec = pack["members"].get(str(m["member_id"]))
            bits = [m.get("party") or "-"]
            if rec:
                if rec["bill"]:
                    bits.append(bill_cell(rec, spec, lang))
                if rec["topic"]:
                    bits.append(topic_counts(spec, lang, rec))
                if rec.get("profile_votes") is not None:
                    bits.append(T("profile_votes", n=rec["profile_votes"]))
            out.append("- **{0}** ({1})".format(m.get("name"), "; ".join(b for b in bits if b)))
    else:
        out.append(T("speakers_none"))
    out.append("")

    # Members to watch.
    out += ["## " + T("section_watch"), ""]
    if pack["watch"]:
        out += [T("watch_intro"), ""]
        for r in pack["watch"][:MAX_WATCH]:
            d, p, major = r["broke"][0]
            line = "- **{0}** ({1}): {2}, {3} *{4}*".format(
                r["name"], r["party"] or "-",
                T("broke", pos=position_word(spec, lang, p.get("position")),
                  party=p.get("party") or "?",
                  major=side_label(spec, lang, major)),
                d.get("date") or "?", clip(d.get("question"), 80))
            if len(r["broke"]) > 1:
                line += " (+{0})".format(len(r["broke"]) - 1)
            if r.get("profile_votes") is not None:
                line += "; " + T("profile_votes", n=r["profile_votes"])
            out.append(line)
        if len(pack["watch"]) > MAX_WATCH:
            out.append("- " + T("and_more", n=len(pack["watch"]) - MAX_WATCH))
    else:
        out.append(T("watch_none"))
    out.append("")

    # Members.
    out += ["## " + T("section_members"), "", T("members_intro")]
    if any(r["derived"] for r in pack["members"].values()):
        out += ["", T("derived_note")]
    out += ["", "| {0} | {1} | {2} | {3} | {4} | {5} |".format(
        T("col_member"), T("col_group"), T("col_bill"), T("col_topic"), T("col_5ca"),
        T("col_profile")), "|---|---|---|---|---|---|"]
    for r in member_rows(pack, folder):
        out.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
            _cell(r["name"]), _cell(r["party"] or "-"), _cell(r["bill_cell"] or "-"),
            _cell(r["topic_cell"] or "-"), _cell(r["place_cell"]),
            "[{0}]({1})".format(T("profile"), r["profile_rel"]) if r["profile_rel"] else "-"))
    out.append("")

    # Sources.
    out += ["## " + T("section_sources"), ""]
    seen = []
    for u in [pack.get("url")] + [p.get("url") for p in pack["agenda"]]:
        if u and u not in seen:
            seen.append(u)
            out.append("- " + u)
    out.append("- config/{0}_stance.yaml".format(cc))
    if any(r["profile"] for r in pack["members"].values()):
        out.append("- profiles/{0}/".format(cc))
    return "\n".join(out).rstrip() + "\n"


def member_rows(pack, folder=None):
    """The members table, by group then name, as dicts (pack.md and members.csv).
    `profile_rel` is relative to the pack folder (a working link in pack.md),
    or to the repository root when no folder is given (members.csv)."""
    cc, lang = pack["cc"], pack["lang"]
    spec = c5.SPECS.get(cc)
    folder_root = folder or ROOT
    rows = []
    for r in pack["members"].values():
        place = pack["placements"].get(r["member_id"])
        if place:
            place_cell = "; ".join(place)
        elif pack["confirmed"]:
            place_cell = i18n.text(lang, "not_placed")
        else:
            place_cell = i18n.text(lang, "awaiting_cell")
        rows.append({
            "member_id": r["member_id"], "name": r["name"], "party": r["party"],
            "chamber": _chamber(cc, r.get("chamber")), "bill_cell": bill_cell(r, spec, lang),
            "topic_cell": topic_counts(spec, lang, r), "place_cell": place_cell,
            "broke": len(r["broke"]), "derived": r["derived"],
            "profile": r["profile"],
            "profile_rel": os.path.relpath(r["profile"], folder_root) if r["profile"] else None})
    rows.sort(key=lambda x: (fold(x["party"] or "~"), fold(x["name"])))
    return rows


def group_lines(pack):
    """[(group, 'how it voted on the latest decisive bill vote')] for the checklist."""
    spec = c5.SPECS.get(pack["cc"])
    if spec is None:
        return []
    last = sorted(pack["decisive"], key=lambda d: (d.get("date") or "", d["key"]))[-1:] \
        or pack["topic_votes"][:1]
    groups = {}
    for d in last:
        for p in pack["positions"].get(d["key"]) or []:
            s = spec.side(p["position"])
            if s:
                g = groups.setdefault(p.get("party") or "?", {"yea": 0, "nay": 0, "abstain": 0})
                g[s] += 1
    out = []
    for party, n in sorted(groups.items(), key=lambda kv: -sum(kv[1].values())):
        bits = ["{0} {1}".format(side_label(spec, pack["lang"], s), n[s])
                for s in ("yea", "nay", "abstain") if n[s]]
        out.append((party, "{0}, {1}: {2}".format(last[0].get("date") or "?",
                                                  clip(last[0].get("question"), 60), ", ".join(bits))))
    return out


def render_checklist(pack, sample=False):
    lang, cc = pack["lang"], pack["cc"]
    T = lambda key, **kw: i18n.text(lang, key, **kw)  # noqa: E731
    out = ["# {0}: {1}".format(T("check_title"), clip(pack["title"], 100)), ""]
    if sample:
        out += ["**{0}**".format(T("sample")), ""]
    out += ["## " + T("check_before"), ""]
    out += ["- [ ] " + T(k, cc=cc) for k in i18n.TASK_KEYS]
    out += ["", "*{0}*".format(T("check_intro")), "", T("check_markers"), "", "---", ""]
    groups = group_lines(pack)
    if groups:
        out += ["## " + T("check_groups"), ""]
        for party, line in groups:
            out += ["### group: {0}".format(party), "- {0}: {1}".format(T("record"), line),
                    "ONSIDE: ", "NOTE: ", ""]
    people = []
    for given, m in pack["speakers"]:
        if m is not None:
            people.append((m.get("name"), m.get("party"), str(m["member_id"])))
    for r in pack["watch"][:MAX_WATCH]:
        if r["member_id"] not in {p[2] for p in people}:
            people.append((r["name"], r["party"], r["member_id"]))
    if people:
        out += ["## " + T("check_members"), ""]
        for name, party, mid in people:
            rec = pack["members"].get(mid)
            out += ["### member: {0}".format(name), "- {0}: {1}".format(T("col_group"), party or "-")]
            if rec:
                if rec["bill"]:
                    out.append("- {0}: {1}".format(T("col_bill"), bill_cell(rec, c5.SPECS[cc], lang)))
                if rec["topic"]:
                    out.append("- {0}: {1}".format(T("col_topic"), topic_counts(
                        c5.SPECS[cc], lang, rec)))
            out += ["ONSIDE: ", "NOTE: ", ""]
    return "\n".join(out).rstrip() + "\n"


README = """# {title}

Debate pack for {country}, debate date {date}, built {today} by
tools/country_debate_pack.py from the store alone (no network, no AI call).
{sample}
  pack.md       for campaigners, in {language}: the item and its bill, the
                agenda slot, the votes on the bill and on the topic, likely
                speakers, members to watch, every member's record
  checklist.md  THE CHECK, in {language}: the tasks before the debate, then
                one ONSIDE: line per group and member to watch. Write yes or
                no; blank is not agreement
  members.csv   the members table as a spreadsheet
  pack.json     what was used, for comparing a rebuild

PLACEMENTS: {placement}

Positions are the record's own words. "Broke with their group" is
arithmetic on the record (a group of three or more voting one way by 60% or
more), never a stance. Rebuild with --speakers "Name; Name" once the
speakers' list is published, and read the onside answers back with
--pack <this folder> --onside.
"""


def write_pack(pack, folder=None, sample=False, root=None):
    folder = folder or pack_dir(pack["cc"], pack["date"], pack["title"], root)
    os.makedirs(folder, exist_ok=True)
    language = {"en": "English", "es": "Spanish", "it": "Italian", "fr": "French",
                "de": "German", "nl": "Dutch", "pl": "Polish", "pt": "Portuguese",
                "hr": "Croatian", "sk": "Slovak", "hu": "Hungarian"}.get(pack["lang"], pack["lang"])
    placement = ("{0} confirmed reading(s) on this topic; columns come from those only.".format(
        pack["confirmed"]) if pack["confirmed"] else
        "none confirmed on this topic, so nobody is placed (awaiting sign-off in "
        "config/{0}_stance.yaml).".format(pack["cc"]))
    files = {
        "README.md": README.format(
            title=clip(pack["title"], 120), country=pack["country"], date=pack["date"],
            today=pack["today"], language=language, placement=placement,
            sample="\nSAMPLE: built from a scoping store; never send.\n" if sample else ""),
        "pack.md": render_pack(pack, sample, folder),
        "checklist.md": render_checklist(pack, sample),
    }
    for name, body in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8") as h:
            h.write(body.rstrip() + "\n")
    with open(os.path.join(folder, "members.csv"), "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["member_id", "name", "group", "chamber", "on_this_bill", "on_this_topic",
                    "5ca", "broke_with_group", "derived", "profile"])
        for r in member_rows(pack):
            w.writerow([r["member_id"], r["name"], r["party"] or "", r["chamber"] or "",
                        r["bill_cell"], r["topic_cell"], r["place_cell"], r["broke"],
                        "yes" if r["derived"] else "", r["profile_rel"] or ""])
    state = {"cc": pack["cc"], "date": pack["date"], "built": pack["today"], "sample": sample,
             "subject": pack["subject"], "title": pack["title"], "ids": pack["ids"],
             "areas": pack["areas"], "chamber": pack["chamber"],
             "bill_votes": [d["key"] for d in pack["bill_votes"]],
             "decisive": [d["key"] for d in pack["decisive"]],
             "topic_votes": [d["key"] for d in pack["topic_votes"]],
             "agenda": [p.get("item_id") or p.get("title") for p in pack["agenda"]],
             "agenda_state": pack["agenda_state"], "confirmed_readings": pack["confirmed"],
             "members": len(pack["members"]), "watch": [r["member_id"] for r in pack["watch"]],
             "speakers": [g for g, _m in pack["speakers"]]}
    with open(os.path.join(folder, "pack.json"), "w", encoding="utf-8") as h:
        json.dump(state, h, ensure_ascii=False, indent=1)
    return folder


def parse_checklist(path):
    """-> [(kind, name, onside, note)] for the lines a person answered.
    Yes and no are accepted in every pack language."""
    yes, no = i18n.answer_words()
    out, cur, onside, note = [], None, None, ""

    def flush():
        if cur and onside is not None:
            out.append((cur[0], cur[1], onside, note))

    with open(path, encoding="utf-8") as h:
        for raw in h:
            line = raw.rstrip("\n")
            hit = re.match(r"###\s*(group|member|speaker):\s*(.*)$", line)
            if hit:
                flush()
                cur, onside, note = (hit.group(1), hit.group(2).strip()), None, ""
            elif line.upper().startswith("ONSIDE:"):
                v = line.split(":", 1)[1].strip().lower()
                onside = True if v in yes else (False if v in no else None)
            elif line.upper().startswith("NOTE:"):
                note = line.split(":", 1)[1].strip()
    flush()
    return out
