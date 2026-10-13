"""Backtest: would the new UN sources have caught the 12 October 2026 vote?

    python3 tools/un_backtest.py              # 5 to 12 October 2026, day by day

On 12 October 2026 the General Assembly voted on the political declaration
on pandemic prevention, preparedness and response (A/81/L.6, agenda item 129,
18th plenary). The monitor said nothing. This replays the archived responses
in tests/fixtures/un/ (fetched 13 October 2026 through src/http.py) as each
day before the vote would have seen them, through the same code the forward
look and the UN DM use (src/un_signals.py), and prints the block that would
have led the output.

What each day could see is decided by each item's OWN date, never by
hindsight:
  * the draft, from its date line ("5 October 2026");
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
    """(letters, plenaries, drafts) from the fixtures, classified."""
    tax, wl = un_filter()
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
    drafts = []
    for symbol, name in (("A/81/L.6", "a-81-l-6-page1.txt"), ("A/81/L.3", "a-81-l-3-page1.txt")):
        d = un_docs.parse_draft(symbol, fixture_text(name))
        drafts.append(un_signals.DraftInfo(
            symbol=symbol, title=d.topic or "", dated=un_signals.parse_un_date(d.dated or ""),
            areas=filt.filter_item(tax, wl, d.classify_on).issue_areas,
            url=un_docs.doc_url(symbol), agenda_item=d.agenda_item))
    return letters, plenaries, drafts


def as_of(day, letters, plenaries, drafts):
    """(due_soon, first_signs) as `day` would have seen them (stateless)."""
    tax, wl = un_filter()
    visible = [m for m in plenaries if (listed_from(m) or day) <= day]
    signals = un_signals.build_signals(letters, visible, drafts, tax, wl, as_of=day)
    return un_signals.due_soon(signals, day), un_signals.first_signs(signals, day)


def main():
    letters, plenaries, drafts = load()
    day = datetime.date(2026, 10, 5)
    while day < VOTE:
        due, first = as_of(day, letters, plenaries, drafts)
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
