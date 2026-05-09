#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON="$PLUGIN_DIR/scripts/daemon.py"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands/app"
SETTINGS="$CLAUDE_DIR/settings.json"

echo "App Monitor — Global Installer"
echo "================================"
echo ""

# 1. Verify Claude config dir exists
if [ ! -d "$CLAUDE_DIR" ]; then
    echo "Error: $CLAUDE_DIR not found. Is Claude Code installed?"
    exit 1
fi

# 2. Verify daemon script exists
if [ ! -f "$DAEMON" ]; then
    echo "Error: $DAEMON not found. Run this script from within the AppPlugin repo."
    exit 1
fi

# 3. Install command files, rewriting relative script path to absolute
mkdir -p "$COMMANDS_DIR"

for src in "$PLUGIN_DIR/.claude/commands/app"/*.md; do
    name="$(basename "$src")"
    sed "s|python scripts/daemon.py|python $DAEMON|g" "$src" > "$COMMANDS_DIR/$name"
    echo "  [OK] ~/.claude/commands/app/$name"
done

# 4. Merge permissions into ~/.claude/settings.json
python3 - "$SETTINGS" "$DAEMON" <<'PYEOF'
import json, sys, os

settings_path = sys.argv[1]
daemon_path   = sys.argv[2]

if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

settings.setdefault("permissions", {}).setdefault("allow", [])
allow = settings["permissions"]["allow"]

new_perms = [
    f"Bash(python {daemon_path} start *)",
    f"Bash(python {daemon_path} stop)",
    f"Bash(python {daemon_path} status)",
    f"Bash(python {daemon_path} get-pending)",
    f"Bash(python {daemon_path} get-crashes)",
    f"Bash(python {daemon_path} mark-crashes-reported)",
    f"Bash(python {daemon_path} acknowledge *)",
    f"Bash(python {daemon_path} set-pref *)",
    f"Bash(nohup python {daemon_path} start *)",
    "Bash(mkdir -p data)",
    "Bash(cat data/app.pid)",
    "Bash(cat data/daemon.log)",
    "Bash(cat data/daemon.pid)",
    "Bash(cat data/crashes.jsonl)",
    "Bash(cat data/issues_pending.jsonl data/issues_handled.jsonl)",
    "Bash(cat data/metrics.jsonl)",
    "Bash(tail -20 data/app.log)",
    "Bash(ps -p *)",
]

added = 0
for perm in new_perms:
    if perm not in allow:
        allow.append(perm)
        added += 1

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print(f"  [OK] ~/.claude/settings.json ({added} permission(s) added)")
PYEOF

echo ""
echo "Done! Type '/app' in any Claude Code project to get started."
