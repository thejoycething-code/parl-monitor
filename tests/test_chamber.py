"""What was said and asked in the chamber (parity layer 5, 10 October 2026):
src/chamber_store.py and the per-country collectors tools/<cc>_chamber.py.

Fixtures (trimmed from the live sources, 10 October 2026):
  tests/fixtures/nl/verslag-2026-10-06-vragenuur.xml.gz  the Tweede Kamer's
      Handelingen of 6 October 2026, two agenda items kept (Vragenuur and
      Regeling van werkzaamheden)
  tests/fixtures/ch/transcripts-sample.json.gz  eight Amtliches Bulletin rows:
      the 26.029 inclusion bill (21 September 2026, where 'IVG' is the
      disability-insurance law) and the abortion constitutional initiative
      25.455 (29 September 2026), each with the chair
"""

import gzip
import json
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import chamber_store as cs  # noqa: E402
from src import country_edition as ce  # noqa: E402
from src import db, drain  # noqa: E402
from src import filter as filt  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")
TODAY = "2026-10-10"


def fixture(*parts):
    with gzip.open(os.path.join(FIX, *parts)) as fh:
        return fh.read()


def mini_taxonomy():
    """Area 1 with one tier-1 and one tier-2 term, for the guard tests."""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w") as fh:
        fh.write("version: test\nareas:\n  1_abortion:\n    tier1: [\"abortus*\"]\n"
                 "    tier2: [\"anticonceptie*\"]\n")
    try:
        return filt.load_taxonomy(path)
    finally:
        os.remove(path)


class FakeClient:
    """Answers by URL fragment; counts the documents fetched."""

    def __init__(self, routes):
        self.routes = routes
        self.fetched = []

    def _find(self, url):
        for frag, body in self.routes.items():
            if frag in url:
                self.fetched.append(frag)
                return body
        raise AssertionError("unexpected fetch: " + url)

    def get_json(self, url, feed, slug, **kw):
        body = self._find(url)
        return json.loads(body) if isinstance(body, (str, bytes)) else body

    def get_bytes(self, url, feed, slug, **kw):
        return self._find(url)


def store():
    return db.init_db(db.connect(":memory:"))


class SchemaTests(unittest.TestCase):

    def test_tables_follow_the_feeds_and_are_declared(self):
        self.assertIn("nl_questions", cs.tables("nl"))
        self.assertNotIn("ch_questions", cs.tables("ch"))   # the Swiss edition has Vorstösse
        self.assertTrue(set(cs.TABLES) <= set(db.TABLES))
        conn = store()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue(set(cs.TABLES) <= names)
        self.assertNotIn("ch_questions", names)


class GuardTests(unittest.TestCase):
    """The long-transcript guard: a speech is matched in its own passages."""

    def setUp(self):
        self.taxes = [mini_taxonomy()]

    def test_tier_one_passage_matches(self):
        m = cs.classify_speech(self.taxes, "Wij spreken vandaag over abortus en de kliniek.")
        self.assertEqual(m.areas, [1])
        self.assertEqual(m.tier, 1)
        self.assertIn("abortus", m.excerpt)

    def test_tier_two_alone_needs_a_tier_one_debate_title(self):
        body = "De minister moet de anticonceptie vergoeden."
        self.assertFalse(cs.classify_speech(self.taxes, body,
                                            cs.classify_title(self.taxes, "Begroting VWS")))
        m = cs.classify_speech(self.taxes, body,
                               cs.classify_title(self.taxes, "Wet afbreking abortus"))
        self.assertEqual((m.areas, m.tier), ([1], 2))

    def test_a_debate_title_never_lends_its_areas(self):
        m = cs.classify_speech(self.taxes, "Voorzitter, ik heb een vraag over de begroting.",
                               cs.classify_title(self.taxes, "Wet afbreking abortus"))
        self.assertFalse(m)

    def test_questions_take_tier_two(self):
        m = cs.classify_question(self.taxes, "Vragen over anticonceptie voor jongeren")
        self.assertEqual((m.areas, m.tier), ([1], 2))


class NetherlandsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import nl_chamber
        cls.nl = nl_chamber
        cls.xml = fixture("nl", "verslag-2026-10-06-vragenuur.xml.gz")
        cls.turns = nl_chamber.parse_verslag(cls.xml)

    def test_turns_carry_debate_speaker_and_party(self):
        debates = {t[1] for t in self.turns}
        self.assertEqual(debates, {"Vragenuur", "Regeling van werkzaamheden"})
        ergin = [t for t in self.turns if t[3] == "Ergin"]
        self.assertTrue(ergin)
        self.assertEqual(ergin[0][4], "DENK")

    def test_the_chair_is_marked_and_the_label_is_not_the_speech(self):
        self.assertTrue(any(t[6] for t in self.turns))          # the voorzitter
        import re
        label = re.compile(r"^(De heer|Mevrouw|Minister|Staatssecretaris) [^.]{0,60}:")
        for t in self.turns:
            self.assertIsNone(label.match(t[7]), t[7][:60])

    def test_collect_store_and_skip_an_unchanged_report(self):
        listing = {"value": [
            {"Id": "a8685b4b-0000", "Soort": "Tussenpublicatie", "Status": "Ongecorrigeerd",
             "GewijzigdOp": "2026-10-07T01:00:00", "Vergadering_Id": "vg-10",
             "Vergadering": {"Id": "vg-10", "Titel": "10e vergadering", "Datum":
                             "2026-10-06T00:00:00+02:00"}}]}
        client = FakeClient({"OData/v4/2.0/Verslag?": listing,
                             "Verslag(a8685b4b-0000)/resource": self.xml})
        conn = store()
        taxes = cs.load_taxonomies("nl")
        run = cs.Run("nl", conn, client, TODAY, "2026-10-01", drain.Budget(600), taxes,
                     log=lambda *_: None)
        self.nl.speeches(run)
        rows = conn.execute("SELECT speaker, party, areas, debate FROM nl_speeches").fetchall()
        self.assertTrue(rows)
        self.assertIn(("Ergin", "DENK"), {(r[0], r[1]) for r in rows})
        self.assertTrue(all(r[2] != "[]" for r in rows))
        reads = conn.execute("SELECT segments, matched, status FROM nl_record_reads").fetchone()
        self.assertEqual(reads[1], len(rows))
        self.assertGreater(reads[0], reads[1])
        # The same version again: listed and re-stamped, not fetched again.
        client.fetched.clear()
        run2 = cs.Run("nl", conn, client, "2026-10-11", "2026-10-01", drain.Budget(600), taxes,
                      log=lambda *_: None)
        self.nl.speeches(run2)
        self.assertNotIn("Verslag(a8685b4b-0000)/resource", client.fetched)
        self.assertEqual(conn.execute("SELECT last_seen FROM nl_record_reads").fetchone()[0],
                         "2026-10-11")

    def test_questions_parse_asker_party_and_minister(self):
        z = {"Nummer": "2026Z21771", "Soort": "Schriftelijke vragen",
             "Onderwerp": "Deepfake pornografie van vrouwelijke politici",
             "GestartOp": "2026-10-09T00:00:00+02:00", "Afgedaan": False, "ZaakActor": [
                 {"ActorNaam": "Q.M. Rajkowski", "ActorFractie": "VVD", "Relatie": "Medeindiener"},
                 {"ActorNaam": "S.C. Kröger", "ActorFractie": "PRO", "Relatie": "Indiener"},
                 {"ActorNaam": "D.M. van Weel", "Functie": "minister van Justitie en Veiligheid",
                  "Relatie": "Gericht aan"}]}
        q = self.nl.parse_question(z)
        self.assertEqual(q["asker"], "S.C. Kröger and 1 other(s)")
        self.assertEqual(q["party"], "PRO")
        self.assertEqual(q["addressee"], "minister van Justitie en Veiligheid")
        self.assertIsNone(q["answered"])
        self.assertEqual(q["date"], "2026-10-09")

    def test_best_version_prefers_the_corrected_record(self):
        vs = [{"Vergadering_Id": "x", "Soort": "Tussenpublicatie", "GewijzigdOp": "2026-10-09"},
              {"Vergadering_Id": "x", "Soort": "Eindpublicatie", "GewijzigdOp": "2026-10-08"}]
        self.assertEqual(self.nl.best_versions(vs)["x"]["Soort"], "Eindpublicatie")


class SwitzerlandTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import ch_chamber
        cls.ch = ch_chamber
        cls.rows = json.loads(fixture("ch", "transcripts-sample.json.gz"))["d"]
        cls.by_file = cs.load_taxonomies("ch", by_file=True)

    def areas(self, row):
        text = self.ch.speech_text(row["Text"])
        lang = self.ch.language(row.get("LanguageOfText"), text)
        return cs.classify_speech(self.ch.taxes_for(self.by_file, lang), self.ch.mask(text)).areas

    def test_ivg_the_disability_law_is_not_abortion(self):
        inclusion = [r for r in self.rows if r["MeetingDate"] == "20260921"
                     and not self.ch.is_chair(r["SpeakerFunction"])]
        self.assertTrue(inclusion)
        for r in inclusion:
            self.assertNotIn(1, self.areas(r), r["SpeakerFullName"])

    def test_the_abortion_debate_is_abortion_in_both_languages(self):
        debate = [r for r in self.rows if r["MeetingDate"] == "20260929"
                  and not self.ch.is_chair(r["SpeakerFunction"])]
        langs = set()
        for r in debate:
            text = self.ch.speech_text(r["Text"])
            langs.add(self.ch.language(r.get("LanguageOfText"), text))
            self.assertIn(1, self.areas(r), r["SpeakerFullName"])
        self.assertEqual(langs, {"DE", "FR"})

    def test_chair_label_and_layout_marks(self):
        self.assertTrue(self.ch.is_chair("P-M"))
        self.assertTrue(self.ch.is_chair("1VP-F"))
        self.assertFalse(self.ch.is_chair("BR-F"))
        self.assertEqual(self.ch.role_of("BR-F"), "Federal Councillor")
        text = self.ch.speech_text("<pd_text><p><b>Bühler Manfred</b> (V, BE): Frau Kollegin, "
                                   "Sie argumentieren[GZ]</p></pd_text>")
        self.assertEqual(text, "Frau Kollegin, Sie argumentieren")


class AustriaTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import at_chamber
        cls.at = at_chamber
        cls.page = json.loads(fixture("at", "sitzung-xxviii-96-kinderschutz.json.gz"))
        cls.html = fixture("at", "rede-a-16-19-18-01017985.html.gz").decode("utf-8")

    def test_contributions_carry_the_debate_and_the_speech_file(self):
        got = self.at.contributions(self.page)
        self.assertEqual(len(got), 18)
        debate_id, debate, who, party, kind, url = got[0]
        self.assertEqual((who, party), ("Ricarda Berger", "FPÖ"))
        self.assertEqual(debate, "Dringlicher Antrag zum Kinderschutz")
        self.assertTrue(url.startswith("https://www.parlament.gv.at/dokument/XXVIII/NRSITZ/96/"))
        self.assertNotIn("#", url)
        minister = [g for g in got if "Regierungsbank" in g[4]][0]
        self.assertEqual(self.at.role_of(minister[4], minister[3]), "Federal Government")

    def test_speech_text_is_the_speech_alone(self):
        text = self.at.speech_text(self.html)
        self.assertIn("Abtreibung", text)
        self.assertNotIn("Die angezeigte Rede", text)
        self.assertNotIn("Sitzung, XXVIII. GP", text)
        self.assertNotIn("Beifall", text)                       # the benches, not the speaker
        m = cs.classify_speech(cs.load_taxonomies("at"), text)
        self.assertIn(1, m.areas)

    def test_interjections_never_lend_an_area(self):
        text = self.at.speech_text("<main><p>Name (FPÖ), 96. Sitzung, XXVIII. GP des NR, 19:13 "
                                   "RN/149 19.13 Abgeordnete Name (FPÖ): Wir reden über das "
                                   "Budget. (Ruf bei der FPÖ: Abtreibung ist Mord!) Danke.</p>"
                                   "</main>")
        self.assertEqual(text.split(), "Wir reden über das Budget. Danke.".split())


class BrazilTests(unittest.TestCase):

    def test_addressee_from_the_ementa(self):
        import br_chamber
        self.assertEqual(br_chamber.addressee(
            "Requer informações ao Ministro de Estado da Saúde, Sr. Alexandre Padilha, acerca "
            "de eventuais reuniões"), "Ministro de Estado da Saúde")
        self.assertEqual(br_chamber.addressee(
            "Requer informações ao Ministério das Relações Exteriores acerca das providências"),
            "Ministério das Relações Exteriores")

    def test_untracked_answers_are_not_called_unanswered(self):
        conn = store()
        cs.store_question(conn, "br", {
            "question_id": "RIC 1/2026", "kind": "request", "date": "2026-10-08",
            "title": "Requer informações sobre o aborto legal", "asker": "Deputada X",
            "party": "PL", "addressee": "Ministro da Saúde", "answered": "untracked"},
            cs.Match([1], ["aborto"], 1), TODAY)
        got = cs.edition_items(conn, "br", "2026-10-01", "2026-10-09", {})
        self.assertEqual(got[0]["takeaway"],
                         "Request for information from Deputada X (PL) to Ministro da Saúde")


class FranceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import fr_chamber
        cls.fr = fr_chamber
        cls.date, cls.items = fr_chamber.parse_sitting(fixture("fr", "compte-rendu-2027o1n011.xml.gz"))

    def test_debates_are_the_level_one_points_and_each_question(self):
        debates = {i[0] for i in self.items}
        self.assertIn("Questions au gouvernement: Mobilisation lycéenne", debates)
        self.assertTrue(any(d and d.startswith("Réponse intégrale aux violences") for d in debates))
        self.assertEqual(self.date, "2026-10-07")

    def test_the_chair_is_left_out_and_turns_are_joined(self):
        self.assertFalse([i for i in self.items if self.fr.CHAIR.match(i[2])])
        pairs = [(i[0], i[1]) for i in self.items]
        for a, b in zip(pairs, pairs[1:]):
            self.assertNotEqual(a, b)                           # consecutive turns merged
        self.assertEqual(self.fr.split_name("Mme Sandrine Josso (Dem)"),
                         ("Mme Sandrine Josso", "Dem"))

    def test_sessions_and_uids(self):
        self.assertEqual(self.fr.sessions_for("2026-09-01", "2026-10-10"),
                         ["S2026E1", "S2026E2", "S2027O1"])
        self.assertEqual(self.fr.uid("S2027O1", 12), "CRSANR5L17S2027O1N012")

    def test_questions_classified_on_the_index_not_the_text(self):
        import zipfile
        with open(os.path.join(FIX, "fr", "questions-ecrites-sample.json.zip"), "rb") as fh:
            zf = zipfile.ZipFile(fh)
            qs = {n: self.fr.parse_question(json.loads(zf.read(n))["question"], "written")
                  for n in zf.namelist()}
        taxes = cs.load_taxonomies("fr")
        condoms = qs["json/QANR5L17QE18270.json"]
        self.assertEqual(condoms["question_id"], "QE 18270")
        self.assertEqual(condoms["party"], "GDR")
        self.assertTrue(condoms["asker"].startswith("M. Stéphane Peu"))
        self.assertIn(1, cs.classify_question(taxes, condoms["title"], condoms["text"]).areas)
        music = qs["json/QANR5L17QE18826.json"]          # its text names 'soins palliatifs'
        self.assertFalse(cs.classify_question(taxes, music["title"], music["text"]))


class PolandTests(unittest.TestCase):

    def test_interpellations(self):
        import pl_chamber
        recs = json.loads(fixture("pl", "interpellations-sample.json.gz"))
        conn = store()
        conn.execute("INSERT INTO pl_members (mp_key, term, mp_id, name, club) VALUES "
                     "('10/36', 10, 36, 'Posłanka X', 'KO')")
        roster = pl_chamber.members(conn)
        taxes = cs.load_taxonomies("pl")
        got = {r["num"]: pl_chamber.parse(r, "interpellation", roster) for r in recs}
        child = got[20130]
        self.assertEqual(child["question_id"], "I 10/20130")
        self.assertEqual((child["asker"], child["party"]), ("Posłanka X and 7 other(s)", "KO"))
        self.assertIn(6, cs.classify_question(taxes, child["title"]).areas)
        self.assertFalse(cs.classify_question(taxes, got[20311]["title"]))
        self.assertTrue(got[20311]["url"].startswith("https://sejm.gov.pl/"))


class PortugalTests(unittest.TestCase):

    def test_questions_and_requests(self):
        import pt_chamber
        rec = {"Assunto": "Acesso ao planeamento familiar e a métodos contracetivos",
               "Autores": [{"GP": "PCP", "idCadastro": "1", "nome": "Paula Santos"}],
               "DataEnvio": "2026-10-02", "Destinatarios": [
                   {"nomeEntidade": "Ministra da Saúde", "respostas": [
                       {"dataResposta": "2026-11-02"}]}],
               "Id": "231000", "Legislatura": "XVII", "Nr": "102", "Sessao": "2",
               "Tipo": "Pergunta"}
        q = pt_chamber.parse(rec)
        self.assertEqual(q["question_id"], "XVII/2/P/102")
        self.assertEqual((q["asker"], q["party"], q["addressee"], q["answered"]),
                         ("Paula Santos", "PCP", "Ministra da Saúde", "2026-11-02"))
        self.assertIn(1, cs.classify_question(cs.load_taxonomies("pt"), q["title"]).areas)
        self.assertEqual(pt_chamber.parse(dict(rec, Tipo="Requerimento"))["kind"], "request")


class EditionTests(unittest.TestCase):
    """Speeches grouped by debate, questions one each, in the framework."""

    def setUp(self):
        self.conn = store()
        m = cs.Match([1], ["abortus*"], 1, "Over abortus: een uitspraak.")
        for i, who in enumerate(("Flach", "Van der Plas", "Flach")):
            cs.store_speech(self.conn, "nl", {
                "speech_id": "vg#{0}".format(i), "doc_id": "vg", "date": "2026-10-07",
                "debate_id": "act-1", "debate": "Demonstratierecht", "speaker": who,
                "party": "SGP" if who == "Flach" else "BBB", "role": "member",
                "text": "abortus", "url": "https://example.org/v"}, m, TODAY)
        cs.store_speech(self.conn, "nl", {
            "speech_id": "vg#9", "doc_id": "vg", "date": "2026-10-07", "debate_id": "act-2",
            "debate": "Asiel", "speaker": "X", "text": "asiel"}, cs.Match([11], ["asiel*"], 1, "asiel"),
            TODAY)
        cs.store_question(self.conn, "nl", {
            "question_id": "2026Z1", "kind": "written", "date": "2026-10-08",
            "title": "Vragen over abortus", "asker": "A. Lid", "party": "SGP",
            "addressee": "minister van VWS", "answered": None, "url": "https://example.org/q"},
            cs.Match([1], ["abortus*"], 1), TODAY)
        cs.mark_read(self.conn, "nl", "vg", "speeches", "2026-10-07", "v1", 900, 4, 10, TODAY)
        self.conn.commit()

    def test_items(self):
        got = cs.edition_items(self.conn, "nl", "2026-10-03", "2026-10-09", {})
        speeches = [i for i in got if i["kind"] == "speech"]
        self.assertEqual(len(speeches), 1)                      # migration hidden; one debate
        self.assertEqual(speeches[0]["title"], "Demonstratierecht")
        self.assertIn("3 speeches", speeches[0]["takeaway"])
        self.assertIn("Flach, Van der Plas", speeches[0]["takeaway"])
        q = [i for i in got if i["kind"] == "question"][0]
        self.assertIn("Written question from A. Lid (SGP) to minister van VWS", q["takeaway"])
        self.assertIn("no answer recorded yet", q["takeaway"])

    def test_rendered_in_the_netherlands_edition_not_its_dm(self):
        with tempfile.TemporaryDirectory() as d:
            text = ce.render(self.conn, ce.adapter("nl"), "2026-10-09", since="2026-10-02",
                             directory=d)
            dm = ce.dm_summary(self.conn, ce.adapter("nl"), "2026-10-09", since="2026-10-02",
                               directory=d)
        self.assertIn("## Said in the chamber", text)
        self.assertIn("## Questions", text)
        self.assertIn("*Demonstratierecht*", text)
        self.assertIn("Said in the chamber: 1 report(s) read in the window, 900 speeches", text)
        self.assertNotIn("—", text)
        self.assertNotIn("Demonstratierecht", dm)                # NL3: the DM is votes only

    def test_reclassify_keeps_rows(self):
        self.conn.execute("UPDATE nl_speeches SET text='niets ter zake' WHERE speech_id='vg#0'")
        cs.reclassify(self.conn, "nl", log=lambda *_: None)
        self.assertEqual(self.conn.execute("SELECT areas FROM nl_speeches WHERE speech_id='vg#0'")
                         .fetchone()[0], "[]")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM nl_speeches").fetchone()[0], 4)


if __name__ == "__main__":
    unittest.main()
