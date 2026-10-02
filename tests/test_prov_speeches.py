"""Provincial Hansard speeches (src/prov_speeches.py, src/ingest/prov_<code>_hansard.py,
tools/prov_speeches.py). No network: trimmed copies of the live probes of 2
October 2026 in tests/fixtures/prov/.

The rules under test, from the build brief:
  * a speaker is resolved to a prov_members key, unique-or-nothing, or
    stored with the label as printed and NO key -- never an invented name;
  * only speeches on our ground are stored, matched per passage, with an
    excerpt; the chair and the collective labels are counted, not stored;
  * every day read gets a prov_speech_sittings row, and prov_sittings (the
    vote collectors' resume record) is never touched;
  * Quebec is classified in French, New Brunswick in its English column;
  * the weekly runs a speeches step per province, and a speeches backfill is
    its own dispatch input, so the vote backfill is exactly what it was.
"""

import importlib.util
import json
import os
import sys
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, prov_classify as pc, prov_names as pn, prov_speeches as sp, prov_store as ps  # noqa: E402
from src.http import FetchError, slugify  # noqa: E402
from src.ingest import (prov_ab_hansard as ab, prov_bc_hansard as bc, prov_mb_hansard as mb,  # noqa: E402
                        prov_nb_hansard as nb, prov_nl_hansard as nl, prov_on_hansard as on,
                        prov_qc_hansard as qc, prov_sk_hansard as sk)
from src.prov_fetch import Context  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "prov")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "prov-weekly.yml")
BUILT = ("ab", "sk", "bc", "mb", "on", "nb", "nl", "qc")


def fx(name, encoding="utf-8"):
    with open(os.path.join(FIX, name), encoding=encoding) as fh:
        return fh.read()


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _conn():
    return db.init_db(db.connect(":memory:"))


def member(conn, prov, key, given, surname, riding=None, start="2000-01-01", end=None, leg=1, sitting=1):
    ps.upsert_member(conn, prov, key, name=given + " " + surname, surname=surname, given=given,
                     riding=riding, sitting=sitting)
    conn.execute("INSERT INTO prov_member_terms (prov, member_key, legislature, party, riding, start, end, "
                 "party_dated, source) VALUES (?,?,?,?,?,?,?,0,'roster')",
                 (prov, key, leg, "P", riding, start, end))


class FakeClient:
    """The HttpClient surface Context uses, recording what was archived."""

    def __init__(self, pages):
        self.pages = pages
        self.user_agent = "CitizenGO-ParlMonitor/1.0 (contact: test)"
        self.throttle = 1.1
        self.asked = []
        self.archived = []

    def get_text(self, url, feed, slug, archive=True, fallback_encoding=None):
        self.asked.append(url)
        if archive:
            self.archived.append((feed, slugify(slug)))
        if url not in self.pages:
            raise FetchError(url, feed, slug, 1, "HTTP Error 404: Not Found")
        return self.pages[url]

    def get_bytes(self, url, feed, slug, archive=True):
        return self.get_text(url, feed, slug, archive=archive).encode()


class Ctx:
    """The fields of a Context the engine reads, without a client."""

    def __init__(self, conn, prov):
        self.conn, self.prov, self.gaps = conn, prov, []
        self.dry_run = self.refresh = False

    def gap(self, detail):
        self.gaps.append(detail)


def turn(label, *paras, subject=None, rubric=None, bill=None, hint=None):
    return {"label": label, "paras": list(paras), "subject": subject, "rubric": rubric, "bill": bill,
            "hint": hint}


# -- labels ---------------------------------------------------------------------------------

class LabelTests(unittest.TestCase):
    def test_the_chair_and_the_collective_labels_are_counted_not_stored(self):
        for label in ("The Speaker (Hon. Donna Skelly):", "Madam Speaker:", "Mr. Chairperson (Dennis Smook)",
                      "The Deputy Clerk (Mr. Todd Decker)", "Some Hon. Members", "An Honourable Member",
                      "Le Président", "La Vice- Présidente (Mme Soucy)", "Des voix", "Une voix",
                      "Le Secrétaire adjoint", "SPEAKER (Lane)", "CLERK", "His Honour", "Interjection",
                      "The C hair", "Disclaimer"):
            self.assertTrue(sp.is_chair(label), label)
        for label in ("Hon. Doug Ford", "MLA Asagwara", "S. CROCKER", "M. Legault", "Mrs. Smith",
                      "Hon. Mr. Cockrill", "Member LaGrange", "PREMIER WAKEHAM"):
            self.assertFalse(sp.is_chair(label), label)

    def test_a_label_is_cleaned_for_the_resolver(self):
        self.assertEqual(sp.clean_label("Hon. Mr. Cockrill: —"), "Hon. Mr. Cockrill")
        self.assertEqual(sp.clean_label("MPP Jamie West:"), "Jamie West")
        self.assertEqual(sp.clean_label("Ms Gray"), "Ms Gray")
        self.assertEqual(sp.clean_label("M. Jolin-Barrette :"), "M. Jolin-Barrette")

    def test_a_word_the_pdf_split_is_rejoined_but_not_a_particle(self):
        self.assertEqual(sp.unsplit("Hon. Mr. Coc krill"), "Hon. Mr. Cockrill")
        self.assertEqual(sp.unsplit("Ms. Co nway"), "Ms. Conway")
        self.assertEqual(sp.unsplit("Ms de Jonge"), "Ms de Jonge")
        self.assertEqual(sp.unsplit("Ms. A. Young"), "Ms. A. Young")

    def test_a_bold_lead_is_a_label_only_when_a_colon_follows(self):
        self.assertEqual(sp.bold_label('<b>Mr. Jim </b><b><a name="x">Maloway</a></b><b> (Elmwood):</b> I wish'),
                         ("Mr. Jim Maloway (Elmwood)", "I wish"))
        self.assertEqual(sp.bold_label("<b><span>Hon. Mr.\r\nCockrill</span></b><span>: —</span> Thank you"),
                         ("Hon. Mr. Cockrill", "Thank you"))
        self.assertEqual(sp.bold_label("<b>M.</b> <b>Arcand</b> <b>:</b> M. le Président"),
                         ("M. Arcand", "M. le Président"))
        self.assertEqual(sp.bold_label("<strong>S. CROCKER: </strong>Yes."), ("S. CROCKER", "Yes."))
        self.assertIsNone(sp.bold_label("<b>House Business</b>"))
        self.assertIsNone(sp.bold_label("Plain text then <b>bold:</b>"))

    def test_the_honorific(self):
        self.assertEqual(sp.honorific("Mrs. Smith"), "f")
        self.assertEqual(sp.honorific("Hon. Mr. Herron"), "mr")
        self.assertEqual(sp.honorific("Mme David"), "f")
        self.assertIsNone(sp.honorific("MLA Asagwara"))

    def test_the_bill_a_heading_names(self):
        self.assertEqual(sp.bill_number("Bill No. 137 — The Education ... Act, 2023"), "137")
        self.assertEqual(sp.bill_number("Bill 207–The Abortion Protest Buffer Zone Act"), "207")
        self.assertEqual(sp.bill_number("Debate on Second Reading of Bill 46"), "46")
        self.assertIsNone(sp.bill_number("Tenant protection"))


# -- who spoke ------------------------------------------------------------------------------

class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.conn = _conn()
        member(self.conn, "mb", "andrew-smith", "Andrew", "Smith", "Lagimodière", leg=42)
        member(self.conn, "mb", "bernadette-smith", "Bernadette", "Smith", "Point Douglas", leg=42)
        member(self.conn, "mb", "jon-gerrard", "Jon", "Gerrard", "River Heights", leg=42)
        member(self.conn, "mb", "kelvin-goertzen", "Kelvin", "Goertzen", "Steinbach", leg=42)
        member(self.conn, "mb", "michael-harris", "Michael", "Harris", "Kildonan", leg=42)
        member(self.conn, "mb", "jennifer-stevens", "Jennifer", "Stevens", "St. Catharines", leg=42)
        member(self.conn, "mb", "tamara-davidson", "Tamara", "Davidson", "North Coast", leg=42)
        self.conn.commit()
        self.r = pn.Resolver.from_conn(self.conn, "mb")

    def keys(self, turns):
        return [k for k, _h in sp.resolve_turns(self.conn, "mb", self.r, turns, "2021-10-14", 42)]

    def test_a_bracket_is_a_riding_first_and_a_role_second(self):
        self.assertEqual(sp.resolve_label(self.r, "Hon. Jon Gerrard (River Heights)", "2021-10-14", 42),
                         ("jon-gerrard", "full-name+riding"))
        k, how = sp.resolve_label(self.r, "Hon. Kelvin Goertzen (Government House Leader)", "2021-10-14", 42)
        self.assertEqual(k, "kelvin-goertzen")
        self.assertIn("bracket is a role", how)
        self.assertEqual(sp.resolve_label(self.r, "Mrs. Jennifer (Jennie) Stevens", "2021-10-14", 42)[0],
                         "jennifer-stevens")

    def test_a_familiar_given_name_is_retried_as_its_initial(self):
        k, how = sp.resolve_label(self.r, "Hon. Mike Harris", "2021-10-14", 42)
        self.assertEqual(k, "michael-harris")
        self.assertIn("initial", how)

    def test_a_name_in_two_languages_resolves_on_either_side(self):
        self.assertEqual(sp.resolve_label(self.r, "Hon. Laanas / Tamara Davidson", "2021-10-14", 42)[0],
                         "tamara-davidson")

    def test_an_unknown_label_is_none_never_a_guess(self):
        self.assertEqual(sp.resolve_label(self.r, "Mr. Nobody", "2021-10-14", 42)[0], None)
        self.assertEqual(sp.resolve_label(self.r, "The Premier", "2021-10-14", 42)[0], None)
        # A term must be valid on the day.
        self.assertEqual(sp.resolve_label(self.r, "Hon. Jon Gerrard", "1999-01-01", 42)[0], None)

    def test_a_bare_surname_follows_the_one_named_in_full_that_sitting(self):
        self.assertEqual(self.keys([turn("Mr. Andrew Smith (Lagimodière)", "x"), turn("Mr. Smith", "y")]),
                         ["andrew-smith", "andrew-smith"])

    def test_two_named_in_full_are_told_apart_by_honorific(self):
        got = self.keys([turn("Mr. Andrew Smith (Chairperson)", "x"), turn("Mrs. Bernadette Smith (Point Douglas)", "x"),
                         turn("Mrs. Smith", "y"), turn("Mr. Smith", "z")])
        self.assertEqual(got, ["andrew-smith", "bernadette-smith", "bernadette-smith", "andrew-smith"])

    def test_nobody_named_in_full_means_the_surname_stays_unresolved(self):
        """Learning is inside one sitting: another day's full label never counts."""
        self.keys([turn("Mrs. Bernadette Smith (Point Douglas)", "x")])
        self.assertEqual(self.keys([turn("Mrs. Smith", "y")]), [None])

    def test_the_heading_above_a_turn_is_the_speakers_full_name(self):
        conn = _conn()
        member(conn, "qc", "1", "Simon", "Jolin-Barrette", "Borduas", leg=42)
        member(conn, "qc", "2", "Pierre", "Jolin-Barrette", "Ailleurs", leg=42)
        r = pn.Resolver.from_conn(conn, "qc")
        got = sp.resolve_turns(conn, "qc", r, [turn("M. Jolin-Barrette", "x", hint="M. Simon Jolin-Barrette")],
                               "2019-06-16", 42)
        self.assertEqual(got[0][0], "1")
        self.assertIn("heading above the turn", got[0][1])


# -- the day -------------------------------------------------------------------------------

class StoreTests(unittest.TestCase):
    DAY = {"key": "mb-42-3-2021-10-14", "date": "2021-10-14", "legislature": 42, "session": 3,
           "url": "https://www.gov.mb.ca/legislature/hansard/42nd_3rd/vol_80a/h80a.html"}

    def setUp(self):
        self.conn = _conn()
        member(self.conn, "mb", "nahanni-fontaine", "Nahanni", "Fontaine", "St. Johns", leg=42)
        member(self.conn, "mb", "shannon-martin", "Shannon", "Martin", "McPhillips", leg=42)
        self.conn.commit()
        self.ctx = Ctx(self.conn, "mb")
        self.tax = pc.load_taxonomy()
        self.wl = pc.load_watchlist("mb")

    def store(self, turns, day=None):
        r = pn.Resolver.from_conn(self.conn, "mb")
        return sp.store_day(self.ctx, day or self.DAY, turns, r, self.tax, self.wl)

    def test_only_speeches_on_our_ground_are_stored_and_every_turn_is_counted(self):
        t = self.store([
            turn("Madam Speaker", "I will therefore call second reading of Bill 207, The Abortion Protest Buffer Zone Act."),
            turn("Ms. Fontaine", "Women seeking an abortion are harassed outside the clinic every week."),
            turn("Mr. Martin", "The bridge on Nairn Avenue needs replacing."),
            turn("Mr. Unknown", "Abortion access is a right in this province."),
        ])
        self.assertEqual((t["turns"], t["chair"], t["members"], t["resolved"], t["stored"], t["unresolved"]),
                         (4, 1, 3, 2, 2, 1))
        rows = self.conn.execute("SELECT speech_id, member_key, speaker_label, how, areas FROM prov_speeches "
                                 "ORDER BY seq").fetchall()
        self.assertEqual([r["speech_id"] for r in rows], ["mb-42-3-2021-10-14-2", "mb-42-3-2021-10-14-4"])
        self.assertEqual(rows[0]["member_key"], "nahanni-fontaine")
        self.assertIsNone(rows[1]["member_key"])                 # never guessed
        self.assertEqual(rows[1]["speaker_label"], "Mr. Unknown")  # kept as printed
        self.assertIn(1, json.loads(rows[0]["areas"]))
        s = self.conn.execute("SELECT * FROM prov_speech_sittings").fetchone()
        self.assertEqual((s["turns"], s["chair"], s["members"], s["resolved"], s["stored"], s["unresolved"],
                          s["status"]), (4, 1, 3, 2, 2, 1, "ok"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM prov_sittings").fetchone()[0], 0)

    def test_a_watched_bills_debate_is_on_our_ground_and_quotes_the_members_words(self):
        self.store([turn("Ms. Fontaine", "I'm pleased to put some words on the record this morning.",
                         subject="Bill 207–The Abortion Protest Buffer Zone Act", bill="207")])
        row = self.conn.execute("SELECT bill_key, areas, excerpt FROM prov_speeches").fetchone()
        self.assertEqual(row["bill_key"], "mb-42-3/207")
        self.assertIn(1, json.loads(row["areas"]))
        self.assertTrue(row["excerpt"].startswith("I'm pleased"), row["excerpt"])

    def test_a_bills_text_classification_is_not_lent_to_its_debate(self):
        ps.store_bill(self.conn, {"bill_key": "mb-42-3/9", "prov": "mb", "legislature": 42, "session": 3,
                                  "number": "9", "title_en": "The Budget Implementation Act", "text_read": 1,
                                  "areas": [13]})
        self.store([turn("Mr. Martin", "The tax measures in this bill help families.", subject="Bill 9", bill="9")])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM prov_speeches").fetchone()[0], 0)

    def test_another_sessions_bill_of_the_same_number_is_never_joined(self):
        ps.store_bill(self.conn, {"bill_key": "mb-43-2/207", "prov": "mb", "legislature": 43, "session": 2,
                                  "number": "207", "title_en": "Something Else Act"})
        self.assertEqual(sp.bill_for(self.conn, "mb", 42, 1, "207"), (None, []))

    def test_a_day_whose_speakers_mostly_do_not_resolve_is_a_gap_and_stays_owed(self):
        t = self.store([turn("Mr. A{0}".format(i), "Speech number {0}.".format(i)) for i in range(sp.MIN_SPEAKERS)])
        self.assertEqual(t["status"], "gap")
        self.assertIn("roster for the day", self.ctx.gaps[0])
        self.assertFalse(sp.day_done(self.conn, self.DAY["key"]))

    def test_a_day_with_no_turns_is_unreadable_never_an_empty_day(self):
        t = self.store([])
        self.assertEqual(t["status"], "unreadable")
        self.assertFalse(sp.day_done(self.conn, self.DAY["key"]))

    def test_reading_a_day_again_replaces_its_speeches(self):
        speech = turn("Ms. Fontaine", "Women seeking an abortion are harassed outside the clinic.")
        self.store([speech, speech])
        self.store([speech])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM prov_speeches").fetchone()[0], 1)
        self.assertTrue(sp.day_done(self.conn, self.DAY["key"]))

    def test_quebec_is_classified_in_french(self):
        conn = _conn()
        member(conn, "qc", "1", "Simon", "Jolin-Barrette", "Borduas", leg=42)
        conn.commit()
        ctx = Ctx(conn, "qc")
        day = {"key": "qc-42-1-2019-06-16", "date": "2019-06-16", "legislature": 42, "session": 1}
        sp.store_day(ctx, day, [turn("M. Jolin-Barrette", "Ce qu'on vient faire, c'est d'inscrire la laïcité de l'État.")],
                     pn.Resolver.from_conn(conn, "qc"), pc.load_french_taxonomy("qc"), pc.load_watchlist("qc"),
                     language="fr")
        row = conn.execute("SELECT member_key, language, areas FROM prov_speeches").fetchone()
        self.assertEqual((row["member_key"], row["language"]), ("1", "fr"))
        self.assertIn(8, json.loads(row["areas"]))

    def test_resume_is_two_weeks_before_the_newest_day_and_a_first_run_reads_sixty_days(self):
        import datetime
        today = datetime.date(2026, 10, 7)
        self.assertEqual(sp.resume_since(self.conn, "mb", today=today, log=lambda *a: None), "2026-08-08")
        sp.store_sitting(self.conn, "mb", {"key": "k1", "date": "2026-09-30"}, {}, "ok")
        sp.store_sitting(self.conn, "mb", {"key": "k0", "date": "2026-07-01"}, {}, "gap")
        self.assertEqual(sp.resume_since(self.conn, "mb", today=today, log=lambda *a: None), "2026-07-01")


# -- the readers, on the probes' trimmed copies ------------------------------------------------

class ReaderTests(unittest.TestCase):
    def test_ontario(self):
        turns = on.parse_day(fx("on_hansard_trim.html"))
        first = turns[0]
        self.assertEqual((first["label"], first["rubric"], first["subject"]),
                         ("Mr. Brian Saunderson:", "Members’ Statements", "Second Tracks"))
        bill = [t for t in turns if t["subject"] == "Resource Management and Safety Act, 2025"]
        self.assertTrue(bill and all(t["bill"] == "27" for t in bill))   # from the opening line, English half
        self.assertFalse(any("Allsopp" in p for t in turns for p in t["paras"]))   # the division list

    def test_british_columbia(self):
        turns = bc.parse_day(fx("bc_hansard_n119.html"))
        arm = next(t for t in turns if t["label"] == "Tara Armstrong")
        self.assertEqual((arm["rubric"], arm["subject"]),
                         ("Introduction and First Reading of Bills", "Gender Ideology and Child Protection Act"))
        self.assertTrue(any(t["bill"] == "6" for t in turns))

    def test_manitoba_keeps_the_bill_through_its_questions(self):
        turns = mb.parse_day(fx("mb_hansard_211014_trim.html"))
        self.assertEqual(turns[1]["label"], "Ms. Nahanni Fontaine (St. Johns)")
        qs = [t for t in turns if t["subject"].endswith("— Questions")]
        self.assertTrue(qs and all(t["bill"] == "207" for t in qs))

    def test_saskatchewan_pdf_and_html_read_alike(self):
        pdf = sk.parse_pdf(fx("sk_debates_231020_trim.txt"))
        html = sk.parse_html(fx("sk_debates_html_trim.htm"))
        for turns in (pdf, html):
            cock = next(t for t in turns if t["label"] == "Hon. Mr. Cockrill")
            self.assertEqual(cock["bill"], "137")
            self.assertNotIn("Loi", cock["subject"])                  # the French title is dropped
            self.assertTrue(any(t["label"] == "Ms. Beck" for t in turns))

    def test_newfoundland_takes_the_bill_from_the_clerks_reading(self):
        turns = nl.parse_day(fx("nl_hansard_221101.htm"))
        clerk = next(t for t in turns if t["subject"] and "(Bill 7)" in t["subject"])
        self.assertEqual(clerk["bill"], "7")
        self.assertTrue(any(t["label"] == "S. CROCKER" for t in turns))

    def test_quebec_reads_the_speaker_heading_as_a_hint(self):
        turns = qc.parse_day(fx("qc_jd_190616_trim.html"))
        self.assertEqual(turns[0]["rubric"], "Questions et réponses orales")
        jb = next(t for t in turns if t["label"] == "M. Jolin-Barrette")
        self.assertEqual(jb["hint"], "M. Simon Jolin-Barrette")
        self.assertTrue(any(sp.is_chair(t["label"]) for t in turns))

    def test_alberta_heads_and_bill_lines(self):
        turns = ab.parse_pdf(fx("ab_hansard_241203_trim.txt"))
        self.assertEqual(turns[0]["rubric"], "Prayers")
        la = next(t for t in turns if t["label"] == "Member LaGrange")
        self.assertEqual((la["bill"], la["rubric"]), ("26", "Government Bills and Orders"))
        self.assertTrue(la["subject"].startswith("Third Reading — Bill 26"))
        nic = next(t for t in turns if t["label"].endswith("Nicolaides"))
        self.assertEqual(nic["bill"], "27")                       # "3:50  Bill 27", no head: line
        self.assertGreater(len(la["paras"]), 1)                   # indented lines open paragraphs

    def test_new_brunswick_keeps_the_english_column(self):
        frags = [tuple(f) for f in json.loads(fx("nb_hansard_230615_frags.json"))]
        paras = nb.english_stream(frags)
        joined = " ".join(paras)
        self.assertIn("Policy 713", joined)
        self.assertNotIn("Merci beaucoup, Monsieur le président", joined)
        turns = nb.parse_paragraphs(paras)
        self.assertTrue(any(t["label"] == "Hon. Mr. Hogan" for t in turns))
        self.assertTrue(any(t["subject"] == "Introduction of Guests" for t in turns))
        self.assertGreater(nb.english_score("Thank you, Mr. Speaker."), nb.english_score("Merci, Monsieur le président."))

    def test_new_brunswick_before_58_3_is_not_published_and_not_a_gap(self):
        """The Hansard page offers sessions from 58-3 (2017) on; earlier ones are on
        request from the Legislative Library (measured 2 October 2026)."""
        menu = "".join('<a href="/en/house-business/hansard/{0}/{1}">x</a>'.format(l, s)
                       for l, s in ((58, 3), (58, 4), (61, 2)))
        pages = {"https://www.legnb.ca/en/house-business/hansard/57/1": menu,
                 "https://www.legnb.ca/en/house-business/hansard/61/1": menu}
        for session, gaps in (("57-1", 0), ("61-1", 1)):
            ctx = Context(_conn(), FakeClient(pages), "nb", dry_run=True, robots=False, log=lambda *a: None)
            self.assertEqual(nb.list_days(ctx, session), [])
            self.assertEqual(len(ctx.gaps), gaps, session)

    def test_saskatchewan_lists_both_archive_layouts(self):
        old = ('<a data-bs-toggle="collapse" href="#20151126"></a><ul><li><a href="https://docs.legassembly.sk.ca/'
               'legdocs/Assembly/Debates/27L4S/151126Debates.pdf" target="_blank">Debates</a></li><li><a href="https:'
               '//docs.legassembly.sk.ca/legdocs/Assembly/Minutes/27L4S/151126Minutes.pdf">Minutes</a></li></ul>')
        new = ('<a data-bs-toggle="collapse" href="#20251022"></a><span>Debates (<a href="https://docs.legassembly.sk.ca'
               '/legdocs/Assembly/Debates/30L1S/20251022Debates-AM.pdf">PDF</a>, <a href="https://docs.legassembly.sk.ca'
               '/legdocs/Assembly/Debates/30L1S/20251022Debates-AM-HTML.htm">HTML</a>)</span><span>Debates (<a href="'
               'https://docs.legassembly.sk.ca/legdocs/Assembly/Debates/30L2S/20251022Debates.pdf">PDF</a>)</span>')
        got = sk.list_debates(old) + sk.list_debates(new)
        self.assertEqual([(d["date"], d["legislature"], d["session"], d["part"], bool(d["html"])) for d in got],
                         [("2015-11-26", 27, 4, None, False), ("2025-10-22", 30, 1, "am", True),
                          ("2025-10-22", 30, 2, None, False)])

    def test_every_reader_has_the_interface_and_its_language(self):
        for mod in (ab, bc, mb, nb, nl, on, qc, sk):
            for name in ("list_days", "read_day", "resolver", "LANGUAGE", "PROV"):
                self.assertTrue(hasattr(mod, name), (mod.__name__, name))
        self.assertEqual(qc.LANGUAGE, "fr")
        self.assertEqual({m.LANGUAGE for m in (ab, bc, mb, nb, nl, on, sk)}, {"en"})


class ArchiveTests(unittest.TestCase):
    def test_the_day_is_archived_under_a_lowercase_slug_and_listings_are_not(self):
        url = "https://lims.leg.bc.ca/hdms/file/Debates/43rd2nd/20260219am-Hansard-n119.html"
        client = FakeClient({url: fx("bc_hansard_n119.html")})
        ctx = Context(_conn(), client, "bc", feed=sp.feed("bc"), log=lambda *a: None)
        turns, problems = bc.read_day(ctx, {"key": "bc-43-2-2026-02-19-am", "date": "2026-02-19", "part": "am",
                                            "legislature": 43, "session": 2, "url": url})
        self.assertTrue(turns)
        self.assertEqual(client.archived, [("prov-bc-speeches", "hansard-bc-43-2-2026-02-19-am")])
        for _feed, name in client.archived:
            self.assertEqual(name, name.lower())


# -- the tool -------------------------------------------------------------------------------

class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tool = _load("prov_speeches")

    def test_a_reader_for_every_built_province_and_none_for_the_rest(self):
        # Nova Scotia (built 2 October 2026) reads its divisions from Hansard
        # but has no speeches reader yet: the one named exception, so a new
        # province without one still fails here.
        no_reader_yet = {"ns"}
        self.assertEqual(sorted(self.tool.READERS),
                         sorted(set(self.tool.collector.MODULES) - no_reader_yet))
        with self.assertRaises(SystemExit):
            self.tool.reader_for("pe")

    def test_a_run_reads_the_days_stamps_its_heartbeat_and_records_its_gaps(self):
        conn = _conn()
        member(conn, "on", "fife", "Catherine", "Fife", "Waterloo", leg=44)
        conn.commit()

        class Reader:
            LANGUAGE = "en"

            @staticmethod
            def list_days(ctx, session):
                return [{"key": "on-44-1-2025-11-24", "date": "2025-11-24", "legislature": 44, "session": 1,
                         "url": "u1"},
                        {"key": "on-44-1-2025-11-25", "date": "2025-11-25", "legislature": 44, "session": 1,
                         "url": "u2"}]

            @staticmethod
            def read_day(ctx, day):
                if day["key"].endswith("25"):
                    return None, ["the day's Hansard page was not fetched"]
                return [turn("Ms. Catherine Fife", "Conversion therapy harms young people.")], []

            @staticmethod
            def resolver(ctx):
                return pn.Resolver.from_conn(ctx.conn, "on")

        self.tool.reader_for = lambda prov: Reader
        stats, gaps = self.tool.run(conn, FakeClient({}), "on", session="44-1", since="2025-11-01",
                                    until="2025-11-30", log=lambda *a: None)
        self.assertEqual((stats["days_read"], stats["speeches"], stats["day_gaps"]), (1, 1, 1))
        self.assertEqual(conn.execute("SELECT member_key FROM prov_speeches").fetchone()[0], "fife")
        self.assertEqual(conn.execute("SELECT last_run IS NOT NULL FROM source_runs WHERE source=?",
                                      (self.tool.HEARTBEAT,)).fetchone()[0], 1)
        self.assertTrue(any("not fetched" in g for g in gaps))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM gaps WHERE feed='prov-on-speeches'").fetchone()[0], 1)
        # Read cleanly, never again; the unreadable day stays owed.
        stats, _ = self.tool.run(conn, FakeClient({}), "on", session="44-1", since="2025-11-01",
                                 until="2025-11-30", log=lambda *a: None)
        self.assertEqual(stats["days_read"], 0)
        self.assertEqual(stats["day_gaps"], 1)

    def test_all_sessions_needs_a_since(self):
        with self.assertRaises(SystemExit):
            self.tool.run(_conn(), FakeClient({}), "on", all_sessions=True, log=lambda *a: None)


# -- the 5CA ---------------------------------------------------------------------------------

class FiveCATests(unittest.TestCase):
    def test_speeches_are_evidence_one_line_a_debate_and_never_place(self):
        p5 = _load("prov_5ca")
        conn = _conn()
        member(conn, "mb", "nahanni-fontaine", "Nahanni", "Fontaine", "St. Johns", leg=42, sitting=1)
        member(conn, "mb", "gone", "Former", "Member", "Nowhere", leg=42, sitting=0)
        for seq, key in ((1, "nahanni-fontaine"), (2, "nahanni-fontaine"), (3, "gone")):
            conn.execute("INSERT INTO prov_speeches (speech_id, prov, sitting_key, date, subject, member_key, "
                         "areas, excerpt, seq) VALUES (?,?,?,?,?,?,?,?,?)",
                         ("s{0}".format(seq), "mb", "mb-42-3-2021-10-14", "2021-10-14",
                          "Bill 207–The Abortion Protest Buffer Zone Act", key, "[1]", "Women are harassed.", seq))
        conn.commit()
        rows, _t, _u, _v = p5.build_rows(conn, "mb", 1, {}, {})
        by = {r["key"]: r for r in rows}
        self.assertEqual(by["nahanni-fontaine"]["column"], "0")
        self.assertEqual(len(by["nahanni-fontaine"]["comments"]), 1)
        self.assertIn("SPEECH x2", by["nahanni-fontaine"]["comments"][0])
        self.assertIn("activity, not direction", by["nahanni-fontaine"]["comments"][0])
        self.assertNotIn("gone", by)                         # a former member with only speeches is not listed


# -- the workflow and the coverage watch ------------------------------------------------------

def steps():
    with open(WORKFLOW, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["jobs"]["collect"]["steps"]


class WorkflowTests(unittest.TestCase):
    def test_a_speeches_step_per_province_after_the_collectors_and_before_the_sheets(self):
        names = [s.get("name") for s in steps()]
        last_collect = max(i for i, s in enumerate(steps()) if "prov_collect.py" in s.get("run", "")
                           and "--resume" in s.get("run", ""))
        first_sheet = min(i for i, s in enumerate(steps()) if "prov_5ca.py" in s.get("run", ""))
        found = {}
        for i, s in enumerate(steps()):
            run = s.get("run", "")
            if "prov_speeches.py" in run and "--resume" in run:
                p = run.split("--prov ")[1].split()[0]
                found[p] = s
                self.assertTrue(last_collect < i < first_sheet, (names[i], names))
                self.assertIn("always()", s["if"])
                self.assertIn("inputs.provinces == ''", s["if"])
                budget = int(run.split("--budget-seconds ")[1].split()[0])
                self.assertGreater(s["timeout-minutes"] * 60, budget)
        self.assertEqual(sorted(found), sorted(BUILT))

    def test_the_weekly_job_outlasts_every_clock(self):
        with open(WORKFLOW, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        weekly = int(str(doc["jobs"]["collect"]["timeout-minutes"]).split("||")[1].strip(" }"))
        total = sum(int(s["run"].split("--budget-seconds ")[1].split()[0]) for s in steps()
                    if "--resume" in s.get("run", "") or "--roster-only" in s.get("run", ""))
        self.assertGreater(weekly * 60, total)

    def test_the_speeches_backfill_is_its_own_input_and_the_vote_backfill_is_unchanged(self):
        with open(WORKFLOW, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        inputs = doc.get("on", doc.get(True))["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["speeches_since"]["default"], "")
        self.assertEqual(inputs["provinces"]["default"], "")
        self.assertEqual(inputs["since"]["default"], "2010-01-01")
        votes = next(s for s in steps() if "prov_collect.py" in s.get("run", "") and "--all-sessions" in s["run"])
        self.assertIn("inputs.provinces != ''", votes["if"])
        self.assertIn("inputs.speeches_since == ''", votes["if"])
        self.assertIn('--since "$SINCE"', votes["run"])
        talk = next(s for s in steps() if "prov_speeches.py" in s.get("run", "") and "--all-sessions" in s["run"])
        self.assertIn("inputs.speeches_since != ''", talk["if"])
        self.assertIn("inputs.provinces != ''", talk["if"])
        self.assertIn('--since "$SPEECHES_SINCE"', talk["run"])
        self.assertIn("|| rc=1", talk["run"])
        self.assertIn('if [ "$MINUTES" -gt 300 ]', talk["run"])
        self.assertLess([s.get("name") for s in steps()].index(votes["name"]),
                        [s.get("name") for s in steps()].index(talk["name"]))


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.cov = _load("coverage")

    def test_the_speech_tables_are_written_once_per_item(self):
        self.assertIn("prov_speeches", self.cov.ONCE_EVER)
        self.assertIn("prov_speech_sittings", self.cov.ONCE_EVER)

    def test_their_emptiness_is_excused_only_until_the_speeches_step_has_run(self):
        import datetime
        import sqlite3
        tool = _load("prov_speeches")
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE source_runs (source TEXT PRIMARY KEY, last_run TEXT NOT NULL, "
                     "run_id TEXT, note TEXT)")
        for t in ("prov_speeches", "prov_speech_sittings"):
            conn.execute("CREATE TABLE {0} (x TEXT, first_seen TEXT)".format(t))
        conn.execute("INSERT INTO source_runs VALUES ('Provinces weekly', '2026-10-07', '1', '')")
        feeds, once = self.cov.FEEDS, self.cov.ONCE_EVER
        self.cov.FEEDS = []
        self.cov.ONCE_EVER = {k: v for k, v in once.items() if k in ("prov_speeches", "prov_speech_sittings")}
        try:
            overdue = self.cov.check(conn, today=datetime.date(2026, 10, 8), log=lambda *a: None)
            self.assertEqual(overdue, [])                     # a vote backfill ran; no speeches step yet
            conn.execute("INSERT INTO source_runs VALUES (?, '2026-10-14', '2', '')", (tool.HEARTBEAT,))
            overdue = self.cov.check(conn, today=datetime.date(2026, 10, 15), log=lambda *a: None)
            self.assertEqual(len([o for o in overdue if "NO ROWS" in o]), 2)
        finally:
            self.cov.FEEDS, self.cov.ONCE_EVER = feeds, once


class SchemaTests(unittest.TestCase):
    def test_the_speech_tables_are_declared_and_carry_no_sighting_column(self):
        conn = _conn()
        for t in ("prov_speeches", "prov_speech_sittings"):
            self.assertIn(t, db.TABLES)
            cols = {c[1] for c in conn.execute("PRAGMA table_info({0})".format(t))}
            self.assertFalse(cols & {"last_seen", "captured_at"}, t)

    def test_an_old_store_gains_the_new_speech_columns(self):
        conn = db.connect(":memory:")
        conn.execute("CREATE TABLE prov_speeches (speech_id TEXT PRIMARY KEY, prov TEXT NOT NULL, "
                     "sitting_key TEXT, date TEXT, subject TEXT, bill_key TEXT, member_key TEXT, "
                     "speaker_label TEXT, language TEXT, text TEXT, areas TEXT, excerpt TEXT, first_seen TEXT)")
        ps.ensure_schema(conn)
        ps.ensure_schema(conn)
        cols = {c[1] for c in conn.execute("PRAGMA table_info(prov_speeches)")}
        self.assertTrue({"how", "matched_terms", "tier", "rubric", "seq", "source_url"} <= cols)


if __name__ == "__main__":
    unittest.main()
