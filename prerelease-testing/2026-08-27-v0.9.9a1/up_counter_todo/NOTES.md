# up_counter_todo — upgrade testing counter + todo examples (0.9.8 -> 0.9.9a1)

Cluster: upgrade-path testing of two reflex-examples apps (`counter`, `todo`) from
reflex 0.9.8 (stable) to 0.9.9a1, in-place venv upgrade preserving `.web/` and
`reflex.lock/`, plus a cold fresh-`.web` run on 0.9.9a1. Date: 2026-08-28.

## Verdict

**No functional regressions found.** All user flows behave identically on 0.9.8 and
0.9.9a1 for both apps (warm-upgrade AND cold run). Screenshots are pixel-identical
(md5-equal) between versions. Two low-severity log-level anomalies noted below.

## Apps and flows tested

### counter (`counter/`) — ports 3100/8100
- initial render (count 0), Increment x2, Decrement, Randomize (+ verify 0..100),
  Decrement after randomize, color-mode toggle (light->dark), reload + rehydrate
  (count persists for the tab session).
- Result: all steps PASS on 0.9.8 baseline, 0.9.9a1 warm-upgraded, 0.9.9a1 cold.
- `counter-0.9.8-initial.png` vs `counter-0.9.9a1-initial.png`: identical md5.

### todo (`todo/`) — ports 3101/8101
- initial render (3 seed items), add via button, add via Enter, empty-submit no-op,
  add item with special chars (`Café <b>&amp;</b> 50%` — renders unescaped-as-text,
  correct), check-off (= remove) middle and first item, reload (items persist for the
  tab session).
- Result: all steps PASS on 0.9.8 baseline, 0.9.9a1 warm-upgraded, 0.9.9a1 cold.
- All three comparison screenshots (initial/added/after-finish) md5-identical
  between 0.9.8 and 0.9.9a1.

## Migration observations (first 0.9.9a1 run after in-place upgrade)

Both apps, from `logs/*-0.9.9a1-run1.log`:

- `.web/` is re-templated; lockfile restored from `<app>/reflex.lock/bun.lock`
  ("Restoring lockfiles"), then re-saved back to `reflex.lock/` after install.
- **react-router-dom pruning works**: `bun remove --legacy-peer-deps react-router-dom`
  runs, log shows "Removed: 1"; `react-router-dom` is gone from `.web/package.json`
  and from `reflex.lock/bun.lock` (0 stale `7.18.2` entries remain).
- Version bumps in package.json (see `logs/*-package.json.diff`):
  - `react-router`/`@react-router/node`/`@react-router/dev`/`@react-router/fs-routes`:
    7.18.2 -> 8.3.0
  - `vite`: 8.0.16 -> 8.2.0
  - everything else unchanged (react 19.2.8, radix themes 3.3.0, postcss 8.5.23
    including the `overrides.postcss` block — unchanged between versions).
- Cold run (rm -rf .web) converges to the exact same package.json (verified by
  normalized JSON diff) and needs no `bun remove` (lock already clean).
- bun/node handling: bun 1.3.11 + node 22.22.2 detected, no re-install attempted,
  no registry fallback issues on these runs (bun cache warm).

## Anomalies (low severity, not regressions in app behavior)

1. **Escaped-markup leak in console warning text (cosmetic log regression).**
   0.9.8 prints: `Event handler on_submit expects (dict[str, typing.Any]) -> () ...`
   0.9.9a1 prints: `... expects (dict\[str, typing.Any]) -> () but got (dict\[str, str]) ...`
   — literal backslashes before `[` leak into the terminal output (rich markup
   escaping applied to text that is then printed escaped). Repro: run the todo app
   (`State.add_item(self, form_data: dict[str, str])` bound to `on_submit`) on both
   versions and grep the server log for `on_submit expects`. The warning itself
   exists on both versions (todo app pre-existing); only the escaping is new.
2. **New vite warning on every 0.9.9a1 dev start** (debug loglevel, twice per start):
   `(!) Your Vite config uses features that are unsupported by configLoader: 'native'
   ... import "./vite-plugin-safari-cachebust" without a file extension
   (vite.config.js:4:35). Add the file extension`. Comes from the reflex web template
   after the vite 8.0.16 -> 8.2.0 bump. Harmless today, but the template import will
   break when vite makes `configLoader: 'native'` the default.
3. Transient `warn: incorrect peer dependency "react-router@7.18.2"` twice during the
   dev-deps install phase of the migration (dev deps `@react-router/dev@8.3.0` are
   installed while runtime `react-router` is still 7.18.2; the very next install step
   bumps it to 8.3.0 and the final `bun.lock` is consistent). Benign, order-of-install
   artifact; absent on cold runs.

Known-benign console lines observed on every run (both versions, ignore per brief):
React Router HydrateFallback 💿 log, vite connecting/connected debug, React DevTools
info line, "Disconnect websocket on page navigation" on reload.

WebSocket behavior identical across versions: one vite HMR socket + one
`/_event` socket.io socket; exactly one close/reopen pair on page reload; no
reconnect churn.

## How to rerun

```bash
SB=<this scratchpad>/apps/up_counter_todo   # or any fresh dir with these contents
cd $SB

# 1. venv on stable (per app; counter shown)
uv venv counter/venv --python 3.11
uv pip install --python counter/venv/bin/python -r counter/requirements.txt 'reflex==0.9.8'

# 2. baseline run + drive
cd counter && REFLEX_TELEMETRY_ENABLED=false \
  venv/bin/reflex run --frontend-port 3100 --backend-port 8100 --loglevel debug \
  > ../logs/counter-0.9.8-run1.log 2>&1 &
# poll http://localhost:3100/ until 200, then:
cd .. && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  <driver-venv>/bin/python counter_drive.py http://localhost:3100/ shots/counter-0.9.8 logs/counter-0.9.8-report.json

# 3. in-place upgrade (SAME venv, SAME dir — keeps .web/ and reflex.lock/)
uv pip install --python counter/venv/bin/python --prerelease=allow -U 'reflex==0.9.9a1'
# re-run server, watch first-run log for the bun remove/add migration, re-drive.

# 4. cold run: kill server (NOTE: also kill the `bun run dev` + node react-router
#    children — killing the reflex PID alone leaves the frontend serving), rm -rf .web,
#    re-run, re-drive.
```

Drivers: `counter_drive.py <url> <shot_prefix> <report.json>`,
`todo_drive.py <url> <shot_prefix> <report.json>` (Playwright, chromium at
/opt/pw-browsers/chromium). Reports are JSON: steps, console, failed requests,
4xx/5xx responses, websocket open/close events.

## Artifact map

- `counter/`, `todo/` — app sources incl. migrated `reflex.lock/` (no .web/venv)
- `counter_drive.py`, `todo_drive.py` — Playwright drivers
- `logs/*-report.json` — per-run step/console/network/ws reports (6 runs)
- `logs/*-run1.log`, `logs/*-coldrun.log` — full `--loglevel debug` server logs
- `logs/*-package.json.0.9.8|0.9.9a1`, `logs/*-package.json.diff` — before/after
- `logs/counter-reflex.lock-0.9.8/` — pre-upgrade lock dir snapshot (counter)
- `shots/` — screenshots (matching names across versions are md5-identical)
