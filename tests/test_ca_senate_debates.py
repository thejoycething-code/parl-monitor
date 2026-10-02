"""Senate of Canada debates (tools/ca_senate_debates.py). No network.

The fixtures are sencanada.ca pages saved on 2 October 2026 and trimmed:
original markup, most paragraphs dropped (tests/fixtures/ca_senate_*.html).
  * 432_029 -- 17 Feb 2021, C-7 (MAID) third reading
  * 451_079 -- 4 June 2026, C-9 (hate propaganda) third reading
  * 403_039 -- 16 June 2010, the span-wrapped markup and split labels
  * 403_042 -- 22 June 2010, a senator who left before 42-1 (Vivienne Poy)
  * soft404 -- what a made-up sitting URL returns, 200 OK
  * index_43-2 -- the session index: backslash hrefs and the latest-sitting box
"""

import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ca_store, db, filter as filt  # noqa: E402
from src.http import FetchError  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sd = _load("ca_senate_debates")
rt = _load("ca_retag")
c5 = _load("ca_5ca")
TAX = filt.load_taxonomy(os.path.join(ROOT, "config", "taxonomy.yaml"))
WL = filt.load_watchlist(os.path.join(ROOT, "config", "watchlist-ca.yaml"))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def quiet(*a):
    return None


# As tools/ca_senate.py stores them: 'Last, First Middle', from vote pages.
SENATORS = [("senator-2858", "Plett, Donald Neil"), ("senator-207804", "Dean, Tony"),
            ("senator-2813", "Martin, Yonah"), ("senator-3568", "Wells, David M."),
            ("senator-235202", "Wells, Kristopher"), ("senator-207808", "Bernard, Wanda Thomas"),
            ("senator-2774", "Eggleton, Art"), ("senator-159", "Cordy, Jane"),
            ("senator-207802", "Pate, Kim"), ("senator-236810", "Hébert, Martine")]
C7 = "An Act to amend the Criminal Code (medical assistance in dying)"
C9 = ("An Act to amend the Criminal Code (hate propaganda, hate crime and access to "
      "religious or cultural places)")


def store(bills=True, senators=SENATORS):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    ca_store.ensure_schema(conn)
    for pid, name in senators:
        conn.execute("INSERT INTO ca_senators (person_id, name) VALUES (?,?)", (pid, name))
    if bills:
        for key, parl, sess, number, title in (("43-2/C-7", 43, 2, "C-7", C7),
                                               ("45-1/C-9", 45, 1, "C-9", C9)):
            conn.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title) "
                         "VALUES (?,?,?,?,?)", (key, parl, sess, number, title))
    conn.commit()
    return conn


def sitting(key):
    ps, rest = key.split("/")
    number, date = rest.split("db_")
    return {"key": key, "parliament": int(ps[:-1]), "session": int(ps[-1]), "number": int(number),
            "date": date, "url": "https://sencanada.ca/en/content/sen/chamber/{0}/debates/{1}-e".format(ps, rest)}


def read(conn, key, page):
    problem, ivs = sd.parse_sitting(fixture(page))
    assert problem is None, problem
    return sd.store_sitting(conn, sitting(key), ivs, TAX, WL, "2026-10-02")


def speeches(conn, **where):
    sql = "SELECT * FROM ca_speeches"
    if where:
        sql += " WHERE " + " AND ".join("{0}=?".format(k) for k in where)
    return [dict(r) for r in conn.execute(sql, tuple(where.values()))]


class IndexTests(unittest.TestCase):
    def test_backslash_hrefs_are_normalised_and_the_latest_box_dropped(self):
        rows = sd.parse_index(fixture("ca_senate_index_43-2.html"), "43-2")
        self.assertEqual(len(rows), 56, "the 56 calendar links; the forward-slash 451 box is not one")
        self.assertTrue(all("\\" not in r["url"] for r in rows))
        self.assertTrue(all(r["url"].startswith("https://sencanada.ca/en/content/sen/chamber/432/debates/")
                            for r in rows))
        c7 = next(r for r in rows if r["key"] == "432/029db_2021-02-17")
        self.assertEqual((c7["number"], c7["date"], c7["parliament"], c7["session"]),
                         (29, "2021-02-17", 43, 2))
        self.assertEqual(c7["url"], "https://sencanada.ca/en/content/sen/chamber/432/debates/029db_2021-02-17-e")
        self.assertNotIn("451", " ".join(r["key"] for r in rows))
        self.assertEqual([r["number"] for r in rows], sorted(r["number"] for r in rows))

    def test_the_current_sessions_latest_sitting_is_counted_once(self):
        page = ('<div class="sc-in-the-chamber-nav-typed-page-latest-url"><a href="/en/content/sen/'
                'chamber/451/debates/088db_2026-09-29-e">Tuesday</a></div>'
                '<a href="/en\\content\\sen\\chamber\\451\\debates\\087db_2026-09-25-e">25</a>'
                '<a href="/en\\content\\sen\\chamber\\451\\debates\\088db_2026-09-29-e">29</a>')
        self.assertEqual([r["number"] for r in sd.parse_index(page, "45-1")], [87, 88])

    def test_an_index_from_another_session_folder_is_not_this_session(self):
        page = '<a href="/en\\content\\sen\\chamber\\441\\debates\\001db_2021-11-23-e">1</a>'
        self.assertEqual(sd.parse_index(page, "45-1"), [])


class ParseTests(unittest.TestCase):
    def test_the_soft_404_is_a_gap_never_an_empty_sitting(self):
        problem, ivs = sd.parse_sitting(fixture("ca_senate_soft404.html"))
        self.assertIn("soft-404", problem)
        self.assertEqual(ivs, [])

    def test_no_senate_heading_or_no_interventions_is_a_gap(self):
        problem, _ = sd.parse_sitting("<html><title>Debates</title><p><b>Hon. A B:</b> x</p></html>")
        self.assertIn("THE SENATE", problem)
        problem, _ = sd.parse_sitting("<title>Debates</title><h2>THE SENATE</h2><p>Prayers.</p>")
        self.assertIn("no interventions", problem)

    def test_headings_time_and_the_bill_from_the_order_line(self):
        problem, ivs = sd.parse_sitting(fixture("ca_senate_432_029.html"))
        self.assertIsNone(problem)
        plett = next(iv for iv in ivs if iv["label"].startswith("Hon. Donald Neil Plett"))
        self.assertEqual(plett["rubric"], "ORDERS OF THE DAY")
        self.assertEqual(plett["subject"], "Criminal Code — Bill to Amend—Third Reading")
        self.assertEqual(plett["bill"], "C-7", "from 'On the Order: ... third reading of Bill C-7'")
        self.assertEqual(plett["time"], "14:50", "the last (1450) marker before him")
        self.assertEqual(ivs[0]["time"], "14:00", "'The Senate met at 2 p.m.' before any marker")
        # A mover's label has no colon, and their own sentence names the bill.
        boisvenu = next(iv for iv in ivs if iv["label"] == "Hon. Pierre-Hugues Boisvenu")
        self.assertEqual(boisvenu["bill"], "S-224")
        self.assertTrue(boisvenu["text"].startswith("introduced Bill S-224"))
        self.assertNotIn("(1", plett["text"][:6], "a time marker is not speech text")

    def test_the_2010_markup_span_wrapped_and_split_labels(self):
        problem, ivs = sd.parse_sitting(fixture("ca_senate_403_039.html"))
        self.assertIsNone(problem)
        labels = [iv["label"] for iv in ivs]
        # <b>The Hon. the Speaker</b><i> pro tempore</i><b>:</b>
        self.assertIn("The Hon. the Speaker pro tempore", labels)
        self.assertNotIn("", labels)
        self.assertEqual({iv["kind"] for iv in ivs if "Speaker" in iv["label"]}, {"chair"})
        self.assertIn("collective", {iv["kind"] for iv in ivs})
        # <b>Hon. Consiglio Di Nino </b>moved second reading of Bill C-2
        dinino = next(iv for iv in ivs if iv["label"] == "Hon. Consiglio Di Nino")
        self.assertEqual(dinino["bill"], "C-2")
        self.assertRegex(dinino["time"], r"^1\d:\d0$")

    def test_uppercase_tags_parse_as_lowercase_ones(self):
        page = ("<TITLE>Debates</TITLE><H2>THE SENATE</H2><H1>ORDERS OF THE DAY</H1>"
                "<H2>Criminal Code</H2><H3>Bill to Amend—Second Reading</H3>"
                "<P><SPAN lang=\"en-ca\">On the Order: second reading of Bill S-7, An Act.</SPAN></P>"
                "<P><SPAN lang=\"en-ca\"><B>Hon. Anne C. Cools:</B> Honourable senators.</SPAN></P>"
                "<P><SPAN lang=\"en-ca\">(1510)</SPAN></P>"
                "<P><SPAN lang=\"en-ca\">More.</SPAN></P>")
        problem, ivs = sd.parse_sitting(page)
        self.assertIsNone(problem)
        self.assertEqual([(iv["label"], iv["bill"], iv["text"]) for iv in ivs],
                         [("Hon. Anne C. Cools", "S-7", "Honourable senators.\nMore.")])

    def test_the_footer_is_not_the_last_speech(self):
        _, ivs = sd.parse_sitting(fixture("ca_senate_432_029.html"))
        self.assertNotIn("Senate of Canada", [iv["label"] for iv in ivs])
        self.assertNotIn("footer text", ivs[-1]["text"])

    def test_emphasis_is_not_a_speaker(self):
        self.assertIsNone(sd.split_label("<b>Fact</b> sheets were tabled."))
        self.assertEqual(sd.split_label("<b>Hon. Patti LaBoucane-Benson (Legislative Deputy)</b><b>,</b> "
                                        "for Senator Moreau")[0],
                         "Hon. Patti LaBoucane-Benson (Legislative Deputy)")


class StoreTests(unittest.TestCase):
    def test_c7_plett_and_dean_are_resolved_and_stored_on_our_ground(self):
        conn = store()
        t = read(conn, "432/029db_2021-02-17", "ca_senate_432_029.html")
        plett = speeches(conn, person_id="senator-2858")
        dean = speeches(conn, person_id="senator-207804")
        self.assertTrue(plett and dean)
        self.assertIn("cave in to the opinion of one judge in one province",
                      " ".join(s["text"] for s in plett))
        self.assertIn("Bill C-7 reaches back to the 2015 Supreme Court decision in Carter",
                      " ".join(s["text"] for s in dean))
        s = plett[0]
        self.assertEqual((s["chamber"], s["forum"], s["committee"], s["bill_number"]),
                         ("senate", "floor", None, "C-7"))
        self.assertRegex(s["speech_id"], r"^sen-432-029-\d+$")
        self.assertEqual(s["sitting_key"], "432/029db_2021-02-17")
        self.assertEqual(s["speaker_key"], "donald neil plett")
        self.assertIn(2, json.loads(s["areas"]))
        # The chair is counted, never stored.
        self.assertFalse([r for r in speeches(conn) if "Speaker" in r["speaker"]])
        self.assertGreater(t["chair"], 0)
        row = dict(conn.execute("SELECT * FROM ca_senate_sittings").fetchone())
        self.assertEqual((row["parliament"], row["session"], row["number"], row["date"]),
                         (43, 2, 29, "2021-02-17"))
        self.assertEqual(row["on_ground"], len(speeches(conn)))
        # Ten senators in this store: the rest of the 2021 speakers are counted unresolved.
        self.assertEqual(row["members_resolved"], 5)
        self.assertGreater(row["speakers"], row["members_resolved"])

    def test_senate_sittings_never_move_the_house_frontier(self):
        conn = store()
        read(conn, "451/079db_2026-06-04", "ca_senate_451_079.html")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ca_sittings").fetchone()[0], 0)
        self.assertEqual(sd.han.next_sitting(conn, 45, 1, seed=138), 138)

    def test_c9_wells_and_martin_and_the_initial_that_tells_two_wells_apart(self):
        conn = store()
        read(conn, "451/079db_2026-06-04", "ca_senate_451_079.html")
        david = speeches(conn, person_id="senator-3568")
        self.assertIn("in my capacity as critic of Bill C-9", " ".join(s["text"] for s in david))
        self.assertTrue(speeches(conn, person_id="senator-2813"), "Yonah Martin")
        k = speeches(conn, speaker="Senator K. Wells")
        self.assertTrue(k)
        self.assertEqual({s["person_id"] for s in k}, {"senator-235202"})
        self.assertEqual({s["bill_number"] for s in david}, {"C-9"})

    def test_the_bills_long_title_lifts_matches_in_its_own_session_only(self):
        with_title = store()
        read(with_title, "451/079db_2026-06-04", "ca_senate_451_079.html")
        without = store(bills=False)
        read(without, "451/079db_2026-06-04", "ca_senate_451_079.html")
        n_with, n_without = len(speeches(with_title)), len(speeches(without))
        self.assertGreater(n_with, n_without + 20,
                           "'Criminal Code -- Motion in Amendment Negatived' says nothing about C-9")
        # A C-9 of ANOTHER session must never lend its title (the 2010 Museums Act tag).
        decoy = store(bills=False)
        decoy.execute("INSERT INTO ca_bills (bill_key, parliament, session, number, long_title) "
                      "VALUES ('44-1/C-9', 44, 1, 'C-9', 'An Act to ban conversion therapy')")
        read(decoy, "451/079db_2026-06-04", "ca_senate_451_079.html")
        self.assertEqual(len(speeches(decoy)), n_without)
        self.assertFalse(any(4 in json.loads(s["areas"]) for s in speeches(decoy)))

    def test_a_senator_who_left_before_2015_keeps_a_key_and_no_id(self):
        conn = store()
        t = read(conn, "403/042db_2010-06-22", "ca_senate_403_042.html")
        poy = speeches(conn, speaker_key="vivienne poy")
        self.assertEqual({s["speaker"] for s in poy}, {"Hon. Vivienne Poy", "Senator Poy"},
                         "'Senator Poy' learned from the Hon. label in the same sitting")
        self.assertEqual({s["person_id"] for s in poy}, {None})
        self.assertIn(1, json.loads(poy[0]["areas"]))
        self.assertEqual(t["unresolved"], len(poy))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ca_senators").fetchone()[0],
                         len(SENATORS), "never minted from a name")

    def test_the_2010_span_markup_stores_a_resolved_senator(self):
        conn = store()
        read(conn, "403/039db_2010-06-16", "ca_senate_403_039.html")
        rows = speeches(conn)
        self.assertEqual([(r["person_id"], r["bill_number"]) for r in rows],
                         [("senator-2774", "C-268")], "Eggleton on trafficking, area 12")
        self.assertIn(12, json.loads(rows[0]["areas"]))

    def test_senator_last_resolves_only_to_an_hon_label_in_the_same_sitting(self):
        ivs = [{"label": "Senator Cordy", "kind": "senator"},
               {"label": "Hon. Kristopher Wells", "kind": "senator"},
               {"label": "Hon. David M. Wells", "kind": "senator"},
               {"label": "Senator Wells", "kind": "senator"},
               {"label": "Senator D. Wells", "kind": "senator"},
               {"label": "Senator Hébert", "kind": "senator"}]
        conn = store()
        sd.attribute(ivs, sd.Senators(conn), sd.Members(conn))
        got = [(iv["label"], iv["person_id"], iv["speaker_key"]) for iv in ivs]
        self.assertEqual(got, [
            ("Senator Cordy", None, None),             # no Hon. Jane Cordy label in this sitting
            ("Hon. Kristopher Wells", "senator-235202", "kristopher wells"),
            ("Hon. David M. Wells", "senator-3568", "david m wells"),
            ("Senator Wells", None, None),             # two Wells, no initial
            ("Senator D. Wells", "senator-3568", "david m wells"),
            ("Senator Hébert", None, None)])

    def test_the_senate_may_file_a_senator_under_a_middle_name(self):
        """Live, 16 Feb 2021: the floor said "Hon. Margaret Dawn Anderson",
        the vote pages "Anderson, Dawn"."""
        conn = store(senators=SENATORS + [("senator-218927", "Anderson, Dawn")])
        senators = sd.Senators(conn)
        self.assertEqual(senators.resolve("Margaret Dawn Anderson"), "senator-218927")
        self.assertEqual(senators.resolve("Wanda Thomas Bernard"), "senator-207808")
        self.assertIsNone(senators.resolve("Margaret Anderson Smith"), "the surname must match too")

    def test_a_nickname_bracket_is_not_the_role(self):
        self.assertEqual(sd.hon_name("Hon. Flordeliz (Gigi) Osler"), "Flordeliz Osler")
        self.assertEqual(sd.hon_name("Hon. Flordeliz (Gigi) Osler (Deputy Facilitator)"),
                         "Flordeliz Osler")
        self.assertEqual(sd.hon_name("Hon. Mark Holland, P.C., M.P., Minister of Health"),
                         "Mark Holland")
        conn = store(senators=[("senator-227907", "Osler, Flordeliz (Gigi)")])
        self.assertEqual(sd.Senators(conn).resolve(sd.hon_name("Hon. Flordeliz (Gigi) Osler")),
                         "senator-227907")

    def test_a_senator_appointed_since_the_last_vote_resolves_once_they_vote(self):
        conn = store()
        conn.execute("INSERT INTO ca_speeches (speech_id, sitting_key, person_id, speaker, "
                     "speaker_key, chamber, areas) VALUES ('sen-451-087-9', '451/087db_2026-09-28', "
                     "NULL, 'Hon. Geeta Tucker', 'geeta tucker', 'senate', '[2]')")
        self.assertEqual(sd.reresolve(conn), 0)
        conn.execute("INSERT INTO ca_senators (person_id, name) VALUES ('senator-9', 'Tucker, Geeta')")
        self.assertEqual(sd.reresolve(conn), 1)
        self.assertEqual(speeches(conn)[0]["person_id"], "senator-9")

    def test_a_minister_resolves_to_the_house_only_by_a_unique_name_and_writes_no_member(self):
        conn = store()
        conn.execute("INSERT INTO ca_members (person_id, name) VALUES ('25524', 'Mark Holland')")
        ivs = [{"label": "Hon. Mark Holland, P.C., M.P., Minister of Health", "kind": "member"},
               {"label": "Hon. Nobody Known, P.C., M.P., Minister of X", "kind": "member"},
               {"label": "Ms. Legault", "kind": "other"}]
        sd.attribute(ivs, sd.Senators(conn), sd.Members(conn))
        self.assertEqual([(iv["person_id"], iv["speaker_key"]) for iv in ivs],
                         [("25524", None), (None, None), (None, None)])
        self.assertEqual(sd.label_kind("Hon. Mark Holland, P.C., M.P., Minister of Health"), "member")
        self.assertEqual(sd.label_kind("Some Hon. Senators"), "collective")
        self.assertEqual(sd.label_kind("Hon. senators"), "collective")
        self.assertEqual(sd.label_kind("Hon Senators"), "collective", "a typo seen live, 2021")
        self.assertEqual(sd.label_kind("The Hon. the Acting Speaker"), "chair")
        self.assertEqual(sd.label_kind("The Chair"), "chair")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ca_members").fetchone()[0], 1)


class FakeClient:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get_text(self, url, feed, slug, archive=True, **kw):
        self.calls.append(url)
        page = self.pages.get(url)
        if isinstance(page, Exception):
            raise page
        if page is None:
            raise FetchError(url, feed, slug, 1, OSError("unexpected " + url))
        return page


SEN = "https://sencanada.ca/en/content/sen/chamber/{0}/debates/{1}-e"


def client_43_2(extra=None):
    index = ('<a href="/en/content/sen/chamber/451/debates/088db_2026-09-29-e">latest</a>'
             '<a href="/en\\content\\sen\\chamber\\432\\debates\\028db_2021-02-16-e">16</a>'
             '<a href="/en\\content\\sen\\chamber\\432\\debates\\029db_2021-02-17-e">17</a>')
    pages = {"https://sencanada.ca/en/in-the-chamber/debates/43-2": index,
             SEN.format("432", "029db_2021-02-17"): fixture("ca_senate_432_029.html"),
             SEN.format("432", "028db_2021-02-16"): fixture("ca_senate_soft404.html")}
    pages.update(extra or {})
    return FakeClient(pages)


class PullTests(unittest.TestCase):
    def pull(self, conn, client, **kw):
        kw.setdefault("sessions", ("43-2",))
        return sd.pull(conn, client, "2026-10-02", tax=TAX, wl=WL, log=quiet,
                       sleep=lambda s: None, **kw)

    def test_a_gap_is_recorded_and_retried_and_a_read_sitting_is_skipped(self):
        conn = store()
        client = client_43_2()
        out = self.pull(conn, client)
        self.assertEqual((out["read"], out["gaps"], out["listed"]), (2, 1, 2))
        self.assertGreater(out["stored"], 5)
        self.assertNotIn(SEN.format("451", "088db_2026-09-29"), client.calls,
                         "the latest box is never followed")
        keys = [r[0] for r in conn.execute("SELECT sitting_key FROM ca_senate_sittings")]
        self.assertEqual(keys, ["432/029db_2021-02-17"], "a gap gets no sittings row")
        gap = conn.execute("SELECT feed, detail FROM gaps").fetchone()
        self.assertEqual(gap[0], "ca-senate-debates")
        self.assertIn("432/028db_2021-02-16", gap[1])
        again = client_43_2()
        out = self.pull(conn, again)
        self.assertEqual(out["read"], 1, "the read sitting is skipped, the gap retried")
        self.assertNotIn(SEN.format("432", "029db_2021-02-17"), again.calls)

    def test_newest_first_under_a_cap_and_the_pause_between_requests(self):
        conn = store()
        client = client_43_2()
        paused = []
        out = sd.pull(conn, client, "2026-10-02", sessions=("43-2",), limit=1, tax=TAX, wl=WL,
                      log=quiet, sleep=paused.append, pause=1.0)
        self.assertEqual((out["read"], out["pending"]), (1, 1))
        self.assertEqual(client.calls[-1], SEN.format("432", "029db_2021-02-17"))
        self.assertEqual(paused, [1.0], "one pause, before the second request")

    def test_only_reads_the_named_numbers_from_the_index(self):
        conn = store()
        client = client_43_2()
        out = self.pull(conn, client, only={29, 99})
        self.assertEqual((out["read"], out["gaps"]), (1, 0), "99 is not in the index: never built")
        self.assertEqual(client.calls[-1], SEN.format("432", "029db_2021-02-17"))

    def test_a_dry_run_writes_nothing(self):
        conn = store()
        out = self.pull(conn, client_43_2(), dry_run=True)
        self.assertGreater(out["stored"], 5)
        for table in ("ca_speeches", "ca_senate_sittings", "gaps"):
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM {0}".format(table)).fetchone()[0], 0)

    def test_an_index_with_no_links_is_a_gap(self):
        conn = store()
        client = FakeClient({"https://sencanada.ca/en/in-the-chamber/debates/43-2": "<html></html>"})
        out = self.pull(conn, client)
        self.assertEqual((out["read"], out["gaps"]), (0, 1))

    def test_three_gaps_in_a_row_stop_the_session(self):
        conn = store()
        index = "".join('<a href="/en\\content\\sen\\chamber\\432\\debates\\{0:03d}db_2021-03-{0:02d}-e">x</a>'
                        .format(n) for n in range(1, 7))
        pages = {"https://sencanada.ca/en/in-the-chamber/debates/43-2": index}
        for n in range(1, 7):
            pages[SEN.format("432", "{0:03d}db_2021-03-{0:02d}".format(n))] = fixture("ca_senate_soft404.html")
        client = FakeClient(pages)
        out = self.pull(conn, client, limit=None)
        self.assertEqual((out["read"], out["gaps"], out["pending"]), (3, 3, 3))


class RetagAndSheetTests(unittest.TestCase):
    def test_the_retag_reproduces_senate_rows_from_the_long_title(self):
        """Trust check: tags that came from the bill's long title must be
        re-derived with it, or the gated table refuses every retag."""
        conn = store()
        read(conn, "451/079db_2026-06-04", "ca_senate_451_079.html")
        changes = rt.retag(conn, TAX, WL, dry_run=True, log=quiet)
        self.assertEqual([c for c in changes if c[0] == "ca_speeches"], [])

    def test_senators_speeches_only_on_senate_sheets(self):
        conn = store()
        read(conn, "432/029db_2021-02-17", "ca_senate_432_029.html")
        conn.execute("INSERT INTO ca_members (person_id, name, sitting) VALUES ('5', 'An MP', 1)")
        conn.execute("INSERT INTO ca_speeches (speech_id, sitting_key, date, subject, person_id, "
                     "areas, excerpt) VALUES ('h1', '45-1-142', '2026-09-23', 'Criminal Code', '5', "
                     "'[2]', 'MAID must stop')")
        conn.execute("UPDATE ca_senators SET affiliation='C'")
        # Seated senators are those on the latest fetched vote's details page.
        conn.execute("INSERT INTO ca_divisions (division_key, chamber, parliament, session, number, "
                     "date, subject, areas, positions_fetched) VALUES ('senate-43-2-1', 'senate', "
                     "43, 2, 1, '2021-02-17', 'Other business', '[9]', 1)")
        conn.execute("INSERT INTO ca_votes (division_key, person_id, position) VALUES "
                     "('senate-43-2-1', 'senator-2858', 'Nay')")
        conn.commit()
        senate, _, _ = c5.build_rows(conn, 2, "senate", {}, {}, today="2026-10-02")
        commons, _, _ = c5.build_rows(conn, 2, "commons", {}, {}, today="2026-10-02")
        senate = {r["person_id"]: r for r in senate}
        commons = {r["person_id"]: r for r in commons}
        self.assertIn("SPEECH", " ".join(senate["senator-2858"]["comments"]))
        self.assertIn("[activity, not direction]", " ".join(senate["senator-2858"]["comments"]))
        self.assertEqual(senate["senator-2858"]["column"], "0", "a speech never places anyone")
        self.assertNotIn("5", senate)
        self.assertFalse([p for p in commons if p.startswith("senator-")])
        self.assertIn("SPEECH", " ".join(commons["5"]["comments"]))


class SchemaTests(unittest.TestCase):
    def test_the_table_is_declared_and_the_key_column_exists(self):
        self.assertIn("ca_senate_sittings", db.TABLES)
        conn = store()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ca_speeches)")}
        self.assertTrue({"chamber", "forum", "committee", "speaker_key"} <= cols)

    def test_speech_title(self):
        self.assertEqual(ca_store.speech_title("Criminal Code — Third Reading", "C-7", C7),
                         "Criminal Code — Third Reading — Bill C-7, " + C7)
        self.assertEqual(ca_store.speech_title("Tributes", None, None), "Tributes")
        self.assertIsNone(ca_store.speech_title(None))


if __name__ == "__main__":
    unittest.main()
