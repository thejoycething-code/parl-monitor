"""The UN DM: first signs on our ground, then the open calls for input.

    python3 tools/post_un_calls.py              # send the DM (Chris only)
    python3 tools/post_un_calls.py --dry-run    # print it, send nothing
    python3 tools/post_un_calls.py --db PATH    # use (and update) a store copy
    python3 tools/post_un_calls.py --walk       # also walk the draft series

Every weekday (Chris, 13 October 2026; jobs/un-weekday.sh on the Mac Mini,
.github/workflows/un-calls-weekly.yml the backup), not monthly like the UPR
harvest: these carry deadlines, and first signs (a PGA letter naming a vote
date) can come only days ahead. The 12 October pandemic declaration was
announced five days before the vote.

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
said so in the message, never left to look like a quiet week.

EXIT CODES (13 October 2026, when the check went to every weekday on the Mac
Mini). 0: sent (or printed), every source read. 3: sent (or printed), but at
least one source could not be read; the message itself says so in its check
log. 1: the DM could not be sent. Kept apart because on the Mini a nonzero
exit leaves MINI_LAST unset, so GitHub's backup would send the same DM a
second time and a failure alert a third, every weekday OHCHR stays
challenged. jobs/un-weekday.sh treats 3 as delivered; the backup workflow
treats it as delivered too and says so in its log.

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
UNREAD = 3                     # exit: delivered, but a source could not be read


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

    unread = checks is not None and any(
        c.source == "OHCHR calls for input" and c.status == "could not read"
        for c in checks.checks)
    if unread:
        # Never "0 open": the listing was not read, so the number is unknown.
        lines += ["*Calls for input*",
                  "COULD NOT READ the OHCHR calls listing this run, so open calls "
                  "are unknown, not zero. See the check log.", ""]
    else:
        lines += ["*Calls for input*",
                  "Written submissions the UN is currently inviting. "
                  "{0} open, {1} touching our issues, {2} closing within {3} days."
                  .format(len(calls), len(flagged), len(urgent), URGENT_DAYS), ""]

    # Draft resolutions (13 October 2026): docs.un.org redirects to
    # documents.un.org/api/..., which robots.txt disallows. When it could not
    # be read the TEXTS of new drafts are unknown, never "no drafts". Since
    # 16 October 2026 iGov's list gives their symbols and titles.
    drafts_unread = [c for c in (checks.checks if checks is not None else [])
                     if "docs.un.org" in c.source and c.status == "could not read"]
    igov = next((c for c in (checks.checks if checks is not None else [])
                 if c.source.endswith("(iGov)")), None)
    if drafts_unread:
        why = drafts_unread[0].detail.split(":", 1)[0]
        if igov is not None and igov.status != "could not read":
            lines += ["*Draft resolutions*",
                      "Draft TEXTS could not be read ({0}); titles come from iGov's list "
                      "({1} GA plenary and Third Committee drafts), which lags, so a draft "
                      "it does not list yet is unknown, not absent. Drafts named by PGA "
                      "letters and Journal agendas are caught too.".format(why, igov.count), ""]
        else:
            lines += ["*Draft resolutions*",
                      "COULD NOT READ docs.un.org this run ({0}), so new drafts are unknown, "
                      "not zero. Drafts named by PGA letters and Journal agendas are still "
                      "caught (above, and in the check log).".format(why), ""]

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
    unread = UNREAD if got.checks.unread() else 0
    if dry_run:
        print(text)
        return unread
    secrets = publish.load_secrets()
    secrets["slack_dm_user_id"] = CHRIS       # Chris alone, whatever secrets.yaml says
    result = publish.slack_dm(secrets, text)
    print("un dm: {0}".format(result))
    if "error" in result:
        return 1
    if unread:
        print("un dm: sent, but {0} source(s) could not be read (the DM's check log "
              "names them)".format(len(got.checks.unread())))
    return unread


if __name__ == "__main__":
    sys.exit(main())
