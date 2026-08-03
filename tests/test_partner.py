"""Partner edition redaction: names out, tags kept, internal machinery dropped."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import partner

EDITION = """# Parliamentary Monitor
### Week commencing Monday 2026-08-10 | Edition 2

## 1. Top lines

- **[NOTE]** Recess: neither House sits this week. Deadlines still apply.

## 2. Active bills board

| Bill | Why we track it | House and stage | Next key date | What happens next | Areas | Movement |
|---|---|---|---|---|---|---|
| [A Bill](https://bills.parliament.uk/bills/1) | Our priority | Commons, 2nd reading | 2026-09-11 | Awaiting 2nd reading | Assisted dying | NEW |

## 6. Committee corner

- **[ACT]** [OSA inquiry, evidence closes 2026-09-07.](https://committees.parliament.uk/work/9955/) (Deadline: 2026-09-07; Owner: Christopher)

## 7. Consultations and secondary legislation

- **[ACT]** [Weddings reform closes 24 September. Campaign live under Zuzana; response push through recess.](https://example.gov.uk/x) (Deadline: 2026-09-24; Owner: Zuzana)
- **[NOTE]** [Foster care standards rewrite.](https://example.gov.uk/y) (Deadline: 2026-09-16)

## 11. MP intelligence notes

- **[NOTE]** Somebody (Party, Seat) said something. Profile updated; 5CA input flagged.

---
**Coverage gaps this edition:**
- pq: a term failed after retries.
"""


class RedactTests(unittest.TestCase):
    def setUp(self):
        self.out = partner.redact(EDITION)

    def test_owner_fields_stripped_but_tags_and_deadlines_kept(self):
        self.assertNotIn("Owner:", self.out)
        self.assertIn("**[ACT]**", self.out)
        self.assertIn("(Deadline: 2026-09-24)", self.out)
        self.assertIn("(Deadline: 2026-09-07)", self.out)

    def test_owner_names_scrubbed_from_prose(self):
        self.assertNotIn("Zuzana", self.out)
        self.assertNotIn("Christopher", self.out)
        self.assertIn("Campaign live under the team", self.out)

    def test_mp_intelligence_section_dropped(self):
        self.assertNotIn("MP intelligence", self.out)
        self.assertNotIn("5CA", self.out)

    def test_banner_and_gaps_footer_present(self):
        self.assertIn("Coalition partner edition", self.out)
        self.assertIn("Coverage gaps this edition", self.out)


class SiteTests(unittest.TestCase):
    def test_html_renders_table_links_and_auth_scaffold(self):
        html = partner.to_html(partner.redact(EDITION), "Test title")
        self.assertIn("<table>", html)
        self.assertIn('<a href="https://bills.parliament.uk/bills/1">A Bill</a>', html)
        s = html
        self.assertIn('<span class="tag act">ACT</span>', html)
        self.assertIn("Roboto", html)
        self.assertIn("#4285f4", html)
        self.assertIn("noindex", html)

    def test_link_text_containing_brackets_parses(self):
        # "Complications from Abortions (Annual Report) Bill [HL]" broke the
        # first regex: nested ] in link text rendered as raw markdown.
        md = "| [A Bill [HL]](https://bills.parliament.uk/bills/4144) | x |\n|---|---|\n| y | z |"
        html = partner.to_html(md, "t")
        self.assertIn('<a href="https://bills.parliament.uk/bills/4144">A Bill [HL]</a>', html)
        self.assertNotIn("](https", html)

    def test_build_site_writes_index_archive_and_middleware(self):
        tmp = tempfile.mkdtemp()
        partner.build_site(tmp, "2026-08-10", partner.redact(EDITION), ["2026-08-10", "2026-08-03"])
        self.assertTrue(os.path.exists(os.path.join(tmp, "index.html")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "archive", "2026-08-10.html")))
        middleware = open(os.path.join(tmp, "middleware.js")).read()
        self.assertIn("PARTNER_PASSPHRASE", middleware)
        self.assertIn("401", middleware)
        index = open(os.path.join(tmp, "index.html")).read()
        self.assertIn('href="/archive/2026-08-03.html"', index)


if __name__ == "__main__":
    unittest.main()
