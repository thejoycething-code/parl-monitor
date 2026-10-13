"""Backtest: would the new UN sources have caught the 12 October 2026 vote?

    python3 tools/un_backtest.py              # 5 to 12 October 2026, day by day

On 12 October 2026 the General Assembly voted on the political declaration
on pandemic prevention, preparedness and response (A/81/L.6, agenda item 129,
18th plenary). The monitor said nothing. This replays the archived responses
in tests/fixtures/un/ (fetched 13 October 2026 through src/http.py) as each
day before the vote would have seen them, through the same code the forward
look and the UN DM use (src/un_signals.py), and prints the block that would
have led the output.

THE ROUTE, since 13 October 2026. The draft's own PDF is no longer read:
docs.un.org/<symbol>?direct=true redirects to documents.un.org/api/symbol/
access, which documents.un.org/robots.txt disallows, and the HTTP client now
refuses that hop (src/http.py). So the replay no longer reads the draft's
first page (tests/fixtures/un/a-81-l-6-page1.txt stays, for the parser's own
tests, but it is not a route the monitor has any more). A draft is known
only when something the monitor CAN read names it: a PGA letter ("to be
annexed to draft resolution A/81/L.6") or a Journal agenda ("Item 129: Draft
resolution (A/81/L.6)"), through src/un_signals.drafts_named, exactly as
tools/un_forward.py does when docs.un.org is refused. The informal
consultations in the same Journal payload are replayed too (none of them is
on our ground). Result: A/81/L.6 surfaces on 7 October (the letter), not 5
October; nothing on 5 and 6 October.

What each day could see is decided by each item's OWN date, never by
hindsight:
  * a draft, from the date it was NAMED (the letter's or the listing's);
  * a consultation, from its own meeting date (conservative: the Journal
    lists it some days ahead);
  * the PGA letter, from its date on the letters listing (7 October 2026);
  * the plenary listing, from the latest PGA letter its Journal programme
    notes cite ("Letters from the President of the General Assembly, dated
    6 October 2026, 7 October 2026 and 8 October 2026"): the listing in its
    archived form cannot predate the last letter it names, so it counts from
    8 October. That is conservative: an earlier version of the entry may have
    been up sooner, but nothing archived shows it.
tests/test_un_backtest.py holds this as a regression test.
"""

from __future__ import annotations

import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import filter as filt, un_signals  # noqa: E402
from src.ingest import pga_letters, un_calendar, un_docs  # noqa: E402
from tests.un_fixtures import fixture_json, fixture_text, un_filter  # noqa: E402

VOTE = datetime.date(2026, 10, 12)


def listed_from(meeting):
    """The earliest day the archived Journal entry could have existed: the
    latest PGA letter date its programme notes cite (see the docstring)."""
    dates = [un_signals.parse_un_date(m) for m in
             re.findall(r"\d{1,2} [A-Z][a-z]+ 20\d\d", meeting.programme or "")]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def load():
    """(letters, plenaries, consultations) from the fixtures."""
    letters = pga_letters.parse_letters(fixture_text("pga-letters-81.html.gz"))
    for letter in letters:
        if letter.url.endswith("letter-pandemic-prevention-declaration-7-october-2026/"):
            letter.body = pga_letters.parse_letter_body(
                fixture_text("pga-letter-pandemic-7oct.html.gz"))
            pga_letters.annotate(letter)
    plenaries = un_calendar.parse_ga_plenaries(fixture_json("journal-ga-2026-10-01.json"))
    details = {"f0bd129c-9251-4047-b00c-cccb49848b30": "journal-meeting-18th-plenary.json",
               "22a390a9": "journal-meeting-19th-plenary.json"}
    for m in plenaries:
        for key, name in details.items():
            if m.id.startswith(key):
                m.agenda, m.programme, m.symbols = un_calendar.parse_meeting_detail(fixture_json(name))
    consultations = un_calendar.parse_ga_consultations(fixture_json("journal-ga-2026-10-01.json"))
    return letters, plenaries, consultations


def drafts_as_of(day, letters, plenaries):
    """The drafts `day` could know of: named by a letter dated by then or a
    listing visible by then (docs.un.org's PDFs are not read; see above)."""
    tax, wl = un_filter()
    seen = [l for l in letters if l.dated <= day]
    visible = [m for m in plenaries if (listed_from(m) or day) <= day]
    return un_signals.drafts_named(seen, visible, tax, wl, meeting_date=listed_from,
                                   doc_url=un_docs.doc_url)


def as_of(day, letters, plenaries, consultations=()):
    """(due_soon, first_signs) as `day` would have seen them (stateless)."""
    tax, wl = un_filter()
    visible = [m for m in plenaries if (listed_from(m) or day) <= day]
    drafts = drafts_as_of(day, letters, plenaries)
    held = [c for c in consultations if c.starts.date() <= day]
    signals = un_signals.build_signals(letters, visible, drafts, tax, wl, as_of=day,
                                       consultations=held)
    return un_signals.due_soon(signals, day), un_signals.first_signs(signals, day)


def main():
    letters, plenaries, consultations = load()
    day = datetime.date(2026, 10, 5)
    while day < VOTE:
        due, first = as_of(day, letters, plenaries, consultations)
        left = (VOTE - day).days
        print("=== as of {0} ({1} day{2} before the vote) ===".format(
            day.strftime("%a %d %B %Y"), left, "" if left == 1 else "s"))
        for line in un_signals.render_top(due, first, day):
            print(line)
        print()
        day += datetime.timedelta(days=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
