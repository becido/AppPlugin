#!/usr/bin/env python3
"""
App monitoring daemon.

Usage:
  daemon.py start "<shell command>"   -- spawn app, monitor output, record metrics
  daemon.py stop                      -- send SIGTERM to running daemon
  daemon.py status                    -- print running/stopped + PID info
  daemon.py get-pending               -- print unacknowledged issues as JSON array
  daemon.py get-crashes               -- print unreported crashes as JSON array
  daemon.py acknowledge <id> [...]    -- move issue IDs from pending to handled
  daemon.py mark-crashes-reported     -- mark all crashes as reported
  daemon.py set-pref <key> <value>    -- update config.json preference key
"""

import sys
import os
import json
import re
import signal
import subprocess
import threading
import datetime
import time
from pathlib import Path
from collections import deque

DATA_DIR = Path.cwd() / "data"
CONFIG_FILE = DATA_DIR / "config.json"
DAEMON_PID_FILE = DATA_DIR / "daemon.pid"
APP_PID_FILE = DATA_DIR / "app.pid"
ISSUES_PENDING_FILE = DATA_DIR / "issues_pending.jsonl"
ISSUES_HANDLED_FILE = DATA_DIR / "issues_handled.jsonl"
CRASHES_FILE = DATA_DIR / "crashes.jsonl"
METRICS_FILE = DATA_DIR / "metrics.jsonl"
LOG_FILE = DATA_DIR / "app.log"

ERROR_RE = re.compile(r"(?i)\berror\b")
WARN_RE = re.compile(r"(?i)\b(warn|warning)\b")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

_app_proc = None


# ── helpers ──────────────────────────────────────────────────────────────────

def read_pid(path):
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def append_jsonl(path, record):
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_jsonl(path):
    records = []
    if not path.exists():
        return records
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def write_jsonl(path, records):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ── metrics ──────────────────────────────────────────────────────────────────

def sample_metrics(pid):
    if HAS_PSUTIL:
        try:
            p = psutil.Process(pid)
            with p.oneshot():
                cpu = p.cpu_percent(interval=1.0)
                mem = p.memory_info().rss / 1024 / 1024
            return cpu, mem
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None, None
    else:
        try:
            out = subprocess.check_output(
                ["ps", "-o", "%cpu,rss", "-p", str(pid)],
                text=True, stderr=subprocess.DEVNULL,
            )
            lines = out.strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                cpu = float(parts[0])
                mem = int(parts[1]) / 1024
                return cpu, mem
        except Exception:
            pass
    return None, None


def metrics_loop(pid, stop_event):
    while not stop_event.wait(10):
        cpu, mem = sample_metrics(pid)
        if cpu is not None:
            append_jsonl(METRICS_FILE, {
                "timestamp": datetime.datetime.now().isoformat(),
                "cpu_percent": cpu,
                "mem_mb": round(mem, 2),
            })


# ── subcommands ───────────────────────────────────────────────────────────────

def cmd_start(command):
    global _app_proc

    DATA_DIR.mkdir(exist_ok=True)

    # Refuse to start if a daemon is already running
    existing_pid = read_pid(DAEMON_PID_FILE)
    if existing_pid and pid_alive(existing_pid):
        print(f"Daemon already running (PID {existing_pid}). Stop it first.")
        sys.exit(1)

    DAEMON_PID_FILE.write_text(str(os.getpid()))

    def handle_signal(signum, frame):
        if _app_proc and _app_proc.poll() is None:
            try:
                os.killpg(_app_proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                _app_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(_app_proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        DAEMON_PID_FILE.unlink(missing_ok=True)
        APP_PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    _app_proc = subprocess.Popen(
        command, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
        start_new_session=True,
    )
    APP_PID_FILE.write_text(str(_app_proc.pid))
    print(f"Started app PID {_app_proc.pid}", flush=True)

    stop_metrics = threading.Event()
    t = threading.Thread(
        target=metrics_loop, args=(_app_proc.pid, stop_metrics), daemon=True
    )
    t.start()

    config = {}
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            pass
    ignore_patterns = config.get("ignore_patterns", [])

    recent_lines = deque(maxlen=100)
    with open(LOG_FILE, "a") as log_f:
        for line in _app_proc.stdout:
            log_f.write(line)
            log_f.flush()
            stripped = line.rstrip()
            recent_lines.append(stripped)

            severity = None
            if ERROR_RE.search(stripped):
                severity = "ERROR"
            elif WARN_RE.search(stripped):
                severity = "WARN"

            if severity and not any(p in stripped for p in ignore_patterns):
                append_jsonl(ISSUES_PENDING_FILE, {
                    "id": f"{time.time():.6f}",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "severity": severity,
                    "message": stripped,
                    "acknowledged": False,
                })

    exit_code = _app_proc.wait()
    stop_metrics.set()
    APP_PID_FILE.unlink(missing_ok=True)

    if exit_code != 0:
        append_jsonl(CRASHES_FILE, {
            "timestamp": datetime.datetime.now().isoformat(),
            "exit_code": exit_code,
            "signal": None,
            "last_lines": list(recent_lines),
            "reported": False,
        })
        print(f"App exited with code {exit_code} — crash recorded.", flush=True)
    else:
        print("App exited cleanly.", flush=True)

    DAEMON_PID_FILE.unlink(missing_ok=True)


def cmd_stop():
    pid = read_pid(DAEMON_PID_FILE)
    if pid is None:
        print("No daemon running (no PID file).")
        return
    if not pid_alive(pid):
        print("Daemon not found (stale PID file).")
        DAEMON_PID_FILE.unlink(missing_ok=True)
        return
    os.kill(pid, signal.SIGTERM)
    print(f"Sent SIGTERM to daemon PID {pid}.")


def cmd_status():
    d_pid = read_pid(DAEMON_PID_FILE)
    a_pid = read_pid(APP_PID_FILE)
    if d_pid is None or not pid_alive(d_pid):
        print("Status: stopped")
        if d_pid:
            DAEMON_PID_FILE.unlink(missing_ok=True)
        return
    print(f"Status: running | daemon_pid={d_pid} | app_pid={a_pid or 'unknown'}")


def cmd_get_pending():
    records = [r for r in read_jsonl(ISSUES_PENDING_FILE) if not r.get("acknowledged")]
    print(json.dumps(records, indent=2))


def cmd_get_crashes():
    records = [r for r in read_jsonl(CRASHES_FILE) if not r.get("reported")]
    print(json.dumps(records, indent=2))


def cmd_acknowledge(ids):
    id_set = set(ids)
    pending = read_jsonl(ISSUES_PENDING_FILE)
    still_pending = []
    now_handled = []
    for r in pending:
        if r["id"] in id_set:
            r["acknowledged"] = True
            now_handled.append(r)
        else:
            still_pending.append(r)
    write_jsonl(ISSUES_PENDING_FILE, still_pending)
    if now_handled:
        with open(ISSUES_HANDLED_FILE, "a") as f:
            for r in now_handled:
                f.write(json.dumps(r) + "\n")
    print(f"Acknowledged {len(now_handled)} issue(s).")


def cmd_mark_crashes_reported():
    crashes = read_jsonl(CRASHES_FILE)
    count = 0
    for r in crashes:
        if not r.get("reported"):
            r["reported"] = True
            count += 1
    write_jsonl(CRASHES_FILE, crashes)
    print(f"Marked {count} crash(es) as reported.")


def cmd_set_pref(key, value):
    DATA_DIR.mkdir(exist_ok=True)
    config = {}
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            pass
    config[key] = value
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"Set {key}={value!r} in config.json")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    sub = sys.argv[1]

    if sub == "start":
        if len(sys.argv) < 3:
            print("Usage: daemon.py start \"<command>\"")
            sys.exit(1)
        cmd_start(sys.argv[2])

    elif sub == "stop":
        cmd_stop()

    elif sub == "status":
        cmd_status()

    elif sub == "get-pending":
        cmd_get_pending()

    elif sub == "get-crashes":
        cmd_get_crashes()

    elif sub == "acknowledge":
        if len(sys.argv) < 3:
            print("Usage: daemon.py acknowledge <id> [<id> ...]")
            sys.exit(1)
        cmd_acknowledge(sys.argv[2:])

    elif sub == "mark-crashes-reported":
        cmd_mark_crashes_reported()

    elif sub == "set-pref":
        if len(sys.argv) < 4:
            print("Usage: daemon.py set-pref <key> <value>")
            sys.exit(1)
        cmd_set_pref(sys.argv[2], sys.argv[3])

    else:
        print(f"Unknown subcommand: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
