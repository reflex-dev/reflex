# Reflex 0.9.11a1 pre-release testing — shared agent brief

You are one of several agents independently exercising the reflex 0.9.11a1 pre-release
(published to PyPI 2026-09-10) as a real-world user of the framework. Your job: build small
sample apps / repro scripts for your assigned feature cluster, run them END-TO-END (real
server, real Chromium browser), and hunt for anomalies. You REPORT issues; you never fix
framework code.

## HARD RULES

1. **NEVER install reflex (or any workspace package) from the local checkout at
   /home/user/reflex.** No `uv sync`, no `uv run`, no `pip install -e`, no `uv pip install .`
   anywhere under /home/user/reflex. Everything you install comes from PyPI.
2. **Never run python with the checkout as your working directory.** `/home/user/reflex/reflex/`
   shadows the installed package, so `import reflex` silently picks up unreleased source.
   Run scripts from a neutral directory (your `$SB/apps/<cluster>/` dir) and start each repro
   with an assertion naming the venv whose python runs it, e.g.
   ```python
   import reflex
   assert "/envs/smoke/" in reflex.__file__, reflex.__file__   # or "/envs/<yours>/"
   ```
3. Reading the checkout source is fine and encouraged: the release source is on branch
   `origin/r/pre-2026.09.10-34457666442` (`git -C /home/user/reflex show origin/r/pre-2026.09.10-34457666442:<path>`;
   the working tree on `claude/reflex-prerelease-testing-t0sd90` is very close to it).
   For PR context load GitHub MCP tools via ToolSearch (`select:mcp__github__pull_request_read`),
   repo `reflex-dev/reflex` (and `reflex-dev/reflex-enterprise` for enterprise clusters).
4. Do NOT run any `git` write commands (add/commit/checkout/stash/...) in /home/user/reflex.
   The orchestrator commits artifacts.
5. Do NOT fix bugs you find — record precise repro steps instead.
6. Kill every server/browser process you started before you finish (track PIDs; verify with
   `ps aux | grep -E 'reflex|vite|granian|bun|chrom'`). Other agents share this 4-CPU/15GB
   machine — run at most ONE dev server at a time unless your cluster needs two simultaneously.

## Environment

- Scratchpad root: `SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad`
- **Prebuilt shared venvs (READ-ONLY — never install into them):**
  - `$SB/envs/smoke` — `reflex==0.9.11a1` (reflex-base 0.9.11a1, radix 0.9.9a1, code 0.9.5a1,
    moment 0.9.4a1, plotly 0.9.6a1, recharts 0.9.3a1, sonner 0.9.3a1, hosting-cli 0.1.72a1),
    Python 3.11. Use `$SB/envs/smoke/bin/reflex` / `.../bin/python` directly.
  - `$SB/envs/base0910` — `reflex==0.9.10.post2` (the previous stable) for baselines.
  - `$SB/envs/ent` — `reflex==0.9.11a1` + `reflex-enterprise==0.9.5` (latest published).
  - `$SB/envs/otel` — `reflex==0.9.11a1` + `reflex-otel==0.1.0a1` + `opentelemetry-sdk` +
    `opentelemetry-exporter-otlp-proto-http`.
  - `$SB/envs/driver` — Playwright driver venv (playwright, httpx, websockets, python-socketio,
    aiohttp). Chromium: `/opt/pw-browsers/chromium`; launch with
    `p.chromium.launch(executable_path="/opt/pw-browsers/chromium")`.
- Need extra deps or other versions? Make your OWN venv:
  ```
  uv venv $SB/envs/<yours> --python 3.11
  uv pip install --python $SB/envs/<yours>/bin/python --prerelease=allow 'reflex==0.9.11a1' <extras>
  ```
  Always pass `--prerelease=allow` for the alpha. PyPI is the default index — never point it at
  the checkout. **Run every `uv pip install` with `cd $SB` (or your app dir) as cwd, never from
  /home/user/reflex:** uv reads the checkout's `pyproject.toml` `[tool.uv] exclude-newer`
  and silently filters out the freshly published alphas ("was filtered by `exclude-newer`"). Python 3.10/3.12/3.13/3.14 are available via `uv venv --python 3.14` etc.
  Transient "Request failed after 3 retries ... operation timed out" from uv is the proxy —
  retry the install once before concluding anything.
- **Ready-made driver with console/network capture:**
  `/home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py` (read-only use; run
  it with `$SB/envs/driver/bin/python`). Actions are JSON; see its docstring.
- **Local HTTP needs proxy bypass on the CLIENT side only:** prefix curl/Playwright commands
  with `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` (curl: `--noproxy '*'`).
  Do NOT export those into the reflex server's environment — it breaks bun's package installs
  through the proxy, which looks like a framework bug and is not.
- Set `REFLEX_TELEMETRY_ENABLED=false` for every reflex command.
- `redis-server`/`redis-cli` are installed (`/usr/bin/redis-server`). If your cluster needs
  redis, start your own instance on a port in YOUR range (`redis-server --port <BP+15> --save ''
  --daemonize no &`) and point the app at it with `REFLEX_REDIS_URL=redis://localhost:<port>`.
  Kill it when done.
- Python 3.10/3.12/3.13 are system interpreters, 3.14.7 via uv (`uv venv --python 3.14`).
- Node v22 (`/opt/node22/bin/node`) and a system bun 1.3.11 (`/root/.bun/bin/bun`) exist;
  reflex 0.9.11a1 installs and uses its OWN bun 1.4.0 under `~/.local/share/reflex/bun`.
  Enterprise apps need `CI=true` (or `CI=1`) to bypass the dev login gate.
- App working dirs: `$SB/apps/<cluster>/...`. Run servers on YOUR ASSIGNED PORTS only:
  `reflex run --frontend-port <FP> --backend-port <BP>`. First run does a bun install
  (1–2 min); poll the frontend URL until it returns 200 for up to ~6 min before concluding
  failure. `--loglevel debug` gives verbose logs; redirect to a file and actually read it.
  **Prod mode needs ONE port for both:** `reflex run --env prod --frontend-port <P> --backend-port <P>`
  (split ports exit with "frontend and backend must run on the same port" — pre-existing, not a finding).

## What "testing" means here

- Real-world exploration, not coverage filling. Combine the feature with: State vars,
  `rx._x.client_state` (ClientStateVar), `@rx.memo` wrapping, `rx.ComponentState`,
  `rx.foreach`/`rx.cond`, event chains (`yield Other.handler()`), background tasks
  (`@rx.event(background=True)`), multiple pages/navigation, dev AND prod
  (`reflex run --env prod`) — whatever plausibly interacts. The PR already tested the happy path.
- Drive the app in Chromium via Playwright as a user would: click, type, navigate, upload,
  use the keyboard, edit source files to trigger hot reload when HMR is in scope.
- On EVERY run capture and inspect: (a) the server log file, (b) browser console messages
  (errors AND warnings), (c) failed requests / 4xx-5xx responses, (d) screenshots at key
  moments.
- Baseline comparisons make findings actionable: if behavior looks wrong, check reflex
  0.9.10.post2 (`$SB/envs/base0910`). Only-on-new is a regression and high severity;
  both-versions is context worth noting, not a blocker. Always report which it is.

## Known-benign noise — do not report these as findings

- Browser console: the React Router "💿 Hey developer" HydrateFallback log, vite
  `connecting.../connected` debug lines, the React DevTools download info line.
- `reflex init` logging three "Failed to connect to https://registry.npmmirror.com" lines
  before falling back (this environment blocks that mirror). Report it if the fallback fails.
- Transient bun "incorrect peer dependency" warnings during a one-time upgrade migration,
  provided the final lockfile is consistent.
- `reflex-otel==0.1.0a1` was published ~17 minutes after the rest of the train (the first
  publish attempt failed; already recorded). It IS on PyPI now: `$SB/envs/otel` has
  reflex 0.9.11a1 + reflex-otel 0.1.0a1 + opentelemetry-sdk + the OTLP/HTTP exporter.

If you see something surprising that is not on this list, investigate it — several real
findings have surfaced first as an unexplained warning.

## Deliverables (MANDATORY)

1. Copy reusable artifacts into the repo (plain `cp`/`rsync`, no git):
   `DEST=/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/<cluster>/`
   - the app source dir(s) — EXCLUDING `.web/`, `node_modules/`, `.states/`, `assets/external/`,
     `*.db`, venvs. `rsync` is NOT installed here — use tar:
     `mkdir -p $DEST && tar -C $SB/apps/<cluster> --exclude=.web --exclude=node_modules --exclude=.states --exclude='assets/external' --exclude='*.db' --exclude=venv --exclude='*.pyc' -cf - appdir | tar -C $DEST -xf -`
   - your Playwright/repro scripts, logs (trimmed to what matters), screenshots
   - `NOTES.md`: what you tested, exact rerun commands, what you observed (including benign
     quirks), and for every issue: repro steps, evidence file paths, regression status.
2. Return structured findings via StructuredOutput: every discrete check as a test entry
   (pass/fail/anomaly/skipped) with enough repro detail that another agent can reproduce a
   failure from NOTES.md + scripts alone. An "anomaly" is anything surprising (console
   error, warning, traceback, visual glitch, perf cliff) even if functionality works.

## Timeboxing

Be thorough but keep moving: if one sub-test resists debugging for ~10 minutes, record it as
an anomaly with logs attached and continue. Finishing the whole cluster beats perfecting one
test.
