# Reflex 0.9.12a1 pre-release testing — shared agent brief

You are one of several agents independently exercising the reflex **0.9.12a1** pre-release
(published to PyPI 2026-09-19 00:55 UTC; changelog dated 2026-09-18) as a real-world user of
the framework. Your job: build small sample apps / repro scripts for your assigned feature
cluster, run them END-TO-END (real server, real Chromium browser), and hunt for anomalies.
You REPORT issues; you never fix framework code.

## HARD RULES

1. **NEVER install reflex (or any workspace package) from the local checkout at
   /home/user/reflex.** No `uv sync`, no `uv run`, no `pip install -e`, no `uv pip install .`
   anywhere under /home/user/reflex. Everything you install comes from PyPI (or, for
   reflex-enterprise, the published wheel file named below — never the enterprise checkout).
2. **Never run python with the checkout as your working directory.** `/home/user/reflex/reflex/`
   shadows the installed package, so `import reflex` silently picks up unreleased source.
   Run scripts from a neutral directory (your `$SB/apps/<cluster>/` dir) and start each repro
   with an assertion naming the venv whose python runs it, e.g.
   ```python
   import reflex
   assert "/envs/shared/" in reflex.__file__, reflex.__file__   # or "/envs/<yours>/"
   ```
3. Reading the checkout source is fine and encouraged. The release source is on branch
   `origin/r/pre-2026.09.18-35410916948`
   (`git -C /home/user/reflex show origin/r/pre-2026.09.18-35410916948:<path>`); the working
   tree (branch `claude/upbeat-feynman-m41a1u` == `origin/main` 4cba00435) differs from it only
   by the changelog-materialization commits, so `grep`/`cat` in `/home/user/reflex` reads the
   release source. For PR context load GitHub MCP tools via ToolSearch
   (`select:mcp__github__pull_request_read`), repo `reflex-dev/reflex`
   (and `reflex-dev/reflex-enterprise` for enterprise clusters).
4. Do NOT run any `git` write commands (add/commit/checkout/stash/...) in /home/user/reflex.
   The orchestrator commits artifacts.
5. Do NOT fix bugs you find — record precise repro steps instead.
6. Kill every server/browser/redis process you started before you finish (track PIDs; verify
   with `ps aux | grep -E 'reflex|vite|granian|bun|chrom|redis'`). Other agents share this
   4-CPU/15GB machine — run at most ONE dev server at a time unless your cluster needs two
   simultaneously. Terminating `reflex run` can orphan the vite process and keep the port
   bound: after killing, check `ss -ltnp | grep <port>` and kill the leftover pid.

## Environment

- Scratchpad root: `SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad`
- **Prebuilt shared venvs (READ-ONLY — never install into them):**
  - `$SB/envs/shared` — Python 3.11, the full alpha train: reflex 0.9.12a1, reflex-base 0.9.12a1,
    reflex-components-code 0.9.6a1, -core 0.9.10a1, -dataeditor 0.9.3a1, -gridjs 0.9.2a1,
    -markdown 0.9.4a1, -plotly 0.9.7a1, -radix 0.9.10a1, -recharts 0.9.4a1, -sonner 0.9.4a1,
    plus the unchanged stables lucide 1.0.4, moment 0.9.4, react-player 0.9.2, hosting-cli 0.1.72.
    Use `$SB/envs/shared/bin/reflex` / `.../bin/python` directly.
  - `$SB/envs/prev` — `reflex==0.9.11.post1` (the previous stable, with its stable component
    packages) for baselines.
  - `$SB/envs/driver` — Playwright driver venv (playwright 1.63, httpx, websockets).
    Chromium: `/opt/pw-browsers/chromium`; launch with
    `p.chromium.launch(executable_path="/opt/pw-browsers/chromium")`.
- Need extra deps or other versions? Make your OWN venv (always from `cd $SB`, never from the
  checkout — uv reads the checkout's `pyproject.toml` `[tool.uv] exclude-newer` and silently
  filters out fresh alphas):
  ```
  cd $SB && uv venv $SB/envs/<yours> --python 3.11
  uv pip install --python $SB/envs/<yours>/bin/python --prerelease=allow \
      'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
      'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
      'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
      'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
      'reflex-components-sonner==0.9.4a1' <extras>
  ```
  Always pass `--prerelease=allow` and NAME the component alphas explicitly: reflex pins
  reflex-base exactly but the component packages only by floor, so a bare
  `reflex==0.9.12a1` install (or an in-place `--upgrade` of an old venv) can leave stable
  component packages behind and you would be testing new core against old components. Check
  with `uv pip freeze --python ... | grep reflex` and record it in NOTES.md.
  The `UV_NATIVE_TLS is deprecated` warning from uv is benign. Transient
  "Request failed after 3 retries ... operation timed out" from uv is the proxy — retry once.
  Python 3.10/3.12/3.13 are system interpreters, 3.14.7 via uv (`uv venv --python 3.14`);
  `uv python install 3.15` may work if your cluster needs it.
- **Enterprise:** the published `reflex-enterprise==0.9.5` wheel is at
  `$SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl` — install it with
  `uv pip install --python <venv> --prerelease=allow 'reflex==0.9.12a1' <component alphas> $SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl`
  (for the MCP extra: `"reflex-enterprise[mcp] @ file://$SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl"`).
  It requires `reflex[db]>=0.9.6` so sqlmodel/alembic come along. The enterprise SOURCE
  checkout (demos live in `demos/`) is at `/home/user/reflex-enterprise` — copy demos out of
  it into `$SB/apps/<cluster>/`, never install from it. Enterprise apps need `CI=true` to
  bypass the dev login gate ("reflex-enterprise is free to use but you must be logged in").
- **reflex-examples** checkout: `/home/user/reflex-dev/reflex-examples` (copy apps out, never run in place).
- **Ready-made driver with console/network capture:**
  `/home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py` (read-only use; run
  it with `$SB/envs/driver/bin/python`). Actions are JSON; see its docstring. For anything
  beyond it, write your own Playwright script (sync API) that records console messages,
  page errors, failed requests, responses >= 400, and websocket frames when deltas matter.
- **Local HTTP needs proxy bypass on the CLIENT side only:** prefix curl/Playwright commands
  with `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` (curl: `--noproxy '*'`).
  Do NOT export those into the reflex server's environment — it breaks bun's package installs
  through the proxy, which looks like a framework bug and is not.
- Set `REFLEX_TELEMETRY_ENABLED=false` for every reflex command.
- `redis-server`/`redis-cli` 7.0 are installed. If your cluster needs redis, start your own
  instance on a port in YOUR range (`redis-server --port <BP+15> --save '' --daemonize no &`)
  and point the app at it with `REFLEX_REDIS_URL=redis://localhost:<port>`. Kill it when done.
- Node v22 (`/opt/node22/bin/node`) and a system bun 1.3.11 (`/root/.bun/bin/bun`) exist;
  reflex installs and uses its OWN bun under `~/.local/share/reflex/bun`.
- App working dirs: `$SB/apps/<cluster>/...`. Run servers on YOUR ASSIGNED PORTS only:
  `reflex run --frontend-port <FP> --backend-port <BP>`. First run does a bun install
  (1–2 min); poll the frontend URL until it returns 200 for up to ~6 min before concluding
  failure. `--loglevel debug` gives verbose logs; redirect to a file and actually read it.
  **Prod mode needs ONE port for both:** `reflex run --env prod --frontend-port <P> --backend-port <P>`
  (split ports exit with "frontend and backend must run on the same port" — expected, not a finding).
- Disk is a fixed allowance (~30 GB shared by everyone): delete `.web/` dirs and venvs you no
  longer need before you finish, and never keep more than a few apps' `node_modules` around.

## What "testing" means here

- Real-world exploration, not coverage filling. Combine the feature with: State vars,
  `rx._x.client_state` (ClientStateVar), `@rx.memo` wrapping, `rx.ComponentState`,
  `rx.foreach`/`rx.cond`/`rx.match`, event chains (`yield Other.handler()`), background tasks
  (`@rx.event(background=True)`), `rx.call_script` callbacks, multiple pages/navigation
  (client-side and direct load), dynamic routes, dev AND prod (`reflex run --env prod`) —
  whatever plausibly interacts. The PR already tested the happy path.
- Drive the app in Chromium via Playwright as a user would: click, type, navigate, upload,
  use the keyboard, open a second tab, reload, edit source files to trigger hot reload when
  HMR is in scope.
- On EVERY run capture and inspect: (a) the server log file, (b) browser console messages
  (errors AND warnings), (c) failed requests / 4xx-5xx responses, (d) screenshots at key
  moments, and when state deltas matter (e) the websocket frames.
- Baseline comparisons make findings actionable: if behavior looks wrong, check reflex
  0.9.11.post1 (`$SB/envs/prev`). Only-on-new is a regression and high severity;
  both-versions is context worth noting, not a blocker. Always report which it is.
- Verify perf claims rather than trusting them (measure delta bytes, render counts, RSS,
  timings) — a claim that does not hold is an anomaly worth recording with numbers.

## Known-benign noise — do not report these as findings

- Browser console: the React Router "💿 Hey developer" HydrateFallback log, vite
  `connecting.../connected` debug lines, the React DevTools download info line.
- `reflex init` logging a few "Failed to connect to https://registry.npmmirror.com" lines
  before falling back (this environment blocks that mirror). Report it if the fallback fails.
- Transient bun "incorrect peer dependency" warnings during a one-time upgrade migration,
  provided the final lockfile is consistent.
- uv's `UV_NATIVE_TLS ... deprecated` warning.
- In prod mode, split frontend/backend ports exiting with "must run on the same port".

If you see something surprising that is not on this list, investigate it — several real
findings have surfaced first as an unexplained warning.

## Deliverables (MANDATORY)

1. Copy reusable artifacts into the repo (plain `cp`/`tar`, no git):
   `DEST=/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/<cluster>/`
   - the app source dir(s) — EXCLUDING `.web/`, `node_modules/`, `.states/`, `assets/external/`,
     `*.db`, venvs, `reflex.lock/`. `rsync` is NOT installed — use tar:
     `mkdir -p $DEST && tar -C $SB/apps/<cluster> --exclude=.web --exclude=node_modules --exclude=.states --exclude='assets/external' --exclude='*.db' --exclude=venv --exclude='*.pyc' --exclude=__pycache__ --exclude=reflex.lock -cf - <appdir> | tar -C $DEST -xf -`
   - your Playwright/repro scripts, logs (trimmed to what matters, no multi-MB dumps),
     screenshots (PNG, a handful)
   - `NOTES.md`: what you tested, exact rerun commands (venv creation included), the resolved
     `uv pip freeze | grep reflex`, what you observed (including benign quirks), and for every
     issue: repro steps, evidence file paths, regression status vs 0.9.11.post1.
2. Return structured findings: every discrete check as a test entry (pass/fail/anomaly/skipped)
   with enough repro detail that another agent can reproduce a failure from NOTES.md + scripts
   alone, without your conversation. An "anomaly" is anything surprising (console error,
   warning, traceback, visual glitch, perf cliff, undocumented behavior change) even if
   functionality works. For each issue give a severity and say whether the previous stable
   behaves correctly (regression) — if you did not check the baseline, say so explicitly.

## Timeboxing

Be thorough but keep moving: if one sub-test resists debugging for ~10 minutes, record it as
an anomaly with logs attached and continue. Finishing the whole cluster beats perfecting one
test. Target 45–75 minutes of wall clock for a cluster.
