"""Tables for the US Congress monitor (phase 1, 9 October 2026): members,
bills with their cosponsors, House roll calls and every member's position,
and the week ahead (us_schedule, us_meetings, us_schedule_weeks); the
Congressional Record's floor speeches on our ground (us_record_days,
us_record_speeches, us_record_bills; phase 3a).

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

THE CURRENT CONGRESS IS A DATE, NOT A CONSTANT. Congress n sits from noon on
3 January of 1789 + 2(n - 1) (the Twentieth Amendment) to 3 January two
years later: the 119th from 3 January 2025, the 120th from 3 January 2027.
Its first session is the odd year, its second the even one. 1 and 2 January
of an odd year still belong to the old Congress. `congress_on` and
`session_on` are what the collector, the job script (`us_rollcalls.py
--print-congress`) and the edition read; nothing hard-codes 119 any more.

AMENDMENT PURPOSES (phase 1b): `us_divisions.amendment_key`,
`amendment_text` and `purpose_source` ('billstatus', keyless and first, or
'congress-api', keyed, for what BILLSTATUS has not explained yet). The rule
that uses them is in tools/us_rollcalls.py.
"""

from __future__ import annotations

import datetime
import json
import os
import re

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
    # THE WEEK AHEAD (tools/us_schedule.py, 9 October 2026). What is
    # scheduled, never what happened: the House floor list, committee
    # hearings and markups in both chambers, and the Senate's next sitting.
    # A row of us_schedule is one BILL at one scheduled event, keyed on the
    # bill KEY (never its title) and joined to us_bills for areas and
    # scores. A hearing that names no bill lives in us_meetings alone.
    """CREATE TABLE IF NOT EXISTS us_schedule (
        sched_key    TEXT PRIMARY KEY,   -- 'house-floor-2026-09-14/119/hr/28',
                                         -- 'house-cmte-119568/119/hr/4615'
        bill_key     TEXT NOT NULL,      -- '119/hr/28'
        chamber      TEXT NOT NULL,      -- 'house' / 'senate'
        kind         TEXT NOT NULL,      -- 'floor', 'markup', 'hearing', 'meeting'
        week_of      TEXT NOT NULL,      -- the Monday of the week, ISO
        date         TEXT,               -- the day, when the source gives one
                                         -- (the House floor list is by WEEK)
        meeting_key  TEXT,               -- us_meetings, for committee rows
        category     TEXT,               -- floor: 'suspension' / 'rule' / 'may be considered'
        legis_num    TEXT,               -- as the source printed it: 'H.R. 309'
        text         TEXT,               -- the source's own line for the item
        doc_url      TEXT,               -- the text the House posted for the week
        status       TEXT,               -- 'listed', 'removed', 'scheduled',
                                         -- 'postponed', 'cancelled'
        own_areas    TEXT,               -- JSON: matched on the line's OWN text
        matched_terms TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS us_meetings (
        meeting_key  TEXT PRIMARY KEY,   -- 'house-119568'; 'senate-SSJU-2026-09-17-10:00'
        chamber      TEXT NOT NULL,
        event_id     TEXT,               -- the House repository's EventID
        committee    TEXT,
        kind         TEXT,               -- 'markup', 'hearing', 'meeting'
        title        TEXT,
        date         TEXT,               -- ISO
        time         TEXT,
        location     TEXT,
        status       TEXT,               -- 'scheduled', 'postponed', 'cancelled'
        url          TEXT,
        bills        TEXT,               -- JSON list of bill KEYS named
        own_areas    TEXT,               -- JSON: matched on the title and bill lines
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # One row per (chamber, source, week) ASKED, whatever came back: a list,
    # nothing posted (the House answers 404 for a week it is out), or a
    # refusal. It is how the edition can say "the House is out" rather than
    # "nothing on our ground", and it moves on every run, recess included.
    """CREATE TABLE IF NOT EXISTS us_schedule_weeks (
        chamber      TEXT NOT NULL,
        source       TEXT NOT NULL,      -- 'floor' / 'committees'
        week_of      TEXT NOT NULL,      -- Monday, ISO
        status       TEXT,               -- 'listed', 'none', 'refused'
        items        INTEGER,            -- rows the source listed (all, not only ours)
        note         TEXT,               -- e.g. the Senate's "Convene for a pro forma session"
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (chamber, source, week_of)
    )""",
    "CREATE INDEX IF NOT EXISTS us_divisions_bill ON us_divisions (bill_key)",
    "CREATE INDEX IF NOT EXISTS us_schedule_bill ON us_schedule (bill_key)",
    "CREATE INDEX IF NOT EXISTS us_schedule_week ON us_schedule (week_of)",
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
    # THE CONGRESSIONAL RECORD (phase 3a, 9 October 2026), from
    # tools/us_record.py: GovInfo's CREC collection, one package per day,
    # one granule per segment of the day (a debate, a statement, a
    # resolution's text). The rule for what is stored and how it is
    # classified is documented once, in tools/us_record.py.
    #
    # One row per DAY asked of GovInfo, whatever it held: a pro forma day
    # with no speech is read, not missed.
    """CREATE TABLE IF NOT EXISTS us_record_days (
        package_id   TEXT PRIMARY KEY,   -- 'CREC-2026-09-17'; 'CREC-2025-01-03-v171'
        date         TEXT NOT NULL,      -- ISO, the issue's date
        congress     INTEGER,
        last_modified TEXT,              -- GovInfo's lastModified when read
        granules     INTEGER,            -- every granule in the day
        speech_granules INTEGER,         -- granules with a member speaking, procedure left out
        speeches     INTEGER,            -- member turns read (one member in one granule)
        ours         INTEGER,            -- of those, on our ground (stored)
        unresolved   INTEGER,            -- turns whose label named no member in the metadata
        status       TEXT,               -- 'read' / 'gap'
        note         TEXT,
        read_at      TEXT,               -- when the day was last read
        first_seen   TEXT,
        last_seen    TEXT                -- when the listing last showed it
    )""",
    # ONE ROW PER MEMBER PER GRANULE, ON OUR GROUND ONLY: everything a member
    # said in one segment of the day, joined. Keyed on the granule ID, never a
    # title. The text is NOT stored: an excerpt (the best-matching passage,
    # for the takeaway line and a quote) and the word count. The granule's
    # own page is the provenance.
    """CREATE TABLE IF NOT EXISTS us_record_speeches (
        speech_key   TEXT PRIMARY KEY,   -- 'CREC-2026-09-17-pt1-PgS4774-3/M001244'
        granule_id   TEXT NOT NULL,      -- 'CREC-2026-09-17-pt1-PgS4774-3'
        package_id   TEXT NOT NULL,
        date         TEXT NOT NULL,
        chamber      TEXT NOT NULL,      -- 'house' / 'senate'
        section      TEXT,               -- 'house', 'senate', 'extensions' (of Remarks)
        sub_class    TEXT,               -- GovInfo's subGranuleClass: 'SLEGISLATIVE', ...
        title        TEXT,               -- the granule's heading
        citation     TEXT,               -- '172 Cong. Rec. S4774'
        bioguide     TEXT,               -- NULL when the label named no known member
        speaker      TEXT,               -- the label as printed: 'Mrs. MOODY'
        name         TEXT,               -- 'Ashley Moody'
        party        TEXT,               -- AT THE TIME, from the granule's metadata
        state        TEXT,
        words        INTEGER,
        bill_keys    TEXT,               -- JSON: bills the granule cites, its subject first
        subject_bill TEXT,               -- the bill the granule is ABOUT (title or headline), or NULL
        own_areas    TEXT,               -- JSON: matched on the speech's own words and heading
        areas        TEXT,               -- JSON: own, plus a watched or subject bill (the rule)
        areas_from   TEXT,               -- 'own' / 'watch' / 'bill'
        matched_terms TEXT,
        tier         INTEGER,
        excerpt      TEXT,               -- the best-matching passage, clipped
        url          TEXT,               -- the granule's details page on govinfo.gov
        triage_score INTEGER,
        why_it_matters TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Every bill a SPEECH granule cites, ours or not, keyed on the bill KEY
    # ('119/hr/28'): the per-bill count of floor speeches reads this.
    # context is GovInfo's: TITLE and HEADERLINE mean the granule is about
    # the bill; FIRSTPARAGRAPH and OTHER are citations.
    """CREATE TABLE IF NOT EXISTS us_record_bills (
        granule_id   TEXT NOT NULL,
        bill_key     TEXT NOT NULL,
        context      TEXT,               -- the strongest context seen in the granule
        date         TEXT,
        chamber      TEXT,
        speakers     INTEGER,            -- members speaking in the granule
        PRIMARY KEY (granule_id, bill_key)
    )""",
    "CREATE INDEX IF NOT EXISTS us_record_speeches_date ON us_record_speeches (date)",
    "CREATE INDEX IF NOT EXISTS us_record_speeches_member ON us_record_speeches (bioguide)",
    "CREATE INDEX IF NOT EXISTS us_record_bills_bill ON us_record_bills (bill_key)",
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
          "us_schedule", "us_meetings", "us_schedule_weeks",
          "us_fr_documents", "us_court_cases", "us_court_orders",
          "us_record_days", "us_record_speeches", "us_record_bills")

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
    # Phase 1b (9 October 2026): a House amendment vote's amendment, from
    # Congress.gov. amendment_checked is the date it was asked for, so a vote
    # with no amendment record is asked once, not every week.
    ("us_divisions", "amendment_key", "TEXT"),      # '119/hamdt/150'
    ("us_divisions", "amendment_text", "TEXT"),     # description | purpose
    ("us_divisions", "amendment_checked", "TEXT"),
    # Which source gave amendment_text: 'billstatus' (the bulk files, keyless,
    # tried first) or 'congress-api' (keyed, only for what BILLSTATUS has not
    # explained yet). Added with the keyless route, 9 October 2026.
    ("us_divisions", "purpose_source", "TEXT"),
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


# --- does a vote stand on its own amendment purpose? -------------------------
#
# Shared by the collector (tools/us_rollcalls.classify_division, where the
# rule is documented) and the edition, so both read it the same way.

EN_BLOC = re.compile(r"\ben bloc\b|comprised of the following amendments", re.I)


def has_own_purpose(amendment_text, chamber="house"):
    """True for a HOUSE vote whose amendment text is a real purpose, not an
    en bloc list of amendment numbers."""
    return bool(amendment_text) and (chamber or "house") == "house" \
        and not EN_BLOC.search(amendment_text)


# --- which Congress is sitting ----------------------------------------------

FIRST_CONGRESS_YEAR = 1789


def _as_date(day=None):
    if day is None:
        return datetime.date.today()
    if isinstance(day, str):
        return datetime.date.fromisoformat(day[:10])
    return day


def congress_start(congress):
    """3 January of the Congress's first year: 119 -> 2025-01-03."""
    return datetime.date(FIRST_CONGRESS_YEAR + 2 * (int(congress) - 1), 1, 3)


def congress_end(congress):
    """The day the Congress ends, which is the next one's first day."""
    return congress_start(int(congress) + 1)


def congress_on(day=None):
    """The Congress sitting on a date: 2026-10-09 -> 119, 2027-01-02 -> 119,
    2027-01-03 -> 120."""
    d = _as_date(day)
    year = d.year
    if year % 2 == 1 and d < datetime.date(year, 1, 3):
        year -= 1
    return (year - FIRST_CONGRESS_YEAR) // 2 + 1


def session_on(day=None):
    """1 in the Congress's odd (first) year, 2 in its even one."""
    d = _as_date(day)
    return 1 if d.year == congress_start(congress_on(d)).year else 2


def congress_ended(congress, day=None):
    """True once the Congress is over: every bill of it not enacted has fallen."""
    return _as_date(day) >= congress_end(congress)


# Weeks after a new Congress starts during which the old one is collected
# too: the last votes and bill statuses of the old Congress keep arriving in
# BILLSTATUS (a bill presented before 3 January can be signed after it, and
# the Library of Congress catches up on actions for weeks).
CATCH_UP_DAYS = 45


def catch_up_congress(day=None):
    """The previous Congress while its records are still settling, else None."""
    d = _as_date(day)
    current = congress_on(d)
    if (d - congress_start(current)).days < CATCH_UP_DAYS:
        return current - 1
    return None


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


def clean_key(value):
    """An API key as a secrets file may hold it: pasted from Markdown, the
    key in config/secrets.yaml arrived wrapped in backticks (9 October 2026)
    and every keyed request answered 401 or 403. Surrounding whitespace,
    quotes and backticks are dropped; None or empty stays None."""
    v = (value or "").strip().strip("`'\"").strip()
    return v or None


def dumps(values):
    return json.dumps(values or [])
