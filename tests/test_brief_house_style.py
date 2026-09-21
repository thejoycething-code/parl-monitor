"""Christopher's refinement of the RE Core Syllabus brief (2026-08-31)
became the generator's house style. Source of truth: his edited sheet,
diffed field by field against what the generator produced.

What he changed, and where each lesson landed:
- campaign name is a headline ("Tell Paul Givan: ..."), never the official
  consultation title -> drafted campaign_name field, official title kept in
  Notes/slug/Drive name for traceability;
- addressee is one named decision-maker in formal style -> drafted field,
  deterministic fallback;
- long fields are labelled claim-colon-support points, the ask is one moral
  demand in prose -> DRAFT_SYSTEM house-style block;
- TIM row filled with related petition ids -> model picks from a WHITELIST
  built from campaign_performance (ids never composed), widened by nation
  mention because his top pick matched on geography, not area;
- sources are titled lines, no internal monitor link -> build_sources;
- delivery date is a concrete date days before the close -> delivery_date;
- Main Purposes defaults to Acquisition (his answer, 2026-08-31);
- ledger telemetry stays out of the rendered Background.
"""

import datetime
import importlib.util
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import db

import make_briefs as mb


def perf_conn(rows):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    conn.execute("CREATE TABLE campaign_performance (petition_id INTEGER, "
                 "name TEXT, areas TEXT, new_members INTEGER, "
                 "signatures INTEGER, logged_at TEXT)")
    for pid, name, areas, new_members in rows:
        conn.execute("INSERT INTO campaign_performance (petition_id, name, "
                     "areas, new_members, signatures, logged_at) "
                     "VALUES (?,?,?,?,?, '2026-08-20')",
                     (pid, name, json.dumps(areas), new_members,
                      new_members * 4))
    conn.commit()
    return conn


NI_SUBJECT = {"kind": "consultation", "areas": [6], "nation": "N. Ireland",
              "title": "Consultation on the RE Core Syllabus",
              "url": "https://x/re"}


class TimCandidateTests(unittest.TestCase):
    def test_nation_mention_widens_beyond_area_overlap(self):
        # Petition 17165 is area [8] on a subject tagged [6]; its name says
        # NI. Christopher led his TIM list with it - geography and audience
        # made it the exact match, and areas alone would have missed it.
        conn = perf_conn([
            (17165, "Protect Christian Teaching in NI Schools", [8], 29509),
            (12992, "Stop LGBT indoctrination clubs in schools", [6], 4417),
            (14001, "Defend marriage", [3], 9000)])
        got = mb.tim_candidates(conn, NI_SUBJECT)
        self.assertEqual([c["id"] for c in got], [17165, 12992])

    def test_westminster_subjects_use_area_overlap_only(self):
        conn = perf_conn([
            (17165, "Protect Christian Teaching in NI Schools", [8], 29509),
            (12992, "Stop LGBT indoctrination clubs in schools", [6], 4417)])
        subject = dict(NI_SUBJECT, nation=None)
        self.assertEqual([c["id"] for c in mb.tim_candidates(conn, subject)],
                         [12992])

    def test_the_whitelist_is_capped_and_ranked(self):
        conn = perf_conn([(9000 + i, "Education petition {0}".format(i),
                           [6], i) for i in range(20)])
        got = mb.tim_candidates(conn, dict(NI_SUBJECT, nation=None))
        self.assertEqual(len(got), 15)
        self.assertEqual(got[0]["new_members"], 19)

    def test_the_model_is_told_to_cite_only_the_whitelist(self):
        tim_q = dict(mb.NARRATIVE_FIELDS)["tim"]
        self.assertIn("tim_candidates ONLY", tim_q)
        self.assertIn("verbatim", tim_q)


class SourcesTests(unittest.TestCase):
    SOURCE = ("**Sources**\n"
              "- Consultation portal: https://x/re\n"
              "- Supreme Court judgment: https://supremecourt.uk/j.pdf\n"
              "\n**What should the image look like**\nA child.")

    def test_source_material_lines_are_copied_verbatim(self):
        got = mb.build_sources(NI_SUBJECT, self.SOURCE)
        self.assertIn("- Supreme Court judgment: https://supremecourt.uk/j.pdf",
                      got)

    def test_the_subject_url_is_not_duplicated(self):
        got = mb.build_sources(NI_SUBJECT, self.SOURCE)
        self.assertEqual(got.count("https://x/re"), 1)

    def test_without_source_material_the_subject_url_is_titled(self):
        got = mb.build_sources(NI_SUBJECT)
        self.assertEqual(got, "- Consultation on the RE Core Syllabus: "
                              "https://x/re")

    def test_the_internal_monitor_link_is_never_a_source(self):
        src = open(os.path.join(ROOT, "tools", "make_briefs.py"),
                   encoding="utf-8").read()
        self.assertNotIn("parl-monitor-partner", src)


class DeliveryDateTests(unittest.TestCase):
    def test_a_concrete_date_days_before_the_close(self):
        # Christopher set 26 September against a 30 September close.
        self.assertEqual(mb.delivery_date("2026-09-30"),
                         "2026-09-26 (close: 2026-09-30)")

    def test_an_unparseable_deadline_degrades_to_before(self):
        self.assertEqual(mb.delivery_date("late September"),
                         "Before late September")


class HouseStyleTests(unittest.TestCase):
    def test_the_system_prompt_carries_the_refinement_rules(self):
        for anchor in ("ONE memorable hook phrase",
                       "one moral demand of the named decision-maker",
                       "short assertive claim ending in a colon",
                       "silence would read as consent",
                       "never a bulleted\n  list"):
            self.assertIn(anchor, mb.DRAFT_SYSTEM)

    def test_campaign_name_and_addressee_are_drafted_fields(self):
        ids = [fid for fid, _ in mb.NARRATIVE_FIELDS]
        for fid in ("campaign_name", "addressee", "tim"):
            self.assertIn(fid, ids)

    def test_main_purposes_defaults_to_acquisition(self):
        src = open(os.path.join(ROOT, "tools", "make_briefs.py"),
                   encoding="utf-8").read()
        self.assertIn('("Main Purposes", "Acquisition")', src)
        self.assertNotIn('("Main Purposes", "Political Impact")', src)

    def test_ledger_telemetry_stays_out_of_the_background(self):
        got = mb.background(dict(NI_SUBJECT, deadline="2026-09-30", why=None,
                                 next_key_date=None),
                            {"debate": 105, "pq": 23})
        self.assertNotIn("105", got)
        self.assertNotIn("ledger", got)

    def test_the_markdown_title_is_the_campaign_name_with_the_subject_kept(self):
        fields = {"general": [], "plan": [], "prepare": [],
                  "urgency": "Non-Urgent Campaign (by default)",
                  "campaign_name": "Tell Paul Givan: keep your promise"}
        md = mb.render_markdown(NI_SUBJECT, fields, ["", "", "", "", ""],
                                [], "", [], "2026-08-31")
        self.assertIn("# Campaigns Brief (DRAFT): Tell Paul Givan: "
                      "keep your promise", md)
        self.assertIn("Subject: Consultation on the RE Core Syllabus", md)


if __name__ == "__main__":
    unittest.main()


class NarrativeDraftBudgetTests(unittest.TestCase):
    """21 Sept 2026: a 6,000-token draft was cut mid-JSON ("Unterminated string
    ... char 5186") and a brief shipped with campaigner placeholders. The
    draft now caps effort, doubles the budget, retries once on a cut, and
    refuses to parse a reply the model could not finish."""

    def _mod(self):
        spec = importlib.util.spec_from_file_location("make_briefs", os.path.join(ROOT, "tools", "make_briefs.py"))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod

    def _run(self, replies):
        mb = self._mod()
        from src import stance
        fid = mb.NARRATIVE_FIELDS[0][0]
        for r in replies:
            for b in r["content"]:
                b["text"] = b["text"].replace("why_now", fid)
        calls = []

        def fake(payload, api_key):
            calls.append(payload)
            return replies[min(len(calls) - 1, len(replies) - 1)]
        real = stance._default_transport
        stance._default_transport = fake
        try:
            out = mb.draft_narrative({"title": "T", "kind": "pq", "area_labels": ["Abortion"]}, ["fact"], "key")
        finally:
            stance._default_transport = real
        return mb, calls, out

    def test_effort_is_capped_and_the_budget_is_larger(self):
        full = {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps({"why_now": "Because."})}]}
        mb, calls, out = self._run([full])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["output_config"], {"effort": mb.NARRATIVE_EFFORT})
        self.assertGreaterEqual(calls[0]["max_tokens"], 12000)
        self.assertEqual(out.get(mb.NARRATIVE_FIELDS[0][0]), "Because.")

    def test_a_cut_reply_is_retried_with_room_not_parsed(self):
        cut = {"stop_reason": "max_tokens", "content": [{"type": "text", "text": '{"why_now": "Because the'}]}
        full = {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps({"why_now": "Because."})}]}
        mb, calls, out = self._run([cut, full])
        self.assertEqual(len(calls), 2)
        self.assertGreater(calls[1]["max_tokens"], calls[0]["max_tokens"])
        self.assertEqual(out.get(mb.NARRATIVE_FIELDS[0][0]), "Because.")

    def test_two_cuts_mean_placeholders_with_the_reason_named(self):
        cut = {"stop_reason": "max_tokens", "content": [{"type": "text", "text": '{"why_now": "Because the'}]}
        mb, calls, out = self._run([cut, cut])
        self.assertEqual(len(calls), 2)
        self.assertIsNone(out, "the caller stubs; the truncated text is never parsed as a brief")


class NarrativeEnvelopeTests(unittest.TestCase):
    """21 Sept 2026: the Good Relations draft put "good relations" in quotation
    marks inside a JSON string, the string ended early, the parse failed, and
    all twelve prose fields shipped to Drive as campaigner placeholders under
    an Asana review task that looked finished. Prose is not JSON-shaped."""

    def _mod(self):
        spec = importlib.util.spec_from_file_location("make_briefs", os.path.join(ROOT, "tools", "make_briefs.py"))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod

    def test_quotes_apostrophes_and_blank_lines_survive(self):
        mb = self._mod()
        reply = (
            "@@campaign_name@@\n"
            "Tell The Executive Office: Don't Let 'Good Relations' Become A Licence To Silence\n"
            "\n"
            "@@ask@@\n"
            'Write protection into the framework, so that "good relations" cannot become\n'
            "a licence to silence the people it claims to protect.\n"
            "\n"
            "Second paragraph, with a comma, a colon: and \\ a backslash.\n")
        out = mb.parse_narrative(reply, [f for f, _ in mb.NARRATIVE_FIELDS])
        self.assertEqual(out["campaign_name"],
                         "Tell The Executive Office: Don't Let 'Good Relations' Become A Licence To Silence")
        self.assertIn('"good relations" cannot become', out["ask"])
        self.assertIn("Second paragraph", out["ask"], "a blank line does not end a field")
        self.assertEqual(len(out), 2, "only the fields present come back")

    def test_the_exact_reply_that_broke_the_json_parse(self):
        mb = self._mod()
        prose = ('Write explicit protection into the heart of this framework, not as an '
                 'afterthought but as its founding principle, so that "good relations" cannot '
                 'become a licence to silence the very people it claims to protect.')
        out = mb.parse_narrative("@@ask@@\n" + prose, ["ask"])
        self.assertEqual(out["ask"], prose)
        self.assertEqual(json.loads(json.dumps({"ask": prose}))["ask"], prose,
                         "the prose is fine; it was the envelope that broke")

    def test_unknown_and_empty_fields_are_dropped(self):
        mb = self._mod()
        out = mb.parse_narrative("@@ask@@\nReal.\n@@not_a_field@@\nJunk.\n@@urgency@@\n\n", ["ask", "urgency"])
        self.assertEqual(out, {"ask": "Real."})

    def test_a_json_reply_still_parses_as_a_fallback(self):
        mb = self._mod()
        out = mb.parse_narrative(json.dumps({"ask": "Old shape.", "nope": "x"}), ["ask"])
        self.assertEqual(out, {"ask": "Old shape."})
        fenced = "```json\n" + json.dumps({"ask": "Fenced."}) + "\n```"
        self.assertEqual(mb.parse_narrative(fenced, ["ask"]), {"ask": "Fenced."})

    def test_an_unparsable_reply_is_empty_not_half_read(self):
        mb = self._mod()
        self.assertEqual(mb.parse_narrative('{"ask": "he said "no" to it"}', ["ask"]), {})
        self.assertEqual(mb.parse_narrative("", ["ask"]), {})

    def test_the_prompt_asks_for_markers_and_not_json(self):
        mb = self._mod()
        self.assertIn("@@campaign_name@@", mb.DRAFT_SYSTEM)
        self.assertIn("Do NOT use JSON", mb.DRAFT_SYSTEM)
        self.assertIn("nothing in the prose needs escaping", mb.DRAFT_SYSTEM)

    def test_a_failed_draft_is_named_on_the_sheet(self):
        mb = self._mod()
        self.assertIn("NARRATIVE DRAFT FAILED", mb.DRAFT_FAILED_NOTE)
        self.assertIn("--force {0}", mb.DRAFT_FAILED_NOTE)
        src = open(os.path.join(ROOT, "tools", "make_briefs.py"), encoding="utf-8").read()
        self.assertIn('print("  narrative draft failed for {0}', src,
                      "the relay needs the slug and a trigger word")


class RegenerationKeepsItsPlaceTests(unittest.TestCase):
    def test_force_reuses_the_review_task_and_the_drive_file(self):
        src = open(os.path.join(ROOT, "tools", "make_briefs.py"), encoding="utf-8").read()
        self.assertIn("SELECT asana_gid, drive_file_id FROM brief_log", src)
        self.assertIn("keeping the existing review task", src)
        self.assertIn("drive_file_id) VALUES (?, ?, ?, ?, ?, ?, ?)", src,
                      "the row must carry the drive id forward, not null it")


class ForceSlugResolutionTests(unittest.TestCase):
    """21 Sept 2026: a regeneration pass asked for a slug rebuilt from the
    title, which is longer than the 60-character one brief_log holds. The tool
    printed the subject list and exited 0, so the brief was silently skipped."""

    def _mod(self):
        spec = importlib.util.spec_from_file_location("make_briefs", os.path.join(ROOT, "tools", "make_briefs.py"))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod

    SUBS = [{"slug": "bill-infants-parents-and-carers-bill"},
            {"slug": "consultation-a-new-good-relations-framework-call-for-views"}]
    LOGGED = ["pq-pq-hl3338-lords-gender-dysphoria-health-services-answered-20",
              "pq-pq-hl3337-lords-gender-dysphoria-health-services-answered-20",
              "bill-infants-parents-and-carers-bill"]

    def test_an_exact_slug_resolves_to_itself(self):
        mb = self._mod()
        got, err = mb.resolve_slug("bill-infants-parents-and-carers-bill", self.SUBS, self.LOGGED)
        self.assertEqual((got, err), ("bill-infants-parents-and-carers-bill", None))

    def test_a_slug_rebuilt_from_the_title_resolves_to_the_stored_one(self):
        """The real failure: the log truncates, so what was typed is LONGER."""
        mb = self._mod()
        got, err = mb.resolve_slug(
            "pq-pq-hl3338-lords-gender-dysphoria-health-services-answered-2026-09-17",
            self.SUBS, ["pq-pq-hl3338-lords-gender-dysphoria-health-services-answered-20"])
        self.assertIsNone(err)
        self.assertEqual(got, "pq-pq-hl3338-lords-gender-dysphoria-health-services-answered-20")

    def test_a_shortened_slug_resolves_when_it_is_unique(self):
        mb = self._mod()
        got, err = mb.resolve_slug("consultation-a-new-good", self.SUBS, self.LOGGED)
        self.assertEqual(got, "consultation-a-new-good-relations-framework-call-for-views")
        self.assertIsNone(err)

    def test_an_ambiguous_slug_is_refused_and_lists_the_candidates(self):
        mb = self._mod()
        got, err = mb.resolve_slug("pq-pq-hl333", self.SUBS, self.LOGGED)
        self.assertIsNone(got)
        self.assertIn("ambiguous", err)
        self.assertIn("hl3337", err)
        self.assertIn("hl3338", err)

    def test_an_unknown_slug_is_refused_and_says_why(self):
        mb = self._mod()
        got, err = mb.resolve_slug("made-up", self.SUBS, self.LOGGED)
        self.assertIsNone(got)
        self.assertIn("no brief matches", err)
        self.assertIn("60 characters", err, "the cap is the reason a rebuilt slug misses")

    def test_a_bad_slug_exits_non_zero(self):
        """'nothing new' and 'no such brief' must not look the same."""
        src = open(os.path.join(ROOT, "tools", "make_briefs.py"), encoding="utf-8").read()
        self.assertIn("force, why_not = resolve_slug(force, subs, done)", src)
        self.assertIn("is not a current brief subject", src)
