"""Every division on the vote tracker has its voters in the ledger. Always.

Why this exists. The 5CA placements and the stance scorer read a division's voters
FROM THE LEDGER (mp_events WHERE kind='vote'). The only two paths that put voters
into the ledger are the title-based division sweeps -- and a division the sweep
cannot see, because its title reads "Health Bill: Report Stage: New Clause 142" and
names no issue, never arrives. So a division could be signed off on the tracker and
contribute NOTHING to any member's placement. The first run (2026-09-10) found 13 of
23 signed-off divisions in that state. The review doc had promised "the next Score
stance run ledgers the voters"; nothing did.

Be precise about what was and was not broken. The tracker PAGE renders voters from
the raw archive payloads (make_vote_tracker's docstring: "from the archive, not a
refetch"), so the eleven older divisions always displayed correctly there; a diff of
the regenerated page showed them unchanged. The ledger -- and so every 5CA sheet --
was where they were missing. A brand-new division needs the fetch for both, because
until it runs there is no payload in data/raw for the page to render either.

The rule now: config/vote_tracker.yaml is the list of divisions we care about, and
the ledger follows it. Before the tracker builds, any tracker division with no
ledger rows has its breakdown fetched and its voters recorded under the issue's
area. Idempotent -- record_votes upserts on (member, kind, ref) -- and it never
touches a division that already has rows, so a sweep-found division is left alone.
"""

from src import intel
from src.ingest import divisions as dv

LEDGER_KIND = "vote"


def prefix_for(house):
    return "l" if (house or "").strip().lower() == "lords" else "c"


def ledger_count(conn, division_id, house=None):
    """How many voter rows the ledger holds for this division, either lobby."""
    ref = "div:%s%s:%%" % (prefix_for(house), division_id)
    return conn.execute("SELECT count(*) FROM mp_events WHERE kind=? AND ref LIKE ?",
                        (LEDGER_KIND, ref)).fetchone()[0]


def issue_areas(cfg):
    """issue id -> [area] from the tracker config."""
    return {i["id"]: [i["area"]] if i.get("area") is not None else []
            for i in (cfg.get("issues") or []) if i.get("id")}


def missing_divisions(conn, cfg):
    """[(division_id, house, areas, issue)] on the tracker with no voters in the ledger."""
    areas = issue_areas(cfg)
    out = []
    for d in cfg.get("divisions") or []:
        if not d.get("id"):
            continue
        house = (d.get("house") or "commons").lower()
        if ledger_count(conn, d["id"], house) == 0:
            out.append((int(d["id"]), house, areas.get(d.get("issue"), []), d.get("issue")))
    return out


def ensure(conn, client, cfg, log=print, dry_run=False):
    """Ledger the voters of every tracker division that has none. Returns a report list."""
    report = []
    for division_id, house, areas, issue in missing_divisions(conn, cfg):
        prefix = prefix_for(house)
        if dry_run:
            log("  would ledger %s division %s (%s, areas %s)" % (house, division_id, issue, areas))
            report.append((division_id, house, issue, None))
            continue
        try:
            if prefix == "l":
                division, voters = dv.fetch_lords_breakdown(client, division_id)
            else:
                division, voters = dv.fetch_commons_breakdown(client, division_id)
        except Exception as exc:                                # noqa: BLE001
            log("  [gap] division %s (%s): breakdown unavailable: %s" % (division_id, house, exc))
            report.append((division_id, house, issue, "gap: %s" % exc))
            continue
        division.house = "Lords" if prefix == "l" else "Commons"
        n = intel.record_votes(conn, division, voters, prefix, areas)
        log("  ledgered %s division %s (%s): %d voters under areas %s"
            % (house, division_id, issue, n, areas))
        if prefix == "c":
            raw_dir = getattr(client, "archive_dir", None) or getattr(client, "raw_dir", None) or "data/raw"
            present = present_that_day(raw_dir, division.date.isoformat(), exclude_id=division_id)
            record_absences(conn, division_id, division.date.isoformat(), " ".join((division.title or "").split()), areas, present, log=log)
        report.append((division_id, house, issue, n))
    if not report:
        log("  every tracker division already has its voters in the ledger")
    return report


SIGNED_MODEL = "tracker:signed"
ABSENT_MODEL = "rule:absent"


def present_that_day(raw_dir, date, exclude_id=None):
    """Member ids who voted in ANY Commons division archived for `date`, other than
    `exclude_id`: presence proven by the record. Empty when the day holds no other
    division (then nothing can be said, and nothing is)."""
    import glob
    import gzip
    import json
    import os
    present = set()
    for path in glob.glob(os.path.join(raw_dir, "*", "division_cdetail-*.json.gz")):
        try:
            with gzip.open(path, "rb") as fh:
                d = json.loads(fh.read().decode("utf-8"))
        except Exception:                                   # noqa: BLE001
            continue
        if (d.get("Date") or "")[:10] != date or d.get("DivisionId") == exclude_id:
            continue
        for k in ("Ayes", "Noes", "AyeTellers", "NoTellers"):
            present.update(m.get("MemberId") for m in d.get(k) or [] if m.get("MemberId"))
    return present


def record_absences(conn, division_id, date, title, areas, present, log=print):
    """One 'div:cN:absent' event per sitting MP who was present that day and voted in
    neither lobby of this division; stance 0 by rule. Returns the count.

    Christopher, 12 Sept 2026: "watch absence, not just votes" -- 45 supporters of
    the Bill stayed away on 11 September against 17 opponents, on a margin of 16.
    The closure division an hour earlier proves 48 of the day's members present.
    The comment on the 5CA then distinguishes a member who stayed away from one who
    was ill or abroad, which the bare roll never could.
    """
    from src import intel
    if not present:
        return 0
    voted = {r[0] for r in conn.execute("SELECT member_id FROM mp_events WHERE ref IN (?,?,?)",
                                        ("div:c%d:aye" % division_id, "div:c%d:no" % division_id, "div:c%d:both" % division_id))}
    sitting = {r[0] for r in conn.execute("SELECT id FROM members WHERE current_mp = 1")}
    ref = "div:c%d:absent" % division_id
    n = 0
    for mid in sorted(present & sitting - voted):
        intel.record_event(conn, mid, date, "vote", ref,
                           "Did not vote, though present that day: %s" % title, areas=areas, commit=False)
        n += 1
    conn.execute("CREATE TABLE IF NOT EXISTS stance (ref TEXT PRIMARY KEY, stance INTEGER, why TEXT, model TEXT, scored_at TEXT)")
    conn.execute("INSERT OR IGNORE INTO stance (ref, stance, why, model, scored_at) VALUES (?, 0, ?, ?, date('now'))",
                 (ref, "Present that day but voted in neither lobby.", ABSENT_MODEL))
    conn.commit()
    if n:
        log("  absences: %d sitting member(s) present on %s did not vote in division %d" % (n, date, division_id))
    return n


def apply_signed_stances(conn, cfg, log=print):
    """A signed-off division's two lobby refs take their stance from the tracker,
    never from a model: +2 for our side, -2 for the other, in the meaning lines'
    own words. Returns the number of stance rows written or corrected.

    Why: the nine June 2025 report-stage divisions on the assisted suicide Bill
    were signed off with our side named, and the model scored all eighteen lobby
    refs 0 ("direction unclear"). The 5CA therefore read every supporter who had
    backed our safeguards as a plain supporter, and the five who moved to No on
    11 September 2026 sat at -- in the August plan (found 12 Sept 2026). A human
    sign-off outranks the model; an existing model row is overwritten, and a row
    already written here is left alone.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS stance (ref TEXT PRIMARY KEY, stance INTEGER, why TEXT, model TEXT, scored_at TEXT)")
    n = 0
    for d in cfg.get("divisions") or []:
        side = str(d.get("our_side") or "").lower()
        if not d.get("signed_off") or side not in ("aye", "no") or not d.get("id"):
            continue
        prefix = prefix_for(d.get("house"))
        for lobby in ("aye", "no"):
            ref = "div:%s%s:%s" % (prefix, d["id"], lobby)
            score = 2 if lobby == side else -2
            why = (d.get("meaning_aye") if lobby == "aye" else d.get("meaning_no")) or ""
            why = " ".join(str(why).split())
            have = conn.execute("SELECT stance, model FROM stance WHERE ref=?", (ref,)).fetchone()
            if have and have[1] == SIGNED_MODEL and have[0] == score:
                continue
            conn.execute("INSERT OR REPLACE INTO stance (ref, stance, why, model, scored_at) VALUES (?,?,?,?,date('now'))",
                         (ref, score, "Tracker sign-off (%s side %s): %s" % (d.get("issue"), side, why)[:400], SIGNED_MODEL))
            n += 1
            if have and have[1] != SIGNED_MODEL and have[0] != score:
                log("  stance corrected %s: model said %+d, tracker says %+d" % (ref, have[0] or 0, score))
    conn.commit()
    return n
