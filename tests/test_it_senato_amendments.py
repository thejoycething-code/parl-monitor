"""The Italian Senate's amendment texts (12 October 2026, Chris: "Yes, build
it"): src/it_amendments.py, tools/it_senato_amendments.py and their readers
(the 5CA drafts, the amendment worklist, the session judge's queue).

Fixtures under tests/fixtures/it_senato_amendments/ are trimmed copies of
files read from github.com/SenatoDellaRepubblica/AkomaNtosoBulkData on 12
October 2026 (Leg19/Atto00059761, S.1735): Assembly amendment 1.23, order
of the day G1.1, committee amendment 1.13 (expression, manifestation,
lifecycle and person references cut; body paragraphs trimmed) and the empty
document the Senate published as 01503340-em.akn.xml. The tree and SPARQL
answers are built here in the shape the live services gave. No network.
"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import db, it_amendments as ia  # noqa: E402
from src.http import FetchError  # noqa: E402
from tools import it_senato_amendments as T  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "it_senato_amendments")
QUIET = lambda *a, **k: None  # noqa: E731


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


FILES = {   # path in the act folder -> fixture
    "emend/01503268-em.akn.xml": "01503268-em.akn.xml",
    "emend/01503185-em.akn.xml": "01503185-em.akn.xml",
    "emend/01503340-em.akn.xml": "01503340-em.akn.xml",
    "emendc/01485001-em.akn.xml": "emendc-1.13-em.akn.xml",
}
FOLDER = "Leg19/Atto00059761"


def tree(sha="tree-1", files=FILES, overrides=None):
    items = [{"path": "README.MD", "type": "blob", "sha": "x"},
             {"path": "emend", "type": "tree", "sha": "t1"},
             {"path": "ddlpres/01485369-ft.akn.xml", "type": "blob", "sha": "y"}]
    for path, fx in files.items():
        items.append({"path": path, "type": "blob",
                      "sha": (overrides or {}).get(path) or ia.git_blob_sha(fixture(fx))})
    return {"sha": sha, "tree": items, "truncated": False}


class FakeError(Exception):
    def __init__(self, code):
        self.code = code


class FakeClient:
    """get_bytes by URL; counts what was asked."""

    def __init__(self, trees=None, sparql=None, remaining=50):
        self.trees = trees if trees is not None else {FOLDER: tree()}
        self.sparql = sparql if sparql is not None else {"19/S.1735": 59761}
        self.asked, self.headers_seen, self.remaining = [], [], remaining
        self.last_headers = {}

    def get_bytes(self, url, feed, slug, archive=True, headers=None, **kw):
        self.asked.append(url)
        self.headers_seen.append(headers)
        if url.startswith(T.SENATO_SPARQL):
            rows = [{"leg": {"value": a.split("/")[0]}, "fase": {"value": a.split("/")[1]},
                     "f": {"value": str(f)}} for a, f in self.sparql.items()]
            return json.dumps({"results": {"bindings": rows}}).encode()
        if url.startswith("https://api.github.com/"):
            self.remaining -= 1
            self.last_headers = {"X-RateLimit-Remaining": str(self.remaining)}
            folder = url.split(":", 2)[2].split("?")[0]
            if folder not in self.trees:
                raise FetchError(url, feed, slug, 1, FakeError(404))
            return json.dumps(self.trees[folder]).encode()
        if url.startswith("https://raw.githubusercontent.com/"):
            path = url.split(FOLDER + "/", 1)[1]
            return fixture(FILES[path])
        raise AssertionError("unexpected URL " + url)

    def raw_asked(self):
        return [u for u in self.asked if u.startswith("https://raw.githubusercontent.com/")]


DIVISIONS = (
    # key, title, bill_key, bill_keys
    ("senato-19-424-2", "Em. 1.23 (1a parte) , D'Elia e altri", "19/S.1735", '["19/S.1735"]'),
    ("senato-19-424-8", "ODG G1.1, De Cristofaro e altri", "19/S.1735", '["19/S.1735"]'),
    # a committee-only number: the Assembly never had a 1.13 here
    ("senato-19-424-3", "Em. 1.13, Sbrollini", "19/S.1735", '["19/S.1735"]'),
    # a joint examination recorded under another reading: matched through bill_keys
    ("senato-19-424-20", "Emm. 1.23 e G1.1", "19/S.163", '["19/S.163", "19/S.1735"]'),
    ("senato-19-424-16", "Votazione finale", "19/S.1735", '["19/S.1735"]'),
)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "store.db")
        conn = db.init_db(db.connect(self.path))
        conn.execute("INSERT INTO it_bills (bill_key, legislature, chamber, number, title) VALUES "
                     "('19/S.1735', 19, 'S', '1735', 'Disposizioni in materia di consenso informato')")
        for key, title, bk, bks in DIVISIONS:
            conn.execute("INSERT INTO it_divisions (division_key, chamber, legislature, date, title, bill_key, "
                         "bill_keys, tier, areas) VALUES (?, 'senato', 19, '2026-06-04', ?, ?, ?, 1, '[6]')",
                         (key, title, bk, bks))
        conn.commit()
        conn.close()
        # quiet: the module's prints and the default `log` of its gap and read helpers
        T.print = QUIET
        self._defaults = (T._gap.__defaults__, T.read_act.__defaults__)
        T._gap.__defaults__ = (QUIET,)
        T.read_act.__defaults__ = (QUIET,)

    def tearDown(self):
        del T.print
        T._gap.__defaults__, T.read_act.__defaults__ = self._defaults

    def run_tool(self, client, *args, today="2026-10-12"):
        return T.main(["--db", self.path] + list(args), client=client, today=today)

    def conn(self):
        return db.connect(self.path)


class ParseTests(unittest.TestCase):
    def test_an_assembly_amendment(self):
        got = ia.parse_akn(fixture("01503268-em.akn.xml"))
        self.assertEqual((got["number"], got["kind"], got["act"], got["sede"], got["presented"]),
                         ("1.23", "Emendamento", "19/S.1735", "A", "2026-06-04"))
        self.assertEqual(got["proposers"][:2], ["D'ELIA", "CRISANTI"])
        self.assertTrue(got["text"].startswith("Al comma 1, primo periodo, sostituire le parole"))
        self.assertIn("la comunicazione preventiva", got["text"])

    def test_an_order_of_the_day_and_a_committee_amendment(self):
        odg = ia.parse_akn(fixture("01503185-em.akn.xml"))
        self.assertEqual((odg["number"], odg["kind"], odg["sede"]), ("G1.1", "Ordine del giorno", "A"))
        com = ia.parse_akn(fixture("emendc-1.13-em.akn.xml"))
        self.assertEqual((com["number"], com["sede"], com["proposers"]), ("1.13", "C", ["Sbrollini", "D'Elia"]))

    def test_the_empty_document_and_junk(self):
        self.assertIsNone(ia.parse_akn(fixture("01503340-em.akn.xml")))
        self.assertTrue(ia.is_empty_akn(fixture("01503340-em.akn.xml")))
        self.assertIsNone(ia.parse_akn(b"<html>not xml"))
        self.assertFalse(ia.is_empty_akn(b"<html>not xml"))

    def test_the_vote_wording(self):
        cases = {
            "Em. 1.23 (1a parte) , D'Elia e altri": (["1.23"], "1a parte"),
            "Emm. 3.1 e 3.2": (["3.1", "3.2"], None),
            "Emm. 1.1, 1.2, 1.3, 1.4 e 1.100": (["1.1", "1.2", "1.3", "1.4", "1.100"], None),
            "ODG G1.104, Scalfarotto": (["G1.104"], None),
            "Em. 7.0.100/98 (1a parte), Parrini e altri": (["7.0.100/98"], "1a parte"),
            "Emm. 7.0.100/71, 7.0.100/72 e 7.0.100/73": (["7.0.100/71", "7.0.100/72", "7.0.100/73"], None),
            "Em. 1.5 (testo 2), Giorgis e altri": (["1.5 (testo 2)"], None),
            "Em. 1-ter.1, Giacobbe": (["1-ter.1"], None),
            "Em. 2.0.2, Il Relatore": (["2.0.2"], None),
            "Articolo 3": ([], None), "Votazione finale": ([], None),
            "Votazione questione pregiudiziale": ([], None),
        }
        for title, want in cases.items():
            self.assertEqual(ia.vote_numbers(title), want, title)

    def test_norm_and_folder(self):
        self.assertEqual(ia.norm("1.5 (testo 2)"), ia.norm("1.5(Testo 2)"))
        self.assertEqual(ia.norm(" G1.104 "), "g1.104")
        self.assertEqual(ia.act_folder(19, 59761), "Leg19/Atto00059761")
        self.assertEqual(ia.git_blob_sha(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_the_idfase_query_and_answer(self):
        q = T.q_id_fase(["19/S.1735", "19/S.824"])
        self.assertIn('"S.1735", "S.824"', q)
        self.assertEqual(T.parse_id_fase({"results": {"bindings": [
            {"leg": {"value": "19"}, "fase": {"value": "S.824"}, "f": {"value": "57364"}}]}}),
            {"19/S.824": 57364})


class CollectorTests(Base):
    def test_a_first_read_stores_and_links(self):
        client = FakeClient()
        rc = self.run_tool(client)
        self.assertEqual(rc, 0)
        conn = self.conn()
        rows = conn.execute("SELECT number, sede, kind, act, id_fase FROM it_senate_amendments "
                            "ORDER BY file_path").fetchall()
        self.assertEqual([tuple(r) for r in rows], [
            ("G1.1", "A", "Ordine del giorno", "19/S.1735", 59761),
            ("1.23", "A", "Emendamento", "19/S.1735", 59761),
            (None, "A", None, "19/S.1735", 59761),       # the empty document, kept so it is not refetched
            ("1.13", "C", "Emendamento", "19/S.1735", 59761)])
        links = {(r[0], r[1]): (r[2], r[3]) for r in conn.execute(
            "SELECT division_key, number, status, part FROM it_senate_amendment_votes")}
        self.assertEqual(links, {
            ("senato-19-424-2", "1.23"): ("split", "1a parte"),     # flagged, not guessed
            ("senato-19-424-8", "G1.1"): ("linked", None),
            ("senato-19-424-3", "1.13"): ("not_found", None),       # committee text is not the Assembly's
            ("senato-19-424-20", "1.23"): ("linked", None),
            ("senato-19-424-20", "G1.1"): ("linked", None)})
        # one API request (the tree), one SPARQL query, the raw files
        self.assertEqual(len([u for u in client.asked if "api.github.com" in u]), 1)
        self.assertEqual(len(client.raw_asked()), 4)
        st = conn.execute("SELECT id_fase, tree_sha, files, checked FROM it_senate_amend_acts "
                          "WHERE act='19/S.1735'").fetchone()
        self.assertEqual(tuple(st), (59761, "tree-1", 4, "2026-10-12"))

    def test_nothing_is_fetched_twice(self):
        self.run_tool(FakeClient())
        same = FakeClient()
        self.assertEqual(self.run_tool(same, "--force", today="2026-10-19"), 0)
        self.assertEqual(len([u for u in same.asked if "api.github.com" in u]), 1)
        self.assertEqual(same.raw_asked(), [])            # tree sha unchanged
        self.assertFalse(any(u.startswith(T.SENATO_SPARQL) and "S.1735" in u for u in same.asked))  # idFase kept
        moved = FakeClient(trees={FOLDER: tree(sha="tree-2")})
        self.run_tool(moved, "--force", today="2026-10-26")
        self.assertEqual(moved.raw_asked(), [])           # a new tree, but every file's sha is stored

    def test_a_changed_file_is_fetched_and_a_bad_sha_is_a_gap(self):
        self.run_tool(FakeClient())
        bad = FakeClient(trees={FOLDER: tree(sha="tree-2", overrides={"emend/01503268-em.akn.xml": "0" * 40})})
        self.assertEqual(self.run_tool(bad, "--force", today="2026-10-19"), 3)
        self.assertEqual(len(bad.raw_asked()), 1)
        conn = self.conn()
        self.assertEqual(conn.execute("SELECT file_sha FROM it_senate_amendments WHERE number='1.23'").fetchone()[0],
                         ia.git_blob_sha(fixture("01503268-em.akn.xml")))   # the old row stands
        self.assertEqual(conn.execute("SELECT tree_sha FROM it_senate_amend_acts").fetchone()[0], "tree-1")
        self.assertTrue(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed=?", (T.FEED,)).fetchone()[0])

    def test_an_act_with_no_folder_is_not_a_gap(self):
        client = FakeClient(trees={})
        self.assertEqual(self.run_tool(client), 0)
        self.assertEqual(self.conn().execute("SELECT files, checked FROM it_senate_amend_acts").fetchone()[:],
                         (0, "2026-10-12"))
        links = {r[0] for r in self.conn().execute("SELECT status FROM it_senate_amendment_votes")}
        self.assertEqual(links, {"not_found"})

    def test_the_api_cap_leaves_acts_for_the_next_run(self):
        client = FakeClient()
        self.assertEqual(self.run_tool(client, "--max-api", "0"), 3)
        self.assertEqual(client.raw_asked(), [])
        self.assertEqual({r[0] for r in self.conn().execute("SELECT status FROM it_senate_amendment_votes")},
                         {"not_read"})
        api = T.Api(FakeClient(), 30)                     # GitHub's own counter is honoured too
        self.assertFalse(api.spent())
        api.remaining = T.MIN_REMAINING - 1
        self.assertTrue(api.spent())

    def test_an_act_not_due_is_not_read(self):
        self.run_tool(FakeClient())
        later = FakeClient()
        # votes 2026-06-04: not within 90 days of 2026-10-20, last read 8 days ago
        self.assertEqual(self.run_tool(later, today="2026-10-20"), 0)
        self.assertEqual([u for u in later.asked if "api.github.com" in u], [])
        stale = FakeClient()
        self.run_tool(stale, today="2026-11-20")
        self.assertEqual(len([u for u in stale.asked if "api.github.com" in u]), 1)

    def test_a_token_travels_in_a_header_only(self):
        client = FakeClient()
        api = T.Api(client, 5, token="secret-token")
        api.get_json(ia.TREE_URL.format(folder=FOLDER), "t")
        self.assertNotIn("secret-token", client.asked[-1])
        self.assertEqual(client.headers_seen[-1]["Authorization"], "Bearer secret-token")
        T.Api(client, 5).get_json(ia.TREE_URL.format(folder=FOLDER), "t")
        self.assertIsNone(client.headers_seen[-1])

    def test_link_only_is_offline(self):
        self.run_tool(FakeClient())
        conn = self.conn()
        conn.execute("DELETE FROM it_senate_amendment_votes")
        conn.commit()
        self.assertEqual(T.main(["--db", self.path, "--link-only"], client=object()), 0)
        self.assertEqual(self.conn().execute("SELECT COUNT(*) FROM it_senate_amendment_votes").fetchone()[0], 5)


class ReaderTests(Base):
    def setUp(self):
        super().setUp()
        self.run_tool(FakeClient())
        self.ro = c5.connect_ro(self.path)

    def tearDown(self):
        self.ro.close()
        super().tearDown()

    def test_the_text_line_and_the_split_warning(self):
        line = c5.amendment_text(self.ro, "it", "senato-19-424-2")
        self.assertIn("Em. 1.23 (D'ELIA, CRISANTI, RANDO and others): Al comma 1", line)
        self.assertIn("github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/master/" + FOLDER, line)
        self.assertIn("SPLIT VOTE: only the 1a parte was put", line)
        self.assertIn("ODG G1.1", c5.amendment_text(self.ro, "it", "senato-19-424-8"))
        self.assertIsNone(c5.amendment_text(self.ro, "it", "senato-19-424-3"))   # not found: no text
        self.assertIsNone(c5.amendment_text(self.ro, "pl", "senato-19-424-2"))
        self.assertIsNone(c5.amendment_text(None, "it", "senato-19-424-2"))

    def test_an_old_store_without_the_tables(self):
        conn = db.connect(os.path.join(self.tmp, "empty.db"))
        self.assertEqual(ia.texts_for(conn, "senato-19-424-2"), [])
        self.assertIsNone(c5.amendment_text(conn, "it", "senato-19-424-2"))

    def test_the_5ca_draft_gives_the_reader_the_text(self):
        cfg = tempfile.mkdtemp()
        c5.draft(self.ro, "it", config_dir=cfg, today="2026-10-12", log=QUIET)
        divs, _, _ = c5.load("it", cfg)
        e = divs["senato-19-424-8"]
        self.assertEqual((e["status"], e["vote_kind"]), ("needs_reading", "amendment"))
        self.assertIn("its text is in the store", e["read_first"])
        self.assertIn("Il Senato", e["read_first"])
        self.assertIn("does not hold", divs["senato-19-424-3"]["read_first"])   # no text found

    def test_the_worklist_carries_the_text(self):
        from tools import amendment_worklist as wl
        cfg = tempfile.mkdtemp()
        c5.draft(self.ro, "it", config_dir=cfg, today="2026-10-12", log=QUIET)
        items = {i["key"]: i for i in wl.build(self.ro, ("it",), cfg)}
        it = items["senato-19-424-2"]
        self.assertEqual(it["amendment_texts"][0]["number"], "1.23")
        self.assertIn("1a parte", it["split_vote"])
        self.assertTrue(any(u["sure"] and "AkomaNtosoBulkData" in u["url"] for u in it["urls"]))
        self.assertEqual(items["senato-19-424-3"]["amendment_texts"][0]["status"], "not_found")
        self.assertTrue(any("senato.it/leg/19" in u["url"] for u in items["senato-19-424-3"]["urls"]))
        self.assertIn("with the amendment's text stored (Italy's Senate): 3",
                      wl.summary(list(items.values())))


if __name__ == "__main__":
    unittest.main()
