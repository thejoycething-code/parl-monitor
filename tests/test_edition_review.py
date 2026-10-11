"""The review window for the new country editions (11 October 2026;
src/edition_review.py, tools/edition_review.py, config/edition-review.yaml):
the review file and its merge-preserving rewrite, the edition honouring it,
the held DM, the publish at the window's end, the ONE combined Asana task a
week, and the Mini wiring. Fixture store, fake Slack and Asana: no network."""

import datetime
import os
import plistlib
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_edition as ce, edition_review as er  # noqa: E402
import coverage  # noqa: E402
import edition_review as tool  # noqa: E402
import test_country_edition as tce  # noqa: E402

TODAY = tce.TODAY            # 2026-10-09, a Friday
QUESTION = "at|question|XXVIII/J/1"


def slurp(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def london(text):
    return datetime.datetime.fromisoformat(text).astimezone(er._tz())


class SettingsTests(unittest.TestCase):
    def test_defaults_on_for_own_editions_and_latam_only(self):
        cfg = er.load_config()
        for cc in er.CCS:
            self.assertTrue(er.enabled(cc, cfg), cc)
        for cc in ("uk", "de", "us", "ie", "au", "ca", "co"):
            self.assertFalse(er.enabled(cc, cfg), cc)
        self.assertEqual(set((cfg.get("countries") or {})), set(er.CCS))

    def test_window_is_the_next_morning_0630_london(self):
        d = er.deadline("at", "2026-10-10", {})                  # a Saturday weekly
        self.assertEqual((d.date().isoformat(), d.hour, d.minute), ("2026-10-11", 6, 30))
        self.assertEqual(d.utcoffset(), datetime.timedelta(hours=1))    # BST
        d = er.deadline("at", "2026-11-07", {})
        self.assertEqual(d.utcoffset(), datetime.timedelta(0))          # GMT
        cfg = {"countries": {"nl": {"publish_at": "18:30", "after_days": 0}}}
        d = er.deadline("nl", "2026-10-15", cfg)
        self.assertEqual((d.date().isoformat(), d.hour), ("2026-10-15", 18))
        self.assertFalse(er.enabled("nl", {"countries": {"nl": {"review": False}}}))

    def test_reading_week_saturday_to_friday(self):
        for d in ("2026-10-10", "2026-10-11", "2026-10-13", "2026-10-14", "2026-10-15",
                  "2026-10-16"):
            self.assertEqual(er.reading_week(d), "2026-10-12", d)
        self.assertEqual(er.reading_week("2026-10-17"), "2026-10-19")

    def test_parse_is_forgiving(self):
        rv = er.parse("PUBLISH: Hold\nNOTE: hi\n---\n### item: a\nDECISION: Cut\nTAKEAWAY:\n"
                      "### item: b\nDECISION: keep\nTAKEAWAY: New line.\n"
                      "### item: c\nDECISION: edit\nTAKEAWAY:\n### item: d\nDECISION: what\n")
        self.assertEqual((rv.publish, rv.note), ("hold", "hi"))
        self.assertEqual(rv.decision("a")[0], "cut")
        self.assertEqual(rv.decision("b"), ("edit", "New line."))   # a takeaway is an edit
        self.assertEqual(rv.decision("c")[0], "keep")               # an empty edit is a keep
        self.assertEqual(rv.decision("d")[0], "keep")
        self.assertEqual(rv.counts(), (1, 1))


class ReviewTests(tce.AustriaTests):
    def setUp(self):
        super().setUp()
        self.rev = os.path.join(self.tmp, "reviews")
        self.state = os.path.join(self.tmp, "state")
        self.country = ce.adapter("at")
        self.deadline = er.deadline("at", TODAY, {}).isoformat(timespec="minutes")

    def write_review(self):
        got = ce.gather(self.conn, self.country, tce.SINCE, TODAY, self.cfg)
        return er.write("at", TODAY, "Austria", got, ce.review_entry, self.deadline, self.rev)

    def edit(self, fn):
        path = er.review_path("at", TODAY, self.rev)
        text = fn(slurp(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def cut_question_and_note(self, text):
        text = text.replace("NOTE: \n", "NOTE: Check the Sterbeverfügung date.\n", 1)
        i = text.index("### item: " + QUESTION)
        return text[:i] + text[i:].replace("DECISION: keep", "DECISION: cut", 1)

    def test_review_file_lists_each_entry_with_keep(self):
        path, n = self.write_review()
        text = slurp(path)
        self.assertEqual(os.path.basename(path), "at-review-2026-10-09.md")
        self.assertEqual(n, 4)       # the floor vote (one entry), the amendment, the move, the question
        self.assertIn("### item: " + QUESTION, text)
        self.assertIn("PUBLISH: go", text)
        self.assertIn("06:30 London on Saturday 10 October 2026", text)
        self.assertEqual(len(re.findall(r"^DECISION: keep$", text, re.M)), 4)
        self.assertNotIn("—", text)          # no em dashes

    def test_no_review_renders_exactly_as_before(self):
        plain = self.render(self.country, self.conn)
        self.assertEqual(plain, self.render(self.country, self.conn, review=er.Review()))
        self.assertNotIn("Draft under review", plain)

    def test_edition_and_dm_honour_cut_edit_and_note(self):
        self.write_review()
        self.edit(self.cut_question_and_note)
        rv = er.load("at", TODAY, self.rev)
        text = self.render(self.country, self.conn, review=rv, draft_until=self.deadline)
        self.assertIn("Draft under review: sent to Chris by DM at 06:30 London", text)
        self.assertIn("**Note from the review:** Check the Sterbeverfügung date.", text)
        self.assertNotIn("Anfrage zum Schwangerschaftsabbruch", text)
        self.assertIn("1 item cut in review", text)
        dm = ce.dm_summary(self.conn, self.country, TODAY, tce.SINCE, config_dir=self.cfg,
                           directory=self.eds, review=rv)
        self.assertIn("_Reviewed: 1 cut, a note added._", dm)
        self.assertNotIn("Anfrage", dm)

    def test_edit_replaces_the_takeaway(self):
        self.write_review()

        def edit_vote(text):
            i = text.index("### item: at|vote-group|XXVIII/I/525")
            return text[:i] + text[i:].replace("TAKEAWAY: ", "TAKEAWAY: Our reading, not the source's.", 1)
        self.edit(edit_vote)
        rv = er.load("at", TODAY, self.rev)
        self.assertEqual(rv.counts(), (0, 1))
        self.assertIn("Our reading, not the source's.",
                      self.render(self.country, self.conn, review=rv))

    def test_rewrite_keeps_decisions_and_items_that_left(self):
        self.write_review()
        self.edit(self.cut_question_and_note)
        self.edit(lambda t: t.replace("PUBLISH: go", "PUBLISH: hold"))
        self.write_review()                                  # a rerun the same day
        text = slurp(er.review_path("at", TODAY, self.rev))
        self.assertIn("PUBLISH: hold", text)
        self.assertIn("NOTE: Check the Sterbeverfügung date.", text)
        self.assertEqual(len(re.findall(r"^DECISION: cut$", text, re.M)), 1)
        self.conn.execute("DELETE FROM at_items WHERE item_key='XXVIII/J/1'")
        self.write_review()                                  # the cut item has gone
        text = slurp(er.review_path("at", TODAY, self.rev))
        self.assertIn("## Decisions for items no longer in this edition", text)
        self.assertEqual(er.load("at", TODAY, self.rev).decision(QUESTION)[0], "cut")


class PublishTests(ReviewTests):
    """tools/edition_review.py --publish against the fixture, with the real
    config (the fixture's watchlist is the real one)."""

    def setUp(self):
        super().setUp()
        self.sent, self.asana = [], []
        self.saved = (er.REVIEWS, er.STATE)
        er.REVIEWS, er.STATE = self.rev, self.state
        er.open_window("at", TODAY, {}, now=london("2026-10-09T03:10+01:00"))
        self.write_review()

    def tearDown(self):
        er.REVIEWS, er.STATE = self.saved
        super().tearDown()

    def send(self, text):
        self.sent.append(text)
        return {"channel": "U", "message_ts": "1.{0}".format(len(self.sent))}

    def transport(self, url, payload, headers):
        self.asana.append((url, payload, headers.get("X-Method")))
        return {"data": {"gid": "77", "permalink_url": "https://app.asana.com/0/77"}}

    def publish(self, now):
        return tool.publish_due(self.conn, london(now), send=self.send,
                                secrets={"asana_pat": "2/x"}, editions_dir=self.eds,
                                asana_transport=self.transport, log=lambda *a: None)

    def test_nothing_before_the_window_ends(self):
        self.assertEqual(self.publish("2026-10-10T06:29+01:00"), 0)
        self.assertEqual((self.sent, self.asana), ([], []))
        self.assertEqual(er.pending("at", TODAY), self.deadline)

    def test_unedited_goes_out_unchanged_at_the_window_end(self):
        self.assertEqual(self.publish("2026-10-10T06:31+01:00"), 1)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Review window ended with no changes", self.sent[0])
        self.assertIn("Anfrage zum Schwangerschaftsabbruch", self.sent[0] + slurp(
            ce.edition_path("at", TODAY, self.eds)))
        edition = slurp(ce.edition_path("at", TODAY, self.eds))
        self.assertNotIn("Draft under review", edition)
        st = er.state("at", TODAY)
        self.assertTrue(st["published_at"])
        self.assertIsNone(er.pending("at", TODAY))
        self.assertEqual(self.publish("2026-10-10T18:31+01:00"), 0)   # never twice
        # The combined Asana task, assigned as the UK one is.
        url, payload, method = self.asana[0]
        self.assertTrue(url.endswith("/tasks"))
        self.assertEqual(payload["data"]["assignee"], "me")
        self.assertEqual(payload["data"]["name"], "Read the country editions - w/c 2026-10-05")
        self.assertIn("Austria, 9 Oct", payload["data"]["html_notes"])

    def test_cut_is_honoured_and_one_task_for_the_week(self):
        self.edit(self.cut_question_and_note)
        self.publish("2026-10-10T06:31+01:00")
        self.assertNotIn("Anfrage", self.sent[0])
        self.assertNotIn("Anfrage zum Schwangerschaftsabbruch",
                         slurp(ce.edition_path("at", TODAY, self.eds)))
        # A second edition of the same reading week rewrites the same task.
        er.open_window("latam", "2026-10-08", {}, now=london("2026-10-08T13:15+01:00"))
        self.saved_render = tool.render_one
        tool.render_one = lambda conn, st, rv, d=None: ("# Latam", "Latam DM",
                                                       os.path.join(self.eds, "latam.md"), (3, 1))
        try:
            self.publish("2026-10-10T06:35+01:00")
        finally:
            tool.render_one = self.saved_render
        self.assertEqual([a[2] for a in self.asana], [None, "PUT"])
        self.assertTrue(self.asana[1][0].endswith("/tasks/77"))
        notes = self.asana[1][1]["data"]["html_notes"]
        self.assertIn("Latam, 8 Oct", notes)
        self.assertIn("Austria, 9 Oct", notes)
        self.assertIn("review: 1 cut, 0 edited", notes)
        self.assertEqual(er.asana_state("2026-10-05")["editions"], ["latam-2026-10-08",
                                                                    "at-2026-10-09"])

    def test_hold_and_now(self):
        self.edit(lambda t: t.replace("PUBLISH: go", "PUBLISH: hold"))
        self.assertEqual(self.publish("2026-10-12T06:31+01:00"), 0)
        self.edit(lambda t: t.replace("PUBLISH: hold", "PUBLISH: now"))
        self.assertEqual(self.publish("2026-10-09T18:31+01:00"), 1)   # before the window ends

    def test_a_failed_dm_is_retried(self):
        self.send = lambda text: {"error": "chat.postMessage failed"}
        self.assertEqual(self.publish("2026-10-10T06:31+01:00"), 0)
        self.assertTrue(er.pending("at", TODAY))
        self.assertEqual(self.asana, [])


class MainHoldsTheDmTests(tce.AustriaTests):
    """tools/<cc>_monitor.py --edition --dm with the review on writes the
    draft and the review file and sends nothing; --no-review sends."""

    def setUp(self):
        super().setUp()
        self.db = os.path.join(self.tmp, "store.db")
        disk = sqlite3.connect(self.db)
        self.conn.commit()
        self.conn.backup(disk)
        disk.close()
        self.saved = (er.REVIEWS, er.STATE, ce.EDITIONS, ce.send_dm)
        er.REVIEWS = os.path.join(self.tmp, "reviews")
        er.STATE = os.path.join(self.tmp, "state")
        ce.EDITIONS = self.eds
        self.sent = []
        ce.send_dm = lambda text: self.sent.append(text) or {"message_ts": "1"}

    def tearDown(self):
        er.REVIEWS, er.STATE, ce.EDITIONS, ce.send_dm = self.saved
        super().tearDown()

    def test_dm_is_held_for_review(self):
        ce.main("at", ["--db", self.db, "--date", TODAY, "--edition", "--dm"])
        self.assertEqual(self.sent, [])
        self.assertIn("Draft under review", slurp(ce.edition_path("at", TODAY, self.eds)))
        self.assertTrue(os.path.exists(er.review_path("at", TODAY)))
        self.assertTrue(er.pending("at", TODAY))
        ce.main("at", ["--db", self.db, "--date", TODAY, "--edition"])   # the rerun
        self.assertEqual(self.sent, [])

    def test_no_review_sends_at_once(self):
        ce.main("at", ["--db", self.db, "--date", TODAY, "--edition", "--dm", "--no-review"])
        self.assertEqual(len(self.sent), 1)
        self.assertIsNone(er.state("at", TODAY))


class WiringTests(unittest.TestCase):
    OWN = ("es", "it", "fr", "nl", "be", "at", "ch", "pl", "pt", "hr", "sk", "hu", "br", "ar")

    def test_weeklies_commit_their_reviews(self):
        for cc in self.OWN:
            job = slurp(os.path.join(ROOT, "jobs", cc + "-weekly.sh"))
            line = re.search(r"^# mini_run: commit (.*)$", job, re.M).group(1).split()
            self.assertIn("reviews", line, cc)
        for cc in self.OWN + ("mx",):
            wf = slurp(os.path.join(ROOT, ".github", "workflows", cc + "-weekly.yml"))
            self.assertIn("reviews/", wf, cc)
        self.assertIn("reviews", slurp(os.path.join(ROOT, "jobs", "latam-monthly.sh")))
        self.assertIn("reviews/", slurp(os.path.join(ROOT, ".github", "workflows",
                                                     "latam-monthly.yml")))

    def test_publish_job_plist_install_and_coverage(self):
        job = slurp(os.path.join(ROOT, "jobs", "edition-publish.sh"))
        self.assertIn("# mini_run: no-store", job)
        self.assertIn("# mini_run: commit editions", job)
        self.assertLess(job.index("--due"), job.index("db_state.py --pull"))
        self.assertNotIn("db_state.py --push", job)
        with open(os.path.join(ROOT, "ops", "launchd",
                               "net.citizengo.parlmonitor.edition-publish.plist"), "rb") as fh:
            plist = plistlib.load(fh)
        self.assertEqual(sorted((s["Hour"], s["Minute"]) for s in plist["StartCalendarInterval"]),
                         [(6, 31), (18, 31)])
        self.assertTrue(all("Weekday" not in s for s in plist["StartCalendarInterval"]))
        self.assertIn("edition-publish", slurp(os.path.join(ROOT, "ops",
                                                            "install_country_jobs.sh")))
        self.assertIn("Edition publish", coverage.ON_DEMAND)

    def test_vote_briefs_and_alerts_stay_immediate(self):
        for cc in self.OWN:
            job = slurp(os.path.join(ROOT, "jobs", cc + "-weekly.sh"))
            for m in re.finditer(r"^\s*python3 tools/country_vote_briefs\.py.*$", job, re.M):
                self.assertIn("--send", m.group(0), cc)
        self.assertIn("latam_alerts.py --country ve --country nic --send",
                      slurp(os.path.join(ROOT, "jobs", "latam-monthly.sh")))


if __name__ == "__main__":
    unittest.main()
