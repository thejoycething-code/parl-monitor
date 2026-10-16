"""Send the new country editions whose review window has ended
(src/edition_review.py, config/edition-review.yaml).

    python3 tools/edition_review.py --status     # every edition still under review
    python3 tools/edition_review.py --due        # exit 0 if one is due now, 3 if none
    python3 tools/edition_review.py --publish    # send what is due, then the Asana task
    python3 tools/edition_review.py --publish --dry-run   # render and say, send nothing

jobs/edition-publish.sh runs --due then --publish on the Mac Mini at 06:31
and 21:10 London. For each edition due (its window ended, or PUBLISH: now;
never PUBLISH: hold): the edition is rendered again from the store with the
review honoured (cuts, edits, the note) and editions/<cc>-monitor-<date>.md
is rewritten without the draft line; the DM goes to Chris alone, as the
weekly job sent it before, with a line saying what the review changed; the
window is marked sent in data/edition-reviews/<cc>-<date>.json. A DM that
fails leaves the edition unsent, and the next run tries again.

Then ONE Asana reading task per reading week for all the new-country
editions (src/edition_review.reading_week: Saturday to Friday, named for the
Monday), created by the first edition sent that week and rewritten as later
ones go out, assigned as the UK reading task is (src/publish.py). A missing
asana_pat is reported and retried at the next send. No AI, no paid service.
"""

from __future__ import annotations

import argparse
import datetime
import html
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from src import country_edition as ce  # noqa: E402
from src import edition_review as er  # noqa: E402

NAMES = {"latam": "Latam", "de": "Germany"}


def name_of(cc):
    return NAMES.get(cc) or ce.adapter(cc).name


def due(now, state_dir=None, reviews_dir=None, log=print):
    """[(state, review)] due now; logs the others."""
    out = []
    for st in er.unsent(state_dir):
        review = er.load(st["cc"], st["date"], reviews_dir)
        ok, why = er.is_due(st, review, now)
        if ok:
            out.append((st, review))
        else:
            log("  {0} {1}: {2}".format(st["cc"], st["date"], why))
    return out


def render_one(conn, st, review, editions_dir=None):
    """(edition text, DM text, edition path, (items, watched)) for one window."""
    cc, date = st["cc"], st["date"]
    if cc == "de":                         # tools/de_monitor.py renders its own (16 October 2026)
        import de_monitor
        path = os.path.join(editions_dir or os.path.join(ROOT, "editions"),
                            "de-monitor-{0}.md".format(date))
        text = de_monitor.render_edition(conn, date, review=review, write=False)
        dm = de_monitor.dm_summary(conn, date, review=review)
        items = de_monitor.review_items(conn, date)
        items = [it for it in items if not review or review.decision(
            "de|{0}|{1}".format(it["kind"], it["key"]))[0] != "cut"]
        return text, dm, path, (len(items), 0)
    if cc == er.LATAM:
        import latam_monitor
        from src import latam
        path = os.path.join(editions_dir or os.path.join(ROOT, "editions"),
                            "latam-monitor-{0}.md".format(date))
        text = latam_monitor.render_edition(conn, date, review=review)
        dm = latam_monitor.dm_summary(conn, date, path=path, review=review)
        since, until = latam_monitor.window(date)
        got = latam_monitor.gather(conn, since, until, latam.load_ledger(), review=review)
        items = [it for c in latam.COLLECTED for it in got.get(c, [])]
    else:
        country = ce.adapter(cc)
        path = ce.edition_path(cc, date, editions_dir)
        text = ce.render(conn, country, date, review=review, directory=editions_dir)
        dm = ce.dm_summary(conn, country, date, path=path, review=review,
                           directory=editions_dir)
        since, until = ce.window(cc, date, None, editions_dir, country.cadence_days)
        items = ce.gather(conn, country, since, until, review=review)
    return text, dm, path, (len(items), sum(1 for it in items if it["watched"]))


def task_line(st):
    """One <li> of the combined Asana task."""
    rel = "editions/{0}-monitor-{1}.md".format(st["cc"], st["date"])
    d = datetime.date.fromisoformat(st["date"])
    bits = ["{0} item(s) on our ground, {1} watched".format(st.get("items", 0),
                                                          st.get("watched", 0) or "none")]
    if st.get("cut") or st.get("edited"):
        bits.append("review: {0} cut, {1} edited".format(st.get("cut", 0), st.get("edited", 0)))
    else:
        bits.append("sent as drafted")
    return '<a href="{0}{1}">{2}, {3} {4}</a>: {5}'.format(
        ce.REPO, rel, html.escape(name_of(st["cc"])), d.day, er.MONTHS[d.month - 1][:3],
        html.escape("; ".join(bits)))


def asana_step(weeks, secrets, state_dir=None, transport=None, log=print):
    """Create or rewrite the combined task for each reading week touched."""
    from src import publish
    for week in sorted(weeks):
        sent = er.published_in_week(week, state_dir)
        prior = er.asana_state(week, state_dir) or {}
        due_on = (datetime.date.fromisoformat(week) + datetime.timedelta(days=4)).isoformat()
        got = publish.asana_country_reading_task(
            secrets, week, [task_line(s) for s in sent], due_on,
            task_gid=prior.get("gid"), transport=transport)
        log("asana w/c {0}: {1}".format(week, got))
        if got.get("task_gid"):
            er.save_asana_state(week, {"week": week, "gid": got["task_gid"],
                                       "permalink": got.get("permalink") or prior.get("permalink"),
                                       "editions": ["{0}-{1}".format(s["cc"], s["date"])
                                                    for s in sent]}, state_dir)


def publish_due(conn, now=None, send=None, secrets=None, dry_run=False, state_dir=None,
                reviews_dir=None, editions_dir=None, asana_transport=None, log=print):
    """Send every edition due. Returns the number sent."""
    now = now or er.now_london()
    if send is None:
        send = ce.send_dm
    weeks, n = set(), 0
    for st, review in due(now, state_dir, reviews_dir, log):
        cc, date = st["cc"], st["date"]
        try:
            text, dm, path, (n_items, n_watched) = render_one(conn, st, review, editions_dir)
        except Exception as exc:             # one country's failure never stops the rest
            log("  [gap] {0} {1}: the render failed ({2}); next run retries".format(cc, date, exc))
            continue
        if dry_run:
            log("  {0} {1}: would send ({2} items); DM:\n{3}".format(cc, date, n_items, dm))
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        result = send(dm)
        log("  {0} {1}: edition rewritten, dm: {2}".format(cc, date, result))
        if "error" in result or "skipped" in result:
            log("  [gap] {0} {1}: not marked sent; next run retries".format(cc, date))
            continue
        cut, edited = review.counts() if review else (0, 0)
        st.update(published_at=now.isoformat(timespec="seconds"),
                  message_ts=result.get("message_ts"), items=n_items, watched=n_watched,
                  cut=cut, edited=edited, note=bool(review and review.note))
        er.save_state(st, state_dir)
        weeks.add(er.reading_week(date))
        n += 1
    if weeks and not dry_run:
        if secrets is None:
            from src import publish
            secrets = publish.load_secrets()
        asana_step(weeks, secrets, state_dir, asana_transport, log)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--now", help="ISO datetime with offset, for a rehearsal (default: now)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--status", action="store_true")
    g.add_argument("--due", action="store_true")
    g.add_argument("--publish", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="with --publish: send nothing")
    args = ap.parse_args(argv)
    now = datetime.datetime.fromisoformat(args.now) if args.now else er.now_london()
    if args.status or args.due:
        got = due(now)
        for st, _ in got:
            print("  {0} {1}: due (window ended {2})".format(st["cc"], st["date"],
                                                            er.when_text(st["deadline"])))
        if args.due:
            print("edition-review: {0} edition(s) due".format(len(got)))
            return 0 if got else 3
        return 0
    conn = sqlite3.connect("file:{0}?mode=ro".format(args.db), uri=True)
    conn.row_factory = sqlite3.Row
    n = publish_due(conn, now, dry_run=args.dry_run)
    print("edition-review: {0} edition(s) sent".format(n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
