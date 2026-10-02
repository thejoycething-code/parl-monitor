"""Tables for the Canadian PROVINCIAL legislatures (tools/prov_*.py).

Scoped in docs/canada-provinces-scope.md ("Proposed common design"). One
set of tables serves all thirteen legislatures, keyed by `prov`: ab, bc,
mb, nb, nl, ns, nt, nu, on, pe, qc, sk, yt.

SEPARATION GUARANTEE. Nothing outside tools/prov_*.py, src/ingest/prov_* and
src/prov_speeches.py (the Hansard speeches engine) reads or writes these tables, and nothing here touches a federal (ca_*),
Westminster, devolved, EU or German table. `db.init_db` calls
`ensure_schema` and the names are in `db.TABLES` from day one: the federal
tables were left out of db.TABLES until phase 3 and tests/test_db.py failed
on them the whole time.

THE SIGHTING COLUMN IS `last_seen` (renamed from `last_read` on 3 October
2026, when the Provinces weekly workflow began running these collectors).
tests/test_coverage.py treats every table with a `last_seen` or
`captured_at` column as a scheduled feed that tools/coverage.py must watch,
which is why the column was kept as `last_read` until something scheduled
them. MEASURED, per table, for tools/coverage.py: prov_members and
prov_bills are re-stamped on every weekly run (Alberta, BC and Manitoba
re-read their whole roster or bill listing each time), so they are
heartbeats; prov_divisions is re-stamped only when its record, or a bill
page naming a voice decision, is read again, so it is write-once in practice
and goes quiet in recess. `ensure_schema` renames the old column in a store
that still carries it (the scratch stores of the smoke runs) and is a no-op
on a second call.

PARTY IS A FACT OF THE VOTE, NOT A JOIN. `prov_member_terms` keeps party
over time (Alberta's dated affiliations, Saskatchewan's Hansard cover list
of the sitting day); `prov_votes.party_at_vote` is filled only from a term
dated to cover the vote. Where the source cannot date a party (BC's members
API gives one party per parliament, so BC dates it from each Hansard
issue's list of members instead) it stays NULL -- the NI and federal
lesson is that today's party joined to an old vote misattributes every
floor-crosser.

AN UNRESOLVED NAME IS STORED WITH A NULL MEMBER, NEVER GUESSED. The printed
label is kept exactly as printed in `raw_label`.

THE TALLY CHECK. Every provincial source prints its totals. A division whose
labels, once resolved, do not account for the printed totals one member per
label is a GAP: `positions_ok = 0`, a row in `gaps`, and the votes are kept
for inspection but never trusted for placement. Only `positions_ok = 1`
places anyone.

A VOICE VOTE IS NOT AN EMPTY ROLL-CALL. A decision taken without a recorded
division is stored with `kind = 'voice'`, NULL totals, NULL positions_ok and
no prov_votes rows, so "passed on voice, no member record" can be said and
an empty 5CA never implies one.
"""

from __future__ import annotations

import datetime
import json

PROVINCES = ("ab", "bc", "mb", "nb", "nl", "ns", "nt", "nu", "on", "pe",
             "qc", "sk", "yt")

POSITIONS = ("Yea", "Nay", "Abstain")

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS prov_members (
        prov         TEXT NOT NULL,
        member_key   TEXT NOT NULL,      -- the legislature's own id (AB mid, BC memberId) or a slug
        name         TEXT,               -- 'Danielle Smith'
        surname      TEXT,               -- 'Smith', 'Calahoo Stonehouse', 'de Jonge'
        given        TEXT,
        riding       TEXT,               -- latest seen; prov_member_terms is dated
        party        TEXT,               -- latest seen; prov_votes.party_at_vote is at the vote
        sitting      INTEGER,            -- 1 on the latest roster read, 0 former, NULL unknown
        page_url     TEXT,               -- the member's own page, as linked from a listing (qc)
        first_seen   TEXT,
        last_seen    TEXT,
        PRIMARY KEY (prov, member_key)
    )""",
    """CREATE TABLE IF NOT EXISTS prov_member_terms (
        prov         TEXT NOT NULL,
        member_key   TEXT NOT NULL,
        legislature  INTEGER,
        party        TEXT,
        riding       TEXT,
        start        TEXT,               -- ISO date; NULL = open
        end          TEXT,               -- ISO date; NULL = open
        party_dated  INTEGER NOT NULL DEFAULT 0,  -- 1 when the SOURCE dates the party
        source       TEXT                -- 'roster', 'member-page', 'hansard-cover', 'api'
    )""",
    "CREATE INDEX IF NOT EXISTS prov_member_terms_key ON prov_member_terms (prov, member_key)",
    """CREATE TABLE IF NOT EXISTS prov_divisions (
        division_key TEXT PRIMARY KEY,   -- '<prov>-<leg>-<sess>-<date>-<seq>'
        prov         TEXT NOT NULL,
        legislature  INTEGER,
        session      INTEGER,
        date         TEXT,
        seq          TEXT,
        kind         TEXT NOT NULL,      -- 'recorded' or 'voice'
        question     TEXT,               -- the record's own words, trimmed
        vote_on      TEXT,               -- 'motion' / 'amendment' / 'subamendment', as printed
        bill_key     TEXT,               -- prov_bills.bill_key or NULL
        stage        TEXT,               -- 'First Reading', 'Third Reading', 'Committee of the Whole'
        result       TEXT,               -- the legislature's own words, never derived
        yeas         INTEGER,            -- PRINTED totals
        nays         INTEGER,
        abstentions  INTEGER,
        source_url   TEXT,
        areas        TEXT,               -- JSON list
        matched_terms TEXT,
        tier         INTEGER,
        excerpt      TEXT,
        positions_ok INTEGER,            -- 1 tally matched, 0 gap, NULL voice
        tally_note   TEXT,               -- why it did not match
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS prov_divisions_prov_date ON prov_divisions (prov, date)",
    # Every bill a division decided (2 October 2026). prov_divisions.bill_key
    # stays the PRIMARY bill, so everything that reads it is unchanged; this
    # table holds the primary too (is_primary=1) and any other bill decided by
    # the SAME question: Alberta, 23 March 2022, "The question was put on the
    # approval of Bill 7, Appropriation Act, 2022 ($), and Bill 8, ...". A
    # reader that asks "which divisions decided bill X" asks here, through
    # ON_BILL, so a division on two watched bills shows under both.
    """CREATE TABLE IF NOT EXISTS prov_division_bills (
        division_key TEXT NOT NULL,
        bill_key     TEXT NOT NULL,
        is_primary   INTEGER NOT NULL DEFAULT 0,   -- 1 for prov_divisions.bill_key
        PRIMARY KEY (division_key, bill_key)
    )""",
    "CREATE INDEX IF NOT EXISTS prov_division_bills_bill ON prov_division_bills (bill_key)",
    """CREATE TABLE IF NOT EXISTS prov_votes (
        division_key TEXT NOT NULL,
        position     TEXT NOT NULL,      -- 'Yea' / 'Nay' / 'Abstain'
        ordinal      INTEGER NOT NULL,   -- order within the position's list as printed
        raw_label    TEXT NOT NULL,      -- exactly as printed
        member_key   TEXT,               -- NULL when unresolved; never guessed
        how          TEXT,               -- 'surname', 'surname+riding', 'initial', 'full-name', or why not
        party_at_vote TEXT,              -- from a term that DATES the party, else NULL
        PRIMARY KEY (division_key, position, ordinal)
    )""",
    "CREATE INDEX IF NOT EXISTS prov_votes_member ON prov_votes (member_key)",
    """CREATE TABLE IF NOT EXISTS prov_bills (
        bill_key     TEXT PRIMARY KEY,   -- '<prov>-<leg>-<sess>/<number>' or '/x-<slug>' if unnumbered
        prov         TEXT NOT NULL,
        legislature  INTEGER,
        session      INTEGER,
        number       TEXT,
        title_en     TEXT,
        title_fr     TEXT,
        sponsor      TEXT,
        sponsor_key  TEXT,               -- prov_members.member_key, by id never by name
        is_government INTEGER,
        bill_type    TEXT,
        stages       TEXT,               -- JSON [{stage, date, status, division}]
        latest_stage TEXT,
        royal_assent TEXT,
        page_url     TEXT,
        text_url     TEXT,
        text_read    INTEGER NOT NULL DEFAULT 0,
        areas        TEXT,
        matched_terms TEXT,
        tier         INTEGER,
        excerpt      TEXT,
        first_seen   TEXT,
        last_seen    TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS prov_sittings (
        sitting_key  TEXT PRIMARY KEY,   -- '<prov>-<leg>-<sess>-<date>[-<part>]'
        prov         TEXT NOT NULL,
        date         TEXT,
        record_url   TEXT,
        divisions    INTEGER,            -- recorded divisions parsed
        voice        INTEGER,            -- voice decisions recorded
        speeches_stored INTEGER,
        read_at      TEXT,
        status       TEXT                -- 'ok', 'gap' (a tally failed) or 'unreadable'
    )""",
    # Hansard speeches (src/prov_speeches.py, tools/prov_speeches.py, 2 October
    # 2026). ONLY SPEECHES ON OUR GROUND ARE STORED, as in ca_speeches; every
    # day read gets a prov_speech_sittings row with its totals whatever it held.
    """CREATE TABLE IF NOT EXISTS prov_speeches (
        speech_id    TEXT PRIMARY KEY,   -- '<sitting_key>-<seq>': seq counts every turn, chair included
        prov         TEXT NOT NULL,
        sitting_key  TEXT,               -- prov_speech_sittings.sitting_key
        date         TEXT,
        subject      TEXT,               -- the debate heading the speech sits under
        bill_key     TEXT,               -- prov_bills.bill_key, from the heading, never from the speech
        member_key   TEXT,               -- NULL when unresolved; never guessed
        speaker_label TEXT,              -- exactly as printed
        language     TEXT,               -- 'en' or 'fr'
        text         TEXT,
        areas        TEXT,
        excerpt      TEXT,
        first_seen   TEXT,
        legislature  INTEGER,
        session      INTEGER,
        seq          INTEGER,
        rubric       TEXT,               -- 'Oral Questions', 'Orders of the Day', ...
        how          TEXT,               -- how the speaker resolved, or why not
        matched_terms TEXT,
        tier         INTEGER,
        source_url   TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS prov_speeches_member ON prov_speeches (prov, member_key)",
    # One row per Hansard day (or part) READ for speeches. Kept apart from
    # prov_sittings on purpose: tools/prov_collect.py resumes the VOTE
    # collectors from prov_sittings and skips a record URL already read
    # there, and British Columbia and Newfoundland read divisions from the
    # very Hansard file read here -- a shared table would let one reader
    # mark the other's work done. No sighting column: written once per day.
    """CREATE TABLE IF NOT EXISTS prov_speech_sittings (
        sitting_key  TEXT PRIMARY KEY,   -- '<prov>-<leg>-<sess>-<date>[-<part>]'
        prov         TEXT NOT NULL,
        legislature  INTEGER,
        session      INTEGER,
        date         TEXT,
        record_url   TEXT,
        turns        INTEGER,            -- every speaker turn in the day
        chair        INTEGER,            -- presiding officer and collective labels: counted, not stored
        members      INTEGER,            -- the other turns
        resolved     INTEGER,            -- of those, resolved to a prov_members key
        stored       INTEGER,            -- speeches on our ground stored
        unresolved   INTEGER,            -- of those, stored with no member_key
        chars        INTEGER,
        read_at      TEXT,
        status       TEXT,               -- 'ok', 'gap' (read, but something was owed) or 'unreadable'
        note         TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS prov_speech_sittings_prov_date ON prov_speech_sittings (prov, date)",
)

# page_url (2 October 2026, Quebec): the member page a roster gap is
# completed from (prov_qc.complete_members) -- linked from depcir, never built.
# prov_speeches' columns after the first eight (2 October 2026): the table
# shipped empty from the foundation, and a store created then carries only those.
ADDED_COLUMNS = (("prov_members", "page_url", "TEXT"),
                 ("prov_speeches", "legislature", "INTEGER"),
                 ("prov_speeches", "session", "INTEGER"),
                 ("prov_speeches", "seq", "INTEGER"),
                 ("prov_speeches", "rubric", "TEXT"),
                 ("prov_speeches", "how", "TEXT"),
                 ("prov_speeches", "matched_terms", "TEXT"),
                 ("prov_speeches", "tier", "INTEGER"),
                 ("prov_speeches", "source_url", "TEXT"))


# The sighting column's old name (before the Provinces weekly, 3 October 2026).
RENAMED_COLUMNS = (("prov_members", "last_read", "last_seen"),
                   ("prov_divisions", "last_read", "last_seen"),
                   ("prov_bills", "last_read", "last_seen"))


def ensure_schema(conn):
    for table, old, new in RENAMED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if old in have and new not in have:
            conn.execute("ALTER TABLE {0} RENAME COLUMN {1} TO {2}".format(table, old, new))
    for stmt in SCHEMA:
        conn.execute(stmt)
    for table, column, kind in ADDED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info({0})".format(table))}
        if column not in have:
            conn.execute("ALTER TABLE {0} ADD COLUMN {1} {2}".format(table, column, kind))
    conn.commit()
    return conn


def today():
    return datetime.date.today().isoformat()


# -- keys -------------------------------------------------------------------

def division_key(prov, legislature, session, date, seq):
    return "{0}-{1}-{2}-{3}-{4}".format(prov, legislature, session, date, seq)


def bill_key(prov, legislature, session, number):
    return "{0}-{1}-{2}/{3}".format(prov, legislature, session, number)


def sitting_key(prov, legislature, session, date, part=None):
    key = "{0}-{1}-{2}-{3}".format(prov, legislature, session, date)
    return key + "-" + part if part else key


# -- the tally check --------------------------------------------------------

def tally(printed, votes):
    """(ok, note) for one recorded division.

    printed: {'Yea': 47, 'Nay': 35, 'Abstain': None}; a None total is not
    printed by that source and is not checked.
    votes: [{'position', 'raw_label', 'member_key', ...}].

    ok means, for every printed total: as many labels as the total, every
    label resolved, and no member resolved twice anywhere in the division.
    Anything else is a gap, with the reasons in `note`."""
    problems = []
    for position in POSITIONS:
        want = printed.get(position)
        rows = [v for v in votes if v["position"] == position]
        if want is None:
            if rows:
                problems.append("{0}: {1} name(s) but no printed total".format(position, len(rows)))
            continue
        if len(rows) != want:
            problems.append("{0}: {1} name(s) read, {2} printed".format(position, len(rows), want))
        unresolved = [v["raw_label"] for v in rows if not v.get("member_key")]
        if unresolved:
            problems.append("{0}: unresolved {1}".format(
                position, ", ".join(repr(u) for u in unresolved[:6])
                + (" (+{0})".format(len(unresolved) - 6) if len(unresolved) > 6 else "")))
    seen = {}
    for v in votes:
        k = v.get("member_key")
        if not k:
            continue
        if k in seen:
            problems.append("{0} resolved twice ({1!r} and {2!r})".format(
                k, seen[k], v["raw_label"]))
        seen[k] = v["raw_label"]
    if not printed or all(printed.get(p) is None for p in POSITIONS):
        problems.append("no printed totals")
    return (not problems), "; ".join(problems) or None


# -- writes -----------------------------------------------------------------

def upsert_member(conn, prov, member_key, name=None, surname=None, given=None,
                  riding=None, party=None, sitting=None, when=None, page_url=None):
    when = when or today()
    conn.execute(
        "INSERT INTO prov_members (prov, member_key, name, surname, given, riding, "
        "party, sitting, page_url, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(prov, member_key) DO UPDATE SET "
        "name=COALESCE(excluded.name, prov_members.name), "
        "surname=COALESCE(excluded.surname, prov_members.surname), "
        "given=COALESCE(excluded.given, prov_members.given), "
        "riding=COALESCE(excluded.riding, prov_members.riding), "
        "party=COALESCE(excluded.party, prov_members.party), "
        "sitting=COALESCE(excluded.sitting, prov_members.sitting), "
        "page_url=COALESCE(excluded.page_url, prov_members.page_url), "
        "last_seen=excluded.last_seen",
        (prov, member_key, name, surname, given, riding, party, sitting, page_url, when, when))


def replace_terms(conn, prov, member_key, terms, source, legislature=None):
    """Replace one member's terms from one source with `terms`
    ([{legislature, party, riding, start, end, party_dated}]).

    With `legislature`, only that legislature's terms from that source are
    replaced. A collector that reads one roster PER LEGISLATURE must pass it:
    without it, reading the 31st Legislature's roster deleted the member-page
    terms an earlier read had stored for the 29th and 30th, so a 2015-2023
    member (Jason Nixon, Rachel Notley) held no term in those legislatures
    and every re-read of their divisions failed (Alberta, 2 October 2026)."""
    if legislature is None:
        conn.execute("DELETE FROM prov_member_terms WHERE prov=? AND member_key=? AND source=?",
                     (prov, member_key, source))
    else:
        conn.execute("DELETE FROM prov_member_terms WHERE prov=? AND member_key=? AND source=? "
                     "AND legislature=?", (prov, member_key, source, legislature))
    for t in terms:
        conn.execute(
            "INSERT INTO prov_member_terms (prov, member_key, legislature, party, "
            "riding, start, end, party_dated, source) VALUES (?,?,?,?,?,?,?,?,?)",
            (prov, member_key, t.get("legislature"), t.get("party"), t.get("riding"),
             t.get("start"), t.get("end"), int(bool(t.get("party_dated"))), source))


def extend_term(conn, prov, member_key, legislature, party, riding, date, source,
                party_dated=True):
    """Widen the matching term to cover `date`, or start one. Used where the
    roster is read per sitting (Saskatchewan's Hansard cover list): a term is
    exactly the span of sittings it was SEEN on, never assumed beyond."""
    row = conn.execute(
        "SELECT rowid, start, end FROM prov_member_terms WHERE prov=? AND member_key=? "
        "AND legislature IS ? AND party IS ? AND riding IS ? AND source=?",
        (prov, member_key, legislature, party, riding, source)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO prov_member_terms (prov, member_key, legislature, party, riding, "
            "start, end, party_dated, source) VALUES (?,?,?,?,?,?,?,?,?)",
            (prov, member_key, legislature, party, riding, date, date,
             int(bool(party_dated)), source))
        return
    rowid, start, end = row
    conn.execute("UPDATE prov_member_terms SET start=?, end=? WHERE rowid=?",
                 (min(start or date, date), max(end or date, date), rowid))


def division_bill_keys(d):
    """The bills of one division dict, primary first: d['bill_key'] and then
    d['also_bill_keys'] (other bills decided by the same question)."""
    out = [d["bill_key"]] if d.get("bill_key") else []
    for key in d.get("also_bill_keys") or []:
        if key and key not in out:
            out.append(key)
    return out


# "Did a division decide this bill?" -- the primary column OR the link table.
# Rows stored before prov_division_bills existed carry only the column, so
# both are asked. Bind the bill key TWICE: ... WHERE {ON_BILL} AND date=?
ON_BILL = ("(bill_key=? OR division_key IN "
           "(SELECT division_key FROM prov_division_bills WHERE bill_key=?))")


def linked_bills(conn, division_key):
    """Every bill a stored division decided, primary first."""
    rows = conn.execute("SELECT bill_key FROM prov_division_bills WHERE division_key=? "
                        "ORDER BY is_primary DESC, bill_key", (division_key,)).fetchall()
    if rows:
        return [r[0] for r in rows]
    row = conn.execute("SELECT bill_key FROM prov_divisions WHERE division_key=?",
                       (division_key,)).fetchone()
    return [row[0]] if row and row[0] else []


def store_division(conn, d, when=None):
    """Write one division (a dict) and, if recorded, its votes.

    Re-reading a record replaces the division's votes wholesale, so a roster
    fix that resolves a label is picked up by the next read."""
    when = when or today()
    conn.execute(
        "INSERT INTO prov_divisions (division_key, prov, legislature, session, date, "
        "seq, kind, question, vote_on, bill_key, stage, result, yeas, nays, "
        "abstentions, source_url, areas, matched_terms, tier, excerpt, "
        "positions_ok, tally_note, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(division_key) DO UPDATE SET kind=excluded.kind, "
        "question=excluded.question, vote_on=excluded.vote_on, "
        "bill_key=excluded.bill_key, stage=excluded.stage, result=excluded.result, "
        "yeas=excluded.yeas, nays=excluded.nays, abstentions=excluded.abstentions, "
        "source_url=excluded.source_url, areas=excluded.areas, "
        "matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "excerpt=excluded.excerpt, positions_ok=excluded.positions_ok, "
        "tally_note=excluded.tally_note, last_seen=excluded.last_seen",
        (d["division_key"], d["prov"], d.get("legislature"), d.get("session"),
         d.get("date"), str(d.get("seq")), d["kind"], d.get("question"),
         d.get("vote_on"), d.get("bill_key"), d.get("stage"), d.get("result"),
         d.get("yeas"), d.get("nays"), d.get("abstentions"), d.get("source_url"),
         json.dumps(d.get("areas") or []), json.dumps(d.get("matched_terms") or []),
         d.get("tier"), d.get("excerpt"), d.get("positions_ok"), d.get("tally_note"),
         when, when))
    conn.execute("DELETE FROM prov_division_bills WHERE division_key=?", (d["division_key"],))
    for k, key in enumerate(division_bill_keys(d)):
        conn.execute("INSERT OR IGNORE INTO prov_division_bills (division_key, bill_key, is_primary) "
                     "VALUES (?,?,?)", (d["division_key"], key, 1 if k == 0 and d.get("bill_key") else 0))
    conn.execute("DELETE FROM prov_votes WHERE division_key=?", (d["division_key"],))
    if d["kind"] != "recorded":
        return
    for v in d.get("votes") or []:
        conn.execute(
            "INSERT INTO prov_votes (division_key, position, ordinal, raw_label, "
            "member_key, how, party_at_vote) VALUES (?,?,?,?,?,?,?)",
            (d["division_key"], v["position"], v["ordinal"], v["raw_label"],
             v.get("member_key"), v.get("how"), v.get("party_at_vote")))


def store_bill(conn, b, when=None):
    when = when or today()
    conn.execute(
        "INSERT INTO prov_bills (bill_key, prov, legislature, session, number, "
        "title_en, title_fr, sponsor, sponsor_key, is_government, bill_type, stages, "
        "latest_stage, royal_assent, page_url, text_url, text_read, areas, "
        "matched_terms, tier, excerpt, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(bill_key) DO UPDATE SET "
        "title_en=COALESCE(excluded.title_en, prov_bills.title_en), "
        "title_fr=COALESCE(excluded.title_fr, prov_bills.title_fr), "
        "sponsor=COALESCE(excluded.sponsor, prov_bills.sponsor), "
        "sponsor_key=COALESCE(excluded.sponsor_key, prov_bills.sponsor_key), "
        "is_government=COALESCE(excluded.is_government, prov_bills.is_government), "
        "bill_type=COALESCE(excluded.bill_type, prov_bills.bill_type), "
        "stages=COALESCE(excluded.stages, prov_bills.stages), "
        "latest_stage=COALESCE(excluded.latest_stage, prov_bills.latest_stage), "
        "royal_assent=COALESCE(excluded.royal_assent, prov_bills.royal_assent), "
        "page_url=COALESCE(excluded.page_url, prov_bills.page_url), "
        "text_url=COALESCE(excluded.text_url, prov_bills.text_url), "
        "text_read=MAX(excluded.text_read, prov_bills.text_read), "
        # A bill classified on its TEXT is not overwritten by a later
        # title-only sighting (a division naming it, say).
        "areas=CASE WHEN excluded.text_read >= prov_bills.text_read THEN excluded.areas ELSE prov_bills.areas END, "
        "matched_terms=CASE WHEN excluded.text_read >= prov_bills.text_read THEN excluded.matched_terms ELSE prov_bills.matched_terms END, "
        "tier=CASE WHEN excluded.text_read >= prov_bills.text_read THEN excluded.tier ELSE prov_bills.tier END, "
        "excerpt=CASE WHEN excluded.text_read >= prov_bills.text_read THEN excluded.excerpt ELSE prov_bills.excerpt END, "
        "last_seen=excluded.last_seen",
        (b["bill_key"], b["prov"], b.get("legislature"), b.get("session"), b.get("number"),
         b.get("title_en"), b.get("title_fr"), b.get("sponsor"), b.get("sponsor_key"),
         b.get("is_government"), b.get("bill_type"),
         json.dumps(b["stages"]) if b.get("stages") is not None else None,
         b.get("latest_stage"), b.get("royal_assent"), b.get("page_url"), b.get("text_url"),
         int(bool(b.get("text_read"))), json.dumps(b.get("areas") or []),
         json.dumps(b.get("matched_terms") or []), b.get("tier"), b.get("excerpt"),
         when, when))


def store_sitting(conn, prov, key, date, url, divisions=0, voice=0, status="ok",
                  speeches=None, when=None):
    conn.execute(
        "INSERT OR REPLACE INTO prov_sittings (sitting_key, prov, date, record_url, "
        "divisions, voice, speeches_stored, read_at, status) VALUES (?,?,?,?,?,?,?,?,?)",
        (key, prov, date, url, divisions, voice, speeches, when or today(), status))


def sitting_done(conn, url):
    """True when this record was read cleanly before. A record with a gap or
    an unreadable file is read again: it stays owed."""
    row = conn.execute("SELECT status FROM prov_sittings WHERE record_url=? "
                       "ORDER BY read_at DESC LIMIT 1", (url,)).fetchone()
    return bool(row) and row[0] == "ok"


def bill_areas(conn, key):
    """(areas, terms, tier) stored for a bill, or ([], [], None)."""
    if not key:
        return [], [], None
    row = conn.execute("SELECT areas, matched_terms, tier FROM prov_bills WHERE bill_key=?",
                       (key,)).fetchone()
    if not row:
        return [], [], None
    return json.loads(row[0] or "[]"), json.loads(row[1] or "[]"), row[2]


def summary(conn, prov):
    one = lambda sql: conn.execute(sql, (prov,)).fetchone()[0]  # noqa: E731
    return {
        "members": one("SELECT COUNT(*) FROM prov_members WHERE prov=?"),
        "terms": one("SELECT COUNT(*) FROM prov_member_terms WHERE prov=?"),
        "bills": one("SELECT COUNT(*) FROM prov_bills WHERE prov=?"),
        "bills_ours": one("SELECT COUNT(*) FROM prov_bills WHERE prov=? AND areas NOT IN ('[]', '')"),
        "sittings": one("SELECT COUNT(*) FROM prov_sittings WHERE prov=?"),
        "recorded": one("SELECT COUNT(*) FROM prov_divisions WHERE prov=? AND kind='recorded'"),
        "recorded_ok": one("SELECT COUNT(*) FROM prov_divisions WHERE prov=? AND kind='recorded' AND positions_ok=1"),
        # A division whose source prints totals and no names (Ontario's
        # dilatory motions) is untrusted but is not a gap: no re-read can
        # resolve it. Counted apart so a gap count means "owed".
        "recorded_gap": one("SELECT COUNT(*) FROM prov_divisions WHERE prov=? AND kind='recorded' AND positions_ok=0 "
                            "AND COALESCE(tally_note, '') NOT LIKE 'totals only%'"),
        "recorded_totals_only": one("SELECT COUNT(*) FROM prov_divisions WHERE prov=? AND kind='recorded' "
                                    "AND positions_ok=0 AND tally_note LIKE 'totals only%'"),
        "voice": one("SELECT COUNT(*) FROM prov_divisions WHERE prov=? AND kind='voice'"),
        "ours": one("SELECT COUNT(*) FROM prov_divisions WHERE prov=? AND areas NOT IN ('[]', '')"),
        "votes": one("SELECT COUNT(*) FROM prov_votes v JOIN prov_divisions d USING (division_key) WHERE d.prov=?"),
        "unresolved": one("SELECT COUNT(*) FROM prov_votes v JOIN prov_divisions d USING (division_key) "
                          "WHERE d.prov=? AND v.member_key IS NULL"),
        "with_party": one("SELECT COUNT(*) FROM prov_votes v JOIN prov_divisions d USING (division_key) "
                          "WHERE d.prov=? AND v.party_at_vote IS NOT NULL"),
    }


def refresh_party(conn, prov, resolver, legislature=None, session=None):
    """Re-derive prov_votes.party_at_vote for a province's stored votes from
    the terms that DATE a party (resolver.party_at), so a party record read
    after the divisions (New Brunswick's Hansard member lists, Newfoundland's
    election results) reaches the votes already stored. A vote no dated term
    covers is set back to NULL: never today's party. Returns (resolved votes,
    votes with a party)."""
    sql = ("SELECT v.rowid, v.member_key, v.party_at_vote, d.date, d.legislature FROM prov_votes v "
           "JOIN prov_divisions d USING (division_key) WHERE d.prov=? AND v.member_key IS NOT NULL")
    args = [prov]
    if legislature is not None:
        sql += " AND d.legislature=?"
        args.append(legislature)
    if session is not None:
        sql += " AND d.session=?"
        args.append(session)
    n = with_party = 0
    for rowid, key, have, date, leg in conn.execute(sql, args).fetchall():
        party = resolver.party_at(key, date, leg)
        n += 1
        with_party += 1 if party else 0
        if party != have:
            conn.execute("UPDATE prov_votes SET party_at_vote=? WHERE rowid=?", (party, rowid))
    return n, with_party
