#!/bin/bash
# Set up the Mac Mini to run the two UK debate tasks (8 October 2026).
#
# Christopher: "Let's move clips to my Mac Mini machine". The 16:45
# same-day net and the 18:30 debate pack are Claude desktop scheduled
# tasks that render footage with ffmpeg, yt-dlp and faster-whisper and keep
# the clips in data/packs/<pack>/clips/ for review before anything is
# published. They move from the laptop to the Mini, which stays awake.
#
#   bash tools/macmini_setup.sh          # check, install what is missing, report
#
# Safe to run again: every step checks before it acts. It NEVER prints a
# secret and never copies one: config/secrets.yaml and
# config/google-service-account.json are copied across by hand (AirDrop or
# a USB stick), then this script checks they are present.
# See docs/mac-mini.md for the whole move.

set -u
REPO=thejoycething-code/parl-monitor
DEST="$HOME/parl-monitor"
ok()   { echo "  ok    $*"; }
todo() { echo "  TODO  $*"; TODOS=$((TODOS+1)); }
TODOS=0

echo "1. GitHub CLI and login (as thejoycething-code, never the work account)"
if command -v gh >/dev/null; then ok "gh $(gh --version | head -1 | awk '{print $3}')"
else todo "install the GitHub CLI: brew install gh  (or https://cli.github.com)"; fi
if gh auth status >/dev/null 2>&1; then ok "gh is logged in"
else todo "gh auth login  (GitHub.com, HTTPS, as thejoycething-code)"; fi

echo "2. The repository at $DEST"
if [ -d "$DEST/.git" ]; then ok "cloned"; git -C "$DEST" pull -q --rebase --autostash origin main && ok "pulled"
elif gh auth status >/dev/null 2>&1; then gh repo clone "$REPO" "$DEST" -- -q && ok "cloned"
else todo "clone after logging in: gh repo clone $REPO $DEST"; fi

echo "3. Python packages (user site, as on the laptop)"
PY=$(command -v python3)
"$PY" -m pip install --user -q pyyaml "pypdf==6.14.2" cryptography google-auth imageio-ffmpeg yt-dlp faster-whisper \
  && ok "pyyaml pypdf cryptography google-auth imageio-ffmpeg yt-dlp faster-whisper" \
  || todo "pip install failed: rerun and read the error"
"$PY" - <<'PY' && ok "ffmpeg (bundled), yt-dlp and faster-whisper import" || todo "a footage library does not import"
import imageio_ffmpeg, yt_dlp, faster_whisper
print("    ffmpeg:", imageio_ffmpeg.get_ffmpeg_exe())
PY
YT="$HOME/Library/Python/$("$PY" -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')/bin/yt-dlp"
if command -v yt-dlp >/dev/null || [ -x "$YT" ]; then ok "yt-dlp command"
else todo "yt-dlp command not found (expected at $YT)"; fi

echo "4. Secrets, copied by hand from the laptop (never printed here)"
for f in config/secrets.yaml config/google-service-account.json; do
  if [ -s "$DEST/$f" ]; then ok "$f present"; else todo "copy $f from the laptop's ~/parl-monitor/$f"; fi
done

echo "5. The store and raw archive (the pack task pulls again before every pack)"
if [ -s "$DEST/config/secrets.yaml" ] && gh auth status >/dev/null 2>&1; then
  (cd "$DEST" && "$PY" tools/db_state.py --pull >/tmp/macmini-db.log 2>&1) && ok "store pulled" || todo "store pull failed: see /tmp/macmini-db.log"
  (cd "$DEST" && "$PY" tools/raw_state.py --pull >/tmp/macmini-raw.log 2>&1) && ok "raw archive pulled" || todo "raw pull failed: see /tmp/macmini-raw.log"
else todo "pull the store once the login and secrets are in place: rerun this script"; fi

echo "6. Smoke checks"
if [ -d "$DEST" ]; then
  (cd "$DEST" && "$PY" tools/debate_watch.py today 2>&1 | head -3 | sed 's/^/    /') && ok "debate_watch runs"
fi

echo "7. Keep the Mini awake for the 16:45 and 18:30 tasks"
if pmset -g | grep -qE "^ *sleep +0"; then ok "system sleep is off"
else todo "System Settings > Energy: never sleep (or: sudo pmset -a sleep 0)"; fi

echo
if [ $TODOS -eq 0 ]; then
  echo "Ready. Next: open Claude on the Mini, start a session in $DEST, and ask it to create the two"
  echo "scheduled tasks from ops/scheduled-tasks/ (see docs/mac-mini.md, step 4)."
else
  echo "$TODOS thing(s) to do above; rerun this script after each."
fi
