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
        report.append((division_id, house, issue, n))
    if not report:
        log("  every tracker division already has its voters in the ledger")
    return report
