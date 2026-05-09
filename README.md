# App Monitor — Claude Code Plugin

A Claude Code plugin that manages, monitors, and auto-fixes your running application — all from inside your Claude Code session.

---

## What it does

### `/app start`
Starts your application as a monitored background process.

- **First run:** asks you for the command to start your app (e.g. `python app.py`, `npm start`, `./server`), then saves it. Every subsequent `/app start` uses the saved command automatically — no prompt.
- Spawns the app in the background and begins capturing all console output.
- Automatically starts a continuous monitoring loop.

### Continuous monitoring
After `/app start`, Claude watches your app's output in real time. Whenever a line containing `ERROR`, `WARN`, or `WARNING` is detected, Claude surfaces it and asks:

```
[ERROR] 2026-05-09 12:34:56
database connection failed at line 42

Fix this?
  1. Yes — fix it now
  2. Yes, and auto-fix all future ERRORs (don't ask again)
  3. No — skip
```

- **Yes** — Claude reads your source code, locates the problem, and fixes it.
- **Yes, and don't ask again** — Claude fixes it and switches to auto-fix mode for that severity level. All future errors (or warnings) of the same type are fixed silently without prompting.
- **No** — the issue is acknowledged and skipped.

Crashes (non-zero exit codes) are detected automatically and reported immediately, including the last 100 lines of output at the time of the crash.

### `/app stop`
Stops the monitored application and its background daemon cleanly.

### `/app report`
Generates a full health report for the current (or most recent) session:

- **Crash log** — count, timestamps, exit codes, and last log lines for each crash
- **Issues summary** — total ERROR and WARN counts, most recent entries of each
- **Performance metrics** — average and peak CPU%, average and peak memory usage, session uptime
- **Log tail** — the last 20 lines of application output

---

## Requirements

- [Claude Code](https://claude.ai/code) (CLI, desktop app, or IDE extension)
- Python 3.8+
- *(Optional)* [`psutil`](https://pypi.org/project/psutil/) for accurate CPU/memory metrics — falls back to `ps` if not installed

---

## Installation

### Option A — Global install (recommended)

Installs the `/app` commands once so they are available in **every** Claude Code project without any per-project setup.

**1. Clone this repo to a permanent location**

```bash
git clone <this-repo> ~/claude-plugins/AppPlugin
```

> The repo must stay at this path — the global commands reference the daemon script by absolute path.

**2. Run the installer**

```bash
cd ~/claude-plugins/AppPlugin
./install.sh
```

The installer:
- Copies the `/app` command files into `~/.claude/commands/app/`
- Rewrites the internal script path to the absolute location of `scripts/daemon.py`
- Merges the required shell permissions into `~/.claude/settings.json`

**3. (Optional) Install psutil for richer metrics**

```bash
pip install psutil
```

**4. Verify**

Open any project in Claude Code and type `/app` — you should see `start`, `stop`, `monitor`, `report`.

---

### Option B — Per-project install

Use this if you want to bundle the plugin inside a specific project and keep everything self-contained.

**1. Clone or copy this plugin into your project**

```bash
git clone <this-repo> AppPlugin
```

**2. Open AppPlugin as a Claude Code project**

Claude Code loads slash commands and settings from the `.claude/` directory of whatever folder you open. You must open `AppPlugin/` as your working directory (or add it as an additional directory).

**Option B1 — Open AppPlugin directly:**
```bash
cd AppPlugin
claude
```

**Option B2 — Add as an additional directory in your existing project:**

In your project's `.claude/settings.json` or `.claude/settings.local.json`, add:
```json
{
  "permissions": {
    "additionalDirectories": ["/path/to/AppPlugin"]
  }
}
```

**3. (Optional) Install psutil for richer metrics**

```bash
pip install psutil
```

**4. Verify installation**

In Claude Code, type `/app` — you should see the available commands: `start`, `stop`, `monitor`, `report`.

---

## Usage

### Starting your app for the first time

```
/app start
```

Claude will ask:
> What command should I run to start your application?

Enter your start command, e.g. `python server.py` or `npm run dev`. Claude saves it to `data/config.json` and starts the app immediately.

### Starting again (saved command)

```
/app start
```

Claude reads the saved command and starts without prompting.

### Changing the start command

Edit `data/config.json` directly:
```json
{
  "command": "your new command here",
  "error_pref": "ask",
  "warn_pref": "ask"
}
```

Or delete `data/config.json` and run `/app start` — Claude will ask again.

### Resetting auto-fix preferences

Set `error_pref` and/or `warn_pref` back to `"ask"` in `data/config.json`:
```json
{
  "command": "python server.py",
  "error_pref": "ask",
  "warn_pref": "ask"
}
```

Valid preference values: `"ask"` · `"auto_fix"` · `"ignore"`

### Viewing a session report

```
/app report
```

Works whether the app is running or stopped. All data persists across sessions until you clear the `data/` directory.

---

## File structure

```
AppPlugin/
├── install.sh               # Global installer — run once to enable /app in all projects
├── .claude/
│   ├── commands/
│   │   └── app/
│   │       ├── start.md     # /app start
│   │       ├── stop.md      # /app stop
│   │       ├── monitor.md   # /app monitor (internal, driven by /loop)
│   │       └── report.md    # /app report
│   └── settings.local.json  # Bash permission allowlist (per-project install only)
├── scripts/
│   └── daemon.py            # Background process manager and output monitor
├── data/                    # Runtime state (gitignored except .gitkeep)
│   ├── config.json          # Saved start command and auto-fix preferences
│   ├── app.log              # Full stdout+stderr of the managed app
│   ├── issues_pending.jsonl # Unacknowledged ERROR/WARN records
│   ├── issues_handled.jsonl # Acknowledged issue archive
│   ├── crashes.jsonl        # Crash records with last 100 output lines
│   ├── metrics.jsonl        # CPU/memory samples (every 10 seconds)
│   ├── daemon.pid           # PID of the monitoring daemon
│   └── app.pid              # PID of the managed application
└── .gitignore               # Ignores all data/ files except .gitkeep
```

---

## How it works

`/app start` launches `scripts/daemon.py` as a detached background process using `nohup`. The daemon:

1. Spawns your app via the shell and captures its combined stdout+stderr through a pipe.
2. Writes every line to `data/app.log`.
3. Scans each line for `ERROR`, `WARN`, or `WARNING` (case-insensitive, whole-word match) and appends matching records to `data/issues_pending.jsonl`.
4. On process exit with a non-zero code, records a crash entry in `data/crashes.jsonl` including the last 100 lines of output.
5. Samples CPU% and memory usage every 10 seconds and appends to `data/metrics.jsonl`.

Claude Code's `/loop` mechanism drives `/app monitor` on repeat. Each cycle, Claude reads `issues_pending.jsonl`, applies your saved preferences, and handles issues — prompting when needed, auto-fixing when configured, and finally moving acknowledged records to `issues_handled.jsonl`.

---

## Data and privacy

All captured output, logs, and metrics are stored locally in `data/`. Nothing is sent anywhere. The `data/` directory is gitignored (except for `.gitkeep`) so logs do not end up in version control. `data/config.json` (your saved command and preferences) is not gitignored and will be committed if you `git add` it.
