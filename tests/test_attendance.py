"""Attendance for the new countries (src/attendance.py,
tools/country_attendance.py) and its place in the member profiles and the
debate packs. Fixtures are trimmed copies of the parliaments' own replies,
archived 11 October 2026. No network."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import attendance as att  # noqa: E402
from src import country_debatepack as cdp  # noqa: E402
from src import debatepack_i18n as i18n  # noqa: E402
from src import member_intel as mi  # noqa: E402
from tests.test_member_profiles import Base, pl_store_with_votes  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "attendance")
TODAY = "2026-10-11"
QUIET = lambda *_: None  # noqa: E731


def raw(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


def text(name):
    return raw(name).decode("utf-8")


def js(name):
    return json.loads(text(name))


class FakeClient:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def _answer(self, url):
        self.asked.append(url)
        for part, reply in self.answers:
            if part in url:
                return reply
        raise AssertionError("unexpected request: " + url)

    def get_json(self, url, feed, slug, **_):
        return self._answer(url)

    def get_bytes(self, url, feed, slug, **_):
        return self._answer(url)

    def get_text(self, url, feed, slug, **_):
        return self._answer(url)


def fresh():
    return att.ensure(sqlite3.connect(":memory:"))


class Brazil(unittest.TestCase):
    def test_presence_events_and_organs(self):
        pres = att.parse_br_presence(text("br_presenca.csv"))
        self.assertEqual(sorted(pres), ["80872", "80956", "80965"])
        self.assertEqual(len(pres["80956"]), 4)
        organs = att.parse_br_event_organs(js("br_eventos_orgaos.json"))
        events = att.parse_br_events(js("br_eventos.json"))
        names = att.parse_br_organ_names(js("br_orgaos.json"))
        sittings, marks = att.build_br(pres, organs, events, names)
        kinds = {s["sitting_key"]: (s["body_kind"], s["body_name"], s["roll"]) for s in sittings}
        self.assertEqual(kinds["br-80872-180"][0], "plenary")
        self.assertEqual(kinds["br-80956-2014"], ("committee", "Comissão de Saúde", "present"))
        self.assertTrue(all(m["member_key"].startswith("camara-") for m in marks))
        self.assertEqual(len(marks), 12)

    def test_only_deliberative_plenary_sessions_count(self):
        self.assertTrue(att.br_plenary_kind("Sessão Deliberativa"))
        self.assertTrue(att.br_plenary_kind("Sessão Deliberativa Extraordinária"))
        self.assertFalse(att.br_plenary_kind("Sessão Não Deliberativa Solene"))

    def test_tramitacoes_give_the_committees_not_the_desks(self):
        refs = att.parse_br_tramitacoes("PL 1/2026", js("br_tramitacoes.json"))
        siglas = {r["body_name"] for r in refs}
        self.assertEqual(siglas, {"CSAUDE"})
        self.assertTrue(refs[0]["first_date"] <= refs[0]["last_date"])

    def test_sittings_count_from_the_day_a_member_joined(self):
        conn = fresh()
        mi.ensure(conn)
        sittings = [att.sitting("s1", "committee", "2014", "Comissão de Saúde", "2026-02-04",
                                roll="present"),
                    att.sitting("s2", "committee", "2014", "Comissão de Saúde", "2026-02-25",
                                roll="present"),
                    att.sitting("s3", "committee", "2014", "Comissão de Saúde", "2026-03-04",
                                roll="present")]
        marks = [att.mark("s1", "1", "camara-1"), att.mark("s3", "1", "camara-1"),
                 att.mark("s2", "3", "camara-3")]
        att.store(conn, "br", "br-presenca", TODAY, sittings, marks)
        mi.replace(conn, "br", "br-orgaos", TODAY, [
            mi.group(member_key="camara-1", member_ref="1", group_key="2014",
                     group_name="Comissão de Saúde", start="2026-02-01"),
            mi.group(member_key="camara-2", member_ref="2", group_key="2014",
                     group_name="Comissão de Saúde", start="2026-02-20")])
        got = att.summaries(conn, "br")
        one = got["camara-1"][0]
        self.assertEqual((one["attended"], one["of"], one["absent"]), (2, 3, 1))
        two = got["camara-2"][0]                        # joined after s1: never there
        self.assertEqual((two["attended"], two["of"]), (0, 2))
        three = got["camara-3"][0]                      # not a member: attended only
        self.assertFalse(three["member"])
        self.assertIn("(not a member)", att.row_text(three))
        self.assertIn("from the day the member joined", att.basis(one))


class France(unittest.TestCase):
    def test_presences_and_dossiers_from_the_agenda(self):
        sittings, marks = att.parse_fr_agenda(raw("fr_agenda_small.zip"), TODAY,
                                              {"PO420120": "Commission des affaires sociales"})
        self.assertEqual(len(sittings), 2)              # the séance has no presence list
        first = [s for s in sittings if s["date"] == "2024-10-16"][0]
        self.assertEqual(first["bill_keys"], ["DLR5L17N50588"])
        self.assertEqual(first["body_name"], "Commission des affaires sociales")
        by = {(m["sitting_key"], m["member_ref"]): m for m in marks}
        x = by[(first["sitting_key"], "PA842211")]
        self.assertEqual((x["status"], x["present"], x["excused"]), ("excusé", 0, 1))

    def test_a_future_meeting_is_not_counted(self):
        sittings, _ = att.parse_fr_agenda(raw("fr_agenda_small.zip"), "2025-01-01")
        self.assertEqual([s["date"] for s in sittings], ["2024-10-16"])

    def test_summary_and_referral(self):
        conn = fresh()
        client = FakeClient([("Agenda.json.zip", raw("fr_agenda_small.zip")),
                             ("AMO30", raw("fr_amo30_small.zip"))])
        att.collect(conn, client, "fr", TODAY, log=QUIET)
        got = att.summaries(conn, "fr")
        self.assertEqual((got["PA794138"][0]["attended"], got["PA794138"][0]["of"]), (2, 2))
        self.assertEqual((got["PA642764"][0]["attended"], got["PA642764"][0]["excused"]), (1, 1))
        refs = att.referrals_for(conn, "fr", ["DLR5L17N50588"])
        self.assertEqual([r["body_key"] for r in refs], ["PO420120"])
        on = att.bill_sittings(conn, "fr", ["DLR5L17N50588"])
        self.assertEqual(len(on["PO420120"]), 1)
        self.assertEqual(att.on_bill(conn, "fr", on["PO420120"])["PA794138"], (1, 1))

    def test_organs_named_from_amo30_once(self):
        conn = fresh()
        client = FakeClient([("Agenda.json.zip", raw("fr_agenda_small.zip")),
                             ("AMO30", raw("fr_amo30_small.zip"))])
        att.collect(conn, client, "fr", TODAY, log=QUIET)
        self.assertEqual(conn.execute("SELECT DISTINCT body_name FROM att_sittings").fetchall(),
                         [("Commission des affaires sociales",)])
        client.asked.clear()
        att.collect(conn, client, "fr", TODAY, log=QUIET)
        self.assertFalse(any("AMO30" in u for u in client.asked))

    def test_friendship_groups_are_stored_but_not_counted(self):
        names, types = att.parse_fr_organ_names(raw("fr_amo30_small.zip"))
        self.assertEqual(types["PO800538"], "GA")
        conn = fresh()
        att.store(conn, "fr", "fr-agenda", TODAY,
                  [att.sitting("g1", "committee", "PO800538", names["PO800538"], "2026-01-01",
                               "GA")],
                  [att.mark("g1", "PA1", "PA1", status="absent", present=0)])
        self.assertEqual(att.summaries(conn, "fr"), {})

    def test_rerun_is_idempotent(self):
        conn = fresh()
        client = FakeClient([("Agenda.json.zip", raw("fr_agenda_small.zip")),
                             ("AMO30", raw("fr_amo30_small.zip"))])
        att.collect(conn, client, "fr", TODAY, log=QUIET)
        att.collect(conn, client, "fr", TODAY, log=QUIET)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM att_marks").fetchone()[0], 12)


class Chile(unittest.TestCase):
    def test_plenary_session_roll_with_justification(self):
        s, marks = att.parse_cl_session(text("cl_asistencia_4740.xml"))
        self.assertEqual((s["sitting_key"], s["body_kind"], s["date"]),
                         ("cl-sala-4740", "plenary", "2026-01-12"))
        self.assertEqual(len(marks), 4)
        absent = [m for m in marks if not m["present"]]
        self.assertTrue(absent)
        self.assertTrue(all(m["member_key"].startswith("D-") for m in marks))
        self.assertEqual(marks[0]["name"], "Jaime Naranjo Ortiz")

    def test_sessions_list_and_committees(self):
        listed = att.parse_cl_sessions(text("cl_sesiones.xml"))
        self.assertEqual(listed[0][0], "4736")
        self.assertFalse(listed[-1][2])                 # 'Citada': not held yet
        self.assertEqual(att.parse_cl_committees(text("cl_comisiones.xml")),
                         [("544", "Ética y Transparencia"), ("411", "Salud")])

    def test_committee_sessions_held_only(self):
        sittings, marks = att.parse_cl_committee_sessions(text("cl_comision_411.xml"), TODAY)
        self.assertEqual(len(sittings), 2)              # the suspended session is left out
        self.assertEqual({s["body_name"] for s in sittings}, {"Salud"})
        why = [m for m in marks if m["excused"]]
        self.assertTrue(why and "Impedimento grave" in why[0]["status"])

    def test_collect_reads_only_new_sessions(self):
        conn = fresh()
        answers = [("retornarSesionesXAnno", text("cl_sesiones.xml")),
                   ("retornarSesionAsistencia", text("cl_asistencia_4740.xml")),
                   ("retornarComisionesVigentes", text("cl_comisiones.xml")),
                   ("retornarSesionesXComisionYAnno", text("cl_comision_411.xml"))]
        client = FakeClient(answers)
        att.collect(conn, client, "cl", TODAY, log=QUIET)
        first = sum("retornarSesionAsistencia" in u for u in client.asked)
        self.assertEqual(first, 3)                      # three held sessions listed
        client.asked.clear()
        att.collect(conn, client, "cl", TODAY, log=QUIET)
        # The fixture answers every session with 4740, so only that key is stored;
        # the two others are fetched again until their own key is stored.
        self.assertEqual(sum("retornarSesionAsistencia" in u for u in client.asked), 2)


class Netherlands(unittest.TestCase):
    def test_participants_and_zaken(self):
        sittings, marks = att.parse_nl_activities(js("nl_activiteiten.json")["value"])
        self.assertEqual(len(sittings), 2)
        s = sittings[0]
        self.assertEqual((s["roll"], s["body_name"]), ("participants", "vaste commissie voor Defensie"))
        self.assertEqual(s["bill_keys"], ["2026Z19510", "37020"])
        self.assertTrue(all(m["status"] == "Deelnemer" for m in marks))   # 'Afgemeld' left out

    def test_the_count_says_took_part(self):
        row = {"roll": "participants", "body_kind": "committee", "attended": 3, "of": 9,
               "excused": 0, "first": "2026-01-01", "last": "2026-06-01", "since_basis": "joined"}
        self.assertTrue(att.row_text(row).startswith("took part in 3 of 9 debate(s)"))
        self.assertIn("not a roll call", att.basis(row))


class Colombia(unittest.TestCase):
    def test_copied_from_co_attendance(self):
        conn = fresh()
        conn.execute("CREATE TABLE co_attendance (member_key TEXT, session TEXT, date TEXT, "
                     "joint INTEGER, status TEXT)")
        conn.executemany("INSERT INTO co_attendance VALUES (?,?,?,?,?)", [
            ("camara/a", "s1", "2026-07-20", 0, "ASISTIÓ"), ("camara/a", "s2", "2026-07-21", 0, "EXCUSA"),
            ("camara/b", "s1", "2026-07-20", 0, "NO ASISTIÓ")])
        att.collect(conn, None, "co", TODAY)
        got = att.summaries(conn, "co")
        a = got["camara/a"][0]
        self.assertEqual((a["attended"], a["of"], a["excused"]), (1, 2, 1))
        self.assertEqual(got["camara/b"][0]["attended"], 0)


class Participation(unittest.TestCase):
    def test_pl_absences_counted_from_the_record(self):
        conn = pl_store_with_votes()
        conn.execute("INSERT INTO pl_votes (division_key, mp_key, position, club) VALUES "
                     "('pl-10-60-2', '10/3', 'ABSENT', 'KO')")
        got, basis = att.participation(conn, "pl", TODAY)
        self.assertEqual((got["10/1"]["cast"], got["10/1"]["of"]), (2, 2))
        self.assertEqual((got["10/3"]["cast"], got["10/3"]["absent"]), (0, 1))
        self.assertIn("ABSENT", basis)
        self.assertIn("2026-06-01", basis)
        self.assertEqual(att.participation_text(got["10/3"]),
                         "cast a vote in 0 of 1 recorded vote(s) (1 absent)")

    def test_no_figure_where_absences_are_not_recorded(self):
        self.assertEqual(att.participation(fresh(), "fr", TODAY), ({}, None))
        self.assertEqual(att.participation(fresh(), "it", TODAY), ({}, None))  # no tables


class Profiles(Base):
    def test_attendance_and_participation_in_the_profile(self):
        conn = pl_store_with_votes()
        conn.execute("UPDATE pl_votes SET position='ABSENT' WHERE division_key='pl-10-60-2' "
                     "AND mp_key='10/1'")
        att.ensure(conn)
        att.store(conn, "pl", "test", TODAY,
                  [att.sitting("k1", "committee", "ZDR", "Komisja Zdrowia", "2026-06-02")],
                  [att.mark("k1", "10/1", "10/1", status="present")])
        data = self.build(conn, "pl")
        anna = data["members"]["10/1"]
        from src import member_profiles as mp
        page = mp.render_member(data, anna)
        self.assertIn("## Attendance", page)
        self.assertIn("**Komisja Zdrowia**: attended 1 of 1 sitting(s)", page)
        self.assertIn("**Plenary votes** (derived): cast a vote in 1 of 2 recorded vote(s) "
                      "(1 absent)", page)
        self.assertIn("Basis:", page)
        self.assertIn("Attendance:", "\n".join(mp.notes(data)))

    def test_no_section_without_rows(self):
        from src import member_profiles as mp
        m = mp.Member("x", "Nobody")
        self.assertEqual(mp.render_attendance(m, {"participation_basis": "b"}), [])
        self.assertEqual(mp.render_attendance(m, None), [])


class Packs(unittest.TestCase):
    def test_committee_attendance_section(self):
        conn = fresh()
        client = FakeClient([("Agenda.json.zip", raw("fr_agenda_small.zip")),
                             ("AMO30", raw("fr_amo30_small.zip"))])
        att.collect(conn, client, "fr", TODAY, log=QUIET)
        got = cdp.committee_attendance(conn, "fr", ["DLR5L17N50588"])
        self.assertEqual(len(got), 1)
        a = got[0]
        self.assertEqual(a["sittings_on_bill"], 1)
        ids = [m["member_id"] for m in a["members"]]
        self.assertIn("PA794138", ids)
        T = lambda key, **kw: i18n.text("fr", key, **kw)  # noqa: E731
        lines = "\n".join(cdp.render_attendance({"attendance": got,
                                                 "attendance_collected": True}, T))
        self.assertIn("## Présence à la commission saisie du texte", lines)
        self.assertIn("2 sur 2", lines)
        self.assertIn("Base : les présences publiées", lines)

    def test_country_without_a_source_says_so(self):
        T = lambda key, **kw: i18n.text("it", key, **kw)  # noqa: E731
        lines = cdp.render_attendance({"attendance": [], "attendance_collected": False}, T)
        self.assertIn("non sono raccolte", "\n".join(lines))

    def test_participation_phrase_in_every_language(self):
        r = {"cast": 1, "of": 2, "last": "2026-06-01"}
        for lang in ("en", "es", "pt", "fr", "nl", "it", "de", "pl", "hu"):
            self.assertIn("1", i18n.text(lang, "part_line", **r))


class PortugalClient(FakeClient):
    """The index's second page comes only by postback (post_form)."""
    def __init__(self, answers, posted):
        super().__init__(answers)
        self.posted, self.posts = posted, []

    def post_form(self, url, fields, feed, slug, **_):
        self.posts.append(dict(fields).get("__EVENTTARGET"))
        return self.posted


class Portugal(unittest.TestCase):
    def test_index_rows_pager_and_total(self):
        rows, pages, total = att.parse_pt_index(text("pt_reunioes_1.html"))
        self.assertEqual(rows[0], {"bid": "387162", "date": "2026-10-07", "number": "8",
                                   "kind": "Ordinária", "legislature": "XVII", "session": "2"})
        self.assertEqual(len(rows), 3)
        self.assertEqual(list(pages), [2])
        self.assertTrue(pages[2].endswith("dpgResults$ctl00$ctl01"))
        self.assertEqual(total, 5)
        form = dict(att.pt_form(text("pt_reunioes_1.html"), pages[2]))
        self.assertEqual(form["__EVENTTARGET"], pages[2])
        self.assertIn("__VIEWSTATE", form)

    def test_sitting_roll_with_the_motive_verbatim(self):
        s, marks = att.parse_pt_sitting(text("pt_reuniao_387162.html"), "387162")
        self.assertEqual((s["sitting_key"], s["body_kind"], s["date"], s["roll"]),
                         ("pt-rp-387162", "plenary", "2026-10-07", "roll"))
        got = {m["name"]: (m["member_key"], m["status"], m["present"], m["excused"])
               for m in marks}
        self.assertEqual(got["Adriana Rodrigues"], ("7489", "Presença (P)", 1, 0))
        self.assertEqual(got["Ana Gabriela Cabilhas"],
                         ("8179", "Falta Justificada (FJ): Casamento", 0, 1))
        self.assertEqual(got["Alberto Fonseca"][1:], ("Ausência em Missão Parlamentar (AMP)", 0, 1))
        self.assertEqual(got["Daniel Teixeira"][1:], ("Falta", 0, 0))
        self.assertEqual(got["Miguel Matos"][1:], ("Presença Noutro Órgão (PNO)", 0, 1))

    def test_status_words(self):
        self.assertEqual(att.pt_status("Falta Injustificada (FI)"), (0, 0))
        self.assertEqual(att.pt_status("Falta ao Quórum de Votação"), (0, 0))
        self.assertEqual(att.pt_status("Presença (P)"), (1, 0))
        self.assertEqual(att.pt_status("Something new"), (None, 0))

    def _client(self):
        return PortugalClient([("reunioesplenarias.aspx", text("pt_reunioes_1.html")),
                               ("DetalheReuniaoPlenaria.aspx", text("pt_reuniao_387162.html"))],
                              text("pt_reunioes_2.html"))

    def test_backfill_in_blocks_then_the_newest_page_only(self):
        conn = fresh()
        client = self._client()
        att.collect(conn, client, "pt", TODAY, log=QUIET, max_sittings=3)
        stored = {k for (k,) in conn.execute("SELECT sitting_key FROM att_sittings WHERE cc='pt'")}
        self.assertEqual(stored, {"pt-rp-387162", "pt-rp-387160", "pt-rp-387159"})
        self.assertEqual(client.posts, [])              # three in hand: no second page
        client = self._client()
        att.collect(conn, client, "pt", TODAY, log=QUIET, max_sittings=3)
        self.assertEqual(len(client.posts), 1)          # page 2, by postback
        stored = {k for (k,) in conn.execute("SELECT sitting_key FROM att_sittings WHERE cc='pt'")}
        self.assertEqual(len(stored), 5)
        note = conn.execute("SELECT note FROM att_runs WHERE cc='pt'").fetchone()[0]
        self.assertIn("5 of 5 listed sittings stored", note)
        client = self._client()
        att.collect(conn, client, "pt", TODAY, log=QUIET)
        self.assertEqual(client.posts, [])              # all stored: the newest page only
        # Sittings of the last three weeks are read again (a Falta justified later).
        reads = [u for u in client.asked if "Detalhe" in u]
        self.assertEqual(len(reads), 3)

    def test_summary_counts_excused_apart(self):
        conn = fresh()
        att.collect(conn, self._client(), "pt", TODAY, log=QUIET, max_sittings=1)
        rows = att.summaries(conn, "pt")
        r = rows["8179"][0]
        self.assertEqual((r["body_kind"], r["attended"], r["of"], r["excused"], r["absent"]),
                         ("plenary", 0, 1, 1, 0))
        self.assertEqual(rows["8832"][0]["absent"], 1)
        self.assertIn("present at 1 of 1", att.row_text(rows["7489"][0]))

    def test_verified_against_the_roster_and_member_service(self):
        from src import member_service as ms
        conn = fresh()
        conn.execute("CREATE TABLE pt_members (cad_id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO pt_members VALUES (?,?)",
                         [(7489, "Adriana Rodrigues"), (8179, "Ana Gabriela Cabilhas")])
        ms.ensure(conn)
        ms.replace(conn, "pt", "pt-informacaobase", TODAY,
                   [ms.period("7489", "7489", "Adriana Rodrigues", "AR", "XVII", "2025-06-03")],
                   [ms.spell("7489", "7489", "Adriana Rodrigues", "group", "PSD", "PSD",
                             "2025-06-03"),
                    ms.spell("8179", "8179", "Ana Gabriela Cabilhas", "group", "PSD", "PSD",
                             "2025-06-03")])
        s, marks = att.parse_pt_sitting(text("pt_reuniao_387162.html"), "387162")
        got = att.pt_verify(conn, [s], marks)
        self.assertEqual((got["marks"], got["in_roster"], got["name_match"], got["seated"],
                          got["group_match"], got["no_service"]), (5, 2, 2, 1, 1, 4))

    def test_pack_shows_the_plenary_roll_for_portugal_only(self):
        conn = fresh()
        att.collect(conn, self._client(), "pt", TODAY, log=QUIET, max_sittings=1)
        self.assertEqual(cdp.PLENARY_ROLL_PACKS, ("pt",))
        pack = {"plenary": cdp.plenary_roll(conn, "pt")}
        T = lambda key, **kw: i18n.text("pt", key, **kw)  # noqa: E731
        line = cdp.plenary_bit(pack, "8179", T)
        self.assertIn("presente em 0 de 1 reuniões plenárias", line)
        self.assertIn("1 ausências justificadas", line)
        self.assertIsNone(cdp.plenary_bit(pack, "999", T))
        self.assertIn("present at", i18n.text("en", "plen_line", a=1, n=2, x=0, first="a",
                                               last="b"))


class Tool(unittest.TestCase):
    def test_a_failing_country_is_a_gap_and_the_rest_still_run(self):
        from tools import country_attendance as tool
        tmp = tempfile.mkdtemp()
        try:
            db = os.path.join(tmp, "s.db")
            calls = []

            def boom(conn, client, today, log=print, **_):
                calls.append("nl")
                raise ValueError("bad reply")

            def ok(conn, client, today, log=print, **_):
                calls.append("fr")
                return {"fr-agenda": ([], [], [], None)}
            saved = dict(att.FETCHERS)
            att.FETCHERS.update(nl=boom, fr=ok)
            try:
                rc = tool.main(["nl", "fr", "--db", db, "--raw", tmp, "--date", TODAY])
            finally:
                att.FETCHERS.clear()
                att.FETCHERS.update(saved)
            self.assertEqual(rc, 3)
            self.assertEqual(calls, ["nl", "fr"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
