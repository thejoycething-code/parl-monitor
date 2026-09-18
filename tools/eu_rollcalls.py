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
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, filter as filt
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


EN_WORDS = frozenset("the and of on to for in a with its".split())


def english_label(labels):
    """The English subject label, or the best stand-in while the EP has none.

    The night a sitting ends the API often carries a voted item's label in
    French and in "mul" (French - English - German joined by " - ") but not
    yet under "en". The first live day sweep (17 Sept 2026) skipped all ten
    of that day's voted items for want of an English key, the social-media
    and Hong Kong resolutions among them, and told the DM "0 divisions".
    Returns (label, provisional): provisional means the English key was
    absent and heal_labels() should refresh the row once it appears.
    """
    labels = labels or {}
    en = (labels.get("en") or "").strip()
    if en:
        return en, False
    best, score = "", 0
    for seg in (labels.get("mul") or "").split(" - "):
        words = {w.strip(",.:;'\u2019()\"").lower() for w in seg.split()}
        hits = len(words & EN_WORDS)
        if hits > score:
            best, score = seg.strip(), hits
    if best:
        return best, True
    for lang in ("fr", "de", "es", "it"):
        if (labels.get(lang) or "").strip():
            return labels[lang].strip(), True
    return "", True


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
            if not areas:
                continue
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
            if not provisional:
                heal_labels(conn, v.get("activity_label"), label,
                            [e for e in events if e in known])
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
                        ev_label = "{0} — {1}".format(label, dl.strip())
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
                     json.dumps(areas), json.dumps(res.matched_terms or []),
                     res.tier, today, today))
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
