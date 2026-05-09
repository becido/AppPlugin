Start the monitored application. Follow each step in order.

---

## Step 1 — Load saved configuration

Read the file `data/config.json`.

- If the file does not exist, or does not contain a `"command"` key, ask the user:
  > "What command should I run to start your application? (e.g. `python app.py`, `npm start`, `./server`)"

  Then write `data/config.json` with this content (replacing COMMAND with their answer):
  ```json
  {"command": "COMMAND", "error_pref": "ask", "warn_pref": "ask"}
  ```

- If the file already has a `"command"` key, use that command and do **not** ask.

---

## Step 2 — Check for an already-running app

Run:
```bash
cat data/app.pid 2>/dev/null
```

If a PID is returned, check if it is alive:
```bash
ps -p <pid> > /dev/null 2>&1 && echo alive || echo dead
```

If **alive**: tell the user the app is already running with that PID and stop here — do not start a second instance.

---

## Step 3 — Start the daemon

Ensure the data directory exists and launch the daemon in the background:
```bash
mkdir -p data && nohup python scripts/daemon.py start "COMMAND" >> data/daemon.log 2>&1 &
```

Replace `COMMAND` with the command from Step 1 (keep the surrounding double quotes).

Wait 2 seconds, then verify startup:
```bash
cat data/daemon.pid 2>/dev/null
```

If no PID file appears, read `data/daemon.log` for errors and report them to the user.

---

## Step 4 — Confirm and start monitoring

Tell the user the application is running, then say:
> "Starting continuous monitoring — I'll surface any ERRORs or WARNINGs as they appear. Use `/app stop` to stop the app, or `/app report` for a full health report."

Then immediately start the monitoring loop by invoking:
```
/loop /app monitor
```
