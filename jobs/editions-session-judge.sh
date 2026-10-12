#!/bin/bash
# Country editions and Latam session judge on the Mac Mini
# (tools/mini_run.sh editions-session-judge, Sundays 16:45 London, after the
# last of the week's country weeklies: the Saturday European and Latin
# American ones and Sunday's Uruguay, Dominican Republic, El Salvador,
# Bolivia and Honduras).
#
# THE FREE JUDGE (Chris, 10 October 2026; docs/country-decisions-2026-10-10.md,
# X16 and "The free session judge"): Claude Code on the Mini, signed in to
# Chris's claude.ai account, scores the fifteen country editions' and the
# Latam monitor's pending items on the plan allowance, not the API
# (tools/session_judge.sh, tools/edition_judge.py --queue-out / --queue-in).
# The paid AI judge stays off.
#
# LEAN ON THE PLAN, which Chris's other scheduled jobs share: ONE job a week
# for all sixteen, at most SESSION_JUDGE_MAX items (100) in sessions of 25,
# in one priority order across countries (watched, then tier 1, then tier 2,
# newest first).
#
# MINI ONLY, NO GITHUB WORKFLOW: the CLI and the subscription live here. Its
# heartbeat is its own ("Editions session judge", tools/coverage.py
# ON_DEMAND), and a failure DMs through mini_run.sh.
#
# Order: score; rewrite in place the editions of the countries scored today
# (the latest edition of each, within its cadence; the Latam edition when
# under a week old), with ONE DM to Chris only when the scores changed what
# leads an edition already sent; the Latam alert pass for every country, so
# the tier-1 items held for the judge go out now if it scored them 2 or 3;
# then the raw archive and the store. When claude is missing or not signed
# in, a [gap] line: nothing is scored or rewritten, and only the store (with
# the rule-made vote meanings, below) is published.
#
# THE 5CA STANCE STEPS (10 October 2026; src/country5ca.py, docs/5ca-notes.md
# "The new country editions"), first and offline, seconds to run: prune the
# unsigned, untouched entries whose vote a reclassification took off our
# ground (11 October 2026, --prune-off-ground: Switzerland's IVG guard; a
# confirmed or hand-edited entry is kept and reported), draft
# config/<cc>_stance.yaml entries for the week's new watched and tier-1 votes
# in every new country (by rules, no AI), bring untouched drafts into line
# with any bill direction a person changed (--resync-directions), draft the
# untouched needs_reading votes whose bill has since been given a direction
# (12 October 2026, --fill-directions: they were drafted before it existed and
# nothing else revisits them; it also drafts the amendment entries a reader
# gave an amendment_direction, as every amendment is now read and scored),
# confirm on
# Chris's delegation every draft that passes every automatic check
# (11 October 2026, --auto-confirm: "Automate the checks and we'll make it so
# teams can amend as and when errors come up. Like we're doing with Canada.";
# the rest stay drafts with the check they failed; amended, confirmed and
# hand-edited entries are never touched; docs/5ca-notes.md "Automatic
# sign-off and amendments"), so the sheets below reflect it,
# rewrite each docs/5ca-<cc>-readings.md keeping any ticks not yet applied,
# write the 5CA sheets from CONFIRMED readings only (data/5ca/<cc>-5ca-*.csv),
# rewrite each docs/5ca-<cc>-shortlist.md (11 October 2026, src/shortlist5ca.py:
# the waiting readings ranked by what to sign first; it confirms nothing),
# then the new countries' 5CA tracker and partner sheet
# (tools/make_country_5ca_web.py: docs/5ca-countries.html always;
# partner_site/5ca-countries.html only for countries with a confirmed reading
# that places someone, removed when none has; Monday's deploy ships it),
# then the 5CA canvases for Chris alone (tools/country_5ca_post.py --refresh,
# 11 October 2026: only the canvases whose CONFIRMED readings changed are
# rewritten in place, a newly publishable area gets a canvas shared with his
# user id, never a channel; one DM lists them; nothing confirmed or nothing
# changed, no Slack call and no message; ids in
# data/5ca/country-post-state.json),
# then the weekly "stances awaiting sign-off" digest, one DM to Chris, once
# per ISO week, led by each country's top 5 to sign (tools/stance_digest.py).
# A failure is a [gap] line; the judge still runs. They read the store and write no table, so they need no
# publish of their own.
#
# DRIVE (11 October 2026; tools/country_drive.py, src/country_drive.py): the
# new countries' campaign briefs (briefs/<cc>-*.csv, from each weekly) become
# Sheets from the UK brief template, and their real (non-sample) debate packs
# are uploaded, under "Country editions/<Country>/" in the Automated Briefs
# shared drive, as the UK's are. Only what is new or changed:
# data/country-drive.json (committed with data/) and each sheet's slug tag
# keep a rerun from making a second copy. At most 30 new sheets a run. Before
# the judge, so a judge gap never skips it; its failure is a [gap] line.
#
# THE VOTE PAGES (11 October 2026; src/country_votes.py), after the judge so
# its scores decide what is on our ground, offline, a minute at most: the new
# countries' vote pages (partner_site/<cc>-votes.html), the vote tracker
# (partner_site/votes-countries.html) and the watched bills' timelines
# (partner_site/bill-timelines.html), all behind the partner passphrase;
# Monday's deploy ships them. Records only: no for/against judgement on any
# vote until its reading is CONFIRMED. Run on a judge gap too (exit 3), since
# the pages need no judge. A failure is a [gap] line; last week's pages stand.
#
# mini_run: commit editions config docs partner_site reviews
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Editions session judge}"
export PYTHONUNBUFFERED=1
# The DMs go to Chris alone (the tools also force his id).
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"

python3 tools/country_5ca.py --all-countries --prune-off-ground --draft --resync-directions --fill-directions \
  --auto-confirm --signoff-doc --sheets --shortlist \
  || echo "  [gap] the 5CA stance step failed for a country; the others stand"
python3 tools/make_country_5ca_web.py || echo "  [gap] the new-country 5CA pages failed; last week's stand"
python3 tools/country_5ca_post.py --all-countries --refresh \
  || echo "  [gap] the new-country 5CA canvases were not all refreshed; next week's run retries"
python3 tools/stance_digest.py --dm || echo "  [gap] the stance digest DM failed; next week's covers it"
# --ready-only: briefs reach the campaigners' shared drive only once signed off
# (no NOT READY drafts there); debate packs are unaffected.
python3 tools/country_drive.py --ready-only || echo "  [gap] country-drive: some briefs or packs did not reach Drive; the next run retries"

# THE VOTE MEANINGS (11 October 2026; src/vote_meanings.py): first the rule
# lines (offline, seconds) for every watched and tier-1 vote in the new
# countries, stored per division in vote_meanings; then, AFTER the editions'
# scores and only with what is left of the same weekly budget, the session
# judge writes the lines the rules could not (YES/NO, tools/vote_meanings.py).
python3 tools/vote_meanings.py --rules || echo "  [gap] the vote-meaning rules failed for a country"

rc=0
MAX="${SESSION_JUDGE_MAX:-100}"
JLOG=$(mktemp "${TMPDIR:-/tmp}/editions-judge.XXXXXX")
bash tools/session_judge.sh tools/edition_judge.py "${SESSION_JUDGE_MAX:-100}" 25 > "$JLOG" 2>&1
jrc=$?
cat "$JLOG"
offered=$(sed -n 's/.*; \([0-9][0-9]*\) offered, cap.*/\1/p' "$JLOG" | tail -1)
rm -f "$JLOG"
vote_pages() {
  # Portraits first (12 October 2026, src/portraits.py): only countries whose
  # photo licence is OK (docs/portraits-logos-licences.md), at most 150 new
  # photos each a run, robots.txt obeyed; the manifests go out with data/.
  python3 tools/fetch_portraits.py || echo "  [gap] portraits: some were not fetched; the cached ones stand"
  python3 tools/make_country_votes.py || echo "  [gap] the new-country vote pages failed; last week's stand"
}
gap=""
if [ "$jrc" -eq 3 ]; then
  gap=1                       # a gap, already logged: no judge this week
  vote_pages                  # offline, no judge needed; committed by mini_run.sh
else
  [ "$jrc" -eq 0 ] || rc=1
  left=$((MAX - ${offered:-$MAX}))
  if [ "$left" -gt 0 ]; then
    echo "vote meanings: $left of the week's $MAX session items left after the scores"
    SESSION_JUDGE_PROMPT="$(python3 -c 'import sys; sys.path.insert(0, "tools"); import vote_meanings; print(vote_meanings.MEANING_PROMPT)')" \
      bash tools/session_judge.sh tools/vote_meanings.py "$left" 25 || rc=1
  else
    echo "vote meanings: the scores used the week's $MAX session items; the meanings wait a week"
  fi
fi

if [ -z "$gap" ]; then
  # The week's editions, rewritten with the scores and the meaning lines; one
  # DM only if a lead changed.
  python3 tools/edition_judge.py --rerender --dm || { echo "  [gap] the rewrite failed"; rc=1; }

  # The vote pages, tracker and bill timelines, with this week's scores.
  vote_pages

  # The Latam alerts, every country: releases what was held for the judge.
  python3 tools/latam_alerts.py --send || echo "  [gap] latam-alerts failed; the next country run retries"

  # The archive before the store; both merge, never clobber.
  python3 tools/raw_state.py --push || rc=1
fi
# The store: the scores and meanings, or (on a gap) the rule-made meanings alone.
python3 tools/db_state.py --push || rc=1
exit $rc
