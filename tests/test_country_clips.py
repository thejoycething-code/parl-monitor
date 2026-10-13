"""Speech clips for the new countries (src/country_clips.py, tools/country_clips.py).

Fixtures in tests/fixtures/clips/ are trimmed from the live sources probed on
11 October 2026: the Austrian Mediathek page of NR sitting 96, the Belgian
Chamber's meeting P143 (8 October 2026), the French portal's video page and
seance-publique list. Nothing here touches the network or needs ffmpeg."""

import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import chamber_store as cs  # noqa: E402
from src import country_clips as cc  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "clips")

DE_SPEECH = (
    "Herr Präsident! Meine Damen und Herren! Ich danke für das Wort. "
    "Wir sprechen heute über den Schutz des ungeborenen Lebens und über die Abtreibung. "
    "Jedes Kind hat ein Recht auf Leben, vom ersten Tag an, und dieses Recht steht nicht zur Abstimmung. "
    "Die Fristenregelung ist ein Kompromiss, den wir nicht weiter aufweichen dürfen. "
    "Wer die Abtreibung zu einem Menschenrecht erklärt, verschiebt die Grenze dessen, was wir schützen. "
    "Frauen in Not brauchen Hilfe, Beratung und echte Alternativen, keine leeren Versprechen. "
    "Deshalb lehnen wir diesen Antrag ab und fordern stattdessen mehr Unterstützung für Familien. "
    "Ist das wirklich zu viel verlangt?")


class Words(unittest.TestCase):
    def test_fold_strips_accents_for_the_aligner(self):
        self.assertEqual(cc.fold("Größe Société Œuvre l’IVG"), "grosse societe oeuvre l'ivg")

    def test_passage_grows_around_terms_and_never_ends_on_a_question(self):
        p = cc.choose_passage(DE_SPEECH, ["Abtreibung*", "Fristenregelung*"], floor_s=10, target_s=25, cap_s=40)
        self.assertIsNotNone(p)
        self.assertIn("Abtreibung", p)
        self.assertFalse(p.rstrip().endswith("?"))
        self.assertLessEqual(cc.spoken_seconds(p), 40)

    def test_no_passage_when_nothing_fits(self):
        self.assertIsNone(cc.choose_passage("Kurz. Danke.", ["x"]))


def _row(i, **kw):
    r = {"speech_id": "transcript:%d" % i, "doc_id": "d", "date": "2026-09-29", "chamber": "Ständerat",
         "debate_id": "x", "debate": "25.455: Feministische Verfassungsrevision", "speaker": "Muster Hans",
         "party": "V/SG", "role": "member", "person_id": None, "excerpt": "", "text": DE_SPEECH * 2,
         "url": "u", "areas": "[2]", "matched_terms": json.dumps(["Abtreibung*"]), "tier": 1}
    r.update(kw)
    return r


class Pick(unittest.TestCase):
    def test_ranks_tier_then_terms_then_members(self):
        rows = [_row(1, tier=2), _row(2, role="Bundesrat"),
                _row(3, matched_terms=json.dumps(["Abtreibung*", "Fristenregelung*"])), _row(4),
                _row(5, text="zu kurz")]
        got = [c["speech_id"] for c in cc.candidates(rows)]
        self.assertEqual(got, ["transcript:3", "transcript:4", "transcript:2", "transcript:1"])

    def test_store_rows_and_find(self):
        conn = sqlite3.connect(":memory:")
        cs.ensure_schema(conn, ["ch"])
        for r in (_row(1), _row(2, date="2026-09-30", debate="Bilaterale III")):
            conn.execute("INSERT INTO ch_speeches (speech_id, doc_id, date, debate_id, debate, speaker, party, role,"
                         " text, matched_terms, tier) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (r["speech_id"], r["doc_id"], r["date"], r["debate_id"], r["debate"], r["speaker"],
                          r["party"], r["role"], r["text"], r["matched_terms"], r["tier"]))
        rows = cc.store_rows(conn, "ch", since="2026-09-01")
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["speech_id"] for r in cc.select(rows, find="verfassungsrevision")], ["transcript:1"])

    def test_pack_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [_row(1, speaker="Golay Roger, Mitglied"), _row(2)]
            cands = cc.candidates(rows)
            entry = cc.load_sources()["ch"]
            pack = cc.write_pack("ch", rows, cands, entry, top=1, date="2026-09-29", out_dir=tmp)
            seq = cc.parse_sequence(open(os.path.join(pack, "sequence.md"), encoding="utf-8").read())
            self.assertEqual(len(seq), 1)
            self.assertEqual(seq[0]["name"], "Golay Roger")          # the plate drops the office
            self.assertEqual(seq[0]["speech"], "transcript:1")
            self.assertEqual(" ".join(seq[0]["passage"].split()), " ".join(cands[0]["passage"].split()))
            readme = open(os.path.join(pack, "README.md"), encoding="utf-8").read()
            self.assertIn("awaiting sign-off", readme)
            self.assertIn("© ParlCH", readme)
            self.assertIn("PROVISIONAL", open(os.path.join(pack, "sequence.md"), encoding="utf-8").read())


class Sources(unittest.TestCase):
    def setUp(self):
        self.src = cc.load_sources()

    def test_every_speech_country_is_recorded(self):
        for code in [c for c, feeds in cs.COUNTRIES.items() if "speeches" in feeds]:
            self.assertIn(code, self.src)
        for code in ("br", "pl", "it", "es"):
            self.assertEqual(self.src[code]["status"], "not-built")

    def test_gate(self):
        self.assertIsNone(cc.gate(self.src, "ch"))
        self.assertIsNone(cc.gate(self.src, "at"))
        with self.assertRaises(cc.ClipRefused):
            cc.gate(self.src, "nl")                                   # manual: needs --video
        self.assertIsNone(cc.gate(self.src, "nl", video="speech.mp4"))
        with self.assertRaises(cc.ClipRefused):
            cc.gate(self.src, "be")                                   # no agreement recorded
        src = dict(self.src, be=dict(self.src["be"], agreement="written reply of 1 Nov 2026"))
        self.assertIsNone(cc.gate(src, "be"))
        # France: agreement recorded 12 October 2026, status allowed.
        self.assertIsNone(cc.gate(self.src, "fr"))
        for missing in ("date", "grantor", "conditions"):
            ag = dict(self.src["fr"]["agreement"], **{missing: ""})
            with self.assertRaises(cc.ClipRefused):
                cc.gate(dict(self.src, fr=dict(self.src["fr"], agreement=ag)), "fr")
        with self.assertRaises(cc.ClipRefused):
            cc.gate(dict(self.src, fr=dict(self.src["fr"], agreement="yes")), "fr")
        with self.assertRaises(cc.ClipRefused):
            cc.gate(self.src, "br")

    def test_france_agreement_and_credit(self):
        fr = self.src["fr"]
        self.assertEqual(fr["status"], "allowed")
        self.assertEqual(fr["edits"], "trim-only")
        self.assertEqual(fr["agreement"]["date"], "2026-10-12")
        self.assertIn("Cellule GILDA", fr["agreement"]["grantor"])
        self.assertIn("Fabien Chauvineau", fr["agreement"]["grantor"])
        self.assertIn("not distorted and/or modified", " ".join(fr["agreement"]["conditions"].split()))
        credit = "Archives audiovisuelles de l'Assemblée nationale"
        self.assertEqual(fr["credit"], credit)
        self.assertEqual(fr["post_credit"], credit)
        self.assertFalse(fr["logo"])
        table = cc.sources_table(self.src)
        self.assertIn("| FR | allowed (agreement recorded 2026-10-12), trim-only |", table)
        readme = cc.readme("fr", fr, "t", "2026-10-09")
        self.assertIn("Agreement: written agreement of 2026-10-12", readme)
        self.assertIn("Trim-only", readme)
        self.assertIn("Credit for the post text: `{0}`".format(credit), readme)

    def test_trim_only_with_a_logo_is_refused_at_load(self):
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.yaml")
            with open(path, "w") as fh:
                yaml.safe_dump({"fr": dict(self.src["fr"], logo=True)}, fh, allow_unicode=True)
            with self.assertRaises(ValueError):
                cc.load_sources(path)

    def test_no_em_dashes(self):
        self.assertNotIn("—", open(cc.CONFIG, encoding="utf-8").read())


class Locators(unittest.TestCase):
    def test_ch_speech_file(self):
        s = cc.locate_ch({"speech_id": "transcript:422044"}, None)
        self.assertEqual(s[0]["media"], "https://par-pcache.simplex.tv/content/simvid_1.mp4?externalid=422044")

    def test_at_redner_from_the_mediathek_page(self):
        red = cc.at_redner(open(os.path.join(FIX, "at-mediathek-96.txt"), encoding="utf-8").read())
        self.assertEqual(red[1016332][0], "5f4fc133-c90d-4a9c-821f-746b67fd487f")

    def test_at_locate_with_a_fake_client(self):
        page = open(os.path.join(FIX, "at-mediathek-96.txt"), encoding="utf-8").read()

        class Client:
            calls = []

            def get_text(self, url, feed, slug, archive=True):
                self.calls.append(url)
                if "mediathek" in url:
                    return page
                return json.dumps({"STATUS": "OK", "URL": "https://e130a.media.videokit.cloud/r/x.mp4"})

        c = Client()
        s = cc.locate_at({"speech_id": "XXVIII/NRSITZ/96#A_-_09_05_34_01016332.html"}, c)
        self.assertEqual(s[0]["media"], "https://e130a.media.videokit.cloud/r/x.mp4")
        self.assertEqual(c.calls[0], "https://www.parlament.gv.at/aktuelles/mediathek/XXVIII/NRSITZ/96")
        self.assertIn("5f4fc133-c90d-4a9c-821f-746b67fd487f", c.calls[1])
        with self.assertRaises(LookupError):                          # robots.txt: NRSITZ/19*
            cc.locate_at({"speech_id": "XXVIII/NRSITZ/195#A_-_09_05_34_01016332.html"}, c)

    def test_fr_video_page_and_listing(self):
        listing = open(os.path.join(FIX, "fr-seance-publique.html"), encoding="utf-8").read()
        links = cc.fr_video_links(listing, "2026-10-09", 1)
        self.assertEqual(len(links), 1)
        self.assertIn("1ere-seance", links[0])
        page = open(os.path.join(FIX, "fr-video-page.html"), encoding="utf-8").read()
        self.assertEqual(cc.fr_video_page(page, "CRSANR5L17S2027O1N016"),
                         "http://anorigin.vodalys.com/vod/mp4/ida/domain1/2026/10/hemi_20261009084518_1.mp4")
        self.assertIsNone(cc.fr_video_page(page, "CRSANR5L17S2027O1N017"))   # another sitting's page

    def test_fr_span_runs_past_a_heckle(self):
        timed = [("d", "a", "Mme A", "", "mot " * 213, 9639.0, 9639.0),
                 ("d", "b", "Mme B", "", "Et alors ?", 9661.72, 9661.72),
                 ("d", "a", "Mme A", "", "suite", 9706.0, 9706.0)]
        a, b = cc.fr_span(timed, 0)
        self.assertEqual(a, 9639.0)
        self.assertGreaterEqual(b, 9639.0 + 213 / 2.0 + 15.0)

    def test_be_turns_longest_first(self):
        meeting = json.load(open(os.path.join(FIX, "be-meeting-p143.json"), encoding="utf-8"))
        spans = cc.be_spans(meeting, "Patrick Prévot")
        self.assertEqual(len(spans), 2)                               # question and reply
        self.assertEqual(spans[0][0], 45 * 60 + 6)
        self.assertEqual(cc.be_spans(meeting, "Nobody Here"), [])

    def test_dd_politicians(self):
        pols = [{"id": "1", "lastName": "van der Plas", "name": "Caroline van der Plas"},
                {"id": "2", "lastName": "van den Brink", "name": "Tijs van den Brink"},
                {"id": "3", "lastName": "van den Brink", "name": "Bart van den Brink"}]
        self.assertEqual(cc.dd_politicians(pols, "Van der Plas"), {"1"})
        self.assertEqual(cc.dd_politicians(pols, "Tijs van den Brink"), {"2"})


class Render(unittest.TestCase):
    def test_caption_times_match_accented_words(self):
        heard = [("Größe", 0.0, 0.4), ("über", 0.5, 0.8), ("alles.", 0.9, 1.2), ("Société", 1.5, 2.0), ("libre.", 2.1, 2.5)]
        item = cc.caption_item("A", "B", 3.0, heard, "Grösse über alles. Société libre.", 30, 4)
        self.assertEqual([c[0] for c in item["cards"]], [["Grösse über alles."], ["Société libre."]])
        self.assertEqual([round(c[1], 1) for c in item["cards"]], [0.0, 1.5])

    def test_credit_is_added_for_the_whole_clip(self):
        from src import socialcut as sc
        ass = sc.ass_document([{"name": "A", "party": "", "duration": 4.0, "cards": []}], sc.FONT,
                              (1080, 1920), sc.CAPTION_POS, sc.CAPTION_SIZE, sc.PLATE_Y, 60)
        out = cc.with_credit(ass, "© ParlCH", 4.0, 34)
        self.assertIn("Style: Credit,", out.split("[Events]")[0])
        self.assertIn("Credit,,0,0,0,,© ParlCH", out)

    def test_purge_keeps_fresh_footage(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = os.path.join(tmp, "windows")
            os.makedirs(w)
            old, new = os.path.join(w, "old.mp4"), os.path.join(w, "new.mp4")
            for p in (old, new):
                open(p, "w").close()
            os.utime(old, (time.time() - 31 * 86400,) * 2)
            self.assertEqual(cc.purge(tmp, 30, log=lambda *_a: None), 1)
            self.assertEqual(os.listdir(w), ["new.mp4"])


class TrimOnly(unittest.TestCase):
    """France's agreement (12 October 2026): no distortion or modification.
    The tool checks every ffmpeg command and subtitle file it writes."""

    def setUp(self):
        self.fr = cc.load_sources()["fr"]
        self.ch = cc.load_sources()["ch"]

    def test_the_vertical_is_letterboxed_not_cropped(self):
        vf = cc.vertical_filter(self.fr, None)
        self.assertNotIn("crop", vf)
        self.assertEqual(cc.filter_names(vf), ["scale", "pad", "setsar", "format"])
        self.assertIn("crop=", cc.vertical_filter(self.ch, None))     # CH's terms allow cropping

    def test_trimming_and_resizing_pass(self):
        ok = [["ffmpeg", "-y", "-ss", "12.000", "-i", "w.mp4", "-t", "40.000", "-vf",
               "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
               "fps=25,format=yuv420p", "-c:a", "aac", "part.mp4"],
              ["ffmpeg", "-i", "part.mp4", "-vf", cc.vertical_filter(self.fr, None), "v.mp4"],
              ["ffmpeg", "-i", "v.mp4", "-filter_complex", "[0:v]ass=/p/x.ass:fontsdir=/p/fonts[v]",
               "-map", "[v]", "-map", "0:a", "out.mp4"]]
        for cmd in ok:
            self.assertIsNone(cc.check_trim_only_cmd(self.fr, cmd))

    def test_anything_beyond_trimming_is_refused(self):
        bad = [["ffmpeg", "-i", "a.mp4", "-vf", "setpts=0.8*PTS", "o.mp4"],                 # speed
               ["ffmpeg", "-i", "a.mp4", "-af", "atempo=1.25", "o.mp4"],                    # speed
               ["ffmpeg", "-i", "a.mp4", "-vf", "crop=608:1080:600:0,scale=1080:1920", "o.mp4"],
               ["ffmpeg", "-i", "a.mp4", "-vf", "reverse", "o.mp4"],                        # order
               ["ffmpeg", "-i", "a.mp4", "-vf", "drawtext=text=x", "o.mp4"],                # overlay
               ["ffmpeg", "-i", "a.mp4", "-i", "logo.png", "-filter_complex",
                "[1:v]scale=200:-1[lg];[0:v][lg]overlay=60:70[v]", "o.mp4"],                # logo
               ["ffmpeg", "-f", "concat", "-safe", "0", "-i", "l.txt", "-c", "copy", "r.mp4"],  # reel
               ["ffmpeg", "-itsscale", "0.9", "-i", "a.mp4", "o.mp4"]]
        for cmd in bad:
            with self.assertRaises(cc.ClipRefused, msg=" ".join(cmd)):
                cc.check_trim_only_cmd(self.fr, cmd)
        for cmd in bad:                                             # a full-edit country: unchecked
            self.assertIsNone(cc.check_trim_only_cmd(self.ch, cmd))

    def test_subtitles_carry_only_captions_and_the_exact_credit(self):
        from src import socialcut as sc
        item = {"name": "Mme X", "party": "LR", "duration": 4.0, "cards": [(["Bonjour."], 0.2, 1.0)]}
        ass = sc.ass_document([item], sc.FONT, (1080, 1920), sc.CAPTION_POS, sc.CAPTION_SIZE,
                              sc.PLATE_Y, 60)
        with self.assertRaises(cc.ClipRefused):                     # the name plate
            cc.check_trim_only_ass(self.fr, cc.with_credit(ass, self.fr["credit"], 4.0, 34))
        clean = cc.with_credit(cc.strip_plate(ass), self.fr["credit"], 4.0, 34)
        self.assertIsNone(cc.check_trim_only_ass(self.fr, clean))
        self.assertIn(",Credit,,0,0,0,,Archives audiovisuelles de l'Assemblée nationale\n", clean)
        self.assertIn("Bonjour.", clean)
        with self.assertRaises(cc.ClipRefused):                     # a different credit
            cc.check_trim_only_ass(self.fr, cc.with_credit(cc.strip_plate(ass), "© AN", 4.0, 34))


class CutPack(unittest.TestCase):
    def _pack(self, tmp, country):
        rows = [_row(422044, speaker="Jaccoud Jessica")]
        return cc.write_pack(country, rows, cc.candidates(rows), cc.load_sources()[country], top=1,
                             date="2026-09-29", out_dir=tmp)

    def test_locate_only_writes_the_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = self._pack(tmp, "ch")
            rep = cc.cut_pack(pack, locate_only=True, client=object(), log=lambda *_a: None)
            self.assertEqual(rep[0][1], "LOCATED")
            self.assertIn("simvid_1.mp4?externalid=422044", open(os.path.join(pack, "locate.md")).read())

    def test_refuses_without_agreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = self._pack(tmp, "be")
            with self.assertRaises(cc.ClipRefused):
                cc.cut_pack(pack, client=object(), log=lambda *_a: None)
        src = cc.load_sources()
        src["fr"] = dict(src["fr"], agreement=None)
        with tempfile.TemporaryDirectory() as tmp:
            pack = self._pack(tmp, "fr")
            with self.assertRaises(cc.ClipRefused):
                cc.cut_pack(pack, sources=src, client=object(), log=lambda *_a: None)

    def test_france_pack_readme_records_the_agreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = self._pack(tmp, "fr")
            readme = open(os.path.join(pack, "README.md"), encoding="utf-8").read()
            self.assertIn("Cellule GILDA", readme)
            self.assertIn("Archives audiovisuelles de l'Assemblée nationale", readme)
            self.assertIn("Do not edit these files further", readme)


class FrenchTimes(unittest.TestCase):
    XML = """<?xml version="1.0" encoding="UTF-8"?>
<compteRendu xmlns="http://schemas.assemblee-nationale.fr/referentiel">
 <metadonnees><dateSeance>20261009090000000</dateSeance><numSeanceJour>1</numSeanceJour></metadonnees>
 <contenu>
  <point nivpoint="1"><texte>Violences sexuelles</texte>
   <paragraphe id_acteur="P1"><orateurs><orateur><nom>Mme la présidente</nom></orateur></orateurs><texte stime="895.39">La seance est ouverte.</texte></paragraphe>
   <paragraphe id_acteur="P2"><orateurs><orateur><nom>Mme Agnes Firmin Le Bodo</nom></orateur></orateurs><texte stime="9639.0">Premier.</texte></paragraphe>
   <paragraphe id_acteur="P2"><orateurs><orateur><nom>Mme Agnes Firmin Le Bodo</nom></orateur></orateurs><texte stime="9650.5">Second.</texte></paragraphe>
   <paragraphe id_acteur="P3"><orateurs><orateur><nom>Mme Sarah Legrain</nom></orateur></orateurs><texte stime="9661.72">Et alors ?</texte></paragraphe>
  </point>
 </contenu>
</compteRendu>""".encode("utf-8")

    def test_timed_parse_matches_the_plain_one(self):
        import fr_chamber as fr
        date, timed = fr.parse_sitting_timed(self.XML)
        _d, plain = fr.parse_sitting(self.XML)
        self.assertEqual([t[:5] for t in timed], plain)
        self.assertEqual(date, "2026-10-09")
        self.assertEqual((timed[0][5], timed[0][6]), (9639.0, 9650.5))   # the chair left out
        self.assertEqual(fr.sitting_number_of_day(self.XML), 1)


if __name__ == "__main__":
    unittest.main()
