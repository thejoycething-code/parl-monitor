"""EU roll calls: MEP votes on our ground, collected -- never judged.

    python3 tools/eu_rollcalls.py
    python3 tools/eu_rollcalls.py --days 120 --refetch   # re-read known divisions too

Phase 2d of the EU monitor, COLLECTION ONLY. For every plenary sitting in
the lookback window: the sitting's vote list (EN labels), each label
through the taxonomy, and for MATCHED votes the decision event's full
roll call -- who voted favor/against/abstention, by person id -- plus the
MEP roster to give ids names.

What this deliberately does NOT do: assign verdicts. A division's meaning
comes from its motion text and is signed off by Christopher per division,
never derived from a title (the Lords inversion, 2026-08-31, is the
standing lesson). eu_divisions has no our_side column at all; the eventual
EU 5CA builds on this data only after that sign-off flow exists.

Request budget: one vote-results call per sitting in the window, one
event call per MATCHED vote, one roster page. The 500/5min limit is
untouched by orders of magnitude.

Separation guarantee: writes eu_meps / eu_divisions / eu_votes only.
ONE WRITER AT A TIME on data/parl-monitor.db.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, eulabel, filter as filt
from src.http import FetchError, HttpClient

MEETINGS = ("https://data.europarl.europa.eu/api/v2/meetings"
            "?year={0}&limit=500&format=application%2Fld%2Bjson")
RESULTS = ("https://data.europarl.europa.eu/api/v2/meetings/{0}"
           "/vote-results?format=application%2Fld%2Bjson")
EVENT = ("https://data.europarl.europa.eu/api/v2/events/{0}"
         "?format=application%2Fld%2Bjson")
MEPS = ("https://data.europarl.europa.eu/api/v2/meps"
        "?parliamentary-term=10&limit=1000&format=application%2Fld%2Bjson")
LOOKBACK_DAYS = 60


def pid(uri):
    """'person/197529' -> '197529'."""
    return str(uri).rsplit("/", 1)[-1]


def refresh_roster(conn, client, today, log=print):
    try:
        reply = client.get_json(MEPS, "eu-rollcalls", "meps", archive=False)
    except (FetchError, ValueError) as exc:
        log("  [gap] roster: {0}".format(exc))
        return 0
    n = 0
    for m in reply.get("data") or []:
        conn.execute(
            "INSERT INTO eu_meps (person_id, name, first_seen, last_seen) "
            "VALUES (?,?,?,?) ON CONFLICT(person_id) DO UPDATE SET "
            "name=excluded.name, last_seen=excluded.last_seen",
            (m.get("identifier") or pid(m.get("id", "")), m.get("label"),
             today, today))
        n += 1
    conn.commit()
    return n


def past_sittings(client, today, days=None):
    t = datetime.date.fromisoformat(today)
    start = t - datetime.timedelta(days=days or LOOKBACK_DAYS)
    years = sorted({start.year, t.year})
    out = []
    for y in years:
        reply = client.get_json(MEETINGS.format(y), "eu-rollcalls",
                                "meetings-{0}".format(y), archive=False)
        for m in reply.get("data") or []:
            d = m.get("activity_date")
            if d and start.isoformat() <= d <= today:
                out.append((m["activity_id"], d))
    return sorted(out, key=lambda x: x[1])


def english_label(labels):
    """The voted item's English label, or the best stand-in (src/eulabel.py).
    Roll calls take a French label as a last resort because heal_labels()
    refreshes the row once "en" appears; no other collector does."""
    return eulabel.english_label(labels, any_language=True)


def inherit_from_text(conn, label, date, days=7):
    """The adopted text this vote item belongs to, when the text matched on
    its BODY and the label matched nothing.

    Divisions are matched on their subject label; adopted texts on their
    body. On 16 Sept 2026 the gender-inequalities-in-health resolution
    matched fourteen terms as a text (abortion, SRHR, transgender) and its
    98 roll calls were never stored, because the label says none of that.
    The Parliament gives the vote item and the adopted text the same title,
    so the text's areas are the vote's areas. Returns the eu_texts row or
    None.
    """
    key = eulabel.normalise_title(label)
    if len(key) < 12:
        return None
    lo = (datetime.date.fromisoformat(date) - datetime.timedelta(days=days)).isoformat()
    hi = (datetime.date.fromisoformat(date) + datetime.timedelta(days=days)).isoformat()
    for r in conn.execute(
            "SELECT identifier, title, areas, matched_terms, tier FROM eu_texts "
            "WHERE body_read IS NOT NULL AND areas IS NOT NULL AND areas != '[]' "
            "AND date BETWEEN ? AND ?", (lo, hi)):
        if eulabel.normalise_title(r[1]) == key:
            return r
    return None

SPLIT_TEXT_LIMIT = 160
WITHOUT = re.compile(r"^text as a whole without the words?:?\s*(.+)$", re.I | re.S)


def split_texts(item):
    """{'§ 85': {'1': 'the paragraph without the words ‘and rights’', '2': 'the words ‘and rights’'}, ...}

    The vote item names its splits in was_motivated_by: each SPLIT activity
    carries the paragraph it divides ("§ 85", "Recital AD") and one Work per
    part whose expressionContent is the part's definition. Two idioms cover
    most of them: part 1 "Text as a whole without the words: ‘X’", part 2
    "those words". Read together they say what 146 members voted against on
    17 Sept 2026 (the words "and rights" after "sexual and reproductive
    health"), which a bare "§ 85/2" never will.
    """
    out = {}
    for m in item.get("was_motivated_by") or []:
        if "SPLIT" not in (m.get("activity_id") or ""):
            continue
        key = _split_key(eulabel.english_label(m.get("activity_label"), any_language=True)[0])
        if not key:
            continue
        parts = {}
        for w in m.get("created_a_realization_of") or []:
            text = eulabel.english_label(w.get("expressionContent"), any_language=True)[0]
            text = " ".join(re.sub(r"<[^>]+>", " ", text).split())
            if w.get("number") and text:
                parts[str(w["number"])] = text
        quoted = None
        for text in parts.values():
            hit = WITHOUT.match(text)
            if hit:
                quoted = hit.group(1).strip().rstrip(".")
        for n, text in list(parts.items()):
            if WITHOUT.match(text) and quoted:
                parts[n] = "the text without the words " + quoted
            elif text.lower().rstrip(".") in ("those words", "these words") and quoted:
                parts[n] = "the words " + quoted
        if parts:
            out[key] = parts
    return out


def _split_key(label):
    """'§ 85' from '§ 85', 'A10-0220/2026 – Sandro Ruotolo – § 85' or 'Recital AD'."""
    label = (label or "").split(" – ")[-1].split(" - ")[-1].strip()
    label = " ".join(label.split())
    # The split entry says "Amendment 51"; the decision says "Am 51".
    label = re.sub(r"^Amendments?\b\.?", "Am", label, flags=re.I)
    return label or None


PART = re.compile(r"^(.*?)/(\d+)$")


def annotate(decision_label, splits):
    """'§ 85/2' + splits -> '§ 85/2: the words ‘and rights’'; unchanged when the
    decision is not a part or the part is not defined."""
    if not decision_label or not splits:
        return decision_label
    m = PART.match(decision_label.strip())
    if not m:
        return decision_label
    key, part = _split_key(m.group(1)), m.group(2)
    text = (splits.get(key) or {}).get(part)
    if not text:
        return decision_label
    if len(text) > SPLIT_TEXT_LIMIT:
        text = text[:SPLIT_TEXT_LIMIT - 1].rstrip() + "…"
    return "{0}: {1}".format(decision_label, text)


def annotate_known(conn, known_events, splits):
    """Rows stored before the split texts were read get them now, from the
    vote item this pass has already fetched: no event call, one UPDATE per
    row whose label is still a bare part number."""
    if not known_events or not splits:
        return 0
    n = 0
    for full_id in known_events:
        row = conn.execute("SELECT label FROM eu_divisions WHERE vote_id = ?", (full_id,)).fetchone()
        if not row or " \u2014 " not in (row[0] or ""):
            continue
        head, tail = row[0].split(" \u2014 ", 1)
        if ": " in tail:
            continue
        new = annotate(tail, splits)
        if new != tail:
            conn.execute("UPDATE eu_divisions SET label = ? WHERE vote_id = ?",
                         ("{0} \u2014 {1}".format(head, new), full_id))
            n += 1
    return n


def heal_labels(conn, labels, label, known_events):
    """Once the English key arrives, replace the provisional prefix on rows
    stored from "mul". `known` skips these events entirely, so without this
    a label picked the night of the vote would stand for ever."""
    if not known_events:
        return 0
    stale = english_label({k: x for k, x in (labels or {}).items() if k != "en"})[0]
    if not stale or stale == label:
        return 0
    n = 0
    for full_id in known_events:
        n += conn.execute(
            "UPDATE eu_divisions SET label = ? || substr(label, ?) "
            "WHERE vote_id = ? AND substr(label, 1, ?) = ?",
            (label, len(stale) + 1, full_id, len(stale), stale)).rowcount
    return n


def pull(conn, client, today, log=print, days=None, refetch=False, on_day=None):
    tax = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
    wl = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist.yaml"))
    try:
        sittings = past_sittings(client, today, days)
    except (FetchError, ValueError) as exc:
        conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                     "VALUES (?,?,?)", (today, "eu-rollcalls", str(exc)))
        conn.commit()
        log("  [gap] eu-rollcalls calendar: {0}".format(exc))
        return 0, 0, 0
    # `refetch` empties this (17 Sept 2026). Skipping a division we already
    # hold is what makes the weekly run cheap, and it is also why adding the
    # `outcome` column changed nothing: every row was already known, so no
    # event was fetched again and the new field stayed NULL on all 149. A new
    # column needs one pass that ignores the skip.
    known = set() if refetch else {r[0] for r in conn.execute("SELECT vote_id FROM eu_divisions")}
    seen = matched = gaps = 0
    if on_day:
        # One sitting day only: the per-day sweep (src/eudaysweep.py) aims this
        # at the day that has just finished voting instead of re-walking a
        # 60-day window every Saturday.
        sittings = [(sid, d) for sid, d in sittings if d == on_day]
    for sid, date in sittings:
        try:
            reply = client.get_json(RESULTS.format(sid), "eu-rollcalls", sid,
                                    archive=False)
        except ValueError:
            continue        # no vote results published (204-empty)
        except FetchError as exc:
            if "404" in str(exc.cause):
                continue
            conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) "
                         "VALUES (?,?,?)",
                         (today, "eu-rollcalls",
                          "{0}: {1}".format(sid, exc.cause)))
            log("  [gap] {0}: {1}".format(sid, exc.cause))
            gaps += 1
            continue
        for v in (reply or {}).get("data") or []:
            if (v.get("had_activity_type") or "").rsplit("/", 1)[-1] \
                    != "PLENARY_VOTE_RESULTS":
                continue
            label, provisional = english_label(v.get("activity_label"))
            if not label:
                continue
            seen += 1
            res = filt.filter_item(tax, wl, label)
            areas = res.issue_areas or []
            terms, tier = res.matched_terms or [], res.tier
            if not areas:
                text = inherit_from_text(conn, label, date)
                if text is None:
                    continue
                areas = json.loads(text[2] or "[]")
                terms, tier = json.loads(text[3] or "[]"), text[4]
                log("  inherited from {0}: {1}".format(text[0], label[:60]))
            matched += 1
            # EVERY decision event under the matched subject, not just the
            # first: one vote-results item can carry several decisions (a
            # split vote on one paragraph AND the motion as a whole), and
            # taking consists_of[0] cost us the SDG resolution's
            # whole-motion roll call while storing its electronic
            # paragraph split (found 2026-09-01 against the RCV annex).
            events = [str(e).rsplit("/", 1)[-1]
                      for e in v.get("consists_of") or []] \
                or [v.get("activity_id")]
            splits = split_texts(v)
            already = [e for e in events if e in known]
            if not provisional:
                heal_labels(conn, v.get("activity_label"), label, already)
            annotated = annotate_known(conn, already, splits)
            if annotated:
                log("  split texts added to {0} stored roll call(s): {1}".format(annotated, label[:50]))
            for full_id in events:
                if full_id in known:
                    continue
                fav = agn = abst = None
                ev_label = label
                try:
                    ev = client.get_json(EVENT.format(full_id),
                                         "eu-rollcalls", full_id,
                                         archive=False)
                    e = (ev.get("data") or [{}])[0]
                    fav = e.get("number_of_votes_favor")
                    agn = e.get("number_of_votes_against")
                    abst = e.get("number_of_votes_abstention")
                    # "def/ep-statuses/REJECTED" -> "REJECTED"
                    outcome = (e.get("decision_outcome") or "").rsplit("/", 1)[-1] or None
                    # The decision's own label ("§ 10", "Request for an
                    # urgent decision") names what was actually decided;
                    # the subject label alone hides it.
                    dl = (e.get("activity_label") or {}).get("en") \
                        or (e.get("activity_label") or {}).get("mul")
                    if dl and dl.strip() and dl.strip() != label:
                        ev_label = "{0} — {1}".format(label, annotate(dl.strip(), splits))
                    for pos in ("favor", "against", "abstention"):
                        for voter in e.get("had_voter_" + pos) or []:
                            conn.execute(
                                "INSERT OR REPLACE INTO eu_votes (vote_id, "
                                "person_id, position) VALUES (?,?,?)",
                                (full_id, pid(voter), pos))
                except (FetchError, ValueError) as exc:
                    log("  [gap] roll call {0}: {1}".format(full_id, exc))
                    gaps += 1
                if fav is None and agn is None:
                    # A decision event with no tallies at all is plumbing
                    # (source-motion placeholders, section headers), not a
                    # vote; storing them buried the real divisions in
                    # twelve empty rows on the first multi-event run.
                    continue
                conn.execute(
                    "INSERT INTO eu_divisions (vote_id, sitting_id, date, "
                    "label, favor, against, abstention, outcome, areas, "
                    "matched_terms, tier, first_seen, last_seen) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(vote_id) DO UPDATE SET "
                    "label=excluded.label, favor=excluded.favor, "
                    "against=excluded.against, "
                    "abstention=excluded.abstention, "
                    "outcome=excluded.outcome, "
                    "last_seen=excluded.last_seen",
                    (full_id, sid, date, ev_label, fav, agn, abst, outcome,
                     json.dumps(areas), json.dumps(terms),
                     tier, today, today))
    conn.commit()
    return seen, matched, gaps


def main():
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    conn = db.init_db(db.connect(os.path.join(ROOT, "data",
                                              "parl-monitor.db")))
    today = datetime.date.today().isoformat()
    # --days widens the window (17 Sept 2026). These collectors had a fixed
    # 60-day lookback, so when the 9 Sept store rebuild emptied their tables
    # the July plenary was already out of reach and a plain re-run could not
    # recover it. A gap needs a wider window, the way the Westminster
    # backfills do.
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else LOOKBACK_DAYS
    roster = refresh_roster(conn, client, today)
    seen, matched, gaps = pull(conn, client, today, days=days,
                               refetch="--refetch" in sys.argv)
    print("eu-rollcalls: {0} MEPs on the roster; {1} plenary votes in {2} "
          "days, {3} on our ground, {4} gap(s).".format(
              roster, seen, days, matched, gaps))
    for r in conn.execute("SELECT * FROM eu_divisions ORDER BY date DESC "
                          "LIMIT 10").fetchall():
        n = conn.execute("SELECT COUNT(*) FROM eu_votes WHERE vote_id = ?",
                         (r["vote_id"],)).fetchone()[0]
        print("  [{0}] {1} - {2} ({3}-{4}-{5}; {6} roll-call positions)"
              .format(",".join(str(a) for a in json.loads(r["areas"])),
                      r["date"], r["label"][:70], r["favor"], r["against"],
                      r["abstention"], n))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
