"""France: the amendment a scrutin's title only numbers (src/amendtext_fr.py).

Fixture: tests/fixtures/amendtext/fr/amendements-sample.zip, twelve members
copied byte for byte from the Assemblee's Amendements.json.zip as published
on 16 October 2026 (their real paths kept), served here by a fake client that
answers HTTP Range requests the way data.assemblee-nationale.fr does,
including the CDN serving another build of the zip.

The votes are real scrutins of the store (sha 12dfcd342515):
  an-17-4576  n° 525 (Erodi), PLFSS 2026 nouvelle lecture, a dossier with no
              area: an abortion amendment, tier 1 in its expose -> the ledger
  an-17-6446  n° 592 (Jacobelli), military programming: "l'etat encore
              embryonnaire du programme" (a tank) matches embryon* in the
              body only -> gated, review only
  an-17-1591  sous-amendement n° 77 (Boyard): the sub-amendment is read
  an-17-6574  n° 47 filed under both B2755 and BTC2755: one amendment
  an-17-8626  n° 516 (Rousseau): read, matches nothing
  an-17-5386  n° 16 (Tryzna), no dossier: two seance amendments n° 16 by him
              disposed of that day (a joint examination) -> a gap, not a guess
"""

import io
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import amendtext, amendtext_fr as fr, db  # noqa: E402

ZIP = os.path.join(ROOT, "tests", "fixtures", "amendtext", "fr", "amendements-sample.zip")

ROWS = [
    ("an-17-4576", "2025-12-05", "DLR5L17N52922", "l'amendement n° 525 de Mme Erodi à l'article 17 et annexe "
     "(précédemment réservé) du projet de loi de financement de la sécurité sociale pour 2026 (nouvelle lecture)."),
    ("an-17-6446", "2026-05-07", "DLR5L17N54083", "l'amendement n° 592 de M. Jacobelli à l'article premier et "
     "rapport annexé du projet de loi actualisant la programmation militaire pour les années 2024 à 2030 et "
     "portant diverses dispositions intéressant la défense (première lecture)."),
    ("an-17-1591", "2025-05-07", "DLR5L17N50724", "le sous-amendement n° 77 de M. Boyard à l'amendement n° 46 "
     "de M. Henriet à l'article 3 (supprimé) de la proposition de loi relative à la lutte contre "
     "l'antisémitisme, le racisme, les discriminations, les violences et la haine dans l'enseignement "
     "supérieur (première lecture)."),
    ("an-17-6574", "2026-05-13", "DLR5L17N54006", "l'amendement n° 47 de M. Brugerolles à l'article premier "
     "de la proposition de loi pour une montagne vivante et souveraine (première lecture)."),
    ("an-17-8626", "2026-10-09", "DLR5L17N54776", "l'amendement n° 516 de Mme Sandrine Rousseau à l'article "
     "44 (examen prioritaire) de la proposition de loi apportant une réponse intégrale au phénomène des "
     "violences sexuelles et sexistes contre les femmes et les enfants (première lecture)."),
    ("an-17-5386", "2026-02-12", None, "l'amendement n° 16 de M. Tryzna à l'article premier de la proposition "
     "de loi visant à empêcher la constitution de monopoles économiques dans le secteur des médias "
     "d’information (première lecture)."),
    ("an-17-9999", "2026-02-12", None, "l'article premier de la proposition de loi visant à ..."),
]


class RangeClient:
    """Serves one byte string by HTTP Range, as the AN's CDN does. `builds`
    lists the ETags the CDN hands out in turn; only BUILD's bytes are real."""

    BUILD = '"13836cfd-65dea213bef09"'

    def __init__(self, data, builds=None):
        self.data, self.builds, self.calls, self.last_headers = data, builds or [self.BUILD], 0, {}

    def get_bytes(self, url, feed, slug, headers=None, **kw):
        etag = self.builds[self.calls % len(self.builds)]
        self.calls += 1
        rng = headers["Range"].split("=", 1)[1]
        data = self.data if etag == self.BUILD else b"\0" * 7 + self.data
        if rng.startswith("-"):
            out = data[-int(rng[1:]):]
        else:
            a, b = (int(x) for x in rng.split("-"))
            out = data[a:b + 1]
        self.last_headers = {"ETag": etag, "Content-Range": "bytes */{0}".format(len(data))}
        return out


def reader(builds=None):
    with open(ZIP, "rb") as fh:
        client = RangeClient(fh.read(), builds)
    return fr.FranceReader(client, fr.AmendementsZip(client, pause=0, local="")), client


def store():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    for i, (k, d, ref, t) in enumerate(ROWS):      # the store's own fr_divisions (init_db)
        conn.execute("INSERT INTO fr_divisions (division_key, chamber, legislature, number, date, title, "
                     "dossier_ref, areas, matched_terms, tier) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (k, "an", 17, i, d, t, ref, "[]", "[]", None))
    return conn


class RefsTests(unittest.TestCase):
    def test_title_shapes(self):
        self.assertEqual(fr.refs_of(ROWS[0][3]), ["amendement 525"])
        self.assertEqual(fr.refs_of(ROWS[2][3]), ["sous-amendement 77"])
        self.assertEqual(fr.refs_of("l'amendement de suppression n° 444 (rect.) de M. Le Fur et les "
                                    "amendements identiques suivants à l'article 25 du projet de loi"),
                         ["amendement 444"])
        self.assertEqual(fr.refs_of("l’amendement n° 750 de Mme Blin à l’article 4"), ["amendement 750"])
        self.assertEqual(fr.refs_of(ROWS[6][3]), [])          # an article vote is the bill's own text


class FranceReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = store()
        cls.reader, cls.client = reader()
        cls.out = {o.key: o for o in amendtext.run(cls.conn, cls.reader, log=lambda *a: None)}

    def test_abortion_amendment_passes_the_gate(self):
        o = self.out["an-17-4576"]
        self.assertEqual(o.status, "ok")
        self.assertEqual(o.areas, [1])
        self.assertIn("IVG", o.terms)
        self.assertTrue(o.ledger)
        row = self.conn.execute("SELECT areas, tier FROM fr_divisions WHERE division_key='an-17-4576'").fetchone()
        self.assertEqual((json.loads(row[0]), row[1]), ([1], 1))
        refs = json.loads(self.conn.execute("SELECT refs FROM amendment_text WHERE division_key='an-17-4576'")
                          .fetchone()[0])
        # the nouvelle lecture's seance amendment, not the first reading's nor the committee's
        self.assertEqual(refs[-1], "AMANR5L17PO838901B2141P0D1N000525")

    def test_incidental_body_match_is_gated(self):
        o = self.out["an-17-6446"]
        self.assertEqual((o.status, o.areas, o.ledger), ("ok", [10], False))
        self.assertEqual(json.loads(self.conn.execute(
            "SELECT areas FROM fr_divisions WHERE division_key='an-17-6446'").fetchone()[0]), [])

    def test_sub_amendment_and_duplicate_filing(self):
        self.assertEqual(self.out["an-17-1591"].status, "ok")
        self.assertEqual(self.out["an-17-6574"].status, "ok")
        self.assertEqual(self.out["an-17-8626"].labels, [])         # read, nothing on our ground

    def test_ambiguous_link_fails_loud(self):
        o = self.out["an-17-5386"]
        self.assertEqual(o.status, "unreadable")
        self.assertIn("2 seance amendement(s) n° 16", o.gap)
        self.assertNotIn("an-17-9999", self.out)

    def test_cdn_builds_are_never_mixed(self):
        # the CDN alternates two builds whose bytes differ (offsets shifted by 7)
        rd, client = reader(builds=[RangeClient.BUILD, '"other-build"'])
        lk = rd.fetch({"key": "an-17-4576", "date": "2025-12-05", "title": ROWS[0][3],
                       "dossier_ref": "DLR5L17N52922"}, ["amendement 525"])
        self.assertEqual(lk.status, "ok")               # replies from the other build were asked again
        self.assertGreater(client.calls, 4)


if __name__ == "__main__":
    unittest.main()
