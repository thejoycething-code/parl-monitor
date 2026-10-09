#!/usr/bin/env python3
"""Instant Latam alerts: a short Slack DM to Chris when a watched or tier-1
item lands, between the monthly editions.

    python3 tools/latam_alerts.py --country co            # print what would be sent
    python3 tools/latam_alerts.py --country co --send     # send, and record it
    python3 tools/latam_alerts.py --send                  # every Latam country

Chris, 10 October 2026 (docs/country-decisions-2026-10-10.md, "Edition
structure"): one monthly Latam edition, "and instant alerts for watched or
tier-1 items". Each country's weekly job runs this for its own country right
after its collector (jobs/<cc>-weekly.sh, on the Mini and on GitHub alike);
the monthly job runs it for Venezuela and Nicaragua after their checks.

WHAT ALERTS. From the same reader as the edition (src/latam.py), over the
last --days (default 14, so Guatemala's fortnightly pull is covered):

  * any item whose key is on the country's watchlist (config/watchlist-<cc>.yaml),
    of any kind: a new bill, a vote, an agenda listing, a register update;
  * any tier-1 item (the shared taxonomy-es's tier 1, through the
    collector's filter): a new bill, a vote, a committee report, a pedido, a
    press item, a gazette notice, a law. A tier-1 bill merely re-stamped on
    its register (Bolivia's "updated") does not alert unless watched;
  * a watched item whose status changed since the last pass, even in a
    country whose store keeps no change dates (Colombia, Chile, Peru...):
    the ledger remembers each watched item's last status. That move is
    also what the edition's "stage move" lines read for those countries.

DE-DUPLICATED. data/latam-alerts/<cc>.json records every alert sent, keyed
on country, kind and item key (and the status, for a move), so a Mini run
and its GitHub backup, or two runs a week apart, never send the same thing
twice. One file per country: two countries' jobs never edit the same file.

FIRST RUN SEEDS. The first pass for a country records everything currently
on the list and sends nothing, so switching alerts on never floods Chris
with the backlog; a seeded pass says so in its log.

AT MOST --max (default 8) DMs a run; the rest go in one closing DM that
counts them and points to the coming edition.

The DM goes to Chris alone (U05LJP0BT61), whatever config/secrets.yaml
names. Without --send nothing is sent or recorded. Read-only on the store.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import db, latam  # noqa: E402

CHRIS = "U05LJP0BT61"
DEFAULT_DAYS = 14
DEFAULT_MAX = 8
KEEP_MOVES = 400
KEEP_SENT_DAYS = 400


# --- the ledger -------------------------------------------------------------------

def ledger_path(cc, directory=None):
    return os.path.join(directory or latam.LEDGER_DIR, "{0}.json".format(cc))


def load(cc, directory=None):
    path = ledger_path(cc, directory)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh) or {}
    else:
        got = {}
    got.setdefault("cc", cc)
    got.setdefault("seeded", None)
    got.setdefault("sent", {})
    got.setdefault("status", {})
    got.setdefault("moves", [])
    return got


def save(ledger, today, directory=None):
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=KEEP_SENT_DAYS)).isoformat()
    ledger["sent"] = {k: v for k, v in ledger["sent"].items() if v >= cutoff}
    ledger["moves"] = ledger["moves"][-KEEP_MOVES:]
    path = ledger_path(ledger["cc"], directory)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def alert_key(it):
    key = "{0}|{1}|{2}".format(it["cc"], it["kind"], it["key"])
    if it["kind"] in ("moved", "updated"):
        key += "|" + (it["status"] or "")
    return key


# --- what alerts ------------------------------------------------------------------

def qualifies(it):
    if it["watched"]:
        return True
    return it["tier"] == 1 and it["kind"] != "updated"


def status_moves(conn, cc, ledger, today, config_dir=None):
    """Watched items whose status differs from the ledger's; updates the
    ledger's statuses and moves in place. Returns move items."""
    out = []
    for key, (status, title, url, areas) in sorted(latam.watched_status(conn, cc, config_dir).items()):
        prev = ledger["status"].get(key)
        ledger["status"][key] = status
        if prev is None or prev == status:
            continue
        move = {"date": today, "cc": cc, "key": key, "old": prev, "new": status,
                "title": title, "url": url, "areas": areas}
        ledger["moves"].append(move)
        out.append(latam.item(cc, "moved", key, today, title, areas, 1, True,
                              "{0} → {1}".format(prev, status), url))
    return out


def candidates(conn, cc, today, days, ledger, config_dir=None):
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()
    # ledger=None: the edition's ledger-derived moves are not news to the alerts.
    items = [it for it in latam.country_items(conn, cc, since, today, None, config_dir)
             if qualifies(it)]
    moves = status_moves(conn, cc, ledger, today, config_dir)
    if cc not in latam.SOURCE_MOVES:
        items += moves          # the source's own moves already came through above
    return latam.score(items)


def message(it):
    """One short DM, mrkdwn."""
    name = latam.NAMES.get(it["cc"], it["cc"])
    flags = ", ".join(x for x in ("watched" if it["watched"] else "",
                                  "tier 1" if it["tier"] == 1 else "") if x)
    lines = [":rotating_light: *Latam alert, {0}*: {1}{2}".format(
        name, latam.KINDS.get(it["kind"], it["kind"]).lower(), " ({0})".format(flags) if flags else ""),
        "_{0}_".format(latam.clip(it["title"], 240) or "(no title published)"),
        "{0} · {1} · {2}".format(latam.clip(it["key"], 60), it["date"] or "?",
                                           latam.area_text(it["areas"]) or "watched")]
    if it["status"]:
        lines.append("{0}: “{1}”".format("Moved" if it["kind"] == "moved" else "Status",
                                                  latam.clip(it["status"], 200)))
    lines += [latam.clean(x) for x in it["lines"][:2]]
    if it["url"]:
        lines.append(it["url"])
    return "\n".join(lines)


def send_dm(text):
    from src import publish
    secrets = publish.load_secrets()
    secrets["slack_dm_user_id"] = CHRIS          # Chris alone
    return publish.slack_dm(secrets, text)


def run(conn, countries, today, days=DEFAULT_DAYS, send=False, max_dms=DEFAULT_MAX,
        sender=None, directory=None, config_dir=None, log=print):
    """One pass. Returns the list of (country, alert key, text) sent (or that
    would be, without send)."""
    sender = sender or send_dm
    out, budget, overflow = [], max_dms, 0
    for cc in countries:
        ledger = load(cc, directory)
        items = candidates(conn, cc, today, days, ledger, config_dir)
        fresh = [it for it in items if alert_key(it) not in ledger["sent"]]
        if not ledger["seeded"]:
            for it in items:
                ledger["sent"][alert_key(it)] = today
            ledger["seeded"] = today
            log("latam-alerts: {0} seeded with {1} item(s); nothing sent on a first pass".format(
                cc, len(items)))
            if send:
                save(ledger, today, directory)
            continue
        for it in fresh:
            key, text = alert_key(it), message(it)
            if budget <= 0:
                overflow += 1
                if send:
                    ledger["sent"][key] = today
                continue
            budget -= 1
            if send:
                res = sender(text)
                if isinstance(res, dict) and res.get("error"):
                    log("  [gap] latam-alerts: {0} not sent: {1}".format(key, res["error"]))
                    continue
                ledger["sent"][key] = today
            out.append((cc, key, text))
            log("latam-alerts: {0} {1}".format("sent" if send else "would send", key))
        if send:
            save(ledger, today, directory)
        log("latam-alerts: {0}: {1} candidate(s), {2} new".format(cc, len(items), len(fresh)))
    if overflow:
        text = (":rotating_light: *Latam alerts*: {0} more watched or tier-1 item(s) landed this "
                "run; they are in the next monthly edition.".format(overflow))
        if send:
            sender(text)
        out.append(("", "overflow", text))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--country", action="append", help="a Latam country code (repeatable); default all")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--max", type=int, default=DEFAULT_MAX)
    ap.add_argument("--send", action="store_true", help="send the DMs and record them")
    args = ap.parse_args()
    known = list(latam.COLLECTED) + ["ve", "nic"]
    countries = args.country or known
    bad = [c for c in countries if c not in known]
    if bad:
        ap.error("not a Latam country with a store: {0}".format(", ".join(bad)))
    conn = db.connect(args.db)
    conn.row_factory = sqlite3.Row
    sent = run(conn, countries, args.date, args.days, args.send, args.max)
    if not args.send:
        for _, _, text in sent:
            print("---\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
