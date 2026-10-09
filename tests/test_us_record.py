"""The Congressional Record collector (tools/us_record.py) and its edition
section (tools/us_monitor.py, Floor debate).

No network. tests/fixtures/us_record/ holds real GovInfo files fetched
9 October 2026: the CREC listing for 16 and 17 September 2026 (it carries
no key: the key went as a header), the day metadata of 16 September trimmed
to five granules (the House prayer; a suspension debate on H.R. 7834, the
Safe Cloud Storage Act; Chris Smith's special order on the Hyde Amendment's
fiftieth anniversary; a Constitution Day tribute; and a debate where
Mr. VAN EPPS speaks though the granule's metadata does not name him), and
the four speech granules' pages.
"""

import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, drain, filter as filt, us_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "us_record")
DAY = "CREC-2026-09-16"
HYDE = "CREC-2026-09-16-pt1-PgH5969"
CLOUD = "CREC-2026-09-16-pt1-PgH5936"
EPPS = "CREC-2026-09-16-pt1-PgH5895"
PRAYER = "CREC-2026-09-16-pt1-PgH5835-4"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rec = _load("us_record")
mon = _load("us_monitor")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))


def fixture(name):
    with gzip.open(os.path.join(FIX, name)) as fh:
        return fh.read()


class FakeClient:
    """Answers from the fixtures; records what was asked and with which headers."""

    def __init__(self, fail=()):
        self.asked, self.archived, self.fail = [], [], set(fail)
        self.last_headers = {"x-ratelimit-limit": "36000", "x-ratelimit-remaining": "35990"}

    def get_bytes(self, url, feed, slug, timeout=None, archive=True, headers=None, **kw):
        self.asked.append((url, headers))
        if any(f in url for f in self.fail):
            raise FetchError(url, feed, slug, 1, "HTTP Error 404")
        if "api.govinfo.gov/published" in url:
            return fixture("listing-2026-09-16.json.gz")
        if url.endswith("/mods.xml"):
            if DAY not in url:
                raise FetchError(url, feed, slug, 1, "not in fixtures")
            return fixture("mods-CREC-2026-09-16.xml.gz")
        gid = url.rsplit("/", 1)[1][:-4]
        return fixture(gid + ".htm.gz")

    def archive(self, raw, feed, slug):
        self.archived.append(slug)


def store():
    conn = db.init_db(sqlite3.connect(":memory:"))
    conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, "
                 "short_titles) VALUES ('119/hr/7834', 119, 'hr', 7834, 'Safe Cloud Storage Act', "
                 "'[\"To limit liability for certain entities storing child sexual abuse "
                 "material for law enforcement agencies, and for other purposes.\"]')")
    conn.execute("INSERT INTO us_members (bioguide, name, party, state, chamber) VALUES "
                 "('V000138', 'Matt Van Epps', 'R', 'TN', 'house')")
    conn.commit()
    return conn


def pkg():
    return json.loads(fixture("listing-2026-09-16.json.gz"))["packages"][0]


def read(conn, client=None, **kw):
    client = client or FakeClient()
    titles = rec.BillTitles(conn, TAX, rec.empty_watchlist())
    return rec.read_day(conn, client, pkg(), TAX, rec.empty_watchlist(), "2026-10-09", titles,
                        watch={}, **kw), client


class MetadataTests(unittest.TestCase):
    def test_granules_members_and_bills(self):
        gs = {g["granule_id"]: g for g in rec.parse_mods(fixture("mods-CREC-2026-09-16.xml.gz"))}
        self.assertEqual(len(gs), 5)
        hyde = gs[HYDE]
        self.assertEqual(hyde["section"], "house")
        smith = rec.speakers(hyde)[0]
        self.assertEqual((smith["bioguide"], smith["parsed"], smith["party"], smith["state"]),
                         ("S000522", "Mr. SMITH of New Jersey", "R", "NJ"))
        # A bill is joined on its KEY, with GovInfo's own context.
        self.assertEqual(gs[CLOUD]["bills"][0], ("119/hr/7834", "HEADERLINE"))
        self.assertEqual(rec.subject_bill(gs[CLOUD]), "119/hr/7834")
        self.assertIsNone(rec.subject_bill(hyde))

    def test_procedure_is_not_speech(self):
        gs = {g["granule_id"]: g for g in rec.parse_mods(fixture("mods-CREC-2026-09-16.xml.gz"))}
        self.assertFalse(rec.is_speech_granule(gs[PRAYER]))
        self.assertTrue(rec.is_speech_granule(gs[HYDE]))


class TurnTests(unittest.TestCase):
    def test_chair_and_clerk_end_a_turn(self):
        text = ("  Ms. LEE of Florida. Mr. Speaker, I move to suspend the rules.\n"
                "  The Clerk read the title of the bill.\n"
                "  The text of the bill is as follows:\n  SECTION 1. SHORT TITLE.\n"
                "  The SPEAKER pro tempore. Pursuant to the rule, the gentlewoman is recognized.\n"
                "  Ms. LEE of Florida. Mr. Speaker, I yield myself such time.\n"
                "  The Fit Future Act would help.\n")
        turns = rec.parse_turns(text)
        labels = [t[0] for t in turns]
        self.assertEqual(labels, ["Ms. LEE of Florida", None, None, None, "Ms. LEE of Florida"])
        # A paragraph opening "The Fit..." is the member's, not the chair's.
        self.assertIn("Fit Future", turns[-1][1])
        self.assertNotIn("SHORT TITLE", turns[0][1] + turns[-1][1])

    def test_label_resolved_from_a_fallback_roster(self):
        members = [{"bioguide": "M001223", "parsed": "Mr. MAGAZINER", "role": "SPEAKING"}]
        roster = [{"bioguide": "V000138", "parsed": "Mr. VAN EPPS", "role": "SPEAKING"}]
        self.assertIsNone(rec.resolve("Mr. VAN EPPS", members))
        self.assertEqual(rec.resolve("Mr. VAN EPPS", members, (roster,))["bioguide"], "V000138")
        # The exact label tells Mr. from Mrs.; two of one label is nobody, never a guess.
        two = roster + [{"bioguide": "X1", "parsed": "Mrs. VAN EPPS", "role": "SPEAKING"}]
        self.assertEqual(rec.resolve("Mr. VAN EPPS", members, (two,))["bioguide"], "V000138")
        twins = roster + [{"bioguide": "X1", "parsed": "Mr. VAN EPPS", "role": "SPEAKING"}]
        self.assertIsNone(rec.resolve("Mr. VAN EPPS", members, (twins,)))


class RuleTests(unittest.TestCase):
    def test_own_words(self):
        own, areas, src, terms, tier, excerpt = rec.classify_speech(
            TAX, rec.empty_watchlist(), "A TRIBUTE", "The Hyde Amendment has saved lives.",
            7, None, lambda k: [1], watch={})
        self.assertEqual((own, areas, src, tier), ([1], [1], "own", 1))

    def test_bill_lends_only_to_an_ambiguous_long_speech_on_it(self):
        text = " ".join(["This bill protects our children and families."] * 30)
        lend = lambda k: [6] if k == "119/hr/7834" else []  # noqa: E731
        own, areas, src, *_ = rec.classify_speech(TAX, rec.empty_watchlist(), "SAFE CLOUD STORAGE ACT",
                                                  text, 240, "119/hr/7834", lend, watch={})
        self.assertEqual((own, areas, src), ([], [6], "bill"))
        # Too short: procedure, not a speech; lends nothing.
        self.assertEqual(rec.classify_speech(TAX, rec.empty_watchlist(), "X", "I yield.", 3,
                                             "119/hr/7834", lend, watch={})[1], [])
        # Not the debate's subject: lends nothing.
        self.assertEqual(rec.classify_speech(TAX, rec.empty_watchlist(), "X", text, 240,
                                             None, lend, watch={})[1], [])
        # A watched bill KEY lends whatever the speech says.
        res = rec.classify_speech(TAX, rec.empty_watchlist(), "X", text, 240, "119/hr/15",
                                  lend, watch={"119/hr/15": ([5], "Equality Act")})
        self.assertEqual((res[1], res[2]), ([5], "watch"))

    def test_bill_titles_not_summary(self):
        conn = store()
        conn.execute("INSERT INTO us_bills (bill_key, congress, bill_type, number, title, summary) "
                     "VALUES ('119/hr/1', 119, 'hr', 1, 'One Big Beautiful Bill Act', "
                     "'... no funds to Planned Parenthood or for abortion ...')")
        self.assertEqual(rec.BillTitles(conn, TAX, rec.empty_watchlist()).areas("119/hr/1"), [])


class DayTests(unittest.TestCase):
    def test_reads_a_day(self):
        conn = store()
        totals, client = read(conn)
        self.assertEqual(totals["speech_granules"], 4)
        self.assertEqual(totals["unresolved"], 0)
        rows = {r[0]: r for r in conn.execute(
            "SELECT speech_key, areas, areas_from, party, state, excerpt, words, bioguide "
            "FROM us_record_speeches")}
        smith = rows[HYDE + "/S000522"]
        self.assertEqual(json.loads(smith[1]), [1, 2])
        self.assertEqual((smith[2], smith[3], smith[4]), ("own", "R", "NJ"))
        self.assertLessEqual(len(smith[5]), rec.EXCERPT + 3)
        self.assertGreater(smith[6], 1000)
        # The suspension debate stands on its bill's title, said so.
        self.assertEqual(rows[CLOUD + "/L000597"][2], "bill")
        # Only speeches on our ground are stored; the text never is.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(us_record_speeches)")]
        self.assertNotIn("text", cols)
        # Every speech granule's bills are kept, ours or not.
        self.assertEqual(conn.execute("SELECT context FROM us_record_bills WHERE bill_key="
                                      "'119/hr/7834'").fetchone()[0], "HEADERLINE")
        day = conn.execute("SELECT status, speech_granules, ours FROM us_record_days").fetchone()
        self.assertEqual(day[0], "read")
        # Pages are archived only where a speech was stored.
        self.assertIn("page-" + HYDE, client.archived)
        self.assertNotIn("page-" + EPPS, client.archived)

    def test_page_gap_marks_the_day_for_another_read(self):
        conn = store()
        totals, _ = read(conn, FakeClient(fail=[HYDE]))
        self.assertEqual(totals["gaps"], 1)
        self.assertEqual(conn.execute("SELECT status FROM us_record_days").fetchone()[0], "gap")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='us-record'"
                                      ).fetchone()[0], 1)

    def test_budget_stops_part_way_without_marking_read(self):
        conn = store()
        budget = drain.Budget(0)
        totals, _ = read(conn, budget=budget)
        self.assertIsNone(totals)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM us_record_days").fetchone()[0], 0)

    def test_reread_keeps_the_judge_and_drops_what_left(self):
        conn = store()
        read(conn)
        conn.execute("UPDATE us_record_speeches SET triage_score=3 WHERE speech_key=?",
                     (HYDE + "/S000522",))
        conn.execute("INSERT INTO us_record_speeches (speech_key, granule_id, package_id, date, "
                     "chamber) VALUES ('gone/X', 'gone', ?, '2026-09-16', 'house')", (DAY,))
        read(conn)
        self.assertEqual(conn.execute("SELECT triage_score FROM us_record_speeches WHERE "
                                      "speech_key=?", (HYDE + "/S000522",)).fetchone()[0], 3)
        self.assertIsNone(conn.execute("SELECT 1 FROM us_record_speeches WHERE speech_key="
                                       "'gone/X'").fetchone())


class PullTests(unittest.TestCase):
    def test_key_travels_as_a_header_and_days_are_due_newest_first(self):
        conn = store()
        client = FakeClient()
        logs = []
        rec.pull(conn, client, "2026-10-09", "SECRETKEY", since="2026-09-16",
                 until="2026-09-17", tax=TAX, log=logs.append)
        listing = [a for a in client.asked if "published" in a[0]][0]
        self.assertNotIn("SECRETKEY", listing[0])
        self.assertEqual(listing[1], {"X-Api-Key": "SECRETKEY"})
        # The end date is exclusive at GovInfo: the day after is asked for.
        self.assertIn("/2026-09-16/2026-09-18?", listing[0])
        mods = [a[0] for a in client.asked if a[0].endswith("mods.xml")]
        self.assertEqual(mods[0].split("/")[-2], "CREC-2026-09-17")   # newest first
        # The 17th's metadata is not in the fixtures: a gap, never the key.
        gaps = [r[0] for r in conn.execute("SELECT detail FROM gaps")]
        self.assertTrue(gaps and not any("SECRETKEY" in g for g in gaps))
        self.assertFalse(any("SECRETKEY" in line for line in logs))

    def test_held_days_are_not_read_again(self):
        conn = store()
        rec.pull(conn, FakeClient(), "2026-10-09", "K", since="2026-09-16", until="2026-09-17",
                 tax=TAX, log=lambda *_: None)
        client = FakeClient()
        rec.pull(conn, client, "2026-10-09", "K", since="2026-09-16", until="2026-09-17",
                 tax=TAX, log=lambda *_: None)
        mods = [a[0] for a in client.asked if a[0].endswith("mods.xml")]
        # Only the 17th, whose earlier read was a gap.
        self.assertEqual([m.split("/")[-2] for m in mods], ["CREC-2026-09-17"])

    def test_missing_key_is_one_gap(self):
        import subprocess
        env = dict(os.environ, CONGRESS_API_KEY="")
        # The secrets file may hold a key; point the loader at none.
        code = ("import sys; sys.argv=['x','--db',':memory:']; sys.path.insert(0, %r);"
                "from src import publish; publish.SECRETS_PATH='/nonexistent';"
                "import runpy; runpy.run_path(%r, run_name='__main__')") % (
            ROOT, os.path.join(ROOT, "tools", "us_record.py"))
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
        self.assertEqual(out.stdout.count("[gap]"), 1, out.stdout + out.stderr)
        self.assertIn("no congress_api_key", out.stdout)

    def test_key_cleaned(self):
        self.assertEqual(us_store.clean_key("`abc123`"), "abc123")
        self.assertIsNone(us_store.clean_key("  "))


class HttpTests(unittest.TestCase):
    def test_reply_headers_kept_and_archive_is_explicit(self):
        import tempfile
        from src.http import HttpClient

        class Reply:
            headers = {"X-RateLimit-Remaining": "35990", "X-RateLimit-Limit": "36000"}

            def read(self):
                return b"{}"

        class Opener:
            def __init__(self):
                self.requests = []

            def open(self, request, timeout=None):
                self.requests.append(request)
                return Reply()

        with tempfile.TemporaryDirectory() as raw:
            opener = Opener()
            client = HttpClient(raw_dir=raw, opener=opener, sleep=lambda s: None)
            client.get_bytes("https://api.govinfo.gov/x", "f", "s", headers={"X-Api-Key": "K"})
            self.assertEqual(client.last_headers["x-ratelimit-remaining"], "35990")
            self.assertNotIn("K", opener.requests[0].full_url)
            self.assertEqual(os.listdir(raw), [])         # keyed: never archived
            client.archive(b"{}", "f", "listing")
            self.assertEqual(len(os.listdir(raw)), 1)


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.conn = store()
        read(self.conn)
        self.conn.row_factory = sqlite3.Row
        self.names = mon.area_names()

    def test_section_this_week(self):
        out = "\n".join(mon.floor_section(self.conn, "2026-09-14", "2026-09-18", self.names))
        self.assertIn("## Floor debate", out)
        self.assertIn("Christopher H. Smith (R-NJ)", out)
        self.assertIn("https://www.govinfo.gov/app/details/CREC-2026-09-16/" + HYDE, out)
        self.assertIn("[H.R. 7834]", out)
        self.assertIn("its bill only", out)
        self.assertNotIn("—", out)
        # One line, never the speech: no line longer than a takeaway allows.
        for line in out.splitlines():
            self.assertLess(len(line), 700, line)
        self.assertIn("Most often on our ground", out)

    def test_quiet_week_shows_the_latest(self):
        out = "\n".join(mon.floor_section(self.conn, "2026-10-02", "2026-10-09", self.names))
        self.assertIn("Nothing on our ground this week", out)
        self.assertIn("Christopher H. Smith", out)

    def test_bill_line_counts_floor(self):
        self.assertEqual(mon.floor_counts(self.conn).get("119/hr/7834"), 1)

    def test_empty_store_renders(self):
        conn = db.init_db(sqlite3.connect(":memory:"))
        conn.row_factory = sqlite3.Row
        out = "\n".join(mon.floor_section(conn, "2026-10-02", "2026-10-09", self.names))
        self.assertIn("No speech on our ground in the store yet", out)


class TriageTests(unittest.TestCase):
    def test_speeches_on_their_own_words_are_queued(self):
        tri = _load("us_triage")
        conn = store()
        read(conn)
        conn.row_factory = sqlite3.Row
        ids = [i.id for i in tri.pending(conn) if i.id.startswith("us_record_speeches:")]
        self.assertIn("us_record_speeches:" + HYDE + "/S000522", ids)
        # Borrowing a bill's areas is not the member's own words: not judged.
        self.assertNotIn("us_record_speeches:" + CLOUD + "/L000597", ids)


if __name__ == "__main__":
    unittest.main()
