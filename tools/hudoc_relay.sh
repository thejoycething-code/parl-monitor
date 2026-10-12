#!/bin/bash
# The Mac Mini half of the HUDOC relay (8 October 2026).
#
# HUDOC answers 403 to GitHub Actions but 200 to the Mini. Christopher:
# "Run the HUDOC search from the Mini". launchd runs this daily
# (ops/launchd/net.citizengo.parlmonitor.hudoc-relay.plist): it fetches the
# EU courts' HUDOC searches and commits the replies to data/hudoc-relay/,
# which the EU weekly reads when its own search is refused (tools/eu_courts.py).
#
# It works in its OWN shallow clone (~/parl-relay), never in ~/parl-monitor,
# so it cannot collide with a working session or the debate tasks, and it
# never touches the store.
set -u
export PATH="$HOME/.local/bin:/Library/Frameworks/Python.framework/Versions/3.14/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
CLONE="${HUDOC_RELAY_CLONE:-$HOME/parl-relay}"
URL=https://github.com/thejoycething-code/parl-monitor.git
echo "$(date -u +%Y-%m-%dT%H:%MZ) hudoc relay"

if [ ! -d "$CLONE/.git" ]; then
  git clone -q --depth 1 "$URL" "$CLONE" || { echo "  clone failed"; exit 1; }
fi
cd "$CLONE" || exit 1
# The clone is ours alone: anything left from a failed run is disposable.
git fetch -q --depth 1 origin main && git reset -q --hard origin/main || { echo "  fetch failed"; exit 1; }

python3 tools/eu_courts.py --relay || { echo "  every search failed; nothing committed"; exit 1; }

git add data/hudoc-relay
if git diff --cached --quiet; then echo "  no change"; exit 0; fi
git commit -q -m "HUDOC relay: $(date -u +%Y-%m-%dT%H:%MZ)"
for attempt in 1 2 3; do
  if git push -q origin HEAD:main; then echo "  pushed"; exit 0; fi
  sleep 20
  git fetch -q --depth 1 origin main && git rebase -q origin/main || { echo "  rebase failed"; exit 1; }
done
echo "  push failed three times"; exit 1
