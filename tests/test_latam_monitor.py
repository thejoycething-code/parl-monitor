"""The Latam monitor: the monthly edition, the instant alerts and their
de-duplication, and the two light checks (Venezuela's news feed, Nicaragua's
La Gaceta). No network: a fixture store built here, fixture watchlists in a
temporary config directory, and small inline HTML and PDF fixtures."""
import base64
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db, latam  # noqa: E402
import latam_alerts  # noqa: E402
import latam_monitor  # noqa: E402
import nic_gaceta  # noqa: E402
import ve_news  # noqa: E402

TODAY = "2026-10-09"
SINCE = "2026-09-08"

WATCHLISTS = {
    "co": "bills:\n  \"camara/2026/114\": {areas: [1], why: \"Acto legislativo protecting life from fertilisation. In committee.\"}\n",
    "cl": "bills:\n  \"7736-11\": {areas: [2], why: \"Euthanasia, the matrix bill.\"}\n",
    "hn": "expedientes:\n  \"EXP-2026-0390\": {areas: [6], why: \"Ley de Derechos Parentales. Flagship.\"}\n",
    "ve": ("watch:\n  \"ley-contra-el-odio-reforma\":\n    areas: [7]\n"
           "    match: [\"Ley contra el Odio\"]\n"
           "    why: \"Reform of the Ley Constitucional contra el Odio, the 2017 law.\"\n"
           "    status: \"Special committee drafting\"\n    as_of: \"2026-10-09\"\n"),
}


def build_store(path):
    conn = db.connect(path)
    db.init_db(conn)
    x = conn.execute
    # Colombia: a watched bill filed this month, a tier-2 bill, and one from last year.
    x("INSERT INTO co_bills (bill_key, chamber, year, number, nickname, title, status, filed_at, "
      "url, areas, tier) VALUES ('camara/2026/114','camara',2026,114,'VIDA DESDE LA FECUNDACIÓN',"
      "'Por medio del cual se modifica el artículo 11','Trámite en Comisión','2026-09-20',"
      "'https://www.camara.gov.co/x','[1]',1)")
    x("INSERT INTO co_bills (bill_key, chamber, year, number, nickname, status, filed_at, areas, tier) "
      "VALUES ('camara/2026/217','camara',2026,217,'LEY OLIMPIA COLOMBIA','Trámite en Comisión',"
      "'2026-09-13','[5]',2)")
    x("INSERT INTO co_bills (bill_key, chamber, year, number, nickname, filed_at, areas, tier) "
      "VALUES ('camara/2025/9','camara',2025,9,'VIEJO','2025-09-13','[1]',1)")
    # Chile: a vote on the watched euthanasia bill with per-member positions.
    x("INSERT INTO cl_divisions (division_key, chamber, date, boletin, description, text, result, "
      "yes, no, abstain, own_areas, areas, tier) VALUES ('camara-1','camara','2026-10-01 11:00:00',"
      "'7736-11','Boletín N° 7736-11','Artículo 1','Aprobado',3,1,0,'[]','[2]',1)")
    for member, party, pos in (("D-1", "PC", "Afirmativo"), ("D-2", "PC", "Afirmativo"),
                               ("D-3", "UDI", "Afirmativo"), ("D-4", "UDI", "En Contra")):
        x("INSERT INTO cl_votes (division_key, member_key, position, party) VALUES (?,?,?,?)",
          ("camara-1", member, pos, party))
    # Honduras: a tier-2 press item, and a migration-only one (hidden).
    x("INSERT INTO hn_news (post_id, created_at, title, body, areas, tier) VALUES "
      "('p1','2026-09-25T10:00:00Z','Congreso debate la patria potestad','...','[6]',2)")
    x("INSERT INTO hn_news (post_id, created_at, title, body, areas, tier) VALUES "
      "('p2','2026-09-26T10:00:00Z','Migración y retornados','...','[11]',1)")
    # Uruguay: a tier-1 pedido.
    x("INSERT INTO uy_questions (question_key, chamber, date, organismo, autores, tema, estado, "
      "url_oficio, areas, tier) VALUES ('L50/07799','representantes','2026-09-29',"
      "'MINISTERIO DE SALUD PÚBLICA','Nicolle Salle','BLOQUEO PUBERAL EN MENORES','SIN CONTESTAR',"
      "'https://documentos.diputados.gub.uy/x.pdf','[3]',1)")
    # El Salvador: a vote with its party groups, linked to a pieza.
    x("INSERT INTO sv_piezas (pieza_key, legislature, leyenda, extracto) VALUES "
      "('2024-2027/128/1A','2024-2027','Reforma','Reforma a la Ley de Datos Personales')")
    x("INSERT INTO sv_divisions (division_key, legislature, date, label, kind, item_key, yes, no, "
      "abstain, groups, positions, areas, tier) VALUES ('sv-1','2024-2027','2026-09-17','PIEZA 1A FS',"
      "'pieza','2024-2027/128/1A',57,1,0,'{\"NUEVAS IDEAS\": [54, 0], \"VAMOS\": [0, 1]}',60,'[7]',2)")
    # Venezuela: one news item naming the watched reform, one off our ground.
    x("INSERT INTO ve_news (url, date, title, body, areas, tier) VALUES "
      "('https://www.asambleanacional.gob.ve/noticias/a','2026-09-30','Comisión revisa la Ley contra el Odio',"
      "'La comisión especial ...','[7]',1)")
    x("INSERT INTO ve_news (url, date, title, body, areas, tier) VALUES "
      "('https://www.asambleanacional.gob.ve/noticias/b','2026-09-29','Sismo en Sucre','...','[]',NULL)")
    # Nicaragua: one issue read, one cancellation notice.
    x("INSERT INTO nic_gazette_issues (issue, year, date, url, pages, items, read_at) VALUES "
      "(184, 2026, '2026-10-08', 'https://www.lagaceta.gob.ni/la-gaceta-no-184/', 44, 150, '2026-10-09')")
    x("INSERT INTO nic_gazette_items (item_key, issue, date, url, heading, text, areas, tier) VALUES "
      "('2026/184/12',184,'2026-10-08','https://www.lagaceta.gob.ni/la-gaceta-no-184/',"
      "'Acuerdo Ministerial No. 45-2026 cancela la personalidad jurídica de la Iglesia Monte Sion',"
      "'...','[8]',1)")
    x("INSERT INTO nic_gazette_items (item_key, issue, date, url, heading, text, areas, tier) VALUES "
      "('2026/184/30',184,'2026-10-08','u','Normativa de portabilidad numérica: causales','...','[1]',1)")
    conn.commit()
    return conn


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config")
        os.makedirs(self.cfg)
        for cc, text in WATCHLISTS.items():
            with open(os.path.join(self.cfg, "watchlist-{0}.yaml".format(cc)), "w") as fh:
                fh.write(text)
        latam._WATCH.clear()
        self.conn = build_store(os.path.join(self.tmp, "store.db"))
        self.conn.row_factory = sqlite3.Row
        self.ledgers = os.path.join(self.tmp, "ledgers")

    def tearDown(self):
        latam._WATCH.clear()
        shutil.rmtree(self.tmp)


class EditionTests(Fixture):
    def render(self, ledger=None):
        return latam_monitor.render_edition(self.conn, TODAY, SINCE, ledger=ledger or {"moves": []},
                                            config_dir=self.cfg)

    def test_sections_only_for_countries_with_news(self):
        text = self.render()
        for name in ("Colombia", "Chile", "Honduras", "Uruguay", "El Salvador"):
            self.assertIn("\n## {0}\n".format(name), text)
        for name in ("Peru", "Ecuador", "Bolivia", "Guatemala", "Panama", "Dominican Republic"):
            self.assertNotIn("\n## {0}\n".format(name), text)
        quiet = next(line for line in text.splitlines() if line.startswith("**Nothing new"))
        for name in ("Bolivia", "Dominican Republic", "Ecuador", "Guatemala", "Panama", "Peru"):
            self.assertIn(name, quiet)
        self.assertIn("**Access pending:** Costa Rica", text)
        self.assertIn("Paraguay", text)

    def test_spanish_titles_verbatim_and_english_around_them(self):
        text = self.render()
        self.assertIn("*VIDA DESDE LA FECUNDACIÓN*", text)
        self.assertIn("**watched**", text)
        self.assertIn("Watched: Acto legislativo protecting life from fertilisation.", text)
        self.assertIn("**New bill**", text)

    def test_votes_carry_tally_split_and_no_verdict(self):
        text = self.render()
        self.assertIn("Tally: 3 for, 1 against; result as recorded: “Aprobado”", text)
        self.assertIn("By party (for-against): PC 2-0, UDI 1-1", text)
        self.assertIn("Areas from the bill it names (7736-11)", text)
        self.assertIn("By party (for-against): NUEVAS IDEAS 54-0, VAMOS 0-1", text)
        for word in ("victory", "defeat", " win "):
            self.assertNotIn(word, text.lower())

    def test_out_of_window_and_migration_are_not_shown(self):
        text = self.render()
        self.assertNotIn("VIEJO", text)
        self.assertNotIn("Migración y retornados", text)

    def test_no_em_dashes(self):
        self.assertNotIn("—", self.render())

    def test_venezuela_and_nicaragua_notes(self):
        text = self.render()
        self.assertIn("Watched by hand: Reform of the Ley Constitucional contra el Odio", text)
        self.assertIn("1 news item(s) this month mention it.", text)
        self.assertIn("2 news item(s) read this month; 1 on our ground", text)
        self.assertNotIn("Sismo en Sucre", text)
        self.assertIn("1 issue(s) read", text)
        self.assertIn("cancela la personalidad jurídica", text)
        self.assertIn("1 other notice(s) matched other areas and are not shown", text)
        self.assertNotIn("portabilidad", text)

    def test_ledger_moves_become_stage_moves(self):
        ledger = {"moves": [{"date": "2026-10-02", "cc": "co", "key": "camara/2026/53", "old": "Radicado",
                             "new": "Aprobado en primer debate", "title": "PROTECCIÓN DE LA VIDA",
                             "areas": [1], "url": None}]}
        text = self.render(ledger)
        self.assertIn("**Stage move**", text)
        self.assertIn("Radicado → Aprobado en primer debate", text)

    def test_sample_banner(self):
        text = latam_monitor.render_edition(self.conn, TODAY, SINCE, sample=True,
                                            ledger={"moves": []}, config_dir=self.cfg)
        self.assertIn(latam_monitor.SAMPLE_MARK, text)

    def test_act_without_owner_is_refused(self):
        with self.assertRaises(ValueError):
            latam_monitor.refuse_ownerless_act("- [ACT] a bill")
        latam_monitor.refuse_ownerless_act("- [ACT] a bill (owner: Chris)")

    def test_dm_summary(self):
        text = latam_monitor.dm_summary(self.conn, TODAY, SINCE, path=os.path.join(
            ROOT, "editions", "latam-monitor-2026-10-09.md"), ledger={"moves": []},
            config_dir=self.cfg)
        self.assertIn("*Latam Monitor - October 2026*", text)
        self.assertIn("in 5 countries", text)
        self.assertIn("Access pending: Costa Rica, Paraguay.", text)
        self.assertIn("editions/latam-monitor-2026-10-09.md", text)
        self.assertNotIn("—", text)

    def test_dm_goes_to_chris_alone(self):
        from src import publish
        seen = {}
        orig_load, orig_dm = publish.load_secrets, publish.slack_dm
        publish.load_secrets = lambda: {"slack_bot_token": "x", "slack_dm_user_id": "USOMEONE"}
        publish.slack_dm = lambda secrets, text: seen.update(secrets) or {"ok": True}
        try:
            latam_monitor.send_dm("hello")
            latam_alerts.send_dm("hello")
        finally:
            publish.load_secrets, publish.slack_dm = orig_load, orig_dm
        self.assertEqual(seen["slack_dm_user_id"], "U05LJP0BT61")


class AlertTests(Fixture):
    def run_pass(self, today=TODAY, send=True, max_dms=8, sender=None, countries=None):
        self.sent = []

        def default_sender(text):
            self.sent.append(text)
            return {"ok": True}
        return latam_alerts.run(self.conn, countries or ["co", "cl", "hn", "uy", "sv", "ve", "nic"],
                                today, 30, send, max_dms, sender or default_sender, self.ledgers,
                                self.cfg, log=lambda *a: None)

    def unseed(self):
        for name in os.listdir(self.ledgers):
            path = os.path.join(self.ledgers, name)
            with open(path) as fh:
                ledger = json.load(fh)
            ledger["sent"] = {}
            with open(path, "w") as fh:
                json.dump(ledger, fh)

    def test_first_pass_seeds_and_sends_nothing(self):
        self.run_pass()
        self.assertEqual(self.sent, [])
        self.assertTrue(os.path.exists(os.path.join(self.ledgers, "co.json")))

    def test_watched_and_tier1_alert_once(self):
        self.run_pass()
        self.unseed()
        got = self.run_pass()
        keys = sorted(k for _, k, _ in got)
        self.assertIn("co|new|camara/2026/114", keys)          # watched
        self.assertIn("cl|vote|camara-1", keys)                # watched bill's vote
        self.assertIn("uy|pedido|L50/07799", keys)             # tier 1
        self.assertIn("nic|gazette|2026/184/12", keys)         # tier 1
        self.assertNotIn("nic|gazette|2026/184/30", keys)      # not area 8: not read for it
        self.assertIn("ve|news|https://www.asambleanacional.gob.ve/noticias/a", keys)
        self.assertNotIn("co|new|camara/2026/217", keys)       # tier 2
        self.assertNotIn("hn|press|press-p1", keys)            # tier 2
        self.assertNotIn("sv|vote|sv-1", keys)                 # tier 2
        self.assertFalse(any("press-p2" in k for k in keys))   # migration: hidden
        self.assertEqual(len(self.sent), len(got))
        self.assertEqual(self.run_pass(), [])                  # de-duplicated
        self.assertEqual(self.sent, [])

    def test_dry_run_records_nothing(self):
        self.run_pass()
        self.unseed()
        self.run_pass(send=False)
        self.assertEqual(self.sent, [])
        self.assertTrue(self.run_pass())                       # still to send

    def test_watched_status_move(self):
        self.run_pass()                                        # seeds status 'Trámite en Comisión'
        self.conn.execute("UPDATE co_bills SET status='Aprobado en primer debate' "
                          "WHERE bill_key='camara/2026/114'")
        self.conn.commit()
        got = self.run_pass(today="2026-10-16")
        moved = [t for _, k, t in got if k.startswith("co|moved|camara/2026/114")]
        self.assertEqual(len(moved), 1)
        self.assertIn("Trámite en Comisión → Aprobado en primer debate", moved[0])
        with open(os.path.join(self.ledgers, "co.json")) as fh:
            ledger = json.load(fh)
        self.assertEqual(ledger["moves"][-1]["new"], "Aprobado en primer debate")
        self.assertEqual(self.run_pass(today="2026-10-17"), [])
        # and the edition reads the move from the ledger
        text = latam_monitor.render_edition(self.conn, "2026-10-17", SINCE,
                                            ledger=latam.load_ledger(self.ledgers), config_dir=self.cfg)
        self.assertIn("**Stage move**", text)

    def test_cap_and_overflow(self):
        self.run_pass()
        self.unseed()
        got = self.run_pass(max_dms=2)
        self.assertEqual(len(self.sent), 3)                    # two alerts and the overflow note
        self.assertIn("more watched or tier-1 item(s)", self.sent[-1])
        self.assertEqual(got[-1][1], "overflow")
        self.assertEqual(self.run_pass(), [])                  # overflow items are not resent

    def test_failed_send_is_retried(self):
        self.run_pass()
        self.unseed()
        self.run_pass(sender=lambda text: {"error": "channel_not_found"})
        self.assertTrue(self.run_pass())

    def test_message_shape(self):
        it = latam.item("co", "new", "camara/2026/114", "2026-09-20", "VIDA — DESDE", [1], 1,
                        True, "Trámite", "https://x")
        text = latam_alerts.message(it)
        self.assertIn("*Latam alert, Colombia*: new bill (watched, tier 1)", text)
        self.assertIn("_VIDA - DESDE_", text)
        self.assertNotIn("—", text)


class VenezuelaTests(unittest.TestCase):
    LIST = ('<a href="https://www.asambleanacional.gob.ve/noticias/comision-odio"><h3 class="x"><b>'
            'Comisi&oacute;n revisa la Ley contra el Odio</b></h3></a> ... Fecha: 30/09/2026 ...')

    def test_parse_list(self):
        self.assertEqual(ve_news.parse_list(self.LIST), [
            ("https://www.asambleanacional.gob.ve/noticias/comision-odio",
             "Comisión revisa la Ley contra el Odio", "2026-09-30")])

    def test_parse_body(self):
        page = '<nav>menu</nav><p>Fecha: 30/09/2026</p><p>La comisi&oacute;n <b>especial</b></p><div class="an-text-white">pie</div>'
        self.assertEqual(ve_news.parse_body(page), "Fecha: 30/09/2026 La comisión especial")

    def test_classify_for_venezuela(self):
        tax = ve_news.load_taxonomy()
        areas, terms, tier = ve_news.classify(tax, "Comisión revisa la Ley contra el Odio", "")
        self.assertIn(7, areas)
        self.assertEqual(tier, 1)


def _pdf(*pages):
    """A tiny PDF-shaped byte string: one Flate content stream per page."""
    out = b"%PDF-1.7\n"
    for i, ops in enumerate(pages, 1):
        data = zlib.compress(ops)
        out += b"%d 0 obj<</Length %d/Filter/FlateDecode>>stream\r\n" % (i, len(data)) + data
        out += b"\r\nendstream endobj\n"
    return out


class NicaraguaTests(unittest.TestCase):
    def test_parse_list(self):
        page = ('<a href="/la-gaceta-no-184-jueves-08-de-octubre-de-2026/">x</a>'
                '<a href="/la-gaceta-no-177-del-29-de-septiembre-de-2026/">y</a>'
                '<a href="/la-gaceta-no-183-mie-rcoles-07-de-octubre-de-2026/">z</a>'
                '<a href="/la-gaceta-no-184-jueves-08-de-octubre-de-2026/">again</a>')
        self.assertEqual(nic_gaceta.parse_list(page), [
            ("/la-gaceta-no-184-jueves-08-de-octubre-de-2026/", 184, "2026-10-08"),
            ("/la-gaceta-no-177-del-29-de-septiembre-de-2026/", 177, "2026-09-29"),
            ("/la-gaceta-no-183-mie-rcoles-07-de-octubre-de-2026/", 183, "2026-10-07")])

    def test_embedded_pdf_text_and_notices(self):
        pdf = _pdf(
            b"BT /TT1 1 Tf [(S)-2 (UMARIO)]TJ ET BT 1 Tr (shadow)Tj ET",
            b"BT /TT0 1 Tf [(Reg. 2026-00944 AVISO La Comisi\\363n Liquidadora de la COOPERATIVA "
            b"AGRICOLA insta a los acreedores a presentarse dentro de quince d\\355as.)]TJ ET "
            b"BT [(Reg. 2026-00950 Acuerdo Ministerial No. 45-2026. Se cancela la personalidad)-300"
            b"(jur\\355dica de la Asociaci\\363n Iglesia Evang\\351lica Monte Sion, conforme la Ley 1115.)]TJ ET")
        page = "<script>var pdfData = atob('{0}');</script>".format(base64.b64encode(pdf).decode())
        got = nic_gaceta.embedded_pdf(page)
        self.assertEqual(got, pdf)
        pages = nic_gaceta.pdf_pages(got)
        self.assertEqual(pages[0], "SUMARIO")
        self.assertNotIn("shadow", pages[0])
        found = nic_gaceta.notices(pages)
        self.assertEqual(len(found), 2)
        self.assertIn("personalidad jurídica de la Asociación Iglesia Evangélica", found[1])
        tax = nic_gaceta.load_taxonomy()
        self.assertEqual(nic_gaceta.classify(tax, found[0])[0], [])
        areas, terms, tier = nic_gaceta.classify(tax, found[1])
        self.assertIn(8, areas)
        self.assertEqual(tier, 1)

    def test_store_issue_keeps_only_matched_notices(self):
        conn = sqlite3.connect(":memory:")
        from src import latam_store
        latam_store.ensure_schema(conn)
        pdf = _pdf(b"BT [(Reg. 2026-1 Se cancela la personalidad jur\\355dica de la Iglesia Bautista "
                   b"Betel por no cumplir la Ley 1115 y sus obligaciones.)]TJ ET "
                   b"BT [(Reg. 2026-2 Aviso de liquidaci\\363n de la cooperativa agr\\355cola de "
                   b"Carazo a sus acreedores, dentro de quince d\\355as.)]TJ ET")
        kept = nic_gaceta.store_issue(conn, "/la-gaceta-no-9/", 9, "2026-01-14", pdf,
                                      nic_gaceta.load_taxonomy(), "2026-01-15")
        self.assertEqual(kept, 1)
        self.assertEqual(conn.execute("SELECT item_key FROM nic_gazette_items").fetchall(),
                         [("2026/9/1",)])
        self.assertEqual(conn.execute("SELECT pages, items FROM nic_gazette_issues").fetchone(), (1, 2))

    def test_boilerplate_notices_are_never_kept(self):
        conn = sqlite3.connect(":memory:")
        from src import latam_store
        latam_store.ensure_schema(conn)
        pdf = _pdf(b"BT [(Reg. 2026-TP22127 CERTIFICACI\323N El Departamento de Registro Acad\351mico "
                   b"de la Universidad Evang\351lica certifica el t\355tulo de la estudiante.)]TJ ET")
        self.assertEqual(nic_gaceta.store_issue(conn, "/x/", 170, "2026-09-11", pdf,
                                                nic_gaceta.load_taxonomy(), "2026-09-12"), 0)

    def test_no_text_layer_yields_nothing(self):
        self.assertEqual(nic_gaceta.pdf_pages(b"%PDF-1.7 not really"), [])
        self.assertIsNone(nic_gaceta.embedded_pdf("<html>no pdf</html>"))


if __name__ == "__main__":
    unittest.main()
