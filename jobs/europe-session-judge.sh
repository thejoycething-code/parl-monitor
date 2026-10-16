#!/bin/bash
# Germany and European Parliament session judge on the Mac Mini
# (tools/mini_run.sh europe-session-judge, Mondays 14:30 London): after the
# EU weekly (Saturday 11:00) and the Germany weekly (Sunday 20:00), clear of
# the Monday publish (04:00), the un-weekday slot (08:30) and the evening
# watches (19:00 on).
#
# PAID AI OFF (Chris, 16 October 2026: "ALL model scoring moves off the paid
# Claude API onto the free session judge"). The German judge, the German
# stance pass and the EU judge spent on the API inside their weeklies
# whenever a key was set; they now leave their rows to this job: Claude Code
# on the Mini, signed in to the work account, on the plan allowance
# (tools/session_judge.sh removes ANTHROPIC_API_KEY from claude's
# environment). The paid paths survive only behind DE_TRIAGE_PAID=1,
# DE_STANCE_PAID=1 and EU_TRIAGE_PAID=1 (src/paid_ai.py), set nowhere.
#
# THREE QUEUES, ONE WEEKLY BUDGET (SESSION_JUDGE_MAX, 200 items by default),
# in this order so the editions' own scores come first:
#   1. the German judge (tools/de_triage.py, newest first), at most
#      DE_TRIAGE_MAX (100), 25 to a session;
#   2. the EU judge (tools/eu_triage.py), with what is left, at most
#      EU_TRIAGE_MAX (60);
#   3. the German stances (tools/de_stance.py, newest speeches first), with
#      what is left, at most DE_STANCE_MAX (60), 20 to a session (each item
#      carries a 1,500-character window of the speech).
# A backlog spreads over weeks: what is not reached waits, disclosed, and the
# editions show an unscored row on rules alone. Measured steady state
# (api_spend and judge_verdicts, Sept to Oct 2026, backfill weeks excluded):
# German judge 30 to 120 rows a week, EU judge 20 to 60, German stances 3 to
# 20 speeches. The German speeches backfill to 2020 (8,422 stances in a
# fortnight, 8.5M input tokens on the API) is already scored; a new backfill
# of that size would take some 140 weeks at 60 a week, so raise DE_STANCE_MAX
# or run it in extra hand-started sessions (docs/mac-mini.md).
#
# Then this week's German and EU editions are rewritten in place with the
# scores (no DM: the weeklies spoke), then the raw archive and the store.
#
# MINI ONLY, NO GITHUB WORKFLOW: the CLI and the subscription live here. Its
# heartbeat is its own ("Europe session judge", tools/coverage.py ON_DEMAND),
# and a failure DMs through mini_run.sh. When claude is missing or not
# signed in, a [gap] line: nothing is scored and nothing is published.
#
# mini_run: commit editions reviews
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Europe session judge}"
export PYTHONUNBUFFERED=1

MAX="${SESSION_JUDGE_MAX:-200}"
DE_MAX="${DE_TRIAGE_MAX:-100}"
EU_MAX="${EU_TRIAGE_MAX:-60}"
STANCE_MAX="${DE_STANCE_MAX:-60}"
rc=0
offered() { sed -n 's/.*; \([0-9][0-9]*\) offered, cap.*/\1/p' "$1" | tail -1; }
LOG=$(mktemp "${TMPDIR:-/tmp}/europe-judge.XXXXXX")
trap 'rm -f "$LOG"' EXIT

[ "$DE_MAX" -gt "$MAX" ] && DE_MAX=$MAX
bash tools/session_judge.sh tools/de_triage.py "$DE_MAX" 25 > "$LOG" 2>&1
jrc=$?
cat "$LOG"
if [ "$jrc" -eq 3 ]; then
  exit 0                      # a gap, already logged: nothing scored, nothing to publish
fi
[ "$jrc" -eq 0 ] || rc=1
n=$(offered "$LOG"); left=$((MAX - ${n:-0}))

if [ "$left" -gt 0 ]; then
  want=$EU_MAX; [ "$left" -lt "$want" ] && want=$left
  bash tools/session_judge.sh tools/eu_triage.py "$want" 25 > "$LOG" 2>&1 || rc=1
  cat "$LOG"
  n=$(offered "$LOG"); left=$((left - ${n:-0}))
fi

if [ "$left" -gt 0 ]; then
  want=$STANCE_MAX; [ "$left" -lt "$want" ] && want=$left
  SESSION_JUDGE_PROMPT="$(python3 -c 'import sys; sys.path.insert(0, "tools"); import uk_stance_judge as s; print(s.STANCE_PROMPT)')" \
    bash tools/session_judge.sh tools/de_stance.py "$want" 20 || rc=1
else
  echo "German stances: the scores used the week's $MAX session items; the stances wait a week"
fi

# This week's editions, rewritten with the scores. Each edition's date fixes
# its window, so it is the same edition, ordered and annotated by the judge.
# No DM. Only an edition of the last seven days: an old one is history.
# Germany's rewrite (tools/de_monitor.rewrite, 16 October 2026) keeps an open
# review window's draft line and decisions (src/edition_review.py).
WEEK_AGO=$(python3 -c 'import datetime; print(datetime.date.today() - datetime.timedelta(days=7))')
for cc in de eu; do
  LATEST=$(ls editions/$cc-monitor-*.md 2>/dev/null | sort | tail -1 | sed "s/.*$cc-monitor-\(.*\)\.md/\1/")
  if [ -n "$LATEST" ] && [[ ! "$LATEST" < "$WEEK_AGO" ]]; then
    python3 -c 'import sys; sys.path[:0] = ["tools", "."]; from src import db; import importlib
m = importlib.import_module(sys.argv[1] + "_monitor")
print("edition:", getattr(m, "rewrite", m.render_edition)(db.init_db(db.connect("data/parl-monitor.db")), sys.argv[2]))' "$cc" "$LATEST" \
      || { echo "  [gap] the $cc edition rewrite failed; the weekly's stands"; rc=1; }
  fi
done

# The archive before the store; both merge, never clobber.
python3 tools/raw_state.py --push || rc=1
python3 tools/db_state.py --push || rc=1
exit $rc
