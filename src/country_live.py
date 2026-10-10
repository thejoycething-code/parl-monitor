"""Debate today and the live read, for the new countries (10 October 2026).

The UK pair (src/debatetoday.py, src/livedebate.py) generalised to the new
country editions whose chamber source publishes what was said THE SAME DAY.
Two manual commands, like the UK ones:

    tools/country_debate_today.py   the day's key debate on our ground, from
                                    the agenda (country_agenda) and what the
                                    chamber has published so far
    tools/country_live_debate.py    one debate mid-flight: what each member
                                    said next to their recorded votes on the
                                    area, and, only where a signer has
                                    CONFIRMED what those votes mean, the
                                    contradictions

WHICH COUNTRIES. Only a country whose chamber collector (tools/<cc>_chamber.py,
src/chamber_store.py) reads speeches from a source that publishes them the
same day. Measured on the live sources on 10 October 2026 (QUALIFYING and
NOT_QUALIFYING below say what was measured; the table is in
docs/debate-pack-social.md, "New countries"):

    nl  yes  Handelingen: a provisional report 2.5 to 3 hours after the
             sitting opens, then re-issued 8 to 15 times through the day
    fr  yes  compte rendu, per sitting: in the open data the same night
             (Friday 9 October's sittings by 00:13 and 01:00)
    be  yes  Integraal Verslag of the Thursday plenary: the same evening
             (8 October's record stamped 18:54)
    ch  yes  Amtliches Bulletin: published during the sitting (the
             Parliament's own statement); not yet measured by us, the
             Councils are between sessions until the Wintersession
    at  no   provisional protocol speech files the next day or later
    others   no speech collector at all (questions only, or none)

HOW THE DAY IS READ. The country's own collector does the fetch and the
parse, unchanged, against a THROWAWAY in-memory store (the real store is
attached read-only, so France still finds its group roster): nothing is
written to data/parl-monitor.db, so these commands can run while a Mini job
holds the store. Speeches are therefore exactly the collector's: each matched
on its own words (the long-transcript guard), the chair never kept. Raw
replies are archived as always.

NO VERDICTS BEFORE SIGN-OFF. A member's words are set against their
recorded votes on the area. Which way a vote cut for CitizenGO is a signed
human judgement (config/<cc>_stance.yaml, src/country5ca.py). Until a reading
is CONFIRMED the live read lists what each member said next to how they
voted, labelled "awaiting sign-off", and names no contradiction. A
contradiction (WOBBLE, SLIP, as the UK names them) needs both a confirmed
vote reading and a reading of the WORDS, which is a person's or the free
session judge's (--queue-out / --reads), never an API call. A vote DERIVED
from a party group's show of hands (X5) is the group's record, not the
member's, and never names a contradiction.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3

from src import chamber_store as cs
from src import country5ca as c5
from src import country_debatepack as dp
from src import readings5ca as r5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "parl-monitor.db")

# Measured 10 October 2026 (docs/debate-pack-social.md, "New countries"). "live" says whether a
# read DURING a debate is possible (the source publishes inside the sitting) or
# only once the sitting (or the day) is over.
QUALIFYING = {
    "nl": {"source": "Handelingen (Tweede Kamer open data, Verslag)", "live": True,
           "when": "provisional, a few hours behind the chamber",
           "delay": "first provisional report 2.5 to 3 hours after the sitting opens, then "
                    "re-issued 8 to 15 times through the day (eight plenary days, 23 September "
                    "to 8 October 2026)"},
    "ch": {"source": "Amtliches Bulletin (ws.parlament.ch, Transcript)", "live": True,
           "when": "provisional, published during the sitting",
           "delay": "published during the sitting, by the Parliament's own account; not yet "
                    "measured by us (no session until the Wintersession): confirm on its first day"},
    "fr": {"source": "compte rendu (Assemblée nationale open data)", "live": False,
           "when": "per sitting, after it ends",
           "delay": "each sitting's record the same night (9 October's two sittings by 00:13 "
                    "and 01:00): readable between sittings and in the evening, not mid-sitting"},
    "be": {"source": "Integraal Verslag / Compte rendu intégral (lachambre.be)", "live": False,
           "when": "after the plenary, the same evening",
           "delay": "the Thursday plenary's record the same evening (8 October's stamped "
                    "18:54, 1 October's 19:05, 24 September's 18:24)"},
}
NOT_QUALIFYING = {
    "at": "provisional protocol speech files appear the next day or later (Nationalrat "
          "28 September: every sampled speech stamped 29 September; Bundesrat 8 October: "
          "two of six sampled speeches still unpublished on 10 October)",
    "pl": "no speech source: the Sejm's transcripts never answered; questions only",
    "br": "no speech source: speeches cost one request per deputy; questions only",
    "pt": "no speech source: no open transcript source; questions only",
    "it": "no speech source: the Senate refuses us (403); no Camera speech collector",
    "es": "no speech source: the Cortes are dissolved until 23 December",
    "hr": "no speech collector (debates not built)",
    "sk": "no speech collector (debates not built)",
    "hu": "no speech source (parlament.hu CAPTCHA)",
}
COUNTRIES = tuple(QUALIFYING)

KEY_SPEAKERS = 5        # speakers on our ground that make a key debate
MIN_SPEAKERS = 2        # below this a debate is listed only when the agenda named it
TOPIC_VOTES = 6
EXCERPT = 220
AWAITING = "awaiting sign-off"


def today_local():
    return datetime.date.today().isoformat()


def _minus(iso, days):
    return (datetime.date.fromisoformat(iso) - datetime.timedelta(days=days)).isoformat()


# --- reading the day ---------------------------------------------------------------------

class Capture(cs.Run):
    """A chamber Run that keeps every speech in memory instead of storing it."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.got = []
        self.gap_lines = []

    def speech(self, rec, match):
        self.speeches += 1
        r = dict(rec)
        r.update({"areas": list(match.areas), "terms": list(match.terms), "tier": match.tier,
                  "excerpt": match.excerpt})
        self.got.append(r)

    def gap(self, detail):
        self.gaps += 1
        self.gap_lines.append(detail)
        self.log("  [gap] {0}-live: {1}".format(self.cc, detail))

    def read(self, doc_id, feed, date, version, segments, matched, chars, status="read"):
        self.docs += 1
        self.segments += segments


def scratch_conn(cc, store=STORE):
    """An in-memory store holding only the country's chamber tables (so every
    document reads as never read), with the real store attached read-only."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cs.ensure_schema(conn, [cc])
    if store and os.path.exists(store):
        conn.execute("ATTACH DATABASE ? AS store", ("file:{0}?mode=ro".format(store),))
    return conn


def collector(cc):
    """The country's tools/<cc>_chamber.py module."""
    import importlib.util
    path = os.path.join(ROOT, "tools", "{0}_chamber.py".format(cc))
    spec = importlib.util.spec_from_file_location("{0}_chamber_live".format(cc), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_day(cc, date, client, store=STORE, budget_seconds=600.0, log=print, fetch=None):
    """(speeches on our ground dated `date`, documents read, gap lines).
    `fetch` replaces the collector's speeches(run) in tests."""
    from src import drain
    if cc not in QUALIFYING:
        raise ValueError("{0}: {1}".format(cc, NOT_QUALIFYING.get(cc, "no same-day source")))
    conn = scratch_conn(cc, store)
    mod = None
    if fetch is None:
        mod = collector(cc)
        fetch = mod.speeches
        if hasattr(mod, "configure"):
            mod.configure(client)
    run = Capture(cc, conn, client, date, _minus(date, 1), drain.Budget(budget_seconds),
                  cs.load_taxonomies(cc), dry_run=True, log=log)
    try:
        fetch(run)
    except Exception as exc:                                 # noqa: BLE001
        run.gap("speeches failed: {0}: {1}".format(type(exc).__name__, str(exc)[:160]))
    conn.close()
    return [r for r in run.got if r.get("date") == date], run.docs, run.gap_lines


def debates(speeches):
    """[{chamber, debate_id, title, speakers, n_speeches, areas, tier, url, rows}],
    largest (distinct speakers) first."""
    groups = {}
    for r in speeches:
        k = (r.get("chamber") or "", r.get("debate_id") or r.get("debate") or "")
        groups.setdefault(k, []).append(r)
    out = []
    for (chamber, did), rs in groups.items():
        names = []
        for r in rs:
            n = (r.get("speaker") or "").strip()
            if n and n not in names:
                names.append(n)
        tiers = [r["tier"] for r in rs if r.get("tier")]
        out.append({"chamber": chamber, "debate_id": did, "title": rs[0].get("debate") or "(untitled)",
                    "speakers": names, "n_speeches": len(rs),
                    "areas": sorted({a for r in rs for a in r.get("areas") or []
                                     if a not in dp.HIDDEN_AREAS}),
                    "tier": min(tiers) if tiers else None, "url": rs[-1].get("url"), "rows": rs})
    out.sort(key=lambda d: (-len(d["speakers"]), -d["n_speeches"], d["title"]))
    return out


# --- the agenda --------------------------------------------------------------------------

def agenda_today(conn, cc, date):
    """The day's agenda points on our ground (tier 1 or 2) or watched, from
    country_agenda; None when the country's agenda has never been read."""
    if conn is None or not dp.agenda_read(conn, cc):
        return None
    pts = dp.agenda_points(conn, cc, date, date) or []
    return [p for p in pts if p.get("watch_keys") or (p.get("tier") and p.get("areas"))]


_WORD = re.compile(r"[\w-]{4,}")


def _words(text):
    return {w for w in _WORD.findall(dp.fold(text or "")) if not w.isdigit()}


def agenda_link(debate, points):
    """The agenda point a debate is, by a printed reference in the debate's
    title, else by most of the point's own words appearing in it."""
    title = dp.fold(debate["title"])
    best, score = None, 0.0
    for p in points or []:
        refs = [str(x) for x in (p.get("refs") or []) + (p.get("bill_keys") or []) if x]
        if any(len(ref) >= 4 and dp.fold(ref) in title for ref in refs):
            return p
        want = _words(p.get("title"))
        if len(want) < 2:
            continue
        s = len(want & _words(debate["title"])) / float(len(want))
        if s > score:
            best, score = p, s
    return best if score >= 0.6 else None


def verdict(rows, key=KEY_SPEAKERS):
    """The key debate: the largest with `key` speakers on our ground, or a
    watched agenda point's debate with at least MIN_SPEAKERS; else None."""
    for d in rows:
        if len(d["speakers"]) >= key:
            return d
    for d in rows:
        if d.get("agenda") and d["agenda"].get("watch_keys") and len(d["speakers"]) >= MIN_SPEAKERS:
            return d
    return None


def report(cc, date, rows, points, docs, gaps=(), key=KEY_SPEAKERS):
    """The debate_today text; its last line is the KEY DEBATE line the
    16:45 net task reads."""
    q = QUALIFYING[cc]
    lines = ["{0} ({1}), {2}: {3}".format(dp.name_of(cc), cc, date, q["source"])]
    if points is None:
        lines.append("  Agenda: not collected for this country.")
    elif not points:
        lines.append("  Agenda: nothing on our ground today.")
    else:
        lines.append("  Agenda on our ground today:")
        for p in points[:8]:
            lines.append("    {0} {1}{2} [areas {3}]".format(
                p.get("time") or "--:--", dp.clip(p.get("title"), 90),
                " (watched)" if p.get("watch_keys") else "",
                ",".join(str(a) for a in p.get("areas") or []) or "-"))
    if not rows:
        lines.append("  Said in the chamber: {0}.".format(
            "nothing on our ground in {0} document(s) read".format(docs) if docs
            else "nothing published for the day yet"))
    else:
        lines.append("  Said in the chamber, on our ground ({0} document(s) read):".format(docs))
        for d in rows:
            if len(d["speakers"]) < MIN_SPEAKERS and not d.get("agenda"):
                continue
            lines.append("    {0:>2} speakers  {1}{2}{3} [areas {4}]".format(
                len(d["speakers"]), "{0}: ".format(d["chamber"]) if d["chamber"] else "",
                dp.clip(d["title"], 80), "  (agenda point)" if d.get("agenda") else "",
                ",".join(str(a) for a in d["areas"]) or "-"))
    for g in gaps:
        lines.append("  [gap] {0}".format(g))
    top = verdict(rows, key)
    if top:
        lines.append("KEY DEBATE: {0} | {1} | {2} | {3} | {4} speakers | areas {5}".format(
            cc, top["chamber"] or "-", top["title"], top["debate_id"], len(top["speakers"]),
            ",".join(str(a) for a in top["areas"]) or "-"))
    else:
        watched = [p for p in points or [] if p.get("watch_keys")]
        lines.append("KEY DEBATE: {0} | none{1}".format(
            cc, " (agenda names a watched point: {0}; not yet in the record)".format(
                dp.clip(watched[0].get("title"), 70)) if watched and not rows else ""))
    return "\n".join(lines)


def day(cc, date, client, store=STORE, key=KEY_SPEAKERS, log=print, fetch=None, budget=600.0):
    """(text, rows, published): the whole debate_today pass for one country."""
    speeches, docs, gaps = read_day(cc, date, client, store, budget, log=log, fetch=fetch)
    rows = debates(speeches)
    conn = None
    if store and os.path.exists(store):
        conn = c5.connect_ro(store)
    points = agenda_today(conn, cc, date) if conn is not None else None
    if conn is not None:
        conn.close()
    for d in rows:
        d["agenda"] = agenda_link(d, points)
    return report(cc, date, rows, points, docs, gaps, key), rows, bool(docs)


# --- the live read -----------------------------------------------------------------------

def pick(rows, find=None, debate_id=None):
    """The debates matching --debate (exactly) or --find (folded words, all present)."""
    if debate_id:
        return [d for d in rows if d["debate_id"] == debate_id]
    if find:
        want = dp.fold(find).split()
        return [d for d in rows if all(w in dp.fold(d["title"]) for w in want)]
    return rows[:1]


def _party_ok(a, b):
    a, b = dp.fold(a or ""), dp.fold(b or "")
    if not a or not b:
        return True
    a, b = a.split("/")[0].strip(), b.split("/")[0].strip()
    return a == b or a in b or b in a


def match_member(roster, speaker, party=None, person_id=None):
    """(member, how) for a speaker as printed: by the source's own member id
    first, else by name tokens (a surname alone must be unique, or unique
    within the printed party). (None, why) when it cannot be told."""
    if person_id and str(person_id) in roster:
        return roster[str(person_id)], "id"
    want = dp.name_tokens(re.sub(r"^(M\.|Mme|Mevrouw|De heer|Mr|Mrs)\s+", "", speaker or "", flags=re.I))
    if not want:
        return None, "no name"
    hits = [m for m in roster.values() if want <= dp.name_tokens(m.get("name"))]
    if len(hits) > 1:
        sitting = [m for m in hits if m.get("sitting")]
        hits = sitting or hits
    if len(hits) > 1 and party:
        hits = [m for m in hits if _party_ok(m.get("party"), party)] or hits
    if len(hits) == 1:
        return hits[0], "name"
    return None, "ambiguous name" if hits else "not on the roster"


def vote_reading(entries, spec, d, p):
    """What one recorded vote means, as far as anyone has signed:
    {'word', 'side', 'state', 'stance', 'why', 'by', 'derived'}."""
    side = spec.side(p.get("position"))
    e = entries.get(d["key"])
    st = r5.status(e)
    out = {"word": dp.position_word(spec, "en", p.get("position")), "side": side, "state": st,
           "stance": None, "why": None, "by": None, "derived": bool(p.get("derived"))}
    if st == "confirmed" and side in ("yea", "nay"):
        stance, why = r5.value(e, side)
        out.update({"stance": stance, "why": why,
                    "by": "{0}, {1}".format(e.get("confirmed_by"), e.get("confirmed_on"))})
    return out


def member_votes(conn, cc, areas, date, chamber=None, wl=None, limit=TOPIC_VOTES, config_dir=None):
    """({member_id: [(division, position, reading)]}, divisions, entries):
    the latest decisive votes on the areas, before the debate's date."""
    spec = c5.SPECS[cc]
    divs = dp.topic_divisions(conn, cc, areas, date, set(), chamber, limit, wl)
    entries = c5.load(cc, config_dir)[0]
    out = {}
    for d in divs:
        for p in c5.positions(conn, cc, d["key"]):
            out.setdefault(str(p["member_id"]), []).append((d, p, vote_reading(entries, spec, d, p)))
    for v in out.values():
        v.sort(key=lambda t: (t[0].get("date") or "", t[0]["key"]), reverse=True)
    return out, divs, entries


WORD_READS = ("with", "against", "unclear")


def load_reads(path):
    """{speaker as printed (folded): 'with' | 'against' | 'unclear'} from a
    reads file (--queue-out writes the template; a person or the session
    judge fills it). Anything else is unread."""
    import yaml
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as h:
        raw = yaml.safe_load(h) or {}
    out = {}
    for name, val in (raw.get("reads") or {}).items():
        v = str(val or "").strip().lower()
        if v in WORD_READS:
            out[dp.fold(name)] = v
    return out


def assess(conn, cc, debate, date, reads=None, config_dir=None, wl=None, areas=None):
    """One row per speaker in the debate: words, member, votes, and the
    contradiction when (and only when) it can be named."""
    spec = c5.SPECS[cc]
    areas = [a for a in (areas or debate["areas"]) if a not in dp.HIDDEN_AREAS]
    chamber_key = None
    for k, label in spec.chambers.items():
        if debate.get("chamber") and dp.fold(label) == dp.fold(debate["chamber"]):
            chamber_key = k
    votes, divs, _ = member_votes(conn, cc, areas, date, chamber_key, wl, config_dir=config_dir)
    roster = dp.roster(conn, cc)
    reads = reads or {}
    people = {}
    for r in debate["rows"]:
        name = (r.get("speaker") or "").strip()
        p = people.setdefault(name, {"speaker": name, "party": r.get("party"), "role": r.get("role"),
                                     "person_id": r.get("person_id"), "excerpts": [], "terms": []})
        if r.get("excerpt"):
            p["excerpts"].append(r["excerpt"])
        p["terms"] += [t for t in r.get("terms") or [] if t not in p["terms"]]
    out = []
    for name, p in people.items():
        member, how = match_member(roster, name, p["party"], p["person_id"])
        mv = votes.get(str(member["member_id"]), []) if member else []
        read = reads.get(dp.fold(name))
        signed = [t for t in mv if t[2]["stance"] not in (None, 0) and not t[2]["derived"]]
        last = signed[0] if signed else None
        kind = None
        if last and read:
            with_us = last[2]["stance"] > 0
            if read in ("with", "unclear") and not with_us:
                kind = "WOBBLE"
            elif read == "against" and with_us:
                kind = "SLIP"
        if kind:
            state = kind
        elif last and read:
            state = "consistent"
        elif last:
            state = "words not read"
        elif mv:
            state = AWAITING
        else:
            state = "no recorded vote"
        out.append(dict(p, member=member, match=how, votes=mv, read=read, last_signed=last,
                        kind=kind, state=state))
    order = {"WOBBLE": 0, "SLIP": 1, "words not read": 2, AWAITING: 3, "consistent": 4,
             "no recorded vote": 5}
    out.sort(key=lambda s: (order.get(s["state"], 9), dp.fold(s["speaker"])))
    return out, divs


def _vote_line(t):
    d, p, rd = t
    bits = "{0}{1} on {2} ({3})".format(rd["word"], "*" if rd["derived"] else "", dp.clip(
        d.get("question") or d.get("subject") or d["key"], 70), d.get("date") or "?")
    if rd["stance"] not in (None, 0):
        bits += ": {0} (confirmed by {1})".format("with us" if rd["stance"] > 0 else "against us",
                                                 rd["by"])
    elif rd["state"] == "confirmed":
        bits += ": confirmed, this side carries no value"
    else:
        bits += ": " + AWAITING
    return bits


def render(cc, date, debate, rows, divs, as_of=None):
    """The live read as plain text (Slack DM and terminal)."""
    title = debate["title"]
    head = ["*Live read, {0}: {1}{2}*".format(dp.name_of(cc), dp.clip(title, 100),
                                               " as of {0}".format(as_of) if as_of else ""),
            "{0} on {1}; {2} speaker(s) on our ground so far; source: {3} ({4}).".format(
                debate.get("chamber") or dp.name_of(cc), date, len(rows), QUALIFYING[cc]["source"],
                QUALIFYING[cc]["when"])]
    if not divs:
        head.append("No recorded vote on areas {0} in the store: words only.".format(
            ",".join(str(a) for a in debate["areas"]) or "-"))
    named = [s for s in rows if s["kind"]]
    signed_any = any(s["last_signed"] for s in rows)
    lines = list(head) + [""]
    if named:
        for kind, label in (("WOBBLE", "*Sounding unlike their confirmed vote (voted against us):*"),
                            ("SLIP", "*Sounding unlike their confirmed vote (voted with us):*")):
            got = [s for s in named if s["kind"] == kind]
            if got:
                lines.append(label)
                for s in got:
                    lines.append("- {0} ({1}): words read {2}; {3}".format(
                        s["speaker"], s["party"] or "?", s["read"], _vote_line(s["last_signed"])))
                lines.append("")
    rest = [s for s in rows if not s["kind"]]
    if rest:
        if not signed_any:
            lines.append("*AWAITING SIGN-OFF: what members said, next to how they voted.* No reading "
                         "of these votes is confirmed for CitizenGO, so nothing below is a "
                         "contradiction or a placement.")
        else:
            lines.append("*Said, next to the record:*")
        for s in rest:
            who = "{0} ({1})".format(s["speaker"], s["party"] or "?")
            if s["role"] and s["role"] != "member":
                who += ", " + s["role"]
            if not s["member"]:
                who += " [not matched to a member: {0}]".format(s["match"])
            lines.append("- {0}: \"{1}\"".format(who, dp.clip(s["excerpts"][0] if s["excerpts"] else "", EXCERPT)))
            if s["votes"]:
                for t in s["votes"][:3]:
                    lines.append("    voted " + _vote_line(t))
            elif s["member"]:
                lines.append("    no recorded vote on these areas in the store")
            if s["state"] == "consistent":
                lines.append("    words read {0}: in line with the confirmed vote".format(s["read"]))
            if s["state"] == "words not read":
                lines.append("    words not read yet: no contradiction named (fill --reads)")
        lines.append("")
    if not rows:
        lines.append("Nobody on our ground in this debate yet.")
    if any(t[2]["derived"] for s in rows for t in s["votes"]):
        lines.append("_* a group's show of hands given to each member (X5): never the member's own "
                     "record, never named as a contradiction._")
    lines.append("_Words are the record's own, matched passage by passage; a vote counts only "
                 "once a signer confirms what it means. Re-run before the vote._")
    return "\n".join(lines).rstrip()


def queue_text(cc, date, debate, rows):
    """The reads template: one line per speaker, with what they said, for a
    person or the free session judge to fill (with / against / unclear)."""
    out = ["# Live read: {0}, {1}, {2}".format(dp.name_of(cc), date, debate["title"]),
           "# For each speaker write with, against or unclear: what their OWN WORDS here say",
           "# about CitizenGO's position on areas {0}. Leave blank when unsure.".format(
               ",".join(str(a) for a in debate["areas"]) or "-"),
           "# Judge the words only, never the party or the person.",
           "read_by: \"\"", "reads:"]
    for s in rows:
        for ex in s["excerpts"][:2]:
            out.append("  # {0}".format(dp.clip(ex, 300)))
        out.append("  \"{0}\": \"\"".format(s["speaker"].replace('"', "'")))
    return "\n".join(out) + "\n"
