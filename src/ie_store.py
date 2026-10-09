"""Tables for the Ireland (Oireachtas) monitor (phase 1, 9 October 2026):
members with their party spells, bills with their sponsors and the debate
sections that carry them, divisions in the Dail, the Seanad and committee,
and every member's vote.

See docs/ireland-scope.md for what was measured and why. The schema follows
the US precedent (src/us_store.py): its own module, idempotent statements,
created by db.init_db so every store carries it and db.TABLES stays true.

PHASE 2 (9 October 2026) adds parliamentary questions (tools/ie_questions.py),
debate speeches (tools/ie_debates.py) and the week ahead (tools/ie_schedule.py).

SEPARATION GUARANTEE. Nothing outside tools/ie_*.py writes these tables,
and nothing here touches another jurisdiction's table.

KEYS. A member is the Oireachtas memberCode ('Shay-Brennan.D.2024-11-29'),
the identifier every Oireachtas dataset shares (votes, sponsors, questions,
debates). A bill is '<year>/<number>', '2026/10': the Oireachtas numbers
bills per calendar year across both Houses, and the pair is unique across
all 6,048 bills the API holds (measured 9 October 2026). A division is its
path in the Oireachtas URI, 'dail/34/2026-10-06/vote_214' (committee:
'committee/<committee>/<date>/vote_N'): vote IDs restart, so the bare
'vote_214' names 2 or more divisions (220 distinct IDs across 429 Dail votes).

PARTY IS STORED PER VOTE, as in Canada and the US. The Oireachtas vote
record carries no party at all, so `ie_votes.party` is derived from the
member's party spell (ie_member_parties) covering the vote's date in that
House. A vote with no covering spell stores NULL and records a gap; it is
never filled with the member's latest party.

A BILL LAPSES WITH ITS HOUSE, AND THE API STILL CALLS IT 'CURRENT'. Every
bill lapses when the Dail is dissolved (Seanad bills when that Seanad ends),
and a lapsed bill can be restored to the order paper by motion in the new
House at the stage it reached. On 9 October 2026, 102 of the 266 bills the
API marks 'Current' had lapsed and never been restored. So the board reads
`ie_bills.alive`, derived in tools/ie_rollcalls.py, never `status`.
"""

from __future__ import annotations

import json
import os

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ie_members (
        member_code  TEXT PRIMARY KEY,   -- 'Shay-Brennan.D.2024-11-29'
        name         TEXT,
        first_name   TEXT,
        last_name    TEXT,
        house        TEXT,               -- 'dail' / 'seanad', latest membership
        house_no     INTEGER,            -- 34 / 27
        party        TEXT,               -- latest spell; see ie_votes.party
        represents   TEXT,               -- constituency (Dail) or panel (Seanad)
        start_date   TEXT,               -- latest membership's start
        end_date     TEXT,               -- NULL while sitting
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_member_parties (
        member_code  TEXT NOT NULL,
        house_key    TEXT NOT NULL,      -- 'dail/34', 'seanad/27'
        party        TEXT NOT NULL,      -- 'Fianna Fáil', as the Oireachtas prints it
        start_date   TEXT NOT NULL,
        end_date     TEXT,               -- NULL: the spell is open
        PRIMARY KEY (member_code, house_key, party, start_date)
    )""",
    """CREATE TABLE IF NOT EXISTS ie_bills (
        bill_key     TEXT PRIMARY KEY,   -- '2026/10'
        year         INTEGER NOT NULL,
        number       INTEGER NOT NULL,
        title        TEXT,               -- shortTitleEn, the title it carries NOW
        title_ga     TEXT,               -- shortTitleGa
        long_title   TEXT,               -- longTitleEn, tags stripped
        source       TEXT,               -- 'Government' / 'Private Member'
        bill_type    TEXT,               -- 'Public' / 'Private'
        origin_house TEXT,               -- 'dail' / 'seanad'
        status       TEXT,               -- the API's word; NOT a liveness test
        last_stage   TEXT,               -- 'Second Stage'
        last_stage_house TEXT,           -- 'dail/34'
        last_stage_at TEXT,
        lapsed_at    TEXT,               -- latest 'Bill Lapsed' event
        restored_at  TEXT,               -- latest 'Bill Restored' event
        alive        INTEGER,            -- derived: see the module docstring
        act          TEXT,               -- 'Act 32 of 2026' once enacted
        act_title    TEXT,
        last_updated TEXT,               -- the record's own lastUpdated
        url          TEXT,
        areas        TEXT,               -- JSON list; taxonomy + watchlist-ie by key
        matched_terms TEXT,              -- JSON list
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_sponsors (
        bill_key     TEXT NOT NULL,
        sponsor      TEXT NOT NULL,      -- memberCode, or the office for a Government bill
        member_code  TEXT,               -- NULL for a Government bill sponsored by office
        name         TEXT,
        office       TEXT,               -- 'Minister for Health' (Government bills)
        is_primary   INTEGER,
        PRIMARY KEY (bill_key, sponsor)
    )""",
    """CREATE TABLE IF NOT EXISTS ie_bill_debates (
        debate_uri   TEXT NOT NULL,      -- '.../debateRecord/dail/2026-09-22/debate/main'
        debate_section TEXT NOT NULL,    -- 'dbsect_10'
        bill_key     TEXT NOT NULL,
        date         TEXT,
        title        TEXT,               -- 'X Bill 2026: Second Stage'
        PRIMARY KEY (debate_uri, debate_section, bill_key)
    )""",
    """CREATE TABLE IF NOT EXISTS ie_divisions (
        division_key TEXT PRIMARY KEY,   -- 'dail/34/2026-10-06/vote_214'
        chamber      TEXT NOT NULL,      -- 'dail' / 'seanad' / 'committee'
        house_key    TEXT,               -- 'dail/34'; the parent House for a committee
        committee    TEXT,               -- committee name, NULL in plenary
        date         TEXT,
        vote_id      TEXT,               -- 'vote_214' (restarts; not a key)
        debate_title TEXT,               -- 'X Bill 2025: Report Stage (Resumed)'
        debate_uri   TEXT,
        debate_section TEXT,
        subject      TEXT,               -- 'Amendment put:' -- usually without the amendment
        outcome      TEXT,               -- the Oireachtas's own word, never derived
        ta           INTEGER,            -- Tá (yes)
        nil          INTEGER,            -- Níl (no)
        staon        INTEGER,            -- Staon (abstain)
        tellers      TEXT,
        vote_note    TEXT,
        bill_key     TEXT,               -- joined by debate section ID, or NULL
        debate_bill  TEXT,               -- the bill the debate title names, as printed: text, not a key
        own_areas    TEXT,               -- JSON: matched on the division's OWN text
        areas        TEXT,               -- JSON: own + the bill's
        matched_terms TEXT,
        tier         INTEGER,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_votes (
        division_key TEXT NOT NULL,
        member_code  TEXT NOT NULL,
        position     TEXT,               -- 'Yes' (Tá) / 'No' (Níl) / 'Abstain' (Staon)
        party        TEXT,               -- AT THE VOTE, from ie_member_parties; NULL if none covers it
        PRIMARY KEY (division_key, member_code)
    )""",
    # --- phase 2 (9 October 2026): questions, debates, the week ahead -------
    #
    # STORED ON OUR GROUND ONLY. About 8,000 questions and 15,000 utterances
    # a sitting month; a row is written only when its own text is on our
    # ground (questions) or by the speech rule in tools/ie_debates.py. The
    # volumes read are kept per week in ie_windows, so the measurement
    # survives without the rows.
    """CREATE TABLE IF NOT EXISTS ie_questions (
        question_key TEXT PRIMARY KEY,   -- '2026-10-07/pq_1' (the URI path; numbers restart daily)
        ref          TEXT,               -- '[70836/26]' as printed: the PQ reference
        date         TEXT,
        qtype        TEXT,               -- 'written' / 'oral'
        number       INTEGER,
        house_key    TEXT,               -- 'dail/34' (the Seanad has no PQs)
        member_code  TEXT,               -- the asker
        asker        TEXT,
        party        TEXT,               -- AT THE DATE, from ie_member_parties; NULL if none
        department   TEXT,               -- the API's 'to': 'Justice'
        minister     TEXT,               -- the office asked: 'Minister for Health'
        heading      TEXT,               -- the debate section title: 'Protected Disclosures'
        question     TEXT,               -- the question, '1. Deputy X asked the Minister...' cut, <= 600 chars
        answered     INTEGER,            -- 1 when the record carries an answer
        answer_by    TEXT,               -- the label: 'Minister for Health (Deputy Jennifer Carroll MacNeill)'
        answer_shape TEXT,               -- src/ni_answers.shape: 'data not held', '' = substantive
        answer_takeaway TEXT,            -- ONE sentence, <= 200 chars; never the answer
        debate_uri   TEXT,
        debate_section TEXT,
        areas        TEXT,               -- JSON: the QUESTION's own text, offices struck first
        matched_terms TEXT,
        tier         INTEGER,
        url          TEXT,               -- oireachtas.ie/en/debates/question/<date>/<n>/
        triage_score INTEGER,
        why_it_matters TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_speeches (
        speech_key   TEXT PRIMARY KEY,   -- '<record>/<dbsect_N>/<memberCode>': all one member said in one section
        date         TEXT,
        chamber      TEXT,               -- 'dail' / 'seanad' / 'committee'
        house_key    TEXT,               -- 'dail/34'; a committee's parent House
        committee    TEXT,               -- committee name, NULL in plenary
        debate_uri   TEXT,               -- the day's record: '.../debateRecord/dail/2026-10-07/debate/main'
        debate_section TEXT,             -- 'dbsect_12'
        section_title TEXT,              -- 'Health (Assisted Human Reproduction) Bill 2024: Second Stage'
        debate_type  TEXT,               -- the API's: 'debate', 'motion', 'statement', ...
        member_code  TEXT,
        speaker      TEXT,
        party        TEXT,               -- AT THE DATE; NULL if no spell covers it
        role         TEXT,               -- the label when an office speaks: 'Minister for Health (Deputy ...)'
        words        INTEGER,
        turns        INTEGER,            -- utterances folded into this row
        bill_key     TEXT,               -- the section's bill, by ID (see tools/ie_debates.py)
        own_areas    TEXT,               -- JSON: the member's OWN WORDS, passage by passage
        areas        TEXT,               -- JSON: own, or what was lent (areas_from)
        areas_from   TEXT,               -- 'own' / 'watch' / 'bill' / 'heading'
        matched_terms TEXT,
        tier         INTEGER,
        excerpt      TEXT,               -- the best-matching passage, <= 400 chars; never the speech
        url          TEXT,
        triage_score INTEGER,
        why_it_matters TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_windows (
        feed         TEXT NOT NULL,      -- 'questions' / 'debates-house' / 'debates-committee'
        week_of      TEXT NOT NULL,      -- the Monday
        status       TEXT,               -- 'read' / 'gap' / 'partial'
        records      INTEGER,            -- questions, or debate records, read
        items        INTEGER,            -- questions, or member speeches, read
        ours         INTEGER,            -- stored on our ground
        by_area      TEXT,               -- JSON {area: n} of what was stored
        read_at      TEXT,
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (feed, week_of)
    )""",
    """CREATE TABLE IF NOT EXISTS ie_schedule (
        item_key     TEXT PRIMARY KEY,   -- '<chamber>/<date>/<HH:MM>/<n>': a slot, not a key to join on
        chamber      TEXT,               -- 'dail' / 'seanad' / 'committee'
        date         TEXT,
        time         TEXT,
        committee    TEXT,
        text         TEXT,               -- the line as scheduled, <= 400 chars
        bill_key     TEXT,               -- from the bill LINK on the line ('/en/bills/bill/2026/19/'), or NULL
        bill_named   TEXT,               -- a bill the line names without a link: text, not a key
        own_areas    TEXT,               -- JSON: the line's own text
        matched_terms TEXT,
        url          TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ie_schedule_days (
        chamber      TEXT NOT NULL,
        date         TEXT NOT NULL,
        status       TEXT,               -- 'listed' / 'none' (no business posted)
        items        INTEGER,
        note         TEXT,               -- 'Dáil Éireann resumes on Tuesday, 13 October 2026'
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (chamber, date)
    )""",
    "CREATE INDEX IF NOT EXISTS ie_questions_date ON ie_questions (date)",
    "CREATE INDEX IF NOT EXISTS ie_speeches_date ON ie_speeches (date)",
    "CREATE INDEX IF NOT EXISTS ie_speeches_bill ON ie_speeches (bill_key)",
    "CREATE INDEX IF NOT EXISTS ie_schedule_bill ON ie_schedule (bill_key)",
    "CREATE INDEX IF NOT EXISTS ie_divisions_bill ON ie_divisions (bill_key)",
    "CREATE INDEX IF NOT EXISTS ie_votes_member ON ie_votes (member_code)",
    "CREATE INDEX IF NOT EXISTS ie_bill_debates_bill ON ie_bill_debates (bill_key)",
)

TABLES = ("ie_members", "ie_member_parties", "ie_bills", "ie_sponsors",
          "ie_bill_debates", "ie_divisions", "ie_votes",
          "ie_questions", "ie_speeches", "ie_windows", "ie_schedule", "ie_schedule_days")


# Added with the edition (9 October 2026). The judge's score and why-line
# (tools/ie_triage.py), scored once, ever, as every judge here is; and the
# amendment behind an amendment vote, read from the debate transcript
# (phase 1b, tools/ie_rollcalls.py): amendment_text NULL = not read yet,
# '' = read, but no mover found before the division.
ADDED_COLUMNS = (
    ("ie_bills", "introduced", "TEXT"),        # First Stage date (the edition's "new")
    ("ie_bills", "triage_score", "INTEGER"),
    ("ie_bills", "why_it_matters", "TEXT"),
    ("ie_divisions", "triage_score", "INTEGER"),
    ("ie_divisions", "why_it_matters", "TEXT"),
    ("ie_divisions", "amendment_ref", "TEXT"),
    ("ie_divisions", "amendment_text", "TEXT"),
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


# --- the Ireland watchlist, applied by bill KEY ---------------------------
#
# Applied by key for the same reason as the US list: a title term would
# claim every bill whose title shares the words, and Irish bills change
# their title on the way through (the Incitement to Violence or Hatred and
# Hate Offences Bill 2022 is stored today as the Criminal Justice (Hate
# Offences) Bill 2022). A key is exact and survives a renaming.

_WATCH = {}


def watchlist(path=None):
    """{bill_key: (areas, why)} from config/watchlist-ie.yaml."""
    import yaml
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "config", "watchlist-ie.yaml")
    if path not in _WATCH:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        _WATCH[path] = {str(k): (list(v.get("areas") or []), v.get("why"))
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
    return json.dumps(values or [], ensure_ascii=False)


# --- phase 2: reading by WEEK, newest first, within a budget ---------------
#
# Questions and debates are read a week at a time (Monday to Sunday). A week
# is due when it was never read, when its read stopped (budget or gap), or
# when it ends within `reread_days` of today (answers and transcripts are
# revised for a week or two after the day). Due weeks go newest first, so a
# budget-capped backfill fills the weeks the edition needs before the old
# ones, and the rest drains on later runs.

def monday(day):
    import datetime
    d = datetime.date.fromisoformat(str(day)[:10])
    return d - datetime.timedelta(days=d.weekday())


def due_weeks(conn, feed, start, today, reread_days):
    """Mondays (ISO strings) to read, newest first."""
    import datetime
    first, last = monday(start), monday(today)
    fresh = datetime.date.fromisoformat(today) - datetime.timedelta(days=reread_days)
    done = {w for (w,) in conn.execute(
        "SELECT week_of FROM ie_windows WHERE feed=? AND status='read'", (feed,))}
    out, week = [], last
    while week >= first:
        sunday = week + datetime.timedelta(days=6)
        if week.isoformat() not in done or sunday >= fresh:
            out.append(week.isoformat())
        week -= datetime.timedelta(days=7)
    return out


def record_week(conn, feed, week_of, status, records, items, ours, by_area, today):
    conn.execute(
        "INSERT INTO ie_windows (feed, week_of, status, records, items, ours, by_area, read_at, "
        "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(feed, week_of) DO UPDATE "
        "SET status=excluded.status, records=excluded.records, items=excluded.items, "
        "ours=excluded.ours, by_area=excluded.by_area, read_at=excluded.read_at, "
        "last_seen=excluded.last_seen",
        (feed, week_of, status, records, items, ours,
         json.dumps({str(k): v for k, v in sorted(by_area.items())}), today, today, today))


def stamp(conn, heartbeat, today, note):
    """A STEP heartbeat in source_runs (tools/coverage.py AWAITING_FIRST_RUN)."""
    conn.execute("INSERT OR REPLACE INTO source_runs (source, last_run, run_id, note) "
                 "VALUES (?,?,?,?)", (heartbeat, today, os.environ.get("GITHUB_RUN_ID"), note))
