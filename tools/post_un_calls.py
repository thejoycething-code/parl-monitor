"""DM the week's open OHCHR calls for input.

    python3 tools/post_un_calls.py              # send the DM
    python3 tools/post_un_calls.py --dry-run    # print it, send nothing

Weekly rather than monthly, unlike the UPR harvest: these carry deadlines,
and a fortnight's silence can be the difference between making a submission
and reading about one.

The message leads with calls matching our issues and with anything closing
inside three weeks, because that is what a reader acts on. Everything else
open is listed underneath in one line each -- there are only ever about
fifteen, and the flag list is deliberately crude, so the full list is the
backstop against a call we failed to recognise.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import publish
from src.http import FetchError, HttpClient
from src.ingest import ohchr_calls

sys.path.insert(0, os.path.join(ROOT, "tools"))
from pull_un_calls import flag_terms, matches  # noqa: E402

URGENT_DAYS = 21


def build_message(calls, terms):
    ours = [(c, matches(c, terms)) for c in calls]
    flagged = [(c, h) for c, h in ours if h]
    urgent = [c for c in calls if c.days_left <= URGENT_DAYS]

    lines = ["*UN calls for input — open consultations*", "",
             "Written submissions the UN is currently inviting. "
             "{0} open, {1} touching our issues, {2} closing within {3} days."
             .format(len(calls), len(flagged), len(urgent), URGENT_DAYS), ""]

    if flagged:
        lines.append("*Ours*")
        for call, hits in flagged:
            lines.append("• *{0}* — closes {1} (_{2} days_)".format(
                call.title, call.deadline.strftime("%d %B %Y"), call.days_left))
            lines.append("   {0} · matched: {1}".format(call.body, ", ".join(hits[:4])))
            lines.append("   {0}".format(call.url))
        lines.append("")

    if urgent:
        lines.append("*Closing within {0} days*".format(URGENT_DAYS))
        for call in urgent:
            lines.append("• {0} — {1} (_{2}d_)".format(
                call.title, call.deadline.strftime("%d %b"), call.days_left))
        lines.append("")

    rest = [c for c, h in ours if not h and c.days_left > URGENT_DAYS]
    if rest:
        # Listed, not hidden: the flag list is a crude word match, so the
        # unmatched remainder is where a missed call would be.
        lines.append("*Everything else open*")
        for call in rest:
            lines.append("• {0} — {1}".format(call.title, call.deadline.strftime("%d %b")))
    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    try:
        calls = ohchr_calls.fetch_calls(client)
    except FetchError as exc:
        print("un calls: fetch failed ({0}); nothing sent".format(exc))
        return 1
    if not calls:
        print("un calls: parsed ZERO calls -- the OHCHR listing layout has "
              "probably changed. Nothing sent, because an empty DM would read "
              "as 'nothing is open'.")
        return 1

    live = ohchr_calls.open_calls(calls)
    text = build_message(live, flag_terms())
    if dry_run:
        print(text)
        return 0
    result = publish.slack_dm(publish.load_secrets(), text)
    print("un calls: {0}".format(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
