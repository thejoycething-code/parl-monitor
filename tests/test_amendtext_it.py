"""Italy (Camera): the amendment, order of the day or motion a vote names
(src/amendtext_it.py).

Fixtures: the Allegato A pages of sittings 9, 16, 72 and 251 of the 19th
legislature, captured live from documenti.camera.it on 16 October 2026 and
trimmed to the items the tests read (tests/fixtures/amendtext/it; each file
names its page). Votes of the store (sha 12dfcd342515):
  camera-vs19_072_012  "Emendamento 1.4 QUARTINI ..." to A.C. 977: civil unions
                       in its text -> area 9, through the gate
  camera-vs19_009_071  ODG 9/5/33: "cittadinanza" in its "impegna il Governo" is
                       "reddito di cittadinanza" (the basic income), a false
                       friend masked since 17 October 2026 -> no match
  camera-vs19_251_099  motion 1-00245 "sul capoverso settimo della parte
                       dispositiva": only commitment 7 is the purpose; the
                       press-freedom words elsewhere are gated
  camera-vs19_016_017  motion 1-00031 "limitatamente alla premessa": a vote on
                       the premises has no purpose -> gated

THE OPERATIVE PART (17 October 2026): sittings 179, 582 and 626, captured live
on 17 October 2026 and trimmed the same way, carry the law 194 motions whose
commitments sat past the old 3,000-character purpose clip:
  camera-vs19_626_001  motion 1-00545 (whole): commitment 13 "la relazione
                       sull'attuazione della legge n. 194 del 1978", 5,000+
                       characters into the operative part -> area 1 now
  camera-vs19_582_009  motion 1-00526, all but commitment 12: commitment 15
                       "legge n. 194 del 1978" -> area 1
  camera-vs19_582_010  the same motion, commitment 12 only (mental health) ->
                       no area 1
  camera-vs19_582_011  "CPV 6 E 16 PREMESSA": premise paragraphs only. Read as
                       the whole motion before (the "E" was not split), so
                       the wider purpose would have placed it -> no purpose
  camera-vs19_179_008  motion 1-00191, all but capoversi 1, 7, 9, 12:
                       commitment 8 (law 194, conscientious objection) -> area 1
  camera-vs19_179_029  motion 1-00197, all but capoversi 4, 7, 8, 15:
                       commitment 10 (law 194, obiezione di coscienza) -> area 1
  camera-vs19_179_033  1-00197 "sulla premessa della parte dispositiva": only
                       the opening "impegna il Governo:" -> no area
  camera-vs19_414_032  resolution 6-00159 (sitting 414): "suicidio" (area 2,
                       tier 1) only in its premises (prison suicides) -> review
                       only
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from src import amendtext, amendtext_it as it  # noqa: E402
from amendtext_fake import FixtureClient  # noqa: E402


class ItalyReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = FixtureClient("it")
        cls.reader = it.ItalyReader(cls.client)
        cls.tax, cls.wl, mask = cls.reader.taxonomy()
        cls.mask = staticmethod(mask)
        cls.rows = cls.client.rows()

    def read(self, key):
        row = self.rows[key]
        lk = self.reader.fetch(row, self.reader.refs(row))
        res, labels = amendtext.match(lk, self.tax, self.wl, self.mask)
        return lk, res, (amendtext.ledger_ok(lk, labels, self.tax, self.wl, self.mask) if labels else False)

    def test_refs(self):
        self.assertEqual(it.refs_of("Emendamento 7-bis.1 ORRICO ANNA LAURA (M5S) - Votazione Emendamento 7-bis.1 "
                                    "DDL n. 2662", "camera-vs19_554_061"), ["seduta 554", "eme 7-bis.1 ac 2662"])
        self.assertEqual(it.refs_of("Ordine del giorno n. 9/1866/11 BONETTI ELENA (APERRE) - Votazione",
                                    "camera-vs19_551_078"), ["seduta 551", "odg 9/1866/11"])
        self.assertEqual(it.refs_of("RIS 6-285, PREMESSA - Votazione Risoluzione 6_00285", "camera-vs19_600_001"),
                         ["seduta 600", "risoluzione 6-00285"])
        self.assertEqual(it.refs_of("Articolo 1 - Votazione Articolo 1 DDL n. 2345", "camera-vs19_600_002"), [])

    def test_vote_parts(self):
        self.assertEqual(it.vote_part("Mozione n. 1-00245, sul capoverso settimo della parte dispositiva X"),
                         ("items", [7]))
        self.assertEqual(it.vote_part("RIS 6-254 NO IMP 3, 4 E PREMESSE - Votazione"), ("except", [3, 4]))
        self.assertEqual(it.vote_part("Mozione n. 1-00244, sul capoverso trentesimo delle premesse X"),
                         ("premise", []))
        self.assertEqual(it.vote_part("Mozione n. 1-00517 BOSCHI MARIA ELENA (IVICRE) ed altri"), ("whole", []))

    def test_outcomes_match_the_live_measurement(self):
        for key, want in self.client.expected().items():
            lk, res, gate = self.read(key)
            self.assertEqual(lk.status, want["status"], key)
            self.assertEqual(res.issue_areas if res else None, want["areas"], key)
            self.assertEqual(gate, want["ledger"], key)

    def test_premise_vote_has_no_purpose(self):
        lk, res, gate = self.read("camera-vs19_016_017")
        self.assertEqual(lk.texts[0]["purpose"], "")
        self.assertIn("vote on the premises", lk.texts[0]["label"])

    def test_not_printed_fails_loud(self):
        row = dict(self.rows["camera-vs19_072_012"], title="Emendamento 9.999 X - Votazione Emendamento 9.999 DDL n. 977")
        lk = self.reader.fetch(row, self.reader.refs(row))
        self.assertEqual(lk.status, "unreadable")
        self.assertIn("eme 9.999 ac 977 not printed in the Allegato A", lk.gap)


class OperativePartTests(unittest.TestCase):
    """The purpose is the operative part, whole (17 October 2026)."""

    PREMISES_ONLY = ("La Camera,\npremesso che:\nla legge n. 194 del 1978 tutela la maternità;\n"
                     "fu accolto un ordine del giorno che impegna il Governo a garantire "
                     "l'interruzione volontaria di gravidanza;\n"
                     "impegna il Governo:\n1) a potenziare i servizi di prevenzione oncologica;\n"
                     "2) a ridurre le liste d'attesa.\n(1-00999) «Rossi, Bianchi».")

    @classmethod
    def setUpClass(cls):
        cls.client = FixtureClient("it")
        cls.reader = it.ItalyReader(cls.client)
        cls.tax, cls.wl, mask = cls.reader.taxonomy()
        cls.mask = staticmethod(mask)
        cls.rows = cls.client.rows()

    def gate(self, key, title=None):
        row = dict(self.rows[key], **({"title": title} if title else {}))
        lk = self.reader.fetch(row, self.reader.refs(row))
        self.assertEqual(lk.status, "ok", lk.gap)
        res, labels = amendtext.match(lk, self.tax, self.wl, self.mask)
        g = amendtext.gated(lk, labels, self.tax, self.wl, self.mask, res) if labels else None
        return lk, res, g

    def test_law_194_motion_gains_area_1_from_its_operative_part(self):
        lk, res, g = self.gate("camera-vs19_626_001")
        self.assertIn(1, g.issue_areas)
        self.assertIn("legge n. 194", g.matched_terms)
        purpose = lk.texts[0]["purpose"]
        self.assertTrue(purpose.startswith("impegna il Governo:"))
        self.assertGreater(len(purpose), amendtext.OPERATIVE_CHARS)     # the old clip would have lost it
        self.assertNotIn("(1-00545)", purpose)                          # the signature is not the purpose
        self.assertNotIn("premesso che", purpose)

    def test_conscientious_objection_commitment_of_a_part_vote(self):
        for key in ("camera-vs19_179_008", "camera-vs19_179_029", "camera-vs19_582_009"):
            lk, res, g = self.gate(key)
            self.assertIsNotNone(g, key)
            self.assertIn(1, g.issue_areas, key)
        lk, _, _ = self.gate("camera-vs19_179_029")
        self.assertIn("obiezione di coscienza", lk.texts[0]["purpose"])

    def test_votes_on_other_commitments_or_the_premises_stay_out(self):
        for key in ("camera-vs19_582_010", "camera-vs19_582_011", "camera-vs19_179_033"):
            lk, res, g = self.gate(key)
            self.assertTrue(g is None or 1 not in g.issue_areas, key)
        lk, _, _ = self.gate("camera-vs19_582_011")
        self.assertEqual(lk.texts[0]["purpose"], "")
        lk, _, _ = self.gate("camera-vs19_179_033")
        self.assertEqual(lk.texts[0]["purpose"], "impegna il Governo:")

    def test_tier_1_term_only_in_the_premises_is_review_only(self):
        lk = amendtext.Lookup("ok", texts=[amendtext.entry(
            "mozione 1-00999", "mozione", "si.1-00999", "", it.operative(self.PREMISES_ONLY), self.PREMISES_ONLY,
            purpose_chars=it.PURPOSE_CHARS)])
        res, labels = amendtext.match(lk, self.tax, self.wl, self.mask)
        self.assertIn(1, res.issue_areas)                                # matched in the body ...
        self.assertIsNone(amendtext.gated(lk, labels, self.tax, self.wl, self.mask, res))   # ... review only

    def test_live_motion_with_tier_1_only_in_its_premises(self):
        # resolution 6-00159: "suicidio" (area 2, tier 1) in premise 35, on
        # suicides in the prison police; nothing of area 2 in what it commits to
        lk, res, g = self.gate("camera-vs19_414_032")
        self.assertIn(2, res.issue_areas)
        self.assertTrue(g is None or 2 not in g.issue_areas)
        self.assertNotIn("suicidio", lk.texts[0]["purpose"])      # its commitment 16 says "suicidi", no term

    def test_operative_openings(self):
        self.assertEqual(it.operative(self.PREMISES_ONLY).split("\n")[0], "impegna il Governo:")
        cases = [
            ("La Camera,\npremesso che:\nx;\nimpegna il Governo a:\n1) fare X.\n9/12/3. Rossi.",
             "impegna il Governo a:\n1) fare X."),
            ("La Camera,\npremesso che:\nx,\nimpegna il Governo\na valutare l'opportunità di fare X.\n9/12/3. Rossi.",
             "impegna il Governo\na valutare l'opportunità di fare X."),
            ("La Camera,\npremesso che:\nx,\nimpegnano il Governo e il Ministro della salute:\nfare X.",
             "impegnano il Governo e il Ministro della salute:\nfare X."),
            ("La Camera,\nimpegna, altresì, il Governo\na fare X.", "impegna, altresì, il Governo\na fare X."),
            ("La Camera\nautorizza\nla missione A;\nnon autorizza:\nla missione B.\n(6-00281) «Braga».",
             "autorizza\nla missione A;\nnon autorizza:\nla missione B."),
            ("La Camera,\nudita la relazione,\ndelibera\ndi approvare X.", "delibera\ndi approvare X."),
            ("La Camera, premesso che x, impegna il Governo a fare X.", "impegna il Governo a fare X."),
            ("La Camera,\npremesso che:\nx;", ""),
        ]
        for text, want in cases:
            self.assertEqual(it.operative(text), want, text)

    def test_amendment_operative_text(self):
        text = ("Dopo il comma 2, aggiungere il seguente:\n2-bis. Il Fondo è incrementato di 5 milioni. "
                "Agli oneri derivanti dal presente comma si provvede mediante corrispondente riduzione del "
                "Fondo per le politiche della famiglia.\n*1.23. Ferrari.\n*1.24. Colucci, Penza.")
        self.assertEqual(it.amendment_operative(text),
                         "Dopo il comma 2, aggiungere il seguente:\n2-bis. Il Fondo è incrementato di 5 milioni.")
        self.assertEqual(it.amendment_operative("Sopprimere l'articolo 5.\n5.1. Rossi."), "Sopprimere l'articolo 5.")
        self.assertEqual(it.amendment_operative(
            "Al comma 1, sostituire le parole: X con le seguenti: Y.\n1. 4. Quartini."),
            "Al comma 1, sostituire le parole: X con le seguenti: Y.")

    def test_vote_parts_of_the_camera_shorthand(self):
        cases = {
            "MOZ 1-526 RIF CPV 6 E 16 PREMESSA - Votazione": ("premise", []),
            "MOZ 1-525 RIF CPV 4,7-10,17,18 PREM - Votazione": ("premise", []),
            "MOZ 1-593 PREM NO CPV 4, 5, 16 E 18 - Votazione": ("premise", []),
            "MOZ 1-526 RIF NO CPV 12 DIS, 6,16 P - Votazione": ("except", [12]),
            "RIS 6-217 NO CPV 2-4, 7 E 8-16 DISP - Votazione": ("except", [2, 3, 4, 7] + list(range(8, 17))),
            "RIS 6-258 NO PREM NO CPV2,3,7,10DIS - Votazione": ("except", [2, 3, 7, 10]),
            "RIS 6-282, IMP AGG SCHEDA 3 - Votazione": ("part", []),
            "RIS 6-262 PARTE NON PRECLUSA - Votazione": ("part", []),
            "Mozione n. 1-00197, sulla premessa della parte dispositiva, ZANELLA LUANA (AVS)": ("alinea", []),
            "Risoluzione n. 6-00008, limitamente al ventunesimo capoverso della parte dispositiva": ("items", [21]),
            "Risoluzione n. 6-00158, limitatamente ai capoversi trentaquattresimo e trentacinquesimo della "
            "parte dispositiva": ("items", [34, 35]),
            "Risoluzione n. 6-00158, limitatamente alla premessa e alla restante parte della parte dispositiva":
                ("part", []),
            "Risoluzione n. 6-00071, limitatamente agli impegni nn. 14, 20 e 27, della parte dispositiva":
                ("items", [14, 20, 27]),
            "Risoluzione n. 6-00070, ad eccezione dell'impegno n. 20, BRUNO RAFFAELE": ("except", [20]),
            "Mozione n. 1-00244, sul primo capoverso delle premesse X": ("premise", []),
        }
        for title, want in cases.items():
            self.assertEqual(it.vote_part(title), want, title)

    def test_false_friends(self):
        self.assertNotIn("cittadinanza", it.mask("favorire il pieno sviluppo della persona, la cittadinanza, "
                                                 "attraverso l'inclusione sociale"))
        self.assertIn("cittadinanza", it.mask("le domande di cittadinanza degli stranieri residenti"))
        self.assertNotIn("silenzio-assenso", it.mask("si applica il meccanismo del silenzio-assenso per gli organi"))
        self.assertIn("silenzio-assenso", it.mask("il silenzio-assenso alla donazione di organi"))


if __name__ == "__main__":
    unittest.main()
