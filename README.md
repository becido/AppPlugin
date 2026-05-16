# App Monitor — Claude Code Plugin

A Claude Code plugin that manages, monitors, and auto-fixes your running application — all from inside your Claude Code session.

---

## What it does

### `/app:start`
Starts your application as a monitored background process.

- **First run:** asks you for the command to start your app (e.g. `python app.py`, `npm start`, `./server`), then saves it. Every subsequent `/app:start` uses the saved command automatically — no prompt.
- Spawns the app in the background and begins capturing all console output.
- Automatically starts a continuous monitoring loop.

### Continuous monitoring
After `/app:start`, Claude watches your app's output in real time. Whenever a line containing `ERROR`, `WARN`, or `WARNING` is detected, Claude surfaces it and asks:

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

### `/app:stop`
Stops the monitored application and its background daemon cleanly.

### `/app:restart`
Stops the application, then immediately starts it again. Useful for picking up code changes or recovering from a crash without leaving the monitoring session.

### `/app:report`
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

### Option A — Plugin install (recommended)

Install directly from the Claude Code plugin system — no manual setup required:

```
/plugin install app@claude-plugins-official
```

Or browse to it via `/plugin` → **Discover** in Claude Code.

Once installed, the `/app:*` commands are available in every project automatically.

**Optional: install psutil for richer metrics**

```bash
pip install psutil
```

---

### Option B — Manual global install

Use this if you are not yet on a version of Claude Code that supports the plugin marketplace.

**1. Clone this repo to a permanent location**

```bash
git clone https://github.com/becido/AppPlugin ~/claude-plugins/AppPlugin
```

> The repo must stay at this path — the daemon wrapper resolves `scripts/daemon.py` relative to the repo.

**2. Run the installer**

```bash
cd ~/claude-plugins/AppPlugin
./install.sh
```

The installer:
- Creates `~/.local/bin/app-monitor-daemon` — a wrapper that locates the daemon automatically
- Copies the command files into `~/.claude/commands/app/`
- Merges the required shell permissions into `~/.claude/settings.json`

If `~/.local/bin` is not already in your `PATH`, the installer will warn you. Add this to `~/.bashrc` or `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

**3. (Optional) Install psutil for richer metrics**

```bash
pip install psutil
```

**4. Verify**

Open any project in Claude Code and type `/app` — you should see `start`, `stop`, `restart`, `monitor`, `report`.

---

### Option C — Per-project install (development / sandboxed)

Use this to load the plugin for a single project without installing it globally.

**1. Clone this repo anywhere**

```bash
git clone https://github.com/becido/AppPlugin
```

**2. Load it with `--plugin-dir`**

```bash
claude --plugin-dir /path/to/AppPlugin
```

Or add it to a project's additional directories in `.claude/settings.json`:

```json
{
  "permissions": {
    "additionalDirectories": ["/path/to/AppPlugin"]
  }
}
```

---

## Usage

### Starting your app for the first time

```
/app:start
```

Claude will ask:
> What command should I run to start your application?

Enter your start command, e.g. `python server.py` or `npm run dev`. Claude saves it to `data/config.json` and starts the app immediately.

### Starting again (saved command)

```
/app:start
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

Or delete `data/config.json` and run `/app:start` — Claude will ask again.

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

### Suppressing specific log lines

Add an `ignore_patterns` list to `data/config.json` to silently drop any log line containing one of those strings — before it is classified as an issue:

```json
{
  "command": "python server.py",
  "ignore_patterns": ["WatchFiles detected changes", "Reloading..."]
}
```

Lines that match are still written to `data/app.log` but never surfaced as pending issues. This is useful for noisy but harmless framework messages that you cannot suppress at the logger level.

### Stopping the app

```
/app:stop
```

Stops the managed application and its background daemon cleanly.

### Restarting the app

```
/app:restart
```

Stops the app and immediately starts it again using the saved command. Useful after editing source code or recovering from a crash without leaving the monitoring session.

### Viewing a session report

```
/app:report
```

Works whether the app is running or stopped. All data persists across sessions until you clear the `data/` directory.

---

## Preparing your app for monitoring

The daemon detects issues by scanning your app's console output line by line. For auto-detection and auto-fix suggestions to work, **your application must print `ERROR` or `WARNING`/`WARN` to stdout or stderr** — not swallow them silently inside exception handlers.

### Python / FastAPI apps

Python's `logging` module does not emit to the console by default unless configured. Add this near the top of your entry point (e.g. `main.py`):

```python
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(levelname)s:%(name)s: %(message)s",
    force=True,          # ensures this wins even if a framework configured logging first
)
```

Then use `logger.exception()` (or `logger.error()`) in every `except` block **before** re-raising or returning an error response:

```python
logger = logging.getLogger(__name__)

try:
    result = do_something()
except Exception as e:
    logger.exception("Failed to do something")   # prints full traceback as ERROR
    raise HTTPException(status_code=500, detail=str(e))
```

Without the `logger.exception()` call, the exception is swallowed into the HTTP response and never appears in the console — so the daemon cannot see it.

#### Catching unhandled exceptions (FastAPI)

Add a middleware to log anything that slips past your route handlers:

```python
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse

@app.middleware("http")
async def log_unhandled_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.error("Unhandled exception on %s %s\n%s",
                     request.method, request.url.path, traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

### Node.js / Express apps

Use `console.error(...)` for errors and `console.warn(...)` for warnings. These write to stderr, which the daemon captures alongside stdout. Avoid silently swallowing errors in `.catch()` callbacks without logging them.

### Suppressing known-harmless warnings

Some frameworks emit `WARNING`-level log lines as normal operational messages (e.g. uvicorn's hot-reload notifying you that a file changed). These will show up as pending issues every time you edit a file.

**Option 1 — suppress at the logger level** (preferred when you control the logger):

```python
# Silence uvicorn's WatchFiles reload noise
logging.getLogger("watchfiles").setLevel(logging.ERROR)
```

**Option 2 — suppress via `ignore_patterns`** (useful for third-party output you cannot reconfigure):

Add the substring to `ignore_patterns` in `data/config.json` and the daemon will drop matching lines before they become issues (see [Suppressing specific log lines](#suppressing-specific-log-lines)).

### Quick checklist

- [ ] Logging is configured to write to stdout or stderr
- [ ] All `except` blocks call `logger.exception()` or `logger.error()` before handling the error
- [ ] A catch-all middleware or top-level handler logs unhandled exceptions
- [ ] Known-harmless WARNING sources are suppressed at the logger level

---

## File structure

```
AppPlugin/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest (name, version, author)
├── bin/
│   └── app-monitor-daemon   # Self-locating wrapper — calls scripts/daemon.py
├── commands/
│   ├── start.md             # /app:start
│   ├── stop.md              # /app:stop
│   ├── restart.md           # /app:restart
│   ├── monitor.md           # /app:monitor (internal, driven by /loop)
│   └── report.md            # /app:report
├── scripts/
│   └── daemon.py            # Background process manager and output monitor
├── install.sh               # Manual global installer (fallback for non-plugin installs)
└── .gitignore
```

---

## How it works

`/app:start` launches `scripts/daemon.py` as a detached background process using `nohup`, via the `app-monitor-daemon` wrapper that resolves the script path at runtime. The daemon:

1. Spawns your app via the shell and captures its combined stdout+stderr through a pipe.
2. Writes every line to `data/app.log` inside **your application's working directory**.
3. Scans each line for `ERROR`, `WARN`, or `WARNING` (case-insensitive, whole-word match) and appends matching records to `data/issues_pending.jsonl`. Lines matching any `ignore_patterns` entry are skipped.
4. On process exit with a non-zero code, records a crash entry in `data/crashes.jsonl` including the last 100 lines of output.
5. Samples CPU% and memory usage every 10 seconds and appends to `data/metrics.jsonl`.

Claude Code's `/loop` mechanism drives `/app:monitor` on repeat. Each cycle, Claude reads `issues_pending.jsonl`, applies your saved preferences, and handles issues — prompting when needed, auto-fixing when configured, and finally moving acknowledged records to `issues_handled.jsonl`.

---

## Data and privacy

All captured output, logs, and metrics are stored locally in a `data/` directory created inside **your application's working directory** — not inside the AppPlugin folder. Nothing is sent anywhere. You may want to add `data/` to your project's `.gitignore` so logs do not end up in version control. `data/config.json` (your saved command and preferences) is intentionally not ignored and will be committed if you `git add` it.
