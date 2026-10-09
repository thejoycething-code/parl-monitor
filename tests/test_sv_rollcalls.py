"""El Salvador: Asamblea Legislativa votes, sessions and deputies
(tools/sv_rollcalls.py, src/sv_pdf.py). No network.

Fixtures under tests/fixtures/sv/ are real responses saved on 9 October 2026.
The five vote PDFs had their image, metadata and embedded font-program
streams emptied to keep the repository small (345-545 KB -> 48-111 KB);
every page content stream, font dictionary and ToUnicode map is untouched,
and the text read from each file was checked to be identical before and
after.
"""

import datetime
import gzip
import importlib.util
import json
import os
import sqlite3
import sys
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, sv_pdf, sv_store  # noqa: E402
from src.http import FetchError  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "sv")


def _load():
    spec = importlib.util.spec_from_file_location("sv_rollcalls", os.path.join(ROOT, "tools", "sv_rollcalls.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sv = _load()


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        data = fh.read()
    return gzip.decompress(data) if name.endswith(".gz") else data


class FakeClient:
    """Serves fixtures by URL; records what was asked."""

    def __init__(self, gets=None, posts=None):
        self.gets = gets or {}
        self.posts = posts or {}
        self.asked = []

    def _get(self, url):
        self.asked.append(url)
        for key, value in self.gets.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise FetchError(url, "sv", "x", 1, "no fixture")

    def get_json(self, url, feed, slug, **kw):
        return json.loads(self._get(url))

    def get_text(self, url, feed, slug, **kw):
        return self._get(url).decode("utf-8")

    def get_bytes(self, url, feed, slug, **kw):
        return self._get(url)

    def post_form(self, url, fields, feed, slug, **kw):
        key = (url.rsplit("/", 1)[-1], tuple(sorted(fields.items())))
        self.asked.append(key)
        if key not in self.posts:
            if key[0] == "historico-sesion-ajax":
                # what the archive answers for a day with no sitting
                return '{"sesiones":null,"validar":false,"archivos":[]}'
            raise FetchError(url, "sv", slug, 1, "no fixture")
        return self.posts[key].decode("utf-8")


def store():
    return db.init_db(sqlite3.connect(":memory:"))


class LabelTests(unittest.TestCase):
    def test_dictamen_labels(self):
        self.assertEqual(sv.classify_label("COMISION DE HACIENDA DICTAMEN # 267 FAVORABLE"),
                         ("dictamen", 267, None, "HACIENDA"))
        kind, n, _, com = sv.classify_label("COM. DE SALUD, AGRICULTURA Y MEDIO AMBIENTE DICT#13 APROBANDO INFORME")
        self.assertEqual((kind, n), ("dictamen", 13))
        self.assertTrue(com.startswith("SALUD"))
        self.assertEqual(sv.classify_label("COM. DE TECNOLOGIA TURISMO E INVERSION DICT. #26 FAVORABLE")[:2],
                         ("dictamen", 26))
        self.assertEqual(sv.classify_label("Dictamen #11 Favorable - Ley para la Estabilidad del Sistema Financiero")[:2],
                         ("dictamen", 11))
        self.assertEqual(sv.classify_label("COMISION DE HACIENDA DICTAMEN No148 FAVORABLE")[:2], ("dictamen", 148))
        self.assertEqual(sv.classify_label("HACIENDA DICTAMEN No2 FAVORABLE")[:2], ("dictamen", 2))

    def test_pieza_labels(self):
        self.assertEqual(sv.classify_label("PIEZA 2A FS"), ("pieza", 2, "FS", None))
        self.assertEqual(sv.classify_label("PIEZA 1 A DT"), ("pieza", 1, "DT", None))
        self.assertEqual(sv.classify_label("Pieza 1A Dispensa de Tramites"), ("pieza", 1, "DT", None))
        self.assertEqual(sv.classify_label("PIEZA 1A FS REGIMEN DE EXCEPCION")[:3], ("pieza", 1, "FS"))

    def test_other_labels(self):
        self.assertEqual(sv.classify_label("NOTIFICACIONES CSJ")[0], "other")
        self.assertEqual(sv.classify_label("MODIFICACION DE AGENDA - CONSTITUCION DE LA REPUBLICA")[0], "other")


class VoteListTests(unittest.TestCase):
    def test_parse_first_page(self):
        payload = json.loads(fixture("votelist-start0-len10.json"))
        rows = sv.parse_vote_list(payload)
        self.assertEqual(len(rows), 10)
        self.assertEqual(sv.total_of(payload), 6710)
        first = rows[0]
        self.assertEqual(first["date"], "2026-10-07")
        self.assertEqual(first["session"], 129)
        self.assertEqual(first["legislature"], "2024-2027")
        self.assertEqual(first["kind"], "dictamen")
        self.assertEqual(first["number"], 39)
        self.assertTrue(first["pdf_url"].startswith("https://www.asamblea.gob.sv/sites/default/files/documents/votaciones/"))
        self.assertTrue(first["pdf_url"].endswith(first["doc"] + ".pdf"))
        kinds = {(r["kind"], r["stage"]) for r in rows}
        self.assertIn(("pieza", "DT"), kinds)
        self.assertIn(("pieza", "FS"), kinds)

    def test_only_the_current_legislature_is_stored(self):
        conn = store()
        client = FakeClient(gets={"start=0&": fixture("votelist-boundary.json")})
        leg = sv.pull_vote_list(conn, client, "2026-10-09", log=lambda *a: None)
        self.assertEqual(leg, "2024-2027")
        legs = {r[0] for r in conn.execute("SELECT legislature FROM sv_divisions")}
        self.assertEqual(legs, {"2024-2027"})
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM sv_divisions").fetchone()[0], 3)


class VotePdfTests(unittest.TestCase):
    def test_dictamen_vote(self):
        v = sv.parse_vote_pdf(fixture("vote-dictamen-39.pdf"))
        self.assertEqual(v["meeting"], "PLENARIA ORDINARIA #129")
        self.assertEqual(v["vote_name"], "COMISION DE INFRAESTRUCTURA Y DESARROLLO TERRITORIAL DICTAMEN #39 FAVORABLE")
        self.assertEqual(v["started"], "2026-10-07T14:12:23")
        self.assertEqual(v["totals"], {"SI": 59, "NO": 0, "ABST": 0, "No Votado": 1})
        self.assertEqual(v["groups"]["NUEVAS IDEAS"], [54, 0])
        self.assertEqual(len(v["positions"]), 60)
        yes = [p for p in v["positions"] if p[2] == "SI"]
        self.assertEqual(len(yes), 59)
        self.assertIn(("REINALDO CARBALLO", "PDC", "No Votado"), v["positions"])
        self.assertIn(("ESTUARDO RODRÍGUEZ", "NUEVAS IDEAS", "SI"), v["positions"])  # a split cell
        for party, (y, _n) in v["groups"].items():
            self.assertEqual(sum(1 for p in yes if p[1] == party), y, party)

    def test_pieza_vote_with_a_no(self):
        v = sv.parse_vote_pdf(fixture("vote-pieza-1a-fs-regimen.pdf"))
        self.assertEqual(v["vote_name"], "PIEZA 1A FONDO DE LO SOLICITADO")
        self.assertEqual(v["totals"]["NO"], 1)
        self.assertIn(("CLAUDIA ORTIZ", "VAMOS", "NO"), v["positions"])
        self.assertTrue(all(p[1] for p in v["positions"]), "every position carries a party")

    def test_split_name_cells_rejoin(self):
        v = sv.parse_vote_pdf(fixture("vote-pieza-2a-fs.pdf"))
        names = {p[0]: p for p in v["positions"]}
        self.assertEqual(names["CLAUDIA ORTIZ"][1:], ("VAMOS", "No Votado"))
        self.assertEqual(v["totals"]["SI"], 57)
        self.assertEqual(sum(1 for p in v["positions"] if p[2] == "SI"), 57)

    def test_the_spanish_layout_before_july_2025(self):
        v = sv.parse_vote_pdf(fixture("vote-pieza-3a-fs-2025-es-layout.pdf"))
        self.assertEqual(v["meeting"], "PLENARIA ORDINARIA #40")
        self.assertEqual(v["vote_name"], "PIEZA 3A FONDO DE LO SOLICITADO")
        self.assertEqual(v["started"], "2025-01-22T13:11:37", "p.m. read as the afternoon")
        self.assertEqual(v["totals"], {"SI": 55, "NO": 1, "ABST": 0, "No Votado": 4})
        self.assertEqual(v["groups"]["NUEVAS IDEAS"], [52, 0])
        self.assertEqual(len(v["positions"]), 60)
        self.assertIn(("Claudia Ortiz", "VAMOS", "NO"), v["positions"])
        self.assertIn(("Francisco Lira", "ARENA", "No Votado"), v["positions"])
        self.assertEqual(sum(1 for p in v["positions"] if p[1] == "NUEVAS IDEAS" and p[2] == "SI"), 52)

    def test_the_hybrid_layout_of_late_2025(self):
        """Spanish labels, English structure: positions by position, the
        party on each line. Routed by label alone it read nothing."""
        v = sv.parse_vote_pdf(fixture("vote-pieza-3a-dt-2025-10-hybrid-layout.pdf"))
        self.assertEqual(v["meeting"], "PLENARIA ORDINARIA #80")
        self.assertEqual(v["vote_name"], "PIEZA 3A DISPENSA DE TRÁMITES")
        self.assertEqual(v["totals"], {"SI": 57, "NO": 0, "ABST": 0, "No Votado": 3})
        self.assertEqual(v["groups"]["NUEVAS IDEAS"], [54, 0])
        self.assertEqual(len(v["positions"]), 60)
        self.assertIn(("MARICELA DE GUARDADO", "NUEVAS IDEAS", "SI"), v["positions"])
        self.assertIn(("CLAUDIA ORTIZ", "VAMOS", "No Votado"), v["positions"])

    def test_garbage_is_none_not_an_exception(self):
        self.assertIsNone(sv.parse_vote_pdf(b"not a pdf"))


class PdfReaderTests(unittest.TestCase):
    """src/sv_pdf.py on a synthetic two-font page: WinAnsi with /Widths and a
    Type0 Identity-H font with a /ToUnicode CMap (both seen in the resúmenes)."""

    @staticmethod
    def _pdf():
        content = (b"BT /F1 10 Tf 1 0 0 1 50 700 Tm [(Dict)-3(amen)] TJ ET\n"
                   b"BT /F1 10 Tf 1 0 0 1 82 700 Tm [( No. 3)] TJ ET\n"
                   b"BT /F1 10 Tf 1 0 0 1 300 700 Tm (FAVORABLE) Tj ET\n"
                   b"BT /F2 10 Tf 1 0 0 1 50 680 Tm <00210022> Tj ET\n")
        cmap = (b"begincmap 1 begincodespacerange <0000> <FFFF> endcodespacerange "
                b"2 beginbfchar <0021> <00E9> <0022> <00F1> endbfchar endcmap")
        stream = zlib.compress(content)
        objs = [
            b"<</Type/Catalog/Pages 2 0 R>>",
            b"<</Type/Pages/Count 1/Kids[ 3 0 R] >>",
            b"<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 5 0 R/F2 6 0 R>> >>/Contents 4 0 R>>",
            b"<</Filter/FlateDecode/Length %d>>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<</Type/Font/Subtype/TrueType/BaseFont/Arial/Encoding/WinAnsiEncoding/FirstChar 32/LastChar 126"
            b"/Widths[" + b" ".join([b"500"] * 95) + b"]>>",
            b"<</Type/Font/Subtype/Type0/BaseFont/X/Encoding/Identity-H/ToUnicode 7 0 R>>",
            b"<</Length %d>>\nstream\n" % len(cmap) + cmap + b"\nendstream",
        ]
        out = b"%PDF-1.7\n"
        for n, body in enumerate(objs, 1):
            out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
        return out + b"%%EOF"

    def test_runs_join_and_cells_split(self):
        pages = sv_pdf.pdf_lines(self._pdf())
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0][0], "Dictamen No. 3\tFAVORABLE")

    def test_identity_h_through_tounicode(self):
        self.assertEqual(sv_pdf.pdf_lines(self._pdf())[0][1], "éñ")

    def test_a_damaged_file_yields_nothing(self):
        self.assertEqual(sv_pdf.pdf_lines(b"%PDF-1.7 rubbish"), [])


class ArchiveAndMembersTests(unittest.TestCase):
    def test_session_files(self):
        payload = json.loads(fixture("historico-2026-09-29.json"))
        self.assertEqual(payload["sesiones"][0]["sesion"], "128")
        dictamenes, piezas, resumen, agenda = sv.parse_session_files(payload["archivos"])
        self.assertEqual(len(dictamenes), 7)
        d266 = next(d for d in dictamenes if d["numero"] == 266)
        self.assertEqual(d266["expediente"], "755-9-2026-1")
        self.assertEqual(d266["comision_id"], "97")
        self.assertEqual(d266["resultado"], "Favorable")
        self.assertTrue(d266["pdf_url"].endswith(".pdf") and "/dictamenes/" in d266["pdf_url"])
        self.assertEqual(len(piezas), 6)
        self.assertEqual(piezas[1]["orden"], 2)
        self.assertTrue(piezas[1]["leyenda"].startswith("Ley Esp. Participación de la Fuerza Armada"))
        self.assertEqual(resumen, "9E23FD5E-5191-4808-AA85-54558A8039C3")
        self.assertTrue(agenda)

    def test_members(self):
        members = sv.parse_members(fixture("diputados.html.gz").decode("utf-8"))
        self.assertEqual(len(members), 60)
        by_party = {}
        for m in members:
            by_party[m["party"]] = by_party.get(m["party"], 0) + 1
        self.assertEqual(by_party, {"NI": 54, "ARENA": 2, "PCN": 2, "PDC": 1, "VAMOS": 1})
        self.assertTrue(all(m["department"] for m in members))
        self.assertEqual(len({m["member_id"] for m in members}), 60)


class EndToEndTests(unittest.TestCase):
    def _client(self):
        posts = {
            ("historico-sesion-ajax", (("desde", "2026-09-29"), ("hasta", "2026-09-29"))):
                fixture("historico-2026-09-29.json"),
            ("historico-sesion-ajax", (("desde", "2026-10-07"), ("hasta", "2026-10-07"))):
                fixture("historico-2026-10-07.json"),
        }
        gets = {"start=0&": fixture("votelist-start0-len10.json"),
                "asamblea/diputados": fixture("diputados.html.gz"),
                "61C47464-E186-4899-91F0-21ABEA0FD8B8.pdf": fixture("vote-pieza-2a-fs.pdf"),
                "A8688AB6-7602-43F5-BBDF-4241A8C01E95.pdf": fixture("vote-dictamen-39.pdf")}
        return FakeClient(gets=gets, posts=posts)

    def test_a_weekly_run(self):
        conn = store()
        client = self._client()
        quiet = lambda *a: None  # noqa: E731
        leg = sv.pull_vote_list(conn, client, "2026-10-09", log=quiet)
        self.assertEqual(sv.pull_members(conn, client, "2026-10-09", log=quiet), 60)
        read, gaps = sv.pull_days(conn, client, "2026-10-09", leg, log=quiet)
        self.assertEqual((read, gaps), (1, 0), "7 October not filed yet is not a gap")
        self.assertEqual(conn.execute("SELECT archived FROM sv_vote_days WHERE day='2026-10-07'").fetchone()[0], 0)
        read, gaps = sv.pull_positions(conn, client, "2026-10-09", leg, log=quiet)
        self.assertEqual(read, 2)
        self.assertEqual(gaps, 8, "the other eight PDFs have no fixture: each is a recorded gap")
        sv.link_divisions(conn)
        rows = dict(conn.execute("SELECT label, item_key FROM sv_divisions WHERE date='2026-09-29'").fetchall())
        self.assertEqual(rows["PIEZA 2A FS"], "2024-2027/128/2A")
        self.assertEqual(rows["PIEZA 2A DT"], "2024-2027/128/2A")
        self.assertEqual(rows["COMISION DE HACIENDA DICTAMEN # 267 FAVORABLE"], "2024-2027/97/267")
        exp = conn.execute("SELECT expediente FROM sv_divisions WHERE item_key='2024-2027/97/267'").fetchone()[0]
        self.assertEqual(exp, "756-9-2026-1")
        # 7 October's votes stay unlinked until the archive files the day
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM sv_divisions WHERE date='2026-10-07' "
                                      "AND item_key IS NOT NULL").fetchone()[0], 0)
        pos = conn.execute("SELECT position, COUNT(*) FROM sv_votes WHERE division_key="
                           "'sv-61C47464-E186-4899-91F0-21ABEA0FD8B8' GROUP BY 1").fetchall()
        self.assertEqual(dict(pos)["SI"], 57)
        # no taxonomy: areas stay NULL (unclassified), never '[]'
        self.assertIsNone(conn.execute("SELECT areas FROM sv_dictamenes LIMIT 1").fetchone()[0])
        gaps = conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='sv-rollcalls'").fetchone()[0]
        self.assertEqual(gaps, 8)

    def test_a_day_still_missing_after_the_grace_is_a_gap(self):
        conn = store()
        client = FakeClient(posts={("historico-sesion-ajax", (("desde", "2026-10-07"), ("hasta", "2026-10-07"))):
                                   fixture("historico-2026-10-07.json")})
        conn.execute("INSERT INTO sv_divisions (division_key, legislature, date, kind) "
                     "VALUES ('sv-x', '2024-2027', '2026-10-07', 'other')")
        read, gaps = sv.pull_days(conn, client, "2026-11-20", "2024-2027", log=lambda *a: None)
        self.assertEqual((read, gaps), (0, 1))

    def test_every_day_of_the_legislature_is_asked_once(self):
        """Sessions 41-64 published no recorded vote, so vote days are not
        enough: a sitting with no vote is still read, and an answered day
        is not asked again outside the re-read window."""
        conn = store()
        day = ("historico-sesion-ajax", (("desde", "2025-03-05"), ("hasta", "2025-03-05")))
        client = FakeClient(posts={day: fixture("historico-2026-09-29.json")})
        read, gaps = sv.pull_days(conn, client, "2026-10-09", "2024-2027", log=lambda *a: None)
        self.assertEqual((read, gaps), (1, 0))
        asked = [k for k in client.asked if isinstance(k, tuple)]
        self.assertEqual(len(asked), (datetime.date(2026, 10, 9) - datetime.date(2024, 5, 1)).days + 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM sv_dictamenes").fetchone()[0], 7)
        # asked again: only the days still inside the filing grace, whose
        # "nothing" may yet become a session (it covers the re-read window)
        again = sv.days_to_read(conn, "2026-10-09", "2024-2027")
        self.assertEqual(len(again), sv.ARCHIVE_GRACE_DAYS + 1)
        self.assertEqual(again[-1], "2026-09-18")

    def test_the_watchlist_lends_areas_by_key(self):
        path = os.path.join(FIX, "..", "..", "..", "config", "watchlist-sv.yaml")
        self.assertEqual(sv_store.watchlist(os.path.abspath(path)), {})
        tmp = os.path.join(FIX, "_watch_test.yaml")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write('expedientes:\n  "755-9-2026-1": {areas: [6], why: test}\n'
                     'piezas:\n  "2024-2027/128/2A": {areas: [8], why: test}\n')
        try:
            self.assertEqual(sv_store.watch_areas("755-9-2026-1", path=tmp), [6])
            self.assertEqual(sv_store.watch_areas("2024-2027/128/2A", "755-9-2026-1", path=tmp), [6, 8])
            self.assertEqual(sv_store.watch_areas("nope", path=tmp), [])
        finally:
            os.remove(tmp)

    def test_tables_are_declared(self):
        for t in sv_store.TABLES:
            self.assertIn(t, db.TABLES)


if __name__ == "__main__":
    unittest.main()
