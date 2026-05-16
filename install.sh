#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON="$PLUGIN_DIR/scripts/daemon.py"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands/app-monitor"
LOCAL_BIN="$HOME/.local/bin"
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

# 3. Install the daemon wrapper to ~/.local/bin
mkdir -p "$LOCAL_BIN"
cat > "$LOCAL_BIN/app-monitor-daemon" <<EOF
#!/usr/bin/env bash
exec python "$DAEMON" "\$@"
EOF
chmod +x "$LOCAL_BIN/app-monitor-daemon"
echo "  [OK] $LOCAL_BIN/app-monitor-daemon"

if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    echo "  [WARN] $LOCAL_BIN is not in your PATH."
    echo "         Add this line to your shell profile (~/.bashrc or ~/.zshrc):"
    echo "           export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# 4. Install command files
mkdir -p "$COMMANDS_DIR"
for src in "$PLUGIN_DIR/commands"/*.md; do
    name="$(basename "$src")"
    cp "$src" "$COMMANDS_DIR/$name"
    echo "  [OK] ~/.claude/commands/app-monitor/$name"
done

# 5. Merge permissions into ~/.claude/settings.json
python3 - "$SETTINGS" <<'PYEOF'
import json, sys, os

settings_path = sys.argv[1]

if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

settings.setdefault("permissions", {}).setdefault("allow", [])
allow = settings["permissions"]["allow"]

new_perms = [
    "Bash(app-monitor-daemon start *)",
    "Bash(app-monitor-daemon stop)",
    "Bash(app-monitor-daemon status)",
    "Bash(app-monitor-daemon get-pending)",
    "Bash(app-monitor-daemon get-crashes)",
    "Bash(app-monitor-daemon mark-crashes-reported)",
    "Bash(app-monitor-daemon acknowledge *)",
    "Bash(app-monitor-daemon set-pref *)",
    "Bash(nohup app-monitor-daemon start *)",
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
echo "Done! Commands are available as /app-monitor:start, /app-monitor:stop, etc."
echo ""
echo "Or install via the Claude Code plugin system (preferred):"
echo "  /plugin install app-monitor@claude-plugins-official"
