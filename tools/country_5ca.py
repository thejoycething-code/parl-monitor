#!/usr/bin/env python3
"""5CA with stance sign-off for the new country editions (src/country5ca.py).

    python3 tools/country_5ca.py --all-countries --prune-off-ground --draft --resync-directions \
        --fill-directions --auto-confirm --signoff-doc --sheets --shortlist              # the weekly step
    python3 tools/country_5ca.py --all-countries --auto-confirm --dry-run   # what would be confirmed
    python3 tools/country_5ca.py --cc pl --amend pl-10-1-31 --yea 1 --nay -1 --by "Christopher Joyce" --why "..."
    python3 tools/country_5ca.py --cc pl --amend pl-10-1-31 --take-out --by "Christopher Joyce" --why "..."
    python3 tools/country_5ca.py --cc pl --shortlist [--top 20]   # docs/5ca-pl-shortlist.md
    python3 tools/country_5ca.py --cc pl --draft             # append drafts for new votes
    python3 tools/country_5ca.py --cc pl --signoff-doc       # rewrite docs/5ca-pl-readings.md
    python3 tools/country_5ca.py --cc pl --sign-from-doc --by Christopher
    python3 tools/country_5ca.py --cc pl --confirm pl-10-58-62 --by Christopher [--on 2026-10-10]
    python3 tools/country_5ca.py --cc pl --sheets            # data/5ca/pl-5ca-*.csv (confirmed only)
    python3 tools/country_5ca.py --cc pl --confirm-direction 10/2110 --by Christopher
    python3 tools/country_5ca.py --all-countries --counts
    python3 tools/country_5ca.py --cc fr --prune-out-of-scope [--dry-run]   # no country has a scope now
    python3 tools/country_5ca.py --apply-amendments decisions.json [--dry-run]
    python3 tools/country_5ca.py --all-countries --accept-flagged-amendments --by "Christopher Joyce" [--dry-run]
    python3 tools/country_5ca.py --cc ch --prune-off-ground [--dry-run] --signoff-doc --shortlist
    python3 tools/country_5ca.py --cc pl --draft --db /path/to/store.db
    python3 tools/country_5ca.py --draft --db-map stores.txt # "cc path" per line (initial drafts)

Reads the store only, read-only; fetches nothing, posts nothing. Drafting is
by rules (no AI call). Nothing it does confirms a reading: only --confirm and
--sign-from-doc do, and both need a named person (--by), who must be Chris or
listed for that country in config/stance_signers.yaml. --confirm-direction
signs a bill's direction (`bill_directions`) the same way; the campaign briefs
(tools/country_briefs.py) take their ask from it only once it is confirmed.

--shortlist (11 October 2026, src/shortlist5ca.py) ranks the readings still
waiting so a signer starts with the ones that matter most (decisive votes on
watched bills, close margins, split groups, a meaning line ready, campaigns
and briefs, recent first; procedural, near-unanimous and amendment votes
sink) and writes docs/5ca-<cc>-shortlist.md with each item's reasons, meaning
line, proposed values and the exact command to sign it. It confirms nothing.

--prune-out-of-scope removes the entries outside a country's sign-off scope
that are unsigned and untouched; a confirmed or hand-edited entry is always
kept and reported. No country has a scope since 12 October 2026 (France's
limit to final votes, motions to reject and watched amendments was lifted:
Chris, "score all amendments and reverse France's decision"), and no prune
ever removes an amendment or article entry.

--apply-amendments FILE (12 October 2026) applies readers' amendment
decisions: a JSON list (or {{"decisions": [...]}}) of objects
    {{"cc": "fr", "key": "an-17-1234", "direction": "with|against|unclear|not_scored",
     "why": "...", "source": "https://... the text read", "flag": "",
     "yes_adopts": true}}
`direction` says whether ADOPTING the amendment (or article) is with or
against CitizenGO; `yes_adopts` (optional, default true) is false only where
a Yes does not adopt it. with/against (why and source required) records
`amendment_direction` etc. and drafts the values by the rules; a `flag`
blocks the automatic sign-off. unclear leaves the entry needs_reading with
the flag shown in the guide. not_scored makes it `placeable: false` with the
reason. Confirmed, amended and hand-valued entries, and entries that are not
amendment votes, are refused with the reason. --fill-directions also drafts
any untouched needs_reading amendment entry given an `amendment_direction`
by hand.

--accept-flagged-amendments (12 October 2026, Chris: "Accept all as
drafted") accepts every with/against amendment reading that carries an
`amendment_flag` and the rules' own values, unconfirmed and not amended: the
flag is removed so --auto-confirm can confirm it, and kept on the entry as
`amendment_accepted: "<by>, <date>: accepted as drafted (was flagged: ...)"`.
Unclear and not-scored readings, bill flags and anything a person confirmed
or amended are left alone. --by must be a signer for the country.

--prune-off-ground (11 October 2026) removes the unsigned, untouched entries
whose vote the store no longer holds on our ground (neither watched nor tier
1 with an area): what a reclassification leaves behind, as Switzerland's IVG
guard did. It reads the store; a vote the store lacks is never pruned, and a
confirmed or hand-edited entry is always kept and reported.

--auto-confirm (11 October 2026, Chris: "Automate the checks and we'll make
it so teams can amend as and when errors come up. Like we're doing with
Canada.") confirms each DRAFT reading that passes every deterministic check
(src/country5ca.py, auto_check: drafted and untouched, a settled bill
direction, a final vote or motion to reject (or an amendment with a reader's
unflagged reading, its why and source recorded), values equal to the rules', a
recorded tally that splits members, inside the sign-off scope), stamped
`confirmed_by: "{auto_by}"`, the date and the checks' version. The rest stay
drafts, listed with the check they failed in the guide and the shortlist.
With --dry-run it writes nothing and reports the counts. --resync-directions
first brings untouched drafts into line with a bill direction a person has
changed (or put on hold). --amend lets a country signer change any reading
(values, or --take-out for `draft: true`), stamped amended_by / amended_on /
amended_why; an amended reading is never touched by the automation again.

--fill-directions (12 October 2026) drafts the untouched final, reject and
inverted votes left `needs_reading` because "no bill direction is on file"
once their bill has a with/against direction (src/country5ca.py,
fill_directions): the drafter never rewrites an entry and the resync only
touches drafts, so without it they waited for a person forever. Anything a
person touched is left alone. It runs before --auto-confirm. It also redrafts
the drafts the resync turned into `needs_reading` when their bill went on hold
("The direction of <bill> is on hold: ...") once that bill is with/against
again; a bill still held stays needs_reading.

Readings whose areas are all excluded from the 5CA (config/stance_overrides.yaml
`excluded_from_5ca`, migration) place nobody, so they are never counted as
waiting, checked, shortlisted or put in the digest (12 October 2026).

Countries: {countries}.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import country5ca as c5  # noqa: E402
from src import shortlist5ca as sl  # noqa: E402

__doc__ = __doc__.format(countries=", ".join(c5.COUNTRIES), auto_by=c5.AUTO_BY)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cc", action="append", default=[], help="country code (repeatable)")
    ap.add_argument("--all-countries", action="store_true")
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--db-map", help="file of 'cc path' lines: a store per country")
    ap.add_argument("--draft", action="store_true", help="append drafts for new qualifying votes")
    ap.add_argument("--signoff-doc", action="store_true", help="rewrite docs/5ca-<cc>-readings.md")
    ap.add_argument("--sheets", action="store_true", help="write the 5CA sheets (confirmed only)")
    ap.add_argument("--counts", action="store_true")
    ap.add_argument("--shortlist", action="store_true",
                    help="write docs/5ca-<cc>-shortlist.md: what to sign first (confirms nothing)")
    ap.add_argument("--top", type=int, default=sl.TOP, help="items in the shortlist (default %(default)s)")
    ap.add_argument("--prune-out-of-scope", action="store_true",
                    help="remove unsigned, untouched entries outside the sign-off scope")
    ap.add_argument("--prune-off-ground", action="store_true",
                    help="remove unsigned, untouched entries whose vote is no longer on our ground")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --prune-out-of-scope, --prune-off-ground, --resync-directions, "
                         "--fill-directions, --accept-flagged-amendments or --auto-confirm: write nothing")
    ap.add_argument("--resync-directions", action="store_true",
                    help="bring untouched drafts into line with a changed bill direction")
    ap.add_argument("--fill-directions", action="store_true",
                    help="draft untouched needs_reading votes whose bill now has a direction")
    ap.add_argument("--apply-amendments", metavar="FILE",
                    help="apply a JSON file of amendment decisions (with/against/unclear/not_scored)")
    ap.add_argument("--accept-flagged-amendments", action="store_true",
                    help="accept flagged with/against amendment readings as drafted (needs --by)")
    ap.add_argument("--auto-confirm", action="store_true",
                    help="confirm drafts that pass every check, on Chris's delegation")
    ap.add_argument("--amend", metavar="KEY", help="a signer's amendment of one reading")
    ap.add_argument("--yea", type=int, help="with --amend: the stance of a Yes (-2..2)")
    ap.add_argument("--nay", type=int, help="with --amend: the stance of a No (-2..2)")
    ap.add_argument("--why", help="with --amend: what was wrong")
    ap.add_argument("--take-out", action="store_true",
                    help="with --amend: put `draft: true` (out of play) instead of values")
    ap.add_argument("--confirm", nargs="+", metavar="KEY")
    ap.add_argument("--confirm-direction", nargs="+", metavar="BILL",
                    help="confirm bill_directions entries (the campaign briefs' ask follows them)")
    ap.add_argument("--sign-from-doc", action="store_true")
    ap.add_argument("--by", help="the named person confirming")
    ap.add_argument("--on", help="the date of the confirmation (default today)")
    ap.add_argument("--today", help="ISO date stamped on drafts (default today)")
    ap.add_argument("--out-dir", default=c5.OUT_DIR)
    args = ap.parse_args(argv)

    if args.apply_amendments:
        got = c5.apply_amendments(c5.read_decisions(args.apply_amendments), today=args.today,
                                  dry_run=args.dry_run)
        return 1 if got["refused"] else 0

    ccs = list(c5.COUNTRIES) if args.all_countries else []
    for c in args.cc:
        ccs += [x.strip() for x in c.split(",") if x.strip()]
    stores = {}
    if args.db_map:
        with open(args.db_map, encoding="utf-8") as h:
            for line in h:
                bits = line.split()
                if len(bits) == 2 and not line.startswith("#"):
                    stores[bits[0]] = bits[1]
        if not ccs:
            ccs = [cc for cc in c5.COUNTRIES if cc in stores]
    bad = [cc for cc in ccs if cc not in c5.SPECS]
    if bad:
        ap.error("unknown country: {0} (have {1})".format(", ".join(bad), ", ".join(c5.COUNTRIES)))
    if not ccs:
        ap.error("--cc CC, --all-countries or --db-map")
    if (args.confirm or args.sign_from_doc or args.confirm_direction or args.amend) and len(ccs) != 1:
        ap.error("confirm one country at a time")
    if args.accept_flagged_amendments:
        total = 0
        for cc in ccs:
            if os.path.exists(c5.stance_path(cc)):
                total += len(c5.accept_flagged_amendments(cc, args.by, args.on, dry_run=args.dry_run))
        print("Flagged amendment readings {0} as drafted: {1}".format(
            "that would be accepted" if args.dry_run else "accepted", total))
        return 0
    if args.amend:
        c5.amend(ccs[0], args.amend, args.by, args.yea, args.nay, args.why, args.take_out, args.on)
        return 0
    if args.confirm_direction:
        c5.confirm_direction(ccs[0], args.confirm_direction, args.by, args.on)
        return 0
    if args.confirm:
        c5.confirm(ccs[0], args.confirm, args.by, args.on)
        return 0
    if args.sign_from_doc:
        c5.sign_from_doc(ccs[0], args.by, args.on)
        return 0
    if not (args.draft or args.signoff_doc or args.sheets or args.counts
            or args.prune_out_of_scope or args.prune_off_ground or args.shortlist
            or args.auto_confirm or args.resync_directions or args.fill_directions):
        ap.error("say what to do: --draft, --resync-directions, --fill-directions, --auto-confirm, "
                 "--signoff-doc, --sheets, --shortlist, --counts, --confirm, --amend, --sign-from-doc, "
                 "--prune-out-of-scope or --prune-off-ground")
    if args.prune_out_of_scope:
        for cc in ccs:
            if os.path.exists(c5.stance_path(cc)):
                c5.prune_out_of_scope(cc, dry_run=args.dry_run)

    rc = 0
    totals = {}
    for cc in ccs:
        path = stores.get(cc, args.db)
        need_store = args.draft or args.sheets or args.prune_off_ground
        if not (need_store or args.signoff_doc or args.shortlist or args.auto_confirm
                or args.resync_directions or args.fill_directions):
            continue
        conn = None
        if need_store:
            if not os.path.exists(path):
                print("{0}: no store at {1}; skipped".format(cc, path))
                continue
            conn = c5.connect_ro(path)
        elif os.path.exists(path):
            conn = c5.connect_ro(path)       # the meaning lines (src/vote_meanings.py)
        try:
            if args.prune_off_ground and os.path.exists(c5.stance_path(cc)):
                c5.prune_off_ground(conn, cc, dry_run=args.dry_run)
            if args.draft:
                c5.draft(conn, cc, today=args.today)
            if args.resync_directions and os.path.exists(c5.stance_path(cc)):
                c5.resync_directions(cc, dry_run=args.dry_run)
            if args.fill_directions and os.path.exists(c5.stance_path(cc)):
                c5.fill_directions(cc, dry_run=args.dry_run)
                c5.fill_amendments(cc, dry_run=args.dry_run)
            if args.auto_confirm and os.path.exists(c5.stance_path(cc)):
                got = c5.auto_confirm(cc, today=args.today, dry_run=args.dry_run, conn=conn)
                totals[cc] = (len(got["confirmed"]), len(got["left"]))
            if args.signoff_doc:
                c5.write_signoff_doc(cc, conn=conn)
            if args.sheets:
                c5.run_sheets(conn, cc, out_dir=args.out_dir, today=args.today)
            if args.shortlist:
                sl.write_shortlist(cc, conn=conn, today=args.today, top=args.top)
        except Exception as exc:          # one country's failure is a gap, not a lost run
            print("  [gap] {0}: {1}: {2}".format(cc, type(exc).__name__, exc))
            rc = 1
        finally:
            if conn is not None:
                conn.close()
    if totals:
        print("\nAutomatic sign-off{0} ({1}): confirmed / left for a person".format(
            ", DRY RUN (nothing written)" if args.dry_run else "", c5.AUTO_CHECKS_VERSION))
        for cc, (ok, left) in totals.items():
            print("  {0}  {1:>5} {2:>5}   {3}".format(cc, ok, left, c5.SPECS[cc].name))
        print("  all {0:>5} {1:>5}".format(sum(v[0] for v in totals.values()),
                                           sum(v[1] for v in totals.values())))
    if args.counts or args.draft or args.prune_out_of_scope or args.prune_off_ground:
        print("\nconfig/<cc>_stance.yaml, by country (proposed / procedural / need reading / "
              "confirmed):")
        for cc in ccs:
            if os.path.exists(c5.stance_path(cc)):
                c = c5.counts(cc)
                print("  {0}  {1:>5} {2:>5} {3:>5} {4:>5}   {5}".format(
                    cc, c["proposed"], c["procedural"], c["needs_reading"], c["confirmed"],
                    c5.SPECS[cc].name))
    return rc


if __name__ == "__main__":
    sys.exit(main())
