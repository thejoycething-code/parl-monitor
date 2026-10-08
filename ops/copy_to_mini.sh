#!/bin/bash
# Copy everything Claude-related from this laptop to the Mac Mini, over the
# local network (8 October 2026: Migration Assistant is not an option).
#
#   bash ops/copy_to_mini.sh you@mac-mini.local          # dry run: what would copy
#   bash ops/copy_to_mini.sh you@mac-mini.local --go     # copy for real
#
# BEFORE: on the Mini, System Settings > General > Sharing > Remote Login ON;
# on BOTH machines, quit the Claude app (chat lists and task registries are
# written while it runs); give Terminal Full Disk Access on this laptop
# (System Settings > Privacy & Security), or ~/Desktop and ~/Documents
# refuse to be read.
#
# WHAT: Claude Code chats, memory, scheduled tasks and settings (~/.claude,
# ~/.claude.json), the three app profiles (Claude, Claude-Personal,
# Claude-Work, caches left out), ~/.local (node, gh, uv), and the project
# folders with their secrets. Files go machine to machine; nothing passes
# through any chat. Safe to run again: rsync only sends what changed.
#
# PATHS: chats, memory and tasks are filed under absolute paths
# (/Users/chrisjoyce/...). If the Mini's home folder differs, --go rewrites
# them there after the copy (folder names and text files under ~/.claude,
# ~/.claude.json and the app profiles' session lists).
#
# AFTER: on the Mini, open Claude and sign in (logins live in the Keychain,
# which is not copied), `gh auth login` as thejoycething-code, then
# `bash ~/parl-monitor/tools/macmini_setup.sh`. Then turn the scheduled tasks
# OFF on the laptop, or every Slack post goes out twice.

set -u
DEST=${1:?usage: bash ops/copy_to_mini.sh user@host [--go]}
GO=${2:-}
SRC_HOME=$HOME
CM="$HOME/.ssh/cm-mini-%r@%h:%p"
SSH="ssh -o ControlMaster=auto -o ControlPath=$CM -o ControlPersist=20m"

ITEMS=(
  ".claude"
  ".claude.json"
  ".local"
  "Library/Application Support/Claude"
  "Library/Application Support/Claude-Personal"
  "Library/Application Support/Claude-Work"
  "parl-monitor"
  "Downloads/breakfast-briefing"
  "Downloads/clacton-vercel"
  "Desktop/Claude"
  "Documents/Claude"
)
EXCLUDES=(
  --exclude "Cache" --exclude "Code Cache" --exclude "GPUCache" --exclude "DawnGraphiteCache"
  --exclude "DawnWebGPUCache" --exclude "Crashpad" --exclude "vm_bundles" --exclude "claude-code-vm"
  --exclude "parl-monitor/.claude/worktrees"
)

echo "Connecting to $DEST (one password prompt at most)..."
$SSH "$DEST" true || { echo "Cannot reach $DEST over SSH: is Remote Login on?"; exit 1; }
DEST_HOME=$($SSH "$DEST" 'echo $HOME')
echo "  laptop home: $SRC_HOME"
echo "  mini home:   $DEST_HOME"

if pgrep -xq "Claude"; then echo "Quit the Claude app on this laptop first."; [ "$GO" = "--go" ] && exit 1; fi
if $SSH "$DEST" 'pgrep -xq Claude'; then echo "Quit the Claude app on the Mini first."; [ "$GO" = "--go" ] && exit 1; fi

FLAGS="-a"
[ "$GO" = "--go" ] || FLAGS="-an"
[ "$GO" = "--go" ] && echo "COPYING." || echo "DRY RUN: nothing is written. Add --go to copy."

fails=0
for item in "${ITEMS[@]}"; do
  src="$SRC_HOME/$item"
  if [ ! -e "$src" ]; then echo "  skip  $item (not on this laptop)"; continue; fi
  if [ ! -r "$src" ]; then echo "  FAIL  $item: not readable (give Terminal Full Disk Access)"; fails=$((fails+1)); continue; fi
  parent=$(dirname "$item")
  $SSH "$DEST" "mkdir -p \"\$HOME/$parent\""
  if [ -d "$src" ]; then
    n=$(rsync $FLAGS -e "$SSH" "${EXCLUDES[@]}" --out-format="%n" "$src/" "$DEST:\"$DEST_HOME/$item/\"" 2>/tmp/copy-mini.err | wc -l)
  else
    n=$(rsync $FLAGS -e "$SSH" --out-format="%n" "$src" "$DEST:\"$DEST_HOME/$item\"" 2>/tmp/copy-mini.err | wc -l)
  fi
  if [ -s /tmp/copy-mini.err ]; then echo "  FAIL  $item: $(head -2 /tmp/copy-mini.err | tr '\n' ' ')"; fails=$((fails+1))
  else echo "  ok    $item ($n file(s) $( [ "$GO" = "--go" ] && echo sent || echo to send ))"; fi
done

if [ "$GO" = "--go" ] && [ "$SRC_HOME" != "$DEST_HOME" ]; then
  echo "Rewriting paths on the Mini: $SRC_HOME -> $DEST_HOME"
  $SSH "$DEST" "python3 - '$SRC_HOME' '$DEST_HOME'" <<'PY'
import os, sys
old, new = sys.argv[1], sys.argv[2]
home = os.path.expanduser("~")
okey, nkey = old.replace("/", "-"), new.replace("/", "-")
proj = os.path.join(home, ".claude", "projects")
for name in sorted(os.listdir(proj)) if os.path.isdir(proj) else []:
    if okey in name:
        os.rename(os.path.join(proj, name), os.path.join(proj, name.replace(okey, nkey)))
roots = [os.path.join(home, ".claude"), os.path.join(home, ".claude.json")]
for p in ("Claude", "Claude-Personal", "Claude-Work"):
    base = os.path.join(home, "Library", "Application Support", p)
    for sub in ("claude-code-sessions", "local-agent-mode-sessions", "git-worktrees.json", "config.json",
                "claude_desktop_config.json"):
        roots.append(os.path.join(base, sub))
changed = 0
def fix(path):
    global changed
    if not path.endswith((".json", ".jsonl", ".md", ".yaml", ".yml", ".txt")):
        return
    try:
        with open(path, encoding="utf-8") as h:
            text = h.read()
    except (UnicodeDecodeError, OSError):
        return
    if old in text:
        with open(path, "w", encoding="utf-8") as h:
            h.write(text.replace(old, new))
        changed += 1
for r in roots:
    if os.path.isfile(r):
        fix(r)
    elif os.path.isdir(r):
        for d, _, files in os.walk(r):
            for f in files:
                fix(os.path.join(d, f))
print("  rewrote {0} file(s); project folders renamed to {1}".format(changed, nkey))
PY
fi

echo
[ $fails -eq 0 ] && echo "Done. Next on the Mini: open Claude and sign in, gh auth login, bash ~/parl-monitor/tools/macmini_setup.sh. Then turn the laptop's scheduled tasks OFF." \
  || echo "$fails item(s) failed; fix the cause and run again (rsync resumes)."
