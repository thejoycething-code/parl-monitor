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

## 5. Consultations and calls for evidence

| Consultation / call for evidence | Closes |
|---|---|
| **Evidence** [Immigration scrutiny](https://example.gov.uk/j). JCHR. | Tue 1 Sep · 29 days |
| **Evidence** [Mid-band thing](https://example.gov.uk/m). Soonish. | Tue 18 Aug · 15 days |
| **Consultation** [Weddings reform](https://example.gov.uk/x). Campaign live under Zuzana; response push through recess. | Thu 24 Sep · 52 days |
| **Consultation** [Urgent thing](https://example.gov.uk/u). Closing fast. | Fri 7 Aug · 4 days |

- **Secondary legislation:** CWSA regs approved 369 to 102 on 8 July.

## 7. Consultations extra

- **[ACT]** [OSA push.](https://example.gov.uk/z) (Deadline: 2026-09-07; Owner: Zuzana)

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
        self.assertIn("(Deadline: 2026-09-07)", self.out)
        self.assertIn("Thu 24 Sep", self.out)

    def test_owner_names_scrubbed_from_prose(self):
        self.assertNotIn("Zuzana", self.out)
        self.assertNotIn("Christopher", self.out)
        self.assertIn("Campaign live under the team", self.out)

    def test_prose_names_scrub_without_owner_fields(self):
        # The deadline table prints no Owner fields, so names must come from
        # the store scrub list, not from parsing the page.
        md = "# T\n### W\n\n| A | Closes |\n|---|---|\n| **Consultation** [X](https://x). Campaign live under Zuzana. | Fri 4 Sep \u00b7 32 days |\n"
        out = partner.redact(md, extra_names=["Zuzana"])
        self.assertNotIn("Zuzana", out)
        self.assertIn("under the team", out)

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

    def test_deadline_table_chips_and_urgency_bands(self):
        html = partner.to_html(partner.redact(EDITION), "t")
        self.assertIn('<span class="kind evidence">EVIDENCE</span>', html)
        self.assertIn('<span class="kind consult">CONSULTATION</span>', html)
        # bands: red <=8, amber <=21, grey beyond
        self.assertIn('<span class="due soon">Fri 7 Aug', html)      # 4 days
        self.assertIn('<span class="due mid">Tue 18 Aug', html)      # 15 days
        self.assertIn('<span class="due far">Tue 1 Sep', html)       # 29 days: grey at the &le;21 band
        self.assertIn('<span class="due far">Thu 24 Sep', html)

    def test_procedure_chip_carries_hover_explanation(self):
        md = ("| Instrument | Procedure | Status |\n|---|---|---|\n"
              "| [X](https://x) | Draft affirmative | Laid 2026-05-20 |")
        html = partner.to_html(md, "t")
        self.assertIn('class="proc" title="Laid as a draft: it cannot become law', html)
        self.assertIn(">Draft affirmative</span>", html)

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
