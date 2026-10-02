"""Tables for the Canadian monitor: House divisions and bills (phase 1),
Hansard, petitions, Senate votes and the Canada Gazette (phase 2), and the
Supreme Court of Canada (judgments and leave to appeal).

WHY A MODULE OF ITS OWN. Every other jurisdiction's schema lives in
`src/db.py`. These tables were kept here while the Canadian monitor was
groundwork, so a scoping build could not collide with work in progress on the
shared schema. Since phase 3 (26 September 2026) `db.init_db` calls
`ensure_schema` and the names are in `db.TABLES`: tests/test_db.py fails any
table written but not declared, and had been failing on these since phase 1.
The statements stay here, idempotent, with their own column migrations.

SEPARATION GUARANTEE. Nothing outside tools/ca_*.py reads or writes these
tables, and nothing here touches a Westminster, devolved, EU or German table.

PARTY IS STORED PER VOTE. The House publishes each participant's caucus on
the division itself, so `ca_votes.party` is the party the member voted in,
not the one they sit in today. `ca_members.party` is only the latest seen.
The Northern Ireland roster taught that joining a past vote to today's party
misattributes every floor-crosser (src/ni_store.py).
"""

from __future__ import annotations

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ca_members (
        person_id    TEXT PRIMARY KEY,   -- the House's PersonId
        name         TEXT,
        party        TEXT,               -- latest caucus seen; see ca_votes.party
        constituency TEXT,
        province     TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_divisions (
        division_key TEXT PRIMARY KEY,   -- '<chamber>-<parl>-<session>-<number>'
        chamber      TEXT NOT NULL,      -- 'commons' or 'senate'
        parliament   INTEGER NOT NULL,
        session      INTEGER NOT NULL,
        number       INTEGER NOT NULL,
        date         TEXT,               -- ISO date-time as the House gives it
        subject      TEXT,
        result       TEXT,               -- the House's own words, never derived
        yeas         INTEGER,
        nays         INTEGER,
        paired       INTEGER,
        doc_type     TEXT,               -- 'Legislative Process', 'Supply', ...
        bill_number  TEXT,               -- 'C-9', or NULL for a motion
        areas        TEXT,               -- JSON list; English taxonomy + watchlist-ca
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        positions_fetched INTEGER NOT NULL DEFAULT 0,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_votes (
        division_key TEXT NOT NULL,
        person_id    TEXT NOT NULL,
        position     TEXT,               -- 'Yea' / 'Nay' / 'Paired'
        party        TEXT,               -- caucus AT THE VOTE
        PRIMARY KEY (division_key, person_id)
    )""",
    """CREATE TABLE IF NOT EXISTS ca_bills (
        bill_key     TEXT PRIMARY KEY,   -- '<parl>-<session>/<number>'
        parliament   INTEGER NOT NULL,
        session      INTEGER NOT NULL,
        number       TEXT NOT NULL,      -- 'C-34', 'S-209'
        legisinfo_id TEXT,
        long_title   TEXT,
        short_title  TEXT,
        status       TEXT,
        is_government INTEGER,
        sponsor      TEXT,
        latest_event TEXT,
        latest_event_at TEXT,
        royal_assent_at TEXT,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Phase 2 (26 September 2026): Hansard and petitions.
    #
    # Every sitting READ gets a row whatever it held, so "nothing on our
    # ground that week" can be told apart from "that week was never read".
    """CREATE TABLE IF NOT EXISTS ca_sittings (
        sitting_key  TEXT PRIMARY KEY,   -- '<parl>-<session>-<number>'
        parliament   INTEGER NOT NULL,
        session      INTEGER NOT NULL,
        number       INTEGER NOT NULL,
        date         TEXT,
        interventions INTEGER,           -- every Intervention in the XML
        chair        INTEGER,            -- the presiding officer's, counted not stored
        stored       INTEGER,            -- speeches on our ground
        unresolved   INTEGER,            -- stored speeches with no person_id
        chars        INTEGER,
        read_at      TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_speeches (
        speech_id    TEXT PRIMARY KEY,   -- the Hansard Intervention id
        sitting_key  TEXT NOT NULL,
        date         TEXT,
        time         TEXT,               -- 'HH:MM', the last Hansard timestamp before it
        rubric       TEXT,               -- 'Government Orders', 'Oral Questions', ...
        subject      TEXT,               -- SubjectOfBusinessTitle
        bill_number  TEXT,
        kind         TEXT,               -- the House's Type: Debate/Question/Answer/Interjection
        db_id        TEXT,               -- Hansard Affiliation DbId: a ROLE, not a person
        person_id    TEXT,               -- resolved to ca_members, or NULL, never guessed
        speaker      TEXT,               -- the label exactly as printed
        party        TEXT,               -- as printed in the label, when it is
        text         TEXT,
        areas        TEXT,
        matched_terms TEXT,
        excerpt      TEXT,
        first_seen   TEXT
    )""",
    # Hansard's DbId identifies a member IN A ROLE: Kevin Lamoureux speaking
    # as a parliamentary secretary has a different DbId from his members'
    # PersonId, and a minister's later interventions are labelled only
    # "Minister of Finance". The map is learned from labels that carry a
    # riding, and kept, so a bare role label resolves on a later sitting.
    """CREATE TABLE IF NOT EXISTS ca_speaker_roles (
        db_id        TEXT PRIMARY KEY,
        person_id    TEXT NOT NULL,
        label        TEXT,
        how          TEXT,               -- 'riding' or 'name': which key resolved it
        first_seen   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_petitions (
        petition_id  TEXT PRIMARY KEY,   -- 'e-7000' or '451-00001', the page's own number
        presented_number TEXT,           -- '451-01121' once presented; NULL while open
        kind         TEXT,               -- 'E-petition' / 'Paper petition'
        category     TEXT,               -- the House's subject, e.g. 'Health'
        keywords     TEXT,               -- JSON list of the House's index terms
        addressee    TEXT,
        prayer       TEXT,
        opened       TEXT,
        closed       TEXT,
        presented    TEXT,
        mp_person_id TEXT,               -- the sponsoring/presenting member's PersonId
        mp_name      TEXT,
        response_tabled TEXT,
        response_by  TEXT,
        response_text TEXT,              -- on our ground only
        signatures   INTEGER,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Senate (phase 2b). Senators have their own id space on sencanada.ca,
    # so their rows in ca_votes carry person_id 'senator-<id>' and can never
    # collide with a House PersonId. Divisions share ca_divisions with
    # chamber='senate'; the Senate publishes no division number, so `number`
    # is the vote's details id.
    """CREATE TABLE IF NOT EXISTS ca_senators (
        person_id    TEXT PRIMARY KEY,   -- 'senator-<sencanada id>'
        name         TEXT,               -- 'Martin, Yonah', as the Senate prints it
        affiliation  TEXT,               -- latest seen; ca_votes.party is at the vote
        province     TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Canada Gazette (phase 2b). Part I carries notices and PROPOSED
    # regulations with their comment period; Part II carries made
    # regulations (SOR) and statutory instruments (SI). Every issue READ gets
    # a row, as every Hansard sitting does.
    """CREATE TABLE IF NOT EXISTS ca_gazette_issues (
        issue_key    TEXT PRIMARY KEY,   -- 'p1-2026-09-26'
        part         INTEGER NOT NULL,
        date         TEXT NOT NULL,
        title        TEXT,
        url          TEXT,
        items        INTEGER,
        ours         INTEGER,
        read_at      TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ca_gazette_items (
        item_key     TEXT PRIMARY KEY,   -- the item's URL, with its #anchor for a notice
        issue_key    TEXT NOT NULL,
        part         INTEGER,
        date         TEXT,
        section      TEXT,               -- 'Government notices', 'Proposed Regulations', ...
        department   TEXT,               -- the index's sub-heading
        title        TEXT,
        url          TEXT,
        kind         TEXT,               -- 'regulation'/'extra'/'document' (own page) or 'notice' (anchor on a shared page)
        registration TEXT,               -- 'SOR/2026-184' for Part II
        comment_days INTEGER,            -- Part I: 'within N days after the date of publication'
        comment_until TEXT,              -- date + comment_days
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        excerpt      TEXT,
        matched_on   TEXT,               -- 'body', 'title' (a notice whose anchor was not found) or 'pdf' (a PDF-only issue's English column)
        text         TEXT,               -- a NOTICE's own text; a regulation's lives at url
        first_seen   TEXT
    )""",
    # Supreme Court of Canada (tools/ca_courts.py, 2 October 2026). CONTEXT
    # ONLY: a judgment never places a parliamentarian and never enters a 5CA
    # sheet; a stance file may cite one in a reading's `why`.
    #
    # Every judgment READ gets a row, ours or not, so the feed's re-listing
    # of an updated old judgment (Ford v. Quebec, 1988, beside 2026 SCC 31)
    # is recognised by its id and never read twice.
    """CREATE TABLE IF NOT EXISTS ca_judgments (
        judgment_id  TEXT PRIMARY KEY,   -- Lexum item id ('14637'); a Federal Court row is 'fc-<id>'
        court        TEXT NOT NULL,      -- 'SCC' or 'FC'
        citation     TEXT,               -- '2015 SCC 5'
        scr          TEXT,               -- '[2015] 1 SCR 331', once reported
        docket       TEXT,               -- the SCC case number; joins ca_leave.docket
        date         TEXT,
        title        TEXT,
        subjects     TEXT,               -- JSON list, the Court's own ('Constitutional law')
        judges       TEXT,               -- JSON list, as printed ('McLachlin, Beverley')
        on_appeal_from TEXT,             -- 'British Columbia'
        interveners  TEXT,               -- JSON list of names; NULL = not parsed, [] = none
        headnote     TEXT,               -- from 'Indexed as' up to 'Cases Cited': what is matched
        excerpt      TEXT,               -- the strongest qualifying passage
        matched_on   TEXT,               -- 'headnote', 'opening' (no Cases Cited found) or 'reasons' (FC)
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        triage_score INTEGER,            -- tools/ca_triage.py, once ever
        why_it_matters TEXT,
        url          TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    # Applications for leave to appeal: the early-warning layer. A GRANTED
    # leave is classified on the Registrar's case summary from the docket
    # page; a dismissed one is stored with no summary (the lower court's
    # ruling stands, and the leave text names only the parties).
    """CREATE TABLE IF NOT EXISTS ca_leave (
        docket       TEXT PRIMARY KEY,   -- the SCC case number
        lexum_id     TEXT,               -- the leave document's Lexum id: a feed item is read once
        status       TEXT,               -- 'Granted' / 'Dismissed', the Court's word
        decided      TEXT,
        title        TEXT,
        on_appeal_from TEXT,
        summary      TEXT,               -- Registrar's keywords + summary (granted only)
        excerpt      TEXT,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        url          TEXT,               -- the docket page
        first_seen   TEXT                -- written once per decision: no sighting column
    )""",
    "CREATE INDEX IF NOT EXISTS ca_judgments_docket ON ca_judgments (docket)",
    "CREATE INDEX IF NOT EXISTS ca_leave_lexum ON ca_leave (lexum_id)",
    "CREATE INDEX IF NOT EXISTS ca_gazette_items_issue ON ca_gazette_items (issue_key)",
    "CREATE INDEX IF NOT EXISTS ca_speeches_sitting ON ca_speeches (sitting_key)",
    "CREATE INDEX IF NOT EXISTS ca_speeches_person ON ca_speeches (person_id)",
    "CREATE INDEX IF NOT EXISTS ca_petitions_presented ON ca_petitions (presented_number)",
    "CREATE INDEX IF NOT EXISTS ca_divisions_date ON ca_divisions (date)",
    "CREATE INDEX IF NOT EXISTS ca_votes_person ON ca_votes (person_id)",
)


# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS
# never alters an existing table, so a store made before the column existed
# would silently lack it; each is added here if missing.
ADDED_COLUMNS = (
    ("ca_divisions", "abstentions", "INTEGER"),   # the Senate records them; the House does not
    # 2 October 2026: Senate debates and committee evidence join ca_speeches.
    # chamber: 'commons' (NULL on older rows means commons) or 'senate';
    # forum: 'floor' (NULL means floor) or 'committee'; committee: the
    # acronym (JUST, AMAD, LCJC) when forum is committee. A speech is
    # activity in the 5CA, never direction, wherever it was given.
    ("ca_speeches", "chamber", "TEXT"),
    ("ca_speeches", "forum", "TEXT"),
    ("ca_speeches", "committee", "TEXT"),
    # Phase 3 (the 5CA). Sponsoring a private member's bill is a chosen act
    # of advancing a text, so the sponsor must join to a member by id, never
    # by name. LEGISinfo gives SponsorPersonId for House bills.
    ("ca_bills", "sponsor_person_id", "TEXT"),
    # 1 = on the House's CURRENT roster (members/en/search/xml with no
    # parliament), 0 = has left. NULL = never checked. The 5CA lists everyone
    # who cast a tracked vote and labels the departed former, so it needs to
    # know which is which without guessing from dates the House never gives.
    ("ca_members", "sitting", "INTEGER"),
    # The Canadian judge (tools/ca_triage.py, 27 September 2026): petitions
    # were matched by the taxonomy but never scored, and 1,600-odd "on our
    # ground" included tier-2 noise (US tariffs, IRGC agents) that only a
    # judgement can separate. Same two columns every German table carries.
    ("ca_petitions", "triage_score", "INTEGER"),
    ("ca_petitions", "why_it_matters", "TEXT"),
    # The business date the member's name/party/riding were read AS OF: the
    # division's date, or a roster membership's FromDateTime. A source only
    # overwrites them if it is at least as recent. Without it the backfill
    # to 2010 (read after the current session) left sitting MPs under their
    # 2011 names and ridings: "Michelle Rempel", Kyle Seeback in Brampton
    # West (29 September 2026).
    ("ca_members", "as_of", "TEXT"),
)


# A member's name, party and riding come from the most recent source only:
# a division overwrites them if it is at least as recent as what the row was
# read as of (ca_members.as_of), and never otherwise. ca_votes.party keeps
# the party AT EACH VOTE whatever happens here.
MEMBER_UPSERT = (
    "INSERT INTO ca_members (person_id, name, party, constituency, province, "
    "first_seen, last_seen, as_of) VALUES (?,?,?,?,?,?,?,?) "
    "ON CONFLICT(person_id) DO UPDATE SET "
    "name=CASE WHEN {newer} THEN COALESCE(excluded.name, ca_members.name) ELSE ca_members.name END, "
    "party=CASE WHEN {newer} THEN COALESCE(excluded.party, ca_members.party) ELSE ca_members.party END, "
    "constituency=CASE WHEN {newer} THEN COALESCE(excluded.constituency, ca_members.constituency) "
    "ELSE ca_members.constituency END, "
    "province=CASE WHEN {newer} THEN COALESCE(excluded.province, ca_members.province) "
    "ELSE ca_members.province END, "
    "as_of=CASE WHEN {newer} THEN excluded.as_of ELSE ca_members.as_of END, "
    "last_seen=excluded.last_seen").format(
        newer="COALESCE(excluded.as_of, '') >= COALESCE(ca_members.as_of, '')")


def ensure_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)
    for table, column, kind in ADDED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if column not in have:
            conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(table, column, kind))
    conn.commit()
    return conn


_BILL_KEYS = {}


def bill_key_areas(path=None):
    """{'<parl>-<sess>/<number>': [areas]} from config/watchlist-ca.yaml.

    The watchlist loader matches a bill by its TITLE in the subject line,
    which cannot reach a division whose stored title is generic: Bill C-16
    (2016, gender identity) is printed as "An Act to amend the Canadian
    Human Rights Act and the Criminal Code" with nothing after it. So the
    key, which the file already carries, is honoured too: any division on
    that bill in that session takes its areas (2 October 2026). Used by
    tools/ca_rollcalls.py (Commons) and tools/ca_senate.py (Senate)."""
    import os
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "config", "watchlist-ca.yaml")
    if path not in _BILL_KEYS:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _BILL_KEYS[path] = {str(k): list(v.get("areas") or [])
                            for k, v in (raw.get("bills") or {}).items()}
    return _BILL_KEYS[path]


def add_bill_key_areas(res, parliament, session, bill_number, path=None):
    """Merge a watched bill KEY's areas into a FilterResult, in place."""
    if not bill_number:
        return res
    key = "{0}-{1}/{2}".format(parliament, session, bill_number)
    extra = bill_key_areas(path).get(key)
    if extra:
        res.issue_areas = sorted(set(res.issue_areas or []) | set(extra))
        res.tier = res.tier or 1
        if key not in (res.watchlist_hits or []):
            res.watchlist_hits = list(res.watchlist_hits or []) + [key]
    return res
