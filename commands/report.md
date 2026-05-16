Generate a health report for the monitored application session.

Read all data files and render the report below. If a file doesn't exist, show "No data" for that section.

---

## Step 1 — Daemon status

Run:
```bash
app-monitor-daemon status
```

Show whether the app is currently running or stopped.

---

## Step 2 — Crash summary

Run:
```bash
cat data/crashes.jsonl 2>/dev/null
```

Parse the JSONL (one JSON object per line). Report:
- Total crash count
- For each of the 3 most recent crashes: timestamp, exit code, and the last 5 lines of output

If no crashes, say "No crashes recorded."

---

## Step 3 — Issues summary

Run:
```bash
cat data/issues_pending.jsonl data/issues_handled.jsonl 2>/dev/null
```

Parse both files combined. Report:
- Total ERROR count and total WARN count
- 5 most recent ERRORs (timestamp + message)
- 5 most recent WARNs (timestamp + message)

If none, say "No issues recorded."

---

## Step 4 — Performance metrics

Run:
```bash
cat data/metrics.jsonl 2>/dev/null
```

Parse the JSONL. Compute and show:
- Session duration (first timestamp → last timestamp in the file)
- Average CPU%, peak CPU%
- Average memory (MB), peak memory (MB)

If fewer than 2 samples exist, say "Insufficient metric data."

---

## Step 5 — Log tail

Run:
```bash
tail -20 data/app.log 2>/dev/null
```

Display the last 20 lines of application output under a "Recent log output" heading.

---

Render everything as a clean, readable markdown report with section headers.
