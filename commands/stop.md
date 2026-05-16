Stop the monitored application and its daemon.

---

## Step 1 — Stop the daemon

Run:
```bash
app-monitor-daemon stop
```

The daemon will send SIGTERM to itself, which triggers it to terminate the managed app process and clean up PID files.

---

## Step 2 — Confirm

Wait 1 second, then check:
```bash
app-monitor-daemon status
```

If the status is **stopped**, tell the user:
> "Application stopped. The monitoring loop has ended. Run `/app:report` to review the session's issues, crashes, and performance metrics."

If the status still shows **running**, inform the user the daemon may take a moment to shut down, and suggest they can run `/app:stop` again if needed.
