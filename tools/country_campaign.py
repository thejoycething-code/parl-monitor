#!/usr/bin/env python3
"""Campaign targets and outcomes for the new countries (src/country_campaign.py).

    python3 tools/country_campaign.py open --cc pl 1 pl-abortion-2026 [--chamber sejm]
                                           [--label "..."] [--petition 17165 ...]
    python3 tools/country_campaign.py targets --cc pl pl-abortion-2026
    python3 tools/country_campaign.py members --cc pl Adamska
    python3 tools/country_campaign.py add --cc pl pl-abortion-2026 10/1 10/3 --by Christopher
                                          [--reason "..."]
    python3 tools/country_campaign.py drop --cc pl pl-abortion-2026 10/3
    python3 tools/country_campaign.py find --cc pl "przerywaniu ciąży"
    python3 tools/country_campaign.py outcome --cc pl pl-abortion-2026 pl-10-15-9 --our-side no
                                              [--by Christopher]
    python3 tools/country_campaign.py score --cc pl pl-abortion-2026 [--csv]
    python3 tools/country_campaign.py performance --cc pl [pl-abortion-2026]
    python3 tools/country_campaign.py list [--cc pl]

The country version of tools/ca_campaign.py (UK). `open` snapshots the 5CA
placements on an area from CONFIRMED stance readings only
(config/<cc>_stance.yaml); before sign-off every member sits at 0 and the
campaign is marked "awaiting sign-off". `targets` suggests targets from
confirmed placements only (+, - and mixed records); members who voted on
votes not yet confirmed are listed by their record as "not a target until
the stance is confirmed". `add` records a person's choice of target (--by).
`find` searches the store's divisions for the outcome vote; `outcome`
records it with OUR side (yes or no, as the chamber records it), refusing a
side that contradicts a confirmed reading; `score` reports what members did.
`performance` joins the petition numbers from data/looker/<cc>_campaigns.tsv
and says plainly when a country has none (only the UK has them today).

Manual only: no scheduled job. Reads the store read-only (--db, default
data/parl-monitor.db); writes data/campaigns/<cc>/<slug>.json and, with
--csv, data/5ca/<cc>-5ca-evaluate-<slug>-<date>.csv. Fetches and posts
nothing. Countries: {countries}.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import country_campaign as cc_  # noqa: E402
from src import readings5ca as r5  # noqa: E402

__doc__ = __doc__.format(countries=", ".join(c5.COUNTRIES))


def _store(args):
    if not os.path.exists(args.db):
        raise SystemExit("no store at {0} (pass --db)".format(args.db))
    return c5.connect_ro(args.db)


def _camp(args):
    camp = cc_.load_campaign(args.cc, args.slug, args.campaign_dir)
    if camp is None:
        raise SystemExit("no {0} campaign called {1!r}; open one first".format(args.cc, args.slug))
    return camp


def show_targets(args, conn, camp, out=print):
    rows, ready = cc_.placements(conn, args.cc, camp["chamber"], camp["area"], args.config_dir,
                                 args.today)
    out(cc_.state_line(args.cc, camp["chamber"], camp["area"], ready))
    sugg = cc_.suggested_targets(rows)
    chosen = {t["member_id"] for t in camp["targets"]}
    if ready["placing"]:
        out("\nSuggested targets, from CONFIRMED readings only ({0}):".format(len(sugg)))
        for r in sugg[:args.limit]:
            out("  {0} {1:52} {2:2}  {3}  [{4}]".format(
                "*" if r["person_id"] in chosen else " ", r5.clip(r["decision_maker"], 52),
                r["column"], r["why"], r["person_id"]))
        if len(sugg) > args.limit:
            out("  ...and {0} more (--limit N)".format(len(sugg) - args.limit))
        if not sugg:
            out("  none: the confirmed readings place no one at + or -, and no record is mixed")
    else:
        out("\nSuggested targets: none. No target is suggested until a reading is confirmed.")
    cands, pending = cc_.candidates(conn, args.cc, camp["chamber"], camp["area"], args.config_dir)
    placed = {r["person_id"] for r in rows if r["column"] != "0"}
    cands = [c for c in cands if c["member_id"] not in placed]
    if cands:
        out("\nCandidates by vote record ({0} members, on {1} vote(s) {2}). Each is {3}; the "
            "record says how they voted, not which side is ours:".format(
                len(cands), pending, cc_.AWAITING, cc_.NOT_A_TARGET.upper()))
        for c in cands[:args.limit]:
            spec = c5.SPECS[args.cc]
            out("  {0:40} {1:12} {2} {3}, {4} {5}, abstain {6}{7}  [{8}] -- {9}".format(
                r5.clip(c["name"], 40), r5.clip(c["party"] or "?", 12), spec.labels[0], c["yea"],
                spec.labels[1], c["nay"], c["abstain"],
                "  [DERIVED, X5]" if c["derived"] else "", c["member_id"], cc_.NOT_A_TARGET))
        if len(cands) > args.limit:
            out("  ...and {0} more (--limit N)".format(len(cands) - args.limit))
    elif not ready["placing"]:
        out("\nNo candidates by vote record: no member position is stored for the area's "
            "unconfirmed votes.")
    if camp["targets"]:
        out("\nChosen targets ({0}):".format(len(camp["targets"])))
        for t in camp["targets"]:
            out("  {0:40} {1:12} {2}  ({3}, {4})  [{5}]".format(
                r5.clip(t["name"], 40), r5.clip(t["party"], 12), t["basis"], t["added_by"],
                t["added_on"], t["member_id"]))


def cmd_open(args):
    conn = _store(args)
    try:
        camp = cc_.open_campaign(conn, args.cc, args.area, args.slug, args.label, args.chamber,
                                 args.petition, args.config_dir, args.campaign_dir, args.today)
    except ValueError as exc:
        raise SystemExit(str(exc))
    counts = cc_.column_counts(camp["snapshot"])
    print("opened '{0}' ({1}): {2} sitting members snapshotted on {3}".format(
        camp["slug"], camp["label"], len(camp["snapshot"]), camp["snapshot_on"]))
    print("  " + "  ".join("{0} x{1}".format(c, counts[c]) for c in r5.COLUMNS if c in counts))
    print(cc_.state_line(args.cc, camp["chamber"], camp["area"], camp["readings"]))
    if camp["state"] == cc_.AWAITING:
        print("This snapshot is no prediction. Open the same slug again once a reading is "
              "confirmed (tools/country_5ca.py --cc {0} --confirm KEY --by NAME).".format(args.cc))
    print("\nNext: tools/country_campaign.py targets --cc {0} {1}".format(args.cc, camp["slug"]))
    conn.close()
    return 0


def cmd_targets(args):
    conn = _store(args)
    show_targets(args, conn, _camp(args))
    conn.close()
    return 0


def cmd_members(args):
    conn = _store(args)
    got = cc_.find_members(conn, args.cc, " ".join(args.term), args.chamber)
    if not got:
        print("no member matching {0!r}".format(" ".join(args.term)))
        return 1
    for m in got[:40]:
        print("  [{0}] {1} ({2}), {3}{4}".format(m["member_id"], m["name"], m.get("party") or "?",
                                                 m.get("chamber"), "" if m.get("sitting") else
                                                 " [FORMER]"))
    conn.close()
    return 0


def cmd_add(args):
    conn = _store(args)
    camp = _camp(args)
    try:
        added, refused = cc_.add_targets(camp, conn, args.member, args.by, args.reason,
                                         args.config_dir, args.today, args.campaign_dir)
    except ValueError as exc:
        raise SystemExit(str(exc))
    for t in added:
        print("  added {0} ({1}): {2}".format(t["name"], t["member_id"], t["basis"]))
    for mid, why in refused:
        print("  refused {0}: {1}".format(mid, why))
    conn.close()
    return 0 if added or not refused else 1


def cmd_drop(args):
    n = cc_.drop_targets(_camp(args), args.member, args.campaign_dir)
    print("dropped {0} target(s)".format(n))
    return 0


def cmd_find(args):
    conn = _store(args)
    got = cc_.find_divisions(conn, args.cc, " ".join(args.term), args.config_dir)
    if not got:
        print("no division in the {0} store matching {1!r}".format(args.cc, " ".join(args.term)))
        return 1
    for r, st in got:
        print("  {0}  {1}  {2:10} {3}\n      {4}".format(
            r["key"], r.get("date"), str(r.get("chamber")), r5.clip(r.get("question"), 80), st))
    print("\nThe id is the first column. Record it with: outcome --cc {0} SLUG KEY "
          "--our-side yes|no".format(args.cc))
    conn.close()
    return 0


def cmd_outcome(args):
    conn = _store(args)
    camp = _camp(args)
    try:
        o = cc_.record_outcome(camp, conn, args.key, args.our_side, args.by, args.config_dir,
                               args.today, args.campaign_dir)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print("recorded for '{0}': {1} ({2}), our side = {3} ({4}); {5}".format(
        camp["slug"], r5.clip(o["title"], 70), o["date"], o["our_side"].upper(), o["label"],
        o["basis"]))
    conn.close()
    return 0


def cmd_score(args):
    conn = _store(args)
    camp = _camp(args)
    result = cc_.score(camp, conn)
    print(cc_.score_text(camp, result))
    if args.csv and result["rows"]:
        print("\nEvaluate sheet: {0}".format(cc_.write_score_csv(camp, result, args.out_dir,
                                                                 args.today)))
    conn.close()
    return 0


def cmd_performance(args):
    camp = _camp(args) if args.slug else None
    conn = c5.connect_ro(args.db) if camp is not None and os.path.exists(args.db) else None
    status, lines = cc_.performance(args.cc, camp, conn, args.looker_dir)
    print("\n".join(lines))
    if conn is not None:
        conn.close()
    return 0


def cmd_list(args):
    camps = cc_.list_campaigns(args.cc, args.campaign_dir)
    if not camps:
        print("no campaigns opened yet")
    for c in camps:
        print("  {0} {1:26} {2:34} {3:20} opened {4}; {5} targets, {6} outcome(s)".format(
            c["cc"], c["slug"], r5.clip(c["label"], 34), c["state"], c["opened"],
            len(c["targets"]), len(c["outcomes"])))
    return 0


def parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    common.add_argument("--config-dir", default=None, help=argparse.SUPPRESS)
    common.add_argument("--campaign-dir", default=None, help=argparse.SUPPRESS)
    common.add_argument("--looker-dir", default=None, help=argparse.SUPPRESS)
    common.add_argument("--out-dir", default=None, help=argparse.SUPPRESS)
    common.add_argument("--today", default=None, help="ISO date (default today)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, slug=True, cc_required=True):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("--cc", required=cc_required, choices=c5.COUNTRIES)
        if slug:
            p.add_argument("slug")
        p.set_defaults(fn=fn)
        return p

    p = sub.add_parser("open", parents=[common])
    p.add_argument("--cc", required=True, choices=c5.COUNTRIES)
    p.add_argument("area", type=int)
    p.add_argument("slug")
    p.add_argument("--label")
    p.add_argument("--chamber")
    p.add_argument("--petition", action="append", default=[], help="a petition id (repeatable)")
    p.set_defaults(fn=cmd_open)
    p = add("targets", cmd_targets)
    p.add_argument("--limit", type=int, default=40)
    p = add("members", cmd_members, slug=False)
    p.add_argument("term", nargs="+")
    p.add_argument("--chamber")
    p = add("add", cmd_add)
    p.add_argument("member", nargs="+")
    p.add_argument("--by", required=True)
    p.add_argument("--reason")
    p = add("drop", cmd_drop)
    p.add_argument("member", nargs="+")
    p = add("find", cmd_find, slug=False)
    p.add_argument("term", nargs="+")
    p = add("outcome", cmd_outcome)
    p.add_argument("key")
    p.add_argument("--our-side", required=True, choices=("yes", "no"))
    p.add_argument("--by")
    p = add("score", cmd_score)
    p.add_argument("--csv", action="store_true")
    p = sub.add_parser("performance", parents=[common])
    p.add_argument("--cc", required=True, choices=c5.COUNTRIES)
    p.add_argument("slug", nargs="?")
    p.set_defaults(fn=cmd_performance)
    add("list", cmd_list, slug=False, cc_required=False)
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
