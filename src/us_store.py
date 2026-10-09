"""Tables for the US Congress monitor (phase 1, 9 October 2026): members,
bills with their cosponsors, House roll calls and every member's position.

See docs/us-scope.md for what was measured and why. The schema follows the
Canadian precedent (src/ca_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

SEPARATION GUARANTEE. Nothing outside tools/us_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS. A member is their Bioguide ID, the one identifier every US source
shares (the Clerk's roll calls, BILLSTATUS sponsors and cosponsors, the
congress-legislators crosswalk). A bill is '<congress>/<type>/<number>',
'119/hr/28': bill numbers restart every Congress, and a bill that is
re-introduced in the next one is a different bill with a new number.

PARTY IS STORED PER VOTE, as in Canada: `us_votes.party` is the party the
Clerk printed on that roll call. `us_members.party` is only the latest seen.

A BILL DIES WITH ITS CONGRESS. Every pending bill falls when the Congress
ends (3 January of odd years). Nothing in a bill's own record says so, so
`us_bills.congress` is what the board reads, never `latest_action`.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS us_members (
        bioguide     TEXT PRIMARY KEY,   -- 'S001214'
        name         TEXT,
        party        TEXT,               -- latest seen; see us_votes.party
        state        TEXT,               -- two-letter postal code
        district     TEXT,               -- House only; 'AL' for at-large
        chamber      TEXT,               -- 'house' / 'senate', latest term
        lis_id       TEXT,               -- the Senate's own member ID
        as_of        TEXT,               -- date of the fact stored
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS us_bills (
        bill_key     TEXT PRIMARY KEY,   -- '119/hr/28'
        congress     INTEGER NOT NULL,
        bill_type    TEXT NOT NULL,      -- hr, s, hres, sres, hjres, sjres, hconres, sconres
        number       INTEGER NOT NULL,
        title        TEXT,               -- the display title
        short_titles TEXT,               -- JSON list: every other title the record carries
        policy_area  TEXT,               -- CRS policy area
        subjects     TEXT,               -- JSON list of CRS legislative subjects
        summary      TEXT,               -- latest CRS summary, tags stripped
        introduced   TEXT,
        sponsor      TEXT,               -- bioguide
        sponsor_name TEXT,
        cosponsors   INTEGER,            -- current, withdrawn excluded
        latest_action TEXT,
        latest_action_at TEXT,
        law          TEXT,               -- 'Public Law 119-12' once enacted
        update_date  TEXT,               -- the record's own updateDate
        areas        TEXT,               -- JSON list; taxonomy + watchlist-us by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS us_cosponsors (
        bill_key     TEXT NOT NULL,
        bioguide     TEXT NOT NULL,
        sponsored_at TEXT,
        withdrawn_at TEXT,               -- a public reversal, kept rather than deleted
        original     INTEGER,
        PRIMARY KEY (bill_key, bioguide)
    )""",
    """CREATE TABLE IF NOT EXISTS us_divisions (
        division_key TEXT PRIMARY KEY,   -- 'house-119-1-240': chamber-congress-session-roll
        chamber      TEXT NOT NULL,      -- 'house' (the Senate is phase 2)
        congress     INTEGER NOT NULL,
        session      INTEGER NOT NULL,
        roll         INTEGER NOT NULL,
        date         TEXT,               -- ISO date
        legis_num    TEXT,               -- as the Clerk prints it: 'H R 8800'
        bill_key     TEXT,               -- '119/hr/8800', or NULL (quorum, adjourn)
        question     TEXT,               -- 'On Agreeing to the Amendment'
        description  TEXT,               -- often blank on amendment votes
        vote_type    TEXT,               -- 'YEA-AND-NAY', '2/3 YEA-AND-NAY', ...
        result       TEXT,               -- the Clerk's own words, never derived
        amendment_num TEXT,
        amendment_author TEXT,           -- 'Roy of Texas Amendment No. 1'
        yeas         INTEGER,
        nays         INTEGER,
        present      INTEGER,
        not_voting   INTEGER,
        own_areas    TEXT,               -- JSON: matched on the vote's OWN text
        areas        TEXT,               -- JSON: own + the bill's (see us_rollcalls)
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS us_votes (
        division_key TEXT NOT NULL,
        bioguide     TEXT NOT NULL,
        position     TEXT,               -- 'Yea' / 'Nay' / 'Present' / 'Not Voting'
        party        TEXT,               -- AT THE VOTE: 'R', 'D', 'I'
        state        TEXT,
        PRIMARY KEY (division_key, bioguide)
    )""",
    "CREATE INDEX IF NOT EXISTS us_divisions_bill ON us_divisions (bill_key)",
    "CREATE INDEX IF NOT EXISTS us_votes_member ON us_votes (bioguide)",
    # EXECUTIVE ACTIONS (Christopher, 9 October 2026): the Federal Register's
    # presidential documents, final rules and proposed rules, from
    # tools/us_federal_register.py. Keyed on the FR document number, the one
    # identifier the Register never reissues ('2025-02194').
    """CREATE TABLE IF NOT EXISTS us_fr_documents (
        document_number TEXT PRIMARY KEY, -- '2025-02194'
        doc_type     TEXT NOT NULL,      -- 'Presidential Document' / 'Rule' / 'Proposed Rule'
        subtype      TEXT,               -- 'Executive Order', 'Proclamation', 'Memorandum', ...
        title        TEXT,
        abstract     TEXT,               -- the agency's summary; NULL on presidential documents
        action       TEXT,               -- 'Final rule.', 'Notice of proposed rulemaking.'
        agencies     TEXT,               -- JSON list of agency names
        topics       TEXT,               -- JSON list of CFR index terms
        publication_date TEXT NOT NULL,  -- ISO date in the Register
        signing_date TEXT,               -- presidential documents only
        effective_on TEXT,
        comments_close_on TEXT,          -- a proposed rule's comment deadline, as printed
        eo_number    TEXT,               -- executive orders only
        citation     TEXT,               -- '90 FR 8771'
        docket_ids   TEXT,               -- JSON list
        comment_url  TEXT,               -- regulations.gov, where the agency gives one
        html_url     TEXT,
        significant  INTEGER,            -- OIRA 'significant' flag, where printed
        areas        TEXT,               -- JSON list (shared taxonomy)
        matched_terms TEXT,
        tier         INTEGER,
        triage_score INTEGER,
        why_it_matters TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS us_fr_documents_pub ON us_fr_documents (publication_date)",
    "CREATE INDEX IF NOT EXISTS us_fr_documents_close ON us_fr_documents (comments_close_on)",
    # THE SUPREME COURT (Christopher, 9 October 2026), from tools/us_courts.py:
    # opinions from the term's slip-opinion page and certiorari grants read
    # out of the order lists. One table, two kinds of row:
    #   'opinion/<term>/<R-number>'  e.g. 'opinion/25/62' (the Court's own
    #                                running number within the term)
    #   'grant/<docket>'             e.g. 'grant/24-539'
    """CREATE TABLE IF NOT EXISTS us_court_cases (
        case_key     TEXT PRIMARY KEY,
        kind         TEXT NOT NULL,      -- 'opinion' / 'grant'
        term         TEXT,               -- October Term, two digits: '25' is OT2025
        docket       TEXT,               -- '24-539', or an application '25A312'
        case_name    TEXT,               -- 'Chiles v. Salazar'
        title        TEXT,               -- the docket's full caption, where read
        decided      TEXT,               -- ISO date: the opinion's, or the grant's order date
        summary      TEXT,               -- the Court's one-line holding, or the question presented
        justice      TEXT,               -- the opinion's author code ('R', 'PC', 'EK')
        citation     TEXT,               -- '609 U.S. 422' once assigned
        url          TEXT,               -- the opinion PDF, or the docket page
        order_url    TEXT,               -- the order list that granted it
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        triage_score INTEGER,
        why_it_matters TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Every order PDF read, once: an order list is final when published, so
    # this is what makes the grant reader incremental.
    """CREATE TABLE IF NOT EXISTS us_court_orders (
        url          TEXT PRIMARY KEY,
        term         TEXT,
        order_date   TEXT,               -- ISO date, from the file name (MMDDYY)
        kind         TEXT,               -- 'Order List' / 'Miscellaneous Order'
        grants       INTEGER,            -- plenary certiorari grants found in it
        read_at      TEXT
    )""",
)

TABLES = ("us_members", "us_bills", "us_cosponsors", "us_divisions", "us_votes",
          "us_fr_documents", "us_court_cases", "us_court_orders")

MEMBER_UPSERT = (
    "INSERT INTO us_members (bioguide, name, party, state, district, chamber, "
    "lis_id, as_of, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) "
    "ON CONFLICT(bioguide) DO UPDATE SET "
    "name=CASE WHEN {newer} THEN COALESCE(excluded.name, us_members.name) ELSE us_members.name END, "
    "party=CASE WHEN {newer} THEN COALESCE(excluded.party, us_members.party) ELSE us_members.party END, "
    "state=CASE WHEN {newer} THEN COALESCE(excluded.state, us_members.state) ELSE us_members.state END, "
    "district=CASE WHEN {newer} THEN COALESCE(excluded.district, us_members.district) "
    "ELSE us_members.district END, "
    "chamber=CASE WHEN {newer} THEN COALESCE(excluded.chamber, us_members.chamber) "
    "ELSE us_members.chamber END, "
    "lis_id=COALESCE(excluded.lis_id, us_members.lis_id), "
    "as_of=CASE WHEN {newer} THEN excluded.as_of ELSE us_members.as_of END, "
    "last_seen=excluded.last_seen").format(
        newer="COALESCE(excluded.as_of, '') >= COALESCE(us_members.as_of, '')")


# Added after the first live run (9 October 2026): the judge's score and
# why-line (tools/us_triage.py). Scored once, ever, as every judge here is.
ADDED_COLUMNS = (
    ("us_bills", "triage_score", "INTEGER"),
    ("us_bills", "why_it_matters", "TEXT"),
    ("us_divisions", "triage_score", "INTEGER"),
    ("us_divisions", "why_it_matters", "TEXT"),
)


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    for table, column, kind in ADDED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if column not in have:
            conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(table, column, kind))
    conn.commit()
    return conn


# --- the US watchlist, applied by bill KEY ---------------------------------
#
# Canada's watchlist is matched on titles. The US one is not, on purpose:
# its first entry is the Equality Act, and "Equality Act" as a title term
# would also claim the Refund Equality Act, the TRICARE Equality Act and
# every Supplemental Security Income Equality Act. A key is exact.

_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-us.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-us.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {k: (list(v.get("areas") or []), v.get("why"))
                        for k, v in (raw.get("bills") or {}).items()}
    return _WATCH[path]


def add_watch_areas(res, bill_key, path=None):
    """Union a watched bill's areas into a FilterResult, in place, and say so
    in watchlist_hits so the stored row shows where the area came from."""
    hit = watchlist(path).get(bill_key)
    if not hit:
        return res
    areas, _why = hit
    res.issue_areas = sorted(set(res.issue_areas or []) | set(areas))
    res.watchlist_hits = list(res.watchlist_hits or []) + ["watch:" + bill_key]
    if res.tier is None:
        res.tier = 2
    return res


def dumps(values):
    return json.dumps(values or [])
