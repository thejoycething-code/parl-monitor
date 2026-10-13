"""The UN DM: first signs on our ground, then the week's open calls for input.

    python3 tools/post_un_calls.py              # send the DM (Chris only)
    python3 tools/post_un_calls.py --dry-run    # print it, send nothing
    python3 tools/post_un_calls.py --db PATH    # use (and update) a store copy
    python3 tools/post_un_calls.py --walk       # also walk the draft series

Weekly rather than monthly, unlike the UPR harvest: these carry deadlines,
and a fortnight's silence can be the difference between making a submission
and reading about one.

WHAT LEADS (13 October 2026). Anything on our ground due within 14 days,
then the FIRST SIGNS on our ground: a draft tabled, a GA plenary listed, a
PGA letter naming a date (src/un_signals.py, gathered by
tools/un_forward.collect). Added after the General Assembly adopted the
political declaration on pandemic prevention, preparedness and response on
12 October 2026 without a word from the monitor, although the PGA's letter
named the date on 7 October. Then the calls for input, as before: calls
matching our issues and anything closing inside three weeks first,
everything else open underneath (there are only ever about fifteen, and the
flag list is crude, so the full list is the backstop).

Without --db the run is stateless (the weekly workflow keeps no store): a
first sign is one tabled or announced in the last seven days, and the draft
series are not walked; only the symbols that plenary agendas and PGA letters
name are read. With --db the store says what is new and the walks resume.

The CHECK LOG ends every message: each source, read OK / read but empty /
could not read, with its newest item. A source that could not be read is
said so in the message, never left to look like a quiet week, and the run
exits 1.

To Chris alone, as a DM (CHRIS below, whatever secrets.yaml says). Never a
channel.
"""

from __future__ import annotations

import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, publish, un_signals, un_store  # noqa: E402
from src.http import HttpClient  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
from pull_un_calls import areas_for, load_un_filter  # noqa: E402

URGENT_DAYS = 21
CHRIS = "U05LJP0BT61"          # the DM goes to Chris alone


def build_message(calls, tax, wl, top=None, checks=None):
    """The DM text. `top` is un_signals.render_top's lines; `checks` the
    CheckLog. Slack mrkdwn, British spelling, no em dashes."""
    ours = [(c, areas_for(c, tax, wl)) for c in calls]
    flagged = [(c, h) for c, h in ours if h]
    urgent = [c for c in calls if c.days_left <= URGENT_DAYS]

    lines = ["*UN monitor: first signs and open consultations*", ""]
    if top:
        lines.append("```")
        lines.extend(top)
        lines.append("```")
        lines.append("")

    lines += ["*Calls for input*",
              "Written submissions the UN is currently inviting. "
              "{0} open, {1} touching our issues, {2} closing within {3} days."
              .format(len(calls), len(flagged), len(urgent), URGENT_DAYS), ""]

    if flagged:
        lines.append("*Ours*")
        for call, hits in flagged:
            lines.append("• *{0}*: closes {1} (_{2} days_)".format(
                call.title, call.deadline.strftime("%d %B %Y"), call.days_left))
            lines.append("   {0} · areas {1}".format(
                call.body, ", ".join(str(a) for a in hits)))
            lines.append("   {0}".format(call.url))
        lines.append("")

    if urgent:
        lines.append("*Closing within {0} days*".format(URGENT_DAYS))
        for call in urgent:
            lines.append("• {0}: {1} (_{2}d_)".format(
                call.title, call.deadline.strftime("%d %b"), call.days_left))
        lines.append("")

    rest = [c for c, h in ours if not h and c.days_left > URGENT_DAYS]
    if rest:
        # Listed, not hidden: the flag list is a crude word match, so the
        # unmatched remainder is where a missed call would be.
        lines.append("*Everything else open*")
        for call in rest:
            lines.append("• {0}: {1}".format(call.title, call.deadline.strftime("%d %b")))
        lines.append("")

    if checks is not None:
        lines.append("*Check log* ({0} sources, {1} could not be read)".format(
            len(checks.checks), len(checks.unread())))
        lines.append("```")
        lines.extend(checks.lines())
        lines.append("```")
        if checks.unread():
            lines.append(checks.nothing_new())
    return "\n".join(lines).rstrip()


def main():
    argv = sys.argv[1:]
    dry_run = "--dry-run" in argv
    today = datetime.date.today()
    client = HttpClient(raw_dir=os.path.join(ROOT, "data", "raw"))
    tax, wl = load_un_filter()

    import un_forward
    conn = None
    if "--db" in argv:
        conn = db.init_db(db.connect(argv[argv.index("--db") + 1]))
    got = un_forward.collect(client, today, un_forward.DEFAULT_HORIZON_DAYS, tax, wl,
                             conn=conn, walk=conn is not None or "--walk" in argv)
    new_ids = None
    if conn is not None:
        un_forward.store_drafts(conn, got.drafts_to_store,
                                un_forward.pga_letters.session_for(today), today)
        new_ids, _moved = un_store.record(conn, [un_forward.to_item(r) for r in got.rows],
                                          today=today)
        conn.close()
    top = un_signals.render_top(un_signals.due_soon(got.signals, today),
                                un_signals.first_signs(got.signals, today, new_ids=new_ids),
                                today)
    text = build_message(got.calls, tax, wl, top=top, checks=got.checks)
    if dry_run:
        print(text)
        return 1 if got.checks.unread() else 0
    secrets = publish.load_secrets()
    secrets["slack_dm_user_id"] = CHRIS       # Chris alone, whatever secrets.yaml says
    result = publish.slack_dm(secrets, text)
    print("un dm: {0}".format(result))
    return 1 if ("error" in result or got.checks.unread()) else 0


if __name__ == "__main__":
    sys.exit(main())
