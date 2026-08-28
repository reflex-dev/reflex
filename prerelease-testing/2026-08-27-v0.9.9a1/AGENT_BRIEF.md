# Reflex 0.9.9a1 pre-release testing — shared agent brief

You are one of several agents independently exercising the reflex 0.9.9a1 pre-release
(published 2026-08-27) as a real-world user of the framework. Your job: build small sample
apps / repro scripts for your assigned feature cluster, run them END-TO-END (real server,
real Chromium browser), and hunt for anomalies. You REPORT issues; you never fix framework
code.

## HARD RULES

1. **NEVER install reflex (or any workspace package) from the local checkout at
   /home/user/reflex.** No `uv sync`, no `uv run`, no `pip install -e`, no `uv pip install .`
   anywhere under /home/user/reflex. Everything you install comes from PyPI.
2. Reading the checkout source is fine and encouraged (branch
   `origin/r/pre-2026.08.27-33148999938` has the release source; use `git show` or read the
   working tree, which is close). PR descriptions: load GitHub MCP tools via ToolSearch
   (e.g. `select:mcp__github__pull_request_read`) — repo `reflex-dev/reflex` only.
3. Do NOT run any `git` write commands (add/commit/checkout/etc.) in /home/user/reflex.
   The orchestrator commits artifacts.
4. Do NOT fix bugs you find — record precise repro steps instead.
5. Kill every server/browser process you started before you finish (track PIDs; verify with
   `ps`). Other agents share this machine (4 CPUs, 15GB RAM) — run at most ONE dev server
   at a time unless your cluster requires two simultaneously.

## Environment

- Scratchpad root: `SB=/tmp/claude-0/-home-user-reflex/20b6ffc8-8244-5bac-b158-8501871b3811/scratchpad`
- **Prebuilt shared venv (READ-ONLY — never pip install into it):** `$SB/envs/smoke`
  has `reflex==0.9.9a1` + all alpha subpackages on Python 3.11. Use `$SB/envs/smoke/bin/reflex`
  / `.../bin/python` directly.
- Need extra Python deps or different versions? Make your OWN venv:
  `uv venv $SB/envs/<yours> --python 3.11 && uv pip install --python $SB/envs/<yours>/bin/python --prerelease=allow 'reflex==0.9.9a1' <extras>`
  (add `--prerelease=allow` always; PyPI is the default index — do not point it at the checkout).
  Python 3.14.7 and 3.12/3.13 are available via `uv venv --python 3.14` etc.
- **Playwright driver venv:** `$SB/envs/driver/bin/python` (playwright, httpx, websockets
  installed). Chromium executable: `/opt/pw-browsers/chromium`. Launch with
  `p.chromium.launch(executable_path="/opt/pw-browsers/chromium")`, headless default.
  Example driver: `$SB/drive_smoke.py`.
- Local HTTP needs proxy bypass: prefix commands with `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1`
  (curl: use `--noproxy '*'`).
- Set `REFLEX_TELEMETRY_ENABLED=false` for every reflex command.
- Node v22.22.2, bun 1.3.11 available. `reflex init` probes registry.npmmirror.com and logs
  3 "Failed to connect" lines — known-benign here (proxy blocks that mirror), don't report it
  again, but DO report if the fallback fails.
- App working dirs: `$SB/apps/<cluster>/...`. Init apps there (`reflex init --template blank`),
  run servers with YOUR ASSIGNED PORTS: `reflex run --frontend-port <FP> --backend-port <BP>`.
  First `reflex init`/run does a bun install (~1-2 min); poll the frontend URL until 200
  (up to ~6 min) instead of assuming failure. Server logs: redirect to a file and read it.
- `--loglevel debug` gives verbose server logs; check them for tracebacks/warnings.

## What "testing" means here

- Real-world exploration, not coverage filling. Combine the feature with: State vars,
  `rx._x.client_state` (ClientStateVar), wrapping in `@rx.memo` components, `rx.ComponentState`,
  `rx.foreach`/`rx.cond`, event chains (`yield Other.handler()`), background tasks
  (`@rx.event(background=True)`), multiple pages/navigation — whatever plausibly interacts.
- Drive the app in Chromium via Playwright as a user would: click, type, navigate, upload.
- On EVERY run capture and inspect: (a) server log file, (b) browser console messages
  (errors AND warnings), (c) failed network requests / 4xx-5xx responses, (d) screenshots
  at key moments. Known-benign console lines you can ignore: the React Router
  "HydrateFallback" 💿 dev log, vite "connecting/connected" debug lines, React DevTools
  download info line. Anything else unexpected → investigate.
- Baseline comparisons are valuable: if behavior looks wrong, check whether reflex 0.9.8
  (stable) behaves differently (own venv: `uv pip install 'reflex==0.9.8'`). A regression
  vs 0.9.8 is a high-severity finding; "was always like this" is context.
- Prod mode matters too: `reflex run --env prod` compiles and serves the built frontend.
  If your feature could behave differently in prod (hydration, memoization, routing), test
  both when time permits.

## Deliverables (MANDATORY)

1. Copy reusable artifacts into the repo (plain `cp`, no git):
   `DEST=/home/user/reflex/prerelease-testing/2026-08-27-v0.9.9a1/<cluster>/`
   - the app source dir(s) — EXCLUDING `.web/`, `node_modules/`, `.states/`, `assets/external/`,
     `*.db`, venvs (e.g. `rsync -a --exclude .web --exclude node_modules --exclude .states appdir $DEST/`)
   - your Playwright/repro scripts
   - `NOTES.md`: what you tested, how to rerun, what you observed (including benign quirks)
2. Return structured findings via your final StructuredOutput: every discrete check as a
   test entry (pass/fail/anomaly/skipped) with enough repro detail that another agent can
   reproduce a failure from the NOTES.md + scripts alone, without your conversation.
   An "anomaly" is anything surprising (console error, warning, traceback in server log,
   visual glitch, perf cliff) even if functionality works.

## Timeboxing

Be thorough but keep moving: if a single sub-test resists debugging for ~10 minutes,
record it as an anomaly with logs attached and continue. Prefer finishing the whole
cluster over perfecting one test.
