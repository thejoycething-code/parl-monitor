"""Canadian provincial legislatures: the shared foundation. No network.

src/prov_store.py (schema, tally check, writes), src/prov_names.py (the
dated resolver), src/prov_classify.py (text, per passage, plus
config/watchlist-prov.yaml), src/prov_fetch.py (robots, gaps) and the
runner tools/prov_collect.py.
"""

import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_store as ps  # noqa: E402
from src.http import FetchError  # noqa: E402
from src.prov_fetch import Context, Unreadable, html_text, pdf_text  # noqa: E402


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "prov_collect", os.path.join(ROOT, "tools", "prov_collect.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _conn():
    return db.init_db(db.connect(":memory:"))


MEMBERS = {
    "0814": {"name": "Danielle Smith", "surname": "Smith", "given": "Danielle"},
    "0945": {"name": "R.J. Sigurdson", "surname": "Sigurdson", "given": "R.J."},
    "0875": {"name": "Lori Sigurdson", "surname": "Sigurdson", "given": "Lori"},
    "0958": {"name": "Jodi Calahoo Stonehouse", "surname": "Calahoo Stonehouse", "given": "Jodi"},
    "0975": {"name": "Chantelle de Jonge", "surname": "de Jonge", "given": "Chantelle"},
    "0957": {"name": "Gurinder Brar", "surname": "Brar", "given": "Gurinder"},
    "0988": {"name": "Gurtej Singh Brar", "surname": "Brar", "given": "Gurtej Singh"},
    "0963": {"name": "Sharif Haji", "surname": "Haji", "given": "Sharif"},
    "0871": {"name": "Irfan Sabir", "surname": "Sabir", "given": "Irfan"},
    "bc74": {"name": "Claire Rattée", "surname": "Rattée", "given": "Claire"},
    "nb1": {"name": "Blaine Higgs", "surname": "Higgs", "given": "Blaine"},
    "sk1": {"name": "Betty Nippi-Albright", "surname": "Nippi-Albright", "given": "Betty"},
}


def term(key, party, riding, start="2023-05-29", end=None, leg=31):
    return {"member_key": key, "legislature": leg, "party": party, "riding": riding,
            "start": start, "end": end, "party_dated": 1}


TERMS = [
    term("0814", "UC", "Brooks-Medicine Hat"),
    term("0945", "UC", "Highwood"),
    term("0875", "NDP", "Edmonton-Riverview"),
    term("0958", "NDP", "Edmonton-Rutherford"),
    term("0975", "UC", "Chestermere-Strathmore"),
    term("0957", "NDP", "Calgary-North East"),
    # elected at a by-election in 2025: not a member in December 2024
    term("0988", "NDP", "Edmonton-Ellerslie", start="2025-06-23"),
    term("0963", "NDP", "Edmonton-Decore"),
    term("0871", "NDP", "Calgary-Bhullar-McCall"),
    term("bc74", "BC Conservative", "Skeena", start="2025-02-18", leg=43),
    term("nb1", "PC", "Quispamsis", start="2020-09-14", leg=60),
    term("sk1", "NDP", "Saskatoon Centre", start="2020-11-30", leg=29),
]


class SchemaTests(unittest.TestCase):
    def test_init_db_creates_every_prov_table_and_declares_it(self):
        conn = _conn()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("prov_members", "prov_member_terms", "prov_divisions", "prov_votes",
                  "prov_bills", "prov_sittings", "prov_speeches"):
            self.assertIn(t, names)
            self.assertIn(t, db.TABLES)

    def test_no_prov_table_carries_a_sighting_column(self):
        """tests/test_coverage.py would demand a coverage.py entry for it,
        and nothing schedules these collectors yet."""
        conn = _conn()
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                    "AND name LIKE 'prov|_%' ESCAPE '|'"):
            cols = {c[1] for c in conn.execute("PRAGMA table_info({0})".format(name))}
            self.assertFalse(cols & {"last_seen", "captured_at"}, name)


class TallyTests(unittest.TestCase):
    def v(self, pos, label, key):
        return {"position": pos, "raw_label": label, "member_key": key}

    def test_matching_totals_with_every_name_resolved_is_ok(self):
        ok, note = ps.tally({"Yea": 2, "Nay": 1},
                            [self.v("Yea", "Smith", "a"), self.v("Yea", "Amery", "b"),
                             self.v("Nay", "Notley", "c")])
        self.assertTrue(ok)
        self.assertIsNone(note)

    def test_a_short_list_is_a_gap(self):
        ok, note = ps.tally({"Yea": 3, "Nay": 1},
                            [self.v("Yea", "Smith", "a"), self.v("Yea", "Amery", "b"),
                             self.v("Nay", "Notley", "c")])
        self.assertFalse(ok)
        self.assertIn("Yea: 2 name(s) read, 3 printed", note)

    def test_an_unresolved_name_is_a_gap_even_when_the_count_matches(self):
        ok, note = ps.tally({"Yea": 1, "Nay": 1},
                            [self.v("Yea", "Smith", "a"), self.v("Nay", "Nobody", None)])
        self.assertFalse(ok)
        self.assertIn("unresolved 'Nobody'", note)

    def test_one_member_resolved_twice_is_a_gap(self):
        ok, note = ps.tally({"Yea": 1, "Nay": 1},
                            [self.v("Yea", "Sigurdson", "a"), self.v("Nay", "Sigurdson", "a")])
        self.assertFalse(ok)
        self.assertIn("resolved twice", note)

    def test_no_printed_totals_is_never_ok(self):
        ok, note = ps.tally({}, [self.v("Yea", "Smith", "a")])
        self.assertFalse(ok)


class LabelTests(unittest.TestCase):
    def test_the_forms_that_occur(self):
        lab = pn.parse_label("Sigurdson (Highwood)")
        self.assertEqual((lab.tokens, lab.riding), (["sigurdson"], "Highwood"))
        lab = pn.parse_label("Sigurdson, R.J.")
        self.assertEqual((lab.tokens, lab.initials), (["sigurdson"], "rj"))
        lab = pn.parse_label("L. Neufeld")
        self.assertEqual((lab.tokens, lab.initials), (["neufeld"], "l"))
        lab = pn.parse_label("Hon. Mr. Higgs")
        self.assertEqual(lab.tokens, ["higgs"])
        lab = pn.parse_label("Mr. J. LeBlanc")
        self.assertEqual((lab.tokens, lab.initials), (["leblanc"], "j"))
        lab = pn.parse_label("Betty Nippi -Albright")
        self.assertEqual(lab.tokens, ["betty", "nippi-albright"])
        lab = pn.parse_label("Jean, KC, Honourable Brian M.")
        self.assertEqual(lab.tokens[-1], "jean")
        self.assertEqual(pn.fold("Rattée"), "rattee")


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.r = pn.Resolver(MEMBERS, TERMS)

    def test_surname_only(self):
        self.assertEqual(self.r.resolve("Smith", "2024-12-03", 31), ("0814", "surname"))

    def test_a_shared_surname_needs_its_riding(self):
        self.assertEqual(self.r.resolve("Sigurdson (Highwood)", "2024-12-03", 31)[0], "0945")
        self.assertEqual(self.r.resolve("Sigurdson (Edmonton-Riverview)", "2024-12-03", 31)[0], "0875")
        key, why = self.r.resolve("Sigurdson", "2024-12-03", 31)
        self.assertIsNone(key)
        self.assertIn("ambiguous", why)

    def test_initials_disambiguate(self):
        self.assertEqual(self.r.resolve("Sigurdson, R.J.", "2024-12-03")[0], "0945")
        self.assertEqual(self.r.resolve("Sigurdson, L.", "2024-12-03")[0], "0875")

    def test_the_term_must_be_valid_on_the_day(self):
        """Gurtej Brar won Edmonton-Ellerslie in 2025: a December 2024 'Brar'
        is Gurinder, and a June 2026 'Brar' is nobody we can tell apart."""
        self.assertEqual(self.r.resolve("Brar", "2024-12-03", 31)[0], "0957")
        self.assertIsNone(self.r.resolve("Brar", "2026-03-01", 31)[0])

    def test_two_word_surnames_and_particles(self):
        self.assertEqual(self.r.resolve("Calahoo Stonehouse", "2024-12-03")[0], "0958")
        self.assertEqual(self.r.resolve("de Jonge", "2024-12-03")[0], "0975")

    def test_honorifics_full_names_and_accents(self):
        self.assertEqual(self.r.resolve("Hon. Mr. Higgs", "2023-06-15", 60)[0], "nb1")
        self.assertEqual(self.r.resolve("Betty Nippi -Albright", "2023-10-20", 29)[0], "sk1")
        self.assertEqual(self.r.resolve("Rattee", "2026-02-19", 43)[0], "bc74")
        self.assertEqual(self.r.resolve("Rattée", "2026-02-19", 43)[0], "bc74")

    def test_an_unknown_label_is_none_never_a_guess(self):
        key, why = self.r.resolve("Notley", "2024-12-03", 31)
        self.assertIsNone(key)
        self.assertIn("unknown", why)
        # a full name whose given name does not fit is not the surname's owner
        self.assertIsNone(self.r.resolve("Rachel Smith", "2024-12-03", 31)[0])

    def test_party_at_vote_only_from_a_dated_term(self):
        self.assertEqual(self.r.party_at("0814", "2024-12-03", 31), "UC")
        undated = pn.Resolver(MEMBERS, [dict(TERMS[0], party_dated=0)])
        self.assertIsNone(undated.party_at("0814", "2024-12-03", 31))


class NameRunTests(unittest.TestCase):
    LINES = ["Al-Guneid Elmeligi Loyola", "Calahoo Stonehouse Haji Sabir",
             "Dach Hoyle Sigurdson", "(Edmonton-Riverview)", "", "=====PAGE", "6 ",
             "de Jonge Lunty Sigurdson (Highwood)", "Ross (Regina", "Rochdale) Eyre"]

    def test_greedy_surnames_and_wrapped_ridings(self):
        vocab = {("al-guneid",), ("calahoo", "stonehouse"), ("haji",), ("sabir",),
                 ("de", "jonge"), ("sigurdson",), ("ross",)}
        labels = pn.split_name_run(self.LINES, vocab)
        self.assertEqual(labels, [
            "Al-Guneid", "Elmeligi", "Loyola", "Calahoo Stonehouse", "Haji", "Sabir",
            "Dach", "Hoyle", "Sigurdson (Edmonton-Riverview)", "de Jonge", "Lunty",
            "Sigurdson (Highwood)", "Ross (Regina Rochdale)", "Eyre"])

    def test_prose_and_headings_end_a_list(self):
        vocab = pn.vocab_tokens({("de", "jonge"), ("van", "dijken")})
        self.assertTrue(pn.is_name_line("de Jonge Lunty Smith", vocab))
        self.assertTrue(pn.is_name_line("(Cypress-Medicine Hat)", vocab))
        self.assertTrue(pn.is_name_line("Jaw North) Buckingham", vocab))
        self.assertFalse(pn.is_name_line("The question being immediately put, the motion", vocab))
        self.assertFalse(pn.is_name_line("Third Reading", vocab))
        self.assertFalse(pn.is_name_line("Against the motion:  35", vocab))
        self.assertFalse(pn.is_name_line("Committee of the Whole", vocab))


class ClassifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tax = pc.load_taxonomy()

    def test_bill_26_is_area_3_not_organ_donation(self):
        """The Human Tissue and Organ Donation Act is amended for a rename;
        its NAME must not make a puberty-blocker vote an area-13 position."""
        wl = pc.load_watchlist("ab")
        body = ("(o.1) “gender dysphoria” means a person’s distress caused by a "
                "discrepancy between gender identity and sex assigned at birth;\n"
                "Human Tissue and Organ Donation Act\n"
                "12(1) The Human Tissue and Organ Donation Act is amended by this section.")
        res = pc.classify(self.tax, wl, "ab", title="Health Statutes Amendment Act, 2024 (No. 2)",
                          texts=[body])
        self.assertEqual(res.areas, [3])
        self.assertEqual(res.tier, 1)
        unmasked = pc.classify_text(self.tax, wl, body=body, mask=False)
        self.assertIn(13, unmasked.areas)

    def test_a_title_alone_misses_and_the_key_catches_it(self):
        wl = pc.load_watchlist("ab")
        res = pc.classify(self.tax, wl, "ab", title="Fairness and Safety in Sport Act")
        self.assertEqual(res.areas, [])
        res = pc.classify(self.tax, wl, "ab", title="Fairness and Safety in Sport Act",
                          bill_key="ab-31-1/29")
        self.assertEqual((res.areas, res.tier), ([5], 1))

    def test_provincial_terms_need_their_guards_in_the_same_passage(self):
        wl = pc.load_watchlist("ab")
        hit = pc.classify_text(self.tax, wl, body=(
            "If a student requests that a new preferred name or pronouns be used by "
            "teachers, the principal shall notify the student’s parent."))
        self.assertIn(6, hit.areas)
        miss = pc.classify_text(self.tax, wl, body="A pronoun is a word that replaces a noun.")
        self.assertEqual(miss.areas, [])

    def test_the_watchlist_parses_and_every_entry_says_why(self):
        import yaml
        with open(pc.WATCHLIST, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        for spec in raw["terms"]:
            self.assertTrue(spec.get("why"), spec)
        for prov, block in raw["provinces"].items():
            self.assertIn(prov, ps.PROVINCES)
            for key, spec in block["bills"].items():
                self.assertTrue(key.startswith(prov + "-"), key)
                self.assertTrue(spec.get("why"), key)


class StoreTests(unittest.TestCase):
    def test_a_voice_vote_is_stored_as_such_never_as_an_empty_roll_call(self):
        conn = _conn()
        ps.store_division(conn, {"division_key": "ab-31-1-2024-11-05-v26-2r", "prov": "ab",
                                 "kind": "voice", "result": "passed", "date": "2024-11-05",
                                 "votes": [{"position": "Yea", "ordinal": 1, "raw_label": "X"}]})
        row = conn.execute("SELECT kind, yeas, nays, positions_ok FROM prov_divisions").fetchone()
        self.assertEqual(tuple(row), ("voice", None, None, None))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prov_votes").fetchone()[0], 0)

    def test_an_unresolved_label_is_kept_with_a_null_member(self):
        conn = _conn()
        ps.store_division(conn, {"division_key": "k", "prov": "ab", "kind": "recorded",
                                 "yeas": 1, "nays": 0, "positions_ok": 0,
                                 "votes": [{"position": "Yea", "ordinal": 1,
                                            "raw_label": "Smyth", "member_key": None,
                                            "how": "unknown on 2024-12-03"}]})
        row = conn.execute("SELECT raw_label, member_key FROM prov_votes").fetchone()
        self.assertEqual(tuple(row), ("Smyth", None))

    def test_a_bill_read_from_its_text_keeps_those_areas(self):
        conn = _conn()
        ps.store_bill(conn, {"bill_key": "ab-31-1/26", "prov": "ab", "text_read": 1,
                             "areas": [3], "title_en": "Health Statutes Amendment Act"})
        ps.store_bill(conn, {"bill_key": "ab-31-1/26", "prov": "ab", "areas": []})
        self.assertEqual(ps.bill_areas(conn, "ab-31-1/26")[0], [3])

    def test_a_sitting_with_a_gap_stays_owed(self):
        conn = _conn()
        ps.store_sitting(conn, "ab", "ab-31-1-2024-12-03", "2024-12-03", "u1", status="gap")
        ps.store_sitting(conn, "ab", "ab-31-1-2024-12-04", "2024-12-04", "u2", status="ok")
        self.assertFalse(ps.sitting_done(conn, "u1"))
        self.assertTrue(ps.sitting_done(conn, "u2"))

    def test_extend_term_covers_exactly_the_days_seen(self):
        conn = _conn()
        ps.extend_term(conn, "sk", "scott-moe", 29, "SP", "Rosthern-Shellbrook", "2023-10-20", "hansard-cover")
        ps.extend_term(conn, "sk", "scott-moe", 29, "SP", "Rosthern-Shellbrook", "2023-10-10", "hansard-cover")
        rows = conn.execute("SELECT start, end FROM prov_member_terms").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("2023-10-10", "2023-10-20")])


class FakeClient:
    user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"

    def __init__(self, pages):
        self.pages = pages
        self.throttle = 0.2
        self.asked = []

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        self.asked.append(url)
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.pages[url]

    def get_bytes(self, url, feed, slug, archive=True):
        return self.get_text(url, feed, slug).encode()


class ContextTests(unittest.TestCase):
    def test_robots_is_honoured_and_a_disallowed_url_is_a_gap(self):
        client = FakeClient({"https://x.ca/robots.txt": "User-agent: *\nDisallow: /private/\nCrawl-delay: 10\n",
                             "https://x.ca/ok": "fine"})
        ctx = Context(_conn(), client, "nb", log=lambda *a: None)
        self.assertEqual(client.throttle, 1.1)        # never below 1.1 s
        self.assertEqual(ctx.text("https://x.ca/ok", "ok"), "fine")
        self.assertEqual(client.throttle, 10.0)       # the crawl-delay
        self.assertIsNone(ctx.text("https://x.ca/private/a", "a"))
        self.assertNotIn("https://x.ca/private/a", client.asked)
        self.assertIn("robots.txt disallows", ctx.gaps[0])

    def test_a_missing_robots_txt_means_no_rules(self):
        client = FakeClient({"https://y.ca/doc": "body"})
        ctx = Context(_conn(), client, "bc", log=lambda *a: None)
        self.assertEqual(ctx.text("https://y.ca/doc", "d"), "body")
        self.assertEqual(ctx.gaps, [])

    def test_a_failed_fetch_is_a_gap_not_an_exception(self):
        client = FakeClient({})
        ctx = Context(_conn(), client, "bc", log=lambda *a: None)
        self.assertIsNone(ctx.text("https://y.ca/missing", "m"))
        self.assertEqual(len(ctx.gaps), 1)

    def test_a_truncated_pdf_is_unreadable_not_empty(self):
        with self.assertRaises(Unreadable):
            pdf_text(b"%PDF-1.7\n1 0 obj << >> endobj\n")
        with self.assertRaises(Unreadable):
            pdf_text(b"<!doctype html><p>Not found</p>")

    def test_html_text_keeps_word_split_names_whole(self):
        self.assertEqual(html_text("<p>Betty <span class=SpellE>Nippi</span>-Albright</p>"),
                         "Betty Nippi-Albright")


class RunnerTests(unittest.TestCase):
    def test_an_unbuilt_province_says_so(self):
        runner = _load_runner()
        with self.assertRaises(SystemExit) as cm:
            runner.module_for("pe")
        self.assertIn("not built", str(cm.exception))

    def test_gaps_reach_the_gaps_table(self):
        runner = _load_runner()
        conn = _conn()

        class Mod:
            CURRENT_SESSION = "1-1"

            @staticmethod
            def collect(ctx, session, roster, bills):
                ctx.gap("a test gap")
                return {"records": 0}

        runner.module_for = lambda prov: Mod
        stats, gaps = runner.run(conn, FakeClient({}), "ab", log=lambda *a: None)
        self.assertEqual(gaps, ["a test gap"])
        row = conn.execute("SELECT feed, detail FROM gaps").fetchone()
        self.assertEqual(tuple(row), ("prov-ab", "a test gap"))


if __name__ == "__main__":
    unittest.main()
