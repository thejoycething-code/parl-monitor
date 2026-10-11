"""France's HATVP declarations of interests (src/fr_hatvp.py, tools/fr_hatvp.py):
the declarant's own items only, matched to sitting members, shown in the
profiles with the declaration date and the HATVP page. The fixtures are
invented declarants in the HATVP's own XML and CSV shapes; every spouse,
collaborator, free-text and asset value in them carries the word SECRET,
which must never reach the store, the log or the archive. No network."""
import contextlib
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import fr_hatvp as hv, fr_store, member_intel as mi, member_profiles as mp  # noqa: E402
from src.http import FetchError  # noqa: E402
from tests.test_member_profiles import Base  # noqa: E402
from tools import fr_hatvp as tool  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "fr_hatvp")
TODAY = "2026-10-11"


def xml_bytes():
    with open(os.path.join(FIX, "declarations.xml"), "rb") as fh:
        return fh.read()


def csv_text():
    with open(os.path.join(FIX, "liste.csv"), encoding="utf-8") as fh:
        return fh.read()


def store():
    conn = sqlite3.connect(":memory:")
    for stmt in fr_store.SCHEMA:
        conn.execute(stmt)
    conn.executemany(
        "INSERT INTO fr_members (acteur_ref, chamber, name, civility, current) VALUES (?,?,?,?,?)",
        [("PA900001", "an", "Anne Exemple", "Mme", 1),
         ("PA900002", "an", "Jimmy Modèle", "M.", 1),
         ("PA900004", "an", "Jean Ancien", "M.", 0),          # no longer sits
         ("20001X", "senat", "Paul Sansid", "M.", 1)])
    mi.ensure(conn)
    return conn


def dump(conn):
    return "\n".join(conn.iterdump())


class Parse(unittest.TestCase):
    def test_own_sections_only_with_their_fields(self):
        decls = list(hv.parse_declarations(io.BytesIO(xml_bytes())))
        self.assertEqual(len(decls), 5)                    # the mayor's is not read
        anne = decls[1]
        self.assertEqual((anne["surname"], anne["first_name"], anne["mandate"], anne["dept"]),
                         ("Exemple", "Anne Marie", "depute", "69"))
        self.assertEqual(anne["deposited"], "2025-02-10 09:30:00")
        got = {(i["category"], i["text"], i["role"], i["paid"]) for i in anne["items"]}
        self.assertIn(("Activité professionnelle (cinq dernières années)", "Cabinet Exemple",
                       "Avocate", "rémunéré"), got)
        self.assertIn(("Activité de consultant", "Conseil SARL", "Conseil juridique", None), got)
        self.assertIn(("Participation à un organe dirigeant", "OGEC Saint-Joseph",
                       "Membre du conseil d'administration", "non rémunéré"), got)
        self.assertIn(("Participation financière", "SCI", "50 % du capital", None), got)
        self.assertIn(("Participation financière", "Air Exemple", "12 part(s)", None), got)
        self.assertIn(("Fonction bénévole", "Planning familial du Rhône", "Bénévole", None), got)
        self.assertIn(("Mandat électif", "Députée", None, None), got)
        self.assertNotIn("Néant", {i["text"] for i in anne["items"]})
        self.assertEqual(len(anne["items"]), 7)

    def test_spouse_collaborator_comment_and_asset_data_never_parsed(self):
        decls = list(hv.parse_declarations(io.BytesIO(xml_bytes())))
        self.assertNotIn("SECRET", repr(decls))
        self.assertNotIn("999999", repr(decls))            # a shareholding's valuation
        self.assertNotIn("42 000", repr(decls))            # amounts are never kept
        self.assertTrue({"activProfConjointDto", "activCollaborateursDto",
                         "observationInteretDto", "immeubleDto"} <= hv.SKIP)
        self.assertFalse(set(hv.KEEP) & hv.SKIP)


class Matching(unittest.TestCase):
    def setUp(self):
        self.index = hv.parse_index(csv_text())
        self.members = hv.sitting(store())

    def decl(self, surname, first, mandate="depute", dept="69"):
        return {"surname": surname, "first_name": first, "mandate": mandate, "dept": dept}

    def test_by_hatvp_id_with_a_variant_first_name(self):
        self.assertEqual(hv.match(self.decl("Exemple", "Anne Marie"), self.index, self.members),
                         ("PA900001", "id", "https://www.hatvp.fr/pages_nominatives/exemple-anne-1"))

    def test_the_only_csv_person_with_that_surname(self):
        got = hv.match(self.decl("MODELE", "Jean-Michel", dept="83"), self.index, self.members)
        self.assertEqual(got[:2], ("PA900002", "id"))

    def test_by_name_and_mandate_without_an_id(self):
        got = hv.match(self.decl("SANSID", "Paul", "senateur", "59"), self.index, self.members)
        self.assertEqual(got, ("20001X", "name",
                               "https://www.hatvp.fr/pages_nominatives/sansid-paul-3"))

    def test_former_members_and_wrong_chambers_are_not_matched(self):
        self.assertIsNone(hv.match(self.decl("ANCIEN", "Jean", dept="01"), self.index,
                                   self.members))
        self.assertIsNone(hv.match(self.decl("SANSID", "Paul", "depute"), self.index,
                                   self.members))

    def test_name_agreement(self):
        self.assertTrue(hv.surname_agrees("TACHE DE LA PAGERIE", "Emmanuel Taché"))
        self.assertTrue(hv.surname_agrees("Charret-Godard", "Océane Godard"))
        self.assertTrue(hv.surname_agrees("KBIDI", "Émeline K/Bidi"))
        self.assertFalse(hv.surname_agrees("Martin", "Jean Dupont"))
        self.assertTrue(hv.first_agrees("Liliane", "Liliana"))
        self.assertTrue(hv.first_agrees("Amal Amélia", "Amélia"))
        self.assertFalse(hv.first_agrees("Jean-Michel", "Jimmy"))


class Store(unittest.TestCase):
    def load(self, conn):
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            stats = tool.load(conn, io.BytesIO(xml_bytes()), csv_text(), TODAY)
        return stats, log.getvalue()

    def test_conjoint_data_never_reaches_the_store_or_the_log(self):
        conn = store()
        stats, log = self.load(conn)
        self.assertGreater(stats["interests"], 0)
        self.assertNotIn("SECRET", dump(conn))
        self.assertNotIn("SECRET", log)
        self.assertNotIn("Dupont", dump(conn) + log)       # the spouse's name
        self.assertNotIn("epoux", dump(conn) + log)

    def test_latest_declaration_of_each_sitting_member(self):
        conn = store()
        stats, _ = self.load(conn)
        self.assertEqual((stats["members"], stats["by_id"], stats["by_name"],
                          stats["unmatched"]), (3, 2, 1, 1))
        texts = {r[0] for r in conn.execute(
            "SELECT text FROM mi_interests WHERE member_key='PA900001'")}
        self.assertIn("Cabinet Exemple", texts)
        self.assertNotIn("Cabinet Ancien", texts)           # the older declaration
        self.assertFalse(conn.execute(
            "SELECT 1 FROM mi_interests WHERE member_key='PA900004'").fetchone())
        row = conn.execute("SELECT source, declared, url, start, end FROM mi_interests "
                           "WHERE text='Cabinet Exemple'").fetchone()
        self.assertEqual(row, ("fr-hatvp", "2025-02-10",
                               "https://www.hatvp.fr/pages_nominatives/exemple-anne-1",
                               "2019-01", "2024-06"))

    def test_an_older_store_gains_the_new_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE mi_interests (cc TEXT NOT NULL, source TEXT NOT NULL, "
                     "member_key TEXT, member_ref TEXT, name TEXT, category TEXT, text TEXT "
                     "NOT NULL, role TEXT, paid TEXT, start TEXT, end TEXT, last_seen TEXT "
                     "NOT NULL)")
        mi.ensure(conn)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(mi_interests)")]
        self.assertEqual(cols[-2:], ["declared", "url"])
        mi.replace(conn, "ch", "ch-interests", TODAY, interests=[mi.interest(
            member_key="1", text="Pro Life")])              # the old callers still work


class FakeClient:
    def __init__(self, xml=None, not_modified=False):
        self.xml, self.not_modified, self.asked, self.archived = xml, not_modified, [], []
        self.last_headers = {}

    def get_bytes(self, url, feed, slug, headers=None, archive=True, **_):
        self.asked.append((url, headers, archive))
        if url == hv.XML_URL:
            if self.not_modified:
                raise FetchError(url, feed, slug, 1, urllib.error.HTTPError(
                    url, 304, "Not Modified", {}, None))
            self.last_headers = {"Last-Modified": "Fri, 02 Oct 2026 09:00:12 GMT",
                                 "Content-Length": str(len(self.xml))}
            return self.xml
        return csv_text().encode("utf-8")

    def archive(self, raw, feed, slug):
        self.archived.append((feed, slug, raw))


class Download(unittest.TestCase):
    def run_tool(self, conn, client, today=TODAY, force=False):
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            rc = tool.run(conn, client, today, force=force)
        return rc, log.getvalue()

    def test_first_read_parses_and_archives_only_the_csv_rows(self):
        conn, client = store(), FakeClient(xml_bytes())
        rc, log = self.run_tool(conn, client)
        self.assertEqual(rc, 0)
        self.assertEqual(client.asked[0], (hv.XML_URL, None, False))   # never archived
        self.assertEqual(len(client.archived), 1)
        feed, slug, raw = client.archived[0]
        self.assertEqual(slug, "liste-parlement")
        self.assertNotIn(b"LOCAL", raw)                    # a mayor's row is not ours
        self.assertNotIn(b"SECRET", raw)
        row = hv.download_row(conn)
        self.assertEqual((row[0], row[3], row[4]),
                         ("Fri, 02 Oct 2026 09:00:12 GMT", TODAY, TODAY))
        self.assertIn("fr-hatvp:", log)
        self.assertNotIn("SECRET", log)

    def test_not_due_within_four_weeks_then_a_conditional_request(self):
        conn = store()
        self.run_tool(conn, FakeClient(xml_bytes()))
        client = FakeClient(not_modified=True)
        rc, log = self.run_tool(conn, client, today="2026-10-20")
        self.assertEqual((rc, client.asked), (0, []))
        self.assertIn("not due", log)
        rc, log = self.run_tool(conn, client, today="2026-11-09")
        self.assertEqual(rc, 0)
        self.assertEqual(client.asked, [(hv.XML_URL, {
            "If-Modified-Since": "Fri, 02 Oct 2026 09:00:12 GMT"}, True)])
        self.assertIn("unchanged", log)
        self.assertEqual(hv.download_row(conn)[3:], ("2026-11-09", TODAY))
        self.assertTrue(conn.execute("SELECT 1 FROM mi_interests WHERE source='fr-hatvp'")
                        .fetchone())                       # last month's rows stand

    def test_a_failure_is_a_gap(self):
        tmp = tempfile.mkdtemp()
        try:
            db = os.path.join(tmp, "s.db")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = tool.main(["--db", db, "--xml", os.path.join(FIX, "declarations.xml"),
                                "--csv", os.path.join(FIX, "liste.csv")])
            self.assertEqual(rc, 3)                         # no fr_members: nothing to match
            self.assertIn("[gap] fr-hatvp", out.getvalue())
        finally:
            shutil.rmtree(tmp)


class Flags(unittest.TestCase):
    def test_organisation_names_on_our_ground(self):
        flags = mi.load_flags()
        self.assertEqual(mi.flag(flags, "fr", "OGEC Saint-Joseph")[1],
                         "a Catholic school's governing body (OGEC)")
        self.assertTrue(mi.flag(flags, "fr", "Planning familial du Rhône"))
        self.assertTrue(mi.flag(flags, "fr", "Association diocésaine de Lille"))
        self.assertIsNone(mi.flag(flags, "fr", "Air Exemple"))
        self.assertIsNone(mi.flag(flags, "fr", "Vie privée et numérique"))
        # The Assemblée's own bodies keep their own reading.
        self.assertEqual(mi.flag(flags, "fr", "Délégation aux droits des femmes et à "
                                              "l'égalité des chances")[1],
                         "the women's rights delegation")
        self.assertEqual(mi.flag(flags, "fr", "Enseignement privé")[1],
                         "the study group on independent schools")
        self.assertEqual(mi.flag(flags, "fr", "Chrétiens d'Orient")[1],
                         "a study group on Christians in the East or the Holy See")


class Profiles(Base):
    def setUp(self):
        super().setUp()
        shutil.copy(mi.CONFIG, os.path.join(self.cfg, mi.CONFIG_NAME))

    def test_declared_interests_with_date_and_link(self):
        conn = store()
        with contextlib.redirect_stdout(io.StringIO()):
            tool.load(conn, io.BytesIO(xml_bytes()), csv_text(), TODAY)
        conn.row_factory = sqlite3.Row
        data = self.build(conn, "fr")
        anne = data["members"]["PA900001"]
        text = "\n".join(mp.render_intel(anne))
        self.assertIn("## Declared interests (7)", text)
        self.assertIn("**OGEC Saint-Joseph** (on our ground: a Catholic school's governing "
                      "body (OGEC))", text)
        self.assertIn("From the declaration lodged with the HATVP on 10 February 2025; [the "
                      "HATVP's page for this member](https://www.hatvp.fr/pages_nominatives/"
                      "exemple-anne-1).", text)
        self.assertIn("| Activité professionnelle (cinq dernières années) | Cabinet Exemple | "
                      "Avocate | rémunéré | 2019-01 to 2024-06 |", text)
        self.assertNotIn("SECRET", text)
        self.assertTrue(mp.has_record(anne))               # a flagged interest earns a profile


if __name__ == "__main__":
    unittest.main()
