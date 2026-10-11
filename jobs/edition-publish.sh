#!/bin/bash
# Edition publish on the Mac Mini (tools/mini_run.sh edition-publish, 06:31
# and 18:31 London every day): send the new country editions whose review
# window has ended (src/edition_review.py, tools/edition_review.py,
# config/edition-review.yaml; 11 October 2026, UK parity).
#
# Each own-edition weekly (and the Latam monthly) writes its edition as a
# draft and reviews/<cc>-review-<date>.md, and holds the DM. Chris may cut or
# edit items, add a note, hold or send now, by editing that file on main.
# This job renders each edition due with the review honoured, rewrites
# editions/<cc>-monitor-<date>.md, DMs Chris alone, marks the window sent in
# data/edition-reviews/, then creates or rewrites the week's ONE combined
# Asana reading task for all the new-country editions. Unedited, an edition
# goes out unchanged at the window's end (06:30 London the next morning).
#
# Cheap when nothing is due: the check reads only data/edition-reviews/ and
# reviews/, so the 895 MB store is pulled only when an edition is due. The
# store is read, never written, so nothing is published.
#
# MINI ONLY, NO GITHUB WORKFLOW. If the Mini is down, nothing is lost: the
# windows wait in data/edition-reviews/ and the next run sends every edition
# then due (the 07:30 health DM says the Mini missed its slots).
#
# mini_run: no-store   (the job pulls the store itself, only when an edition is due)
# mini_run: commit editions
set -o pipefail
cd "$(dirname "$0")/.."
export GITHUB_WORKFLOW="${GITHUB_WORKFLOW:-Edition publish}"
export SLACK_DM_USER_ID="${SLACK_DM_USER_ID:-U05LJP0BT61}"
export PYTHONUNBUFFERED=1
python3 tools/edition_review.py --due
d=$?
[ "$d" -eq 3 ] && exit 0          # nothing due: no store, no commit
[ "$d" -eq 0 ] || exit "$d"
python3 tools/db_state.py --pull || exit 1
python3 tools/edition_review.py --publish
