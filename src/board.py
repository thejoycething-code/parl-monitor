"""Active bills board state machine (handoff sections 4.1, 8).

The board is persistent: every edition renders every live tagged bill with its
next key date, sorted ascending. A bill leaves the board only at Royal Assent
or fall, with exactly one closing entry.

The hard, high-value logic (handoff step 2) is detecting the two terminal
transitions that the raw feed does NOT flag:

  * Royal Assent: isAct flips true, currentHouse becomes "Unassigned", stage
    "Royal Assent". Terminal -> closing entry, plus create an acts_watch row and
    trigger the legislation.gov.uk in-force check (step 3).
  * Prorogation fall: a non-Act bill whose includedSessionIds excludes the
    current session has fallen. isDefeated stays false and the stage is frozen
    at the last sitting, so this must be derived from session ids, never from
    isDefeated (handoff section 11).

current_session_id is the max introducedSessionId seen across recent bills
(session 39 = 2024-26, session 40 = opened June 2026).
"""

from __future__ import annotations

from dataclasses import dataclass, field

TBA = "TBA"

# Transition kinds.
NEW = "NEW"              # first appearance on the board
MOVED = "MOVED"          # stage advanced or next key date changed since last edition
UNCHANGED = "UNCHANGED"  # no change since last edition
ROYAL_ASSENT = "ROYAL_ASSENT"  # terminal: Act
FALLEN = "FALLEN"        # terminal: fell at prorogation

# Movement markers rendered in the board (handoff digest-template section 2).
# Words, not bare symbols: readers should not need the codebase to decode the
# column. A one-line key also renders under the table (digest.render_board).
MARKER = {NEW: "NEW", MOVED: "▲ moved", UNCHANGED: "no change"}


def current_session_id(bills):
    """Max introducedSessionId across a set of recently-seen bills."""
    ids = [b.introduced_session_id for b in bills if b.introduced_session_id is not None]
    return max(ids) if ids else None


def has_fallen(bill, session_id):
    """True if a non-Act bill's includedSessionIds excludes the current session."""
    if bill.is_act:
        return False
    if session_id is None:
        return False
    return session_id not in (bill.included_session_ids or [])


@dataclass
class BoardRow:
    bill_id: int
    title: str
    sponsor: str
    house: str
    stage: str
    next_key_date: str            # ISO date or "TBA"
    status: str                   # live | closed
    transition: str               # NEW | MOVED | UNCHANGED | ROYAL_ASSENT | FALLEN
    closed_note: str = None
    closed_date: str = None       # ISO date of the terminal event (RA / fall)
    triggers: list = field(default_factory=list)  # e.g. ["acts_watch", "legislation_check"]
    areas: str = None             # csv of issue-area numbers, set from the watchlist
    why: str = None               # one-line "why we track it", from watchlist.yaml
    url: str = None               # set for non-Westminster rows (e.g. Holyrood)

    @property
    def link(self):
        """Canonical bill page; defaults to the Westminster pattern."""
        return self.url or "https://bills.parliament.uk/bills/{0}".format(self.bill_id)

    @property
    def movement(self):
        return MARKER.get(self.transition)

    def snapshot(self):
        """Minimal state stored as board_snapshot for next-edition diffing."""
        return {"stage": self.stage, "next_key_date": self.next_key_date, "status": self.status}


def _date_str(d):
    return d.isoformat() if d is not None else TBA


def build_row(bill, session_id, run_date, prior_snapshot=None):
    """Compute this edition's board row for a bill.

    prior_snapshot is the stored snapshot dict from the previous edition (or
    None if the bill has never been on the board). Returns a BoardRow.
    """
    # -- terminal transitions first ---------------------------------------
    if bill.is_act:
        ra = bill.royal_assent_date()
        return BoardRow(
            bill_id=bill.bill_id, title=bill.short_title, sponsor=bill.sponsor_name,
            house=bill.current_house, stage=bill.current_stage,
            next_key_date=TBA, status="closed", transition=ROYAL_ASSENT,
            closed_note="Royal Assent {0}".format(_date_str(ra)),
            closed_date=ra.isoformat() if ra else None,
            triggers=["acts_watch", "legislation_check"],
        )

    if has_fallen(bill, session_id):
        last = bill.last_sitting_date()
        return BoardRow(
            bill_id=bill.bill_id, title=bill.short_title, sponsor=bill.sponsor_name,
            house=bill.current_house, stage=bill.current_stage,
            next_key_date=TBA, status="closed", transition=FALLEN,
            closed_note="Fell at prorogation; frozen at {0} ({1})".format(
                bill.current_stage, _date_str(last)),
            closed_date=last.isoformat() if last else None,
        )

    # -- live bill: next key date + movement marker -----------------------
    nkd = _date_str(bill.next_key_date(run_date))
    if prior_snapshot is None:
        transition = NEW
    elif prior_snapshot.get("stage") != bill.current_stage or prior_snapshot.get("next_key_date") != nkd:
        transition = MOVED
    else:
        transition = UNCHANGED

    return BoardRow(
        bill_id=bill.bill_id, title=bill.short_title, sponsor=bill.sponsor_name,
        house=bill.current_house, stage=bill.current_stage,
        next_key_date=nkd, status="live", transition=transition,
    )


def should_render_closing(row, prior_row_status, prior_closed_edition):
    """One-closing-entry guard (handoff section 8).

    A terminal row renders in exactly one edition. If the board already closed
    this bill in a prior edition (prior_closed_edition set), suppress it.
    """
    if row.status != "closed":
        return True  # live rows always render
    return prior_closed_edition is None


def sort_key(row):
    """Board sort: ascending by next key date, TBA rows last (handoff section 8)."""
    if row.next_key_date == TBA:
        return (1, "")
    return (0, row.next_key_date)


def order_board(rows):
    return sorted(rows, key=sort_key)


# -- snapshot persistence (movement markers across editions) -----------------
#
# Movement is a week-on-week diff, so each edition must persist what it saw.
# bills_board.board_snapshot stores JSON:
#   {"edition": <week>, "current": {stage, next_key_date, status},
#    "previous": <the snapshot diffed against, or null>}
# Keeping "previous" makes re-rendering the same edition idempotent: a second
# render of edition E diffs against the same prior state as the first, instead
# of diffing against the snapshot the first render just wrote.


def apply_snapshots(conn, rows, edition):
    """Set movement transitions on live rows by diffing stored snapshots,
    then persist this edition's snapshots. Idempotent per edition."""
    import json

    for row in rows:
        if row.status != "live":
            continue
        stored_row = conn.execute(
            "SELECT board_snapshot FROM bills_board WHERE bill_id = ?", (row.bill_id,)
        ).fetchone()
        stored = None
        if stored_row and stored_row["board_snapshot"]:
            try:
                stored = json.loads(stored_row["board_snapshot"])
            except ValueError:
                stored = None

        if stored is None:
            prior = None
        elif stored.get("edition") == edition:
            prior = stored.get("previous")     # re-render: same baseline as first render
        else:
            prior = stored.get("current")      # new edition: diff against last edition

        if prior is None:
            row.transition = NEW
        elif (prior.get("stage") != row.stage
              or prior.get("next_key_date") != row.next_key_date):
            row.transition = MOVED
        else:
            row.transition = UNCHANGED

        record = json.dumps({"edition": edition, "current": row.snapshot(), "previous": prior})
        conn.execute(
            "INSERT INTO bills_board (bill_id, title, sponsor, house, stage, next_key_date, areas, status, board_snapshot) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'live', ?) "
            "ON CONFLICT(bill_id) DO UPDATE SET title=excluded.title, house=excluded.house, "
            "stage=excluded.stage, next_key_date=excluded.next_key_date, areas=excluded.areas, "
            "board_snapshot=excluded.board_snapshot",
            (row.bill_id, row.title, row.sponsor, row.house, row.stage,
             row.next_key_date, row.areas, record),
        )
    conn.commit()
    return rows


# -- discovery-driven closures (cold-start correct) --------------------------
#
# The board detects terminal state ABSOLUTELY, not relative to a prior live row.
# On each run, candidate bills (watchlist entities + acts_watch short-title
# searches) are evaluated; a bill that is terminal (Act, or session-excluded)
# and has never been closed before emits its closing entry exactly once. The
# `closed_edition` guard in bills_board enforces once-ever. This makes the first
# edition emit the historical closes (3774 fall, CPA/CWSA Royal Assent) that a
# cold, empty board would otherwise never surface.
#
# Westminster only for now: Holyrood fall detection is deferred to the Scotland
# ingester (handoff section 4.11); it is not part of this discovery path.


def discover_closures(bills, session_id, run_date, closed_bill_ids):
    """Closing rows for candidate bills that are terminal and not yet closed.

    bills            candidate Bill objects (from watchlist + acts_watch search)
    closed_bill_ids  set of bill_ids already closed in a prior edition
    """
    already = set(closed_bill_ids or ())
    rows = []
    for bill in bills:
        row = build_row(bill, session_id, run_date, prior_snapshot=None)
        if row.status == "closed" and bill.bill_id not in already:
            rows.append(row)
    return rows


def load_closed_bill_ids(conn, exclude_edition=None):
    """Bill ids the board has already emitted a closing entry for.

    exclude_edition: when re-rendering an edition, pass its week id so bills
    closed IN THAT EDITION still render there. The one-closing-entry rule is
    per-edition, not per-render: a closure appears in exactly one edition, but
    that edition can be rendered many times (draft, post-review, corrections).
    """
    if exclude_edition is None:
        cur = conn.execute("SELECT bill_id FROM bills_board WHERE closed_edition IS NOT NULL")
    else:
        cur = conn.execute(
            "SELECT bill_id FROM bills_board WHERE closed_edition IS NOT NULL AND closed_edition != ?",
            (exclude_edition,))
    return {r["bill_id"] for r in cur.fetchall()}


def record_closure(conn, row, edition):
    """Persist a closing entry once. Returns False if closed in another edition.

    Re-recording within the SAME edition is an idempotent no-op success, so
    re-rendering an edition never trips the guard.
    """
    existing = conn.execute(
        "SELECT closed_edition FROM bills_board WHERE bill_id = ?", (row.bill_id,)
    ).fetchone()
    if existing is not None and existing["closed_edition"] is not None:
        return existing["closed_edition"] == edition  # same edition: idempotent
    if existing is None:
        conn.execute(
            "INSERT INTO bills_board "
            "(bill_id, title, sponsor, house, stage, next_key_date, status, closed_note, closed_edition) "
            "VALUES (?, ?, ?, ?, ?, ?, 'closed', ?, ?)",
            (row.bill_id, row.title, row.sponsor, row.house, row.stage, row.next_key_date,
             row.closed_note, edition),
        )
    else:
        conn.execute(
            "UPDATE bills_board SET status='closed', stage=?, closed_note=?, closed_edition=? "
            "WHERE bill_id=?",
            (row.stage, row.closed_note, edition, row.bill_id),
        )
    conn.commit()
    return True
