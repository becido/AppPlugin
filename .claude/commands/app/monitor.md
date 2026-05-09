One monitoring cycle for the running application. Called automatically on each iteration of the monitoring loop started by `/app start`.

---

## Step 1 — Read pending issues

Run:
```bash
python scripts/daemon.py get-pending
```

This returns a JSON array of unacknowledged ERROR and WARN records. Each record has fields:
`id`, `timestamp`, `severity` (`"ERROR"` or `"WARN"`), `message`, `acknowledged`.

If the array is empty, skip to Step 3.

---

## Step 2 — Handle each pending issue

Read `data/config.json` for the `"error_pref"` and `"warn_pref"` keys (default `"ask"` if absent).

For **each** issue in the pending list, determine the preference based on its severity:
- `"ERROR"` → use `error_pref`
- `"WARN"` → use `warn_pref`

**If preference is `"auto_fix"`:**
- Read the relevant source files, locate the problem described by the message, and fix it using the Edit tool.
- Acknowledge this issue: note its `id` for Step 2b.

**If preference is `"ignore"`:**
- Acknowledge this issue without taking any action: note its `id` for Step 2b.

**If preference is `"ask"` (the default):**
- Present the issue to the user exactly like this:
  ```
  [SEVERITY] TIMESTAMP
  MESSAGE

  Would you like me to fix this?
    1. Yes — fix it now
    2. Yes, and auto-fix all future [ERRORs / WARNINGs] (don't ask again)
    3. No — skip
  ```
- Wait for the user's response:
  - **1 (Yes):** Fix the code, then note the `id`.
  - **2 (Yes + auto):** Fix the code, set the relevant preference to `"auto_fix"` by running:
    ```bash
    python scripts/daemon.py set-pref error_pref auto_fix
    ```
    (or `warn_pref` if it's a WARN), then note the `id`.
  - **3 (No):** Note the `id` without fixing.

### Step 2b — Acknowledge processed issues

After all issues are handled, acknowledge all by passing their IDs to:
```bash
python scripts/daemon.py acknowledge <id1> <id2> ...
```

---

## Step 3 — Check for new crashes

Run:
```bash
python scripts/daemon.py get-crashes
```

If the array is non-empty, alert the user:
```
The application crashed N time(s):
  - TIMESTAMP: exit code EXIT_CODE
    Last lines:
      <last 5 lines of output>
```

Then mark them reported:
```bash
python scripts/daemon.py mark-crashes-reported
```

---

## Step 4 — Done

This cycle is complete. The loop will call `/app monitor` again after a short interval.
If the user asks to stop monitoring, they should run `/app stop` or cancel the loop.
