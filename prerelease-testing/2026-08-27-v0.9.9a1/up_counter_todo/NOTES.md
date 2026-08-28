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

## VERIFICATION (adversarial verifier, 2026-08-28)

Claim verified: **CONFIRMED** — genuine (cosmetic) regression in reflex 0.9.9a1
itself (reflex-base), not an env quirk, app bug, or enterprise issue.

Independent repro (fresh app dirs, PyPI installs only, no browser needed — the
warning is emitted at compile time):

```bash
SB=<scratchpad>; W=$SB/apps/verify_up_counter_todo_0
# copies of ./todo (this dir), reflex.lock removed from the 0.9.8 copy
cd $W/todo_a1 && REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run \
  --loglevel debug --frontend-port 3602 --backend-port 8602 > $W/a1-run.log 2>&1 &
# wait until 'on_submit expects' appears in the log, then kill (incl. bun/node children)
cd $W/todo_098 && REFLEX_TELEMETRY_ENABLED=false $SB/envs/base098/bin/reflex run \
  --loglevel debug --frontend-port 3602 --backend-port 8602 > $W/098-run.log 2>&1 &
```

Results (byte-verified with `grep ... | cat -A`, real backslash characters):

- 0.9.9a1 (`a1-run.log:73`): `Event handler on_submit expects (dict\[str, typing.Any]) -> () but got (dict\[str, str]) -> () ...`
- 0.9.8   (`098-run.log:72`): `Event handler on_submit expects (dict[str, typing.Any]) -> () but got (dict[str, str]) -> () ...`

Root cause (read from the installed 0.9.9a1 wheel and the release checkout,
`packages/reflex-base/src/reflex_base/event/__init__.py` ~lines 2023-2040):
`expect_string`/`given_string` are still built with `.replace("[", "\\[")` —
rich-markup escaping carried over from 0.9.8, where the message went through
`console.warn(...)` and rich consumed the `\[`. In 0.9.9a1 the call site was
migrated to the new logging pipeline (`logger.warning(...)` on
`logging.getLogger(__name__)`), and `reflex_base/utils/log.py`'s
`RichConsoleHandler.emit` prints with `markup=False` unless the record opts in
via `extra={"rich": True}` — this call does not, so the escapes print literally.
Cross-check: the `Debug: [timing] ...` lines in the same 0.9.9a1 log render
clean because the legacy `console._debug` shim path still opts into markup;
only this warning call site kept the escaping without the markup flag.

Fix direction for a fix-agent: drop the two `.replace("[", "\\[")` calls in
`reflex_base/event/__init__.py` (the message no longer passes through rich
markup), or pass `extra={"rich": True}` — the former is correct since the
strings contain user type reprs that should never be parsed as markup.

Refutations attempted: not an env quirk (reproduced in fresh dirs, both
versions, same machine/terminal-less file logging); not app misuse (the
`dict[str, str]` annotation legitimately triggers this intentional warning on
both versions — only the rendering differs); not pre-existing (0.9.8 output is
clean). Severity low/cosmetic: warning text remains readable, no functional
impact. Verifier repro logs: `<scratchpad>/apps/verify_up_counter_todo_0/{a1-run.log,098-run.log}`.

## VERIFICATION of anomaly 2 — vite configLoader:'native' warning (adversarial verifier, 2026-08-28)

Claim verified: **CONFIRMED** — genuine reflex 0.9.9a1 defect (reflex-base web
template), regression vs 0.9.8 in observable behavior. Low severity today
(warning only, dev server works), but the flagged import will hard-break when
vite makes `configLoader: 'native'` the default major.

Independent repro (working dir `<scratchpad>/apps/verify_up_counter_todo_1/`,
PyPI installs only):

- 0.9.9a1 (`envs/smoke`, todo app, `reflex run --loglevel debug` on 3604/8604,
  log `a1_todo_run.log`): warning block appears TWICE before "App running at";
  frontend serves HTTP 200. Matches the reporter's logs (2x per dev start).
- 0.9.8 (`envs/base098`, same todo app, same ports, log `v098_todo_run.log`):
  0 occurrences of `VITE_CONFIG_NATIVE_IGNORE_WARNING` / `configLoader`;
  app starts normally. Also corroborated by `verify_up_counter_todo_0/098-run.log`
  (0 hits) vs `.../a1-run.log` (4 hits).
- Note: a fresh `reflex init` + first run failed twice in this verification pass
  with bun `error: ConnectionClosed downloading package manifest ...` (shared
  proxy overloaded — environment issue, unrelated to the claim); the repro above
  therefore reuses the prebuilt `.web/` app copies (`todo_a1_copy/`, `todo_098_copy/`).

Root cause (byte-level proof):

1. The generated `.web/vite.config.js` line 4 is
   `import safariCacheBustPlugin from "./vite-plugin-safari-cachebust";`
   (no extension), emitted verbatim by
   `packages/reflex-base/src/reflex_base/compiler/templates.py:658` — identical
   in the installed 0.9.9a1 wheel and in the release branch
   `origin/r/pre-2026.08.27-33148999938`.
2. The SAME extensionless import exists in 0.9.8's wheel (its `templates.py:579`)
   — the template line is NOT new. What changed is the pinned vite version:
   `reflex_base/constants/installer.py` pins vite 8.0.16 in 0.9.8 vs 8.2.0 in
   0.9.9a1, and the warning code (`VITE_CONFIG_NATIVE_IGNORE_WARNING`) exists in
   vite 8.2.0's `dist/node/chunks/node.js` but nowhere in vite 8.0.16's dist.
   So: pre-existing template latent issue, surfaced as a new warning by the vite
   bump shipped in 0.9.9a1 — a real (cosmetic) regression vs 0.9.8.
3. Direct-cause A/B test (bypassing reflex recompile): running
   `bun run dev -- --port 3605` in `todo_a1_copy/.web` with the stock config
   prints the warning twice (`direct_stock.log`); after
   `sed 's|safari-cachebust"|safari-cachebust.js"|' vite.config.js` the warning
   is gone and the dev server still starts (`direct_fixed.log`, 0 hits).
4. Upstream already agrees: commit `522cf410a` ("Filter the react-dom/server
   resolveId hook and fix the config import extension", 2026-08-27 20:10 UTC,
   only on branch `origin/claude/reflex-docs-macos-timeout-d3ucaj` — NOT in the
   release) changes the template to `"./vite-plugin-safari-cachebust.js"`.

Fix direction for a fix-agent: add the `.js` extension in
`packages/reflex-base/src/reflex_base/compiler/templates.py:658` (or cherry-pick
522cf410a's template hunk).

Verifier log copies (this dir): `logs/verifier2-a1-todo-run.log` (2 hits),
`logs/verifier2-098-todo-run.log` (0 hits), `logs/verifier2-direct-stock.log`
(warning, stock config), `logs/verifier2-direct-fixed.log` (clean, `.js` added).

Refutations attempted: not an env quirk (reproduced from prebuilt app dirs, and
observed independently by several other clusters — e.g.
`prerelease-testing/.../registration_context/dynapp/run_dev.log`); not app-specific
(config line is template-generated, identical for counter/todo/blank apps); not
misuse (default `reflex run`); not pre-existing (0 hits on 0.9.8 in two
independent log sets). Visibility caveat: normally only surfaced at
`--loglevel debug` (vite stderr -> Debug lines), but it also prints un-prefixed
at default loglevel in frontend-failure dumps and via AppHarness runs, and it
appears in prod mode logs too (`registration_context/dynapp/run_prod.log`).

## VERIFICATION #2 — anomaly 3, transient peer-dep warnings (adversarial verifier, 2026-08-28)

Claim verified: **REFUTED as an actionable defect** (observation itself accurately
reproduced; classified benign-by-design, not something a fix-agent should act on).

Independent repro (fresh dirs, PyPI-only installs, counter app, ports 3608/8608,
logs in `logs/verify2-*.log` and `<scratchpad>/apps/verify_up_counter_todo_2/logs/`):

1. Fresh venv `reflex==0.9.8` (PyPI), `reflex run --loglevel debug` until frontend 200.
   Log `verify2-counter-0.9.8-run1.log` shows ONE `warn: incorrect peer dependency
   "react@19.2.8"` during its own first install — bun peer-dep warnings at debug
   loglevel are pre-existing on 0.9.8, not introduced by 0.9.9a1.
2. Kill server tree, `uv pip install --prerelease=allow -U reflex==0.9.9a1` into the
   SAME venv, keep `.web/` + `reflex.lock/` (lock still pins react-router 7.18.2).
3. Re-run: `verify2-counter-0.9.9a1-run1.log` lines 196/198 (same line numbers as the
   original report) show exactly TWO `warn: incorrect peer dependency
   "react-router@7.18.2"`, both inside the `bun add --legacy-peer-deps -d ...
   @react-router/fs-routes@8.3.0 @react-router/dev@8.3.0 vite@8.2.0` phase.
   Mechanism byte-confirmed: `@react-router/dev@8.3.0` declares peer
   `react-router: ^8.3.0` while the restored lockfile still resolves 7.18.2 at that
   instant; the very next `bun add ... react-router@8.3.0 @react-router/node@8.3.0`
   bumps it. Final state consistent: `.web/package.json` and `reflex.lock/package.json`
   both `react-router 8.3.0`, zero `7.18.2` strings in either bun.lock.
4. Cold-run control (`rm -rf .web`, same migrated lock): 0 warnings
   (`verify2-counter-0.9.9a1-coldrun.log`), matching the original coldrun logs.

Why refuted as a defect despite reproducing:

- The warnings are emitted by bun, printed only at `--loglevel debug` (never at
  default loglevel), only once — during the single migration run.
- Reflex runs every add with `--legacy-peer-deps`, i.e. peer conflicts are tolerated
  by design; bun's warn is informational and does not affect resolution.
- The dev-deps-before-runtime-deps order that creates the transient window is
  INTENTIONAL: `reflex/utils/js_runtimes.py` (~lines 752-754 in the release source)
  documents that dev deps must be added first so overlapping names land in
  `dependencies`. "Fixing" the warning by reordering would reintroduce the
  section-placement bug that ordering prevents.
- Not a regression in class: 0.9.8's own install already prints an
  `incorrect peer dependency` warning (react@19.2.8). The react-router-specific text
  is new only because 0.9.9a1 bumps react-router 7->8; any major dep bump would
  transiently produce the same one-time debug line during in-place migration.
- No functional impact: frontend serves 200, no tracebacks, final lock consistent,
  identical app behavior (per the original 6-run drive reports).

Conclusion: accurate observation, correctly rated benign by the original agent;
recommend recording as release-notes color only ("expect two one-time bun peer
warnings at debug loglevel when upgrading a 0.9.8 app in place"), no code change.
