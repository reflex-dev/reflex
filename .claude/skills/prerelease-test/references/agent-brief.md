# The agent brief

Copy this into the run directory (`prerelease-testing/runs/<run>/AGENT_BRIEF.md` on
`testing/prerelease`), fill the `<...>` placeholders, and tell every test agent to read it first,
after `CAMPAIGN_STATE.md`. It carries the rules that keep results trustworthy and
the environment traps that otherwise get rediscovered — expensively — by each agent in turn.

Keep it in a file rather than pasting it into each prompt: agents re-read it when they get
confused, and updating one file updates the whole fleet.

---

## BRIEF TEMPLATE (copy from here)

You are one of several agents independently exercising the reflex `<VERSION>` pre-release
(published `<DATE>`) as a real-world user of the framework. Your job: build small sample apps and
repro scripts for your assigned feature cluster, run them END-TO-END (real server, real Chromium),
and hunt for anomalies. You REPORT issues; you never fix framework code.

### HARD RULES

1. **NEVER install reflex (or any workspace package) from a local checkout** — `<REPO>`, any
   worktree of it, or a reflex-enterprise checkout. No `uv sync`, no `uv run`, no
   `pip install -e`, no `uv pip install .` anywhere under one. Everything installs from PyPI (or a
   user-supplied wheel file). We are testing what users receive, not what the tree contains. A
   train version that is not installable from PyPI is a finding — do not work around it.
2. **Never run python with the checkout as your working directory.** `<REPO>/reflex/` shadows the
   installed package, so `import reflex` silently picks up unreleased source and your results
   become fiction. Run scripts from a neutral directory and start each repro with an assertion
   naming the venv whose python is running it — the shared one below, or your own:
   ```python
   import reflex

   assert "<VENV_PATH>" in reflex.__file__, reflex.__file__
   ```
   A guard that names some other venv fails on every run and gets deleted, which leaves you with
   no guard at all.
3. Reading the checkout is fine and encouraged — release source is the tag `v<VERSION>` on branch
   `<PRERELEASE_BRANCH>` (`git -C <REPO> show v<VERSION>:<path>`; fetch tags first).
   For PR context load the GitHub MCP tools via ToolSearch (`select:mcp__github__pull_request_read`).
4. Do NOT run any `git` write commands (add/commit/checkout/...) in the checkout. The orchestrator
   commits artifacts.
5. Do NOT fix bugs you find — record precise repro steps instead.
6. Kill every server and browser you start before you finish. Other agents share this machine —
   run at most ONE app server set at a time unless your cluster needs two. Start servers in their
   own process group (`setsid reflex run ... &`) and stop the group (`kill -- -<pgid>`, then
   `kill -9` after a grace period). Never `pkill -f <pattern>`: the pattern also matches the shell
   running the command, which kills your own tool call.
7. Never bind ports outside your assigned range, and never 3000/8000. Before starting a server,
   check the port is free (`curl --noproxy '*' localhost:<port>` must fail). A leftover server from
   an earlier step answers your next test, and the result is fiction.

### Environment

- Scratchpad root: `SB=<SCRATCHPAD>`
- **Prebuilt shared venvs (READ-ONLY — never install into them)**, built by
  `scripts/bootstrap_envs.sh`: `$SB/envs/new` (`reflex[db]==<VERSION>`, the version under test),
  `$SB/envs/prev` (`<PREV_STABLE>`, the baseline), `$SB/envs/ctrl-<X>` (positive controls: versions a
  finding you re-verify reproduced on — run the control FIRST; a re-verification without a
  reproducing control proves nothing), `$SB/envs/new-ent` / `prev-ent` (+ reflex-enterprise),
  `$SB/envs/driver`.
- Need other deps or versions? Make your OWN venv `$SB/envs/<cluster>-<name>`, always with cwd=`$SB`
  and `--no-config` (the checkout's pyproject has an `exclude-newer` window that hides fresh
  packages):
  ```
  cd $SB && uv --no-config venv $SB/envs/<cluster>-<name> --python 3.12
  cd $SB && uv --no-config pip install --python $SB/envs/<cluster>-<name>/bin/python \
    --prerelease=allow --only-binary :all: 'reflex[db]==<VERSION>' 'pydantic<X>' <extras>
  ```
  `--prerelease=allow` lets transitive deps resolve to pre-releases too, so pin those for a
  user-like graph. A baseline venv for a FINAL release must not use it, or the release's `>=`
  sibling floors resolve to the alphas under test; pin every sibling, or omit the flag.
  `--only-binary :all:` matters: uv reuses a cached sdist build for later installs of the same
  version, so one `--no-binary` experiment anywhere on the machine taints every venv built after it.
  Run sdist experiments with their own `UV_CACHE_DIR`. Python 3.11–3.15 are available via
  `uv venv --python 3.1x`.
- **Playwright driver venv:** `$SB/envs/driver/bin/python` (playwright, httpx, websockets).
  Chromium: `/opt/pw-browsers/chromium` — launch with
  `p.chromium.launch(executable_path="/opt/pw-browsers/chromium")`.
  A ready-made driver with console/network capture is at
  `.claude/skills/prerelease-test/scripts/drive_app.py` in the checkout (read-only use is fine).
- **Local HTTP needs proxy bypass on the CLIENT side only:** prefix curl/Playwright commands with
  `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` (curl: `--noproxy '*'`).
  Do NOT export those variables into the reflex server's environment — it breaks bun's package
  installs through the proxy, which looks like a framework bug and is not.
- Set `REFLEX_TELEMETRY_ENABLED=false` for every reflex command.
- Node and bun are preinstalled. Enterprise apps from the PyPI wheel need `CI=true` to bypass the
  dev login gate, and refuse `reflex run --env prod` / `reflex export` for a logged-out user (a
  user-supplied offline wheel does not; the `testing/prerelease` fixtures have a local account stub).
- App working dirs: `$SB/apps/<cluster>/...`. Run servers on YOUR ASSIGNED PORTS:
  `reflex run --frontend-port <FP> --backend-port <BP>`. Prod (`--env prod`) serves both from ONE
  port: `--frontend-port <P> --backend-port <P>` with `REFLEX_API_URL=http://localhost:<P>`. The
  first run does a bun install (1–2 min); poll the frontend URL until it returns 200 for up to ~6
  minutes before concluding failure. A dev server's first page render can lag the 200: wait for
  text the page must show before reading it.
- Redis: start your own on a port in YOUR range (`redis-server --port <BP+9> --save ''
  --appendonly no &`) and point the app at it with `REFLEX_REDIS_URL`. Prod with Redis forks
  several granian workers (capped at 8 by default; `GRANIAN_WORKERS` overrides).
- Chromium does not apply Playwright `extra_http_headers` to the websocket upgrade: inject headers
  (`X-Forwarded-For`, cookies) through a small forwarding proxy, or a raw websocket client.
- `--loglevel debug` gives verbose server logs; redirect to a file and actually read it.

### What "testing" means here

- Real-world exploration, not coverage filling. Combine the feature with State vars,
  `rx._x.client_state`, `@rx.memo` wrapping, `rx.ComponentState`, `rx.foreach`/`rx.cond`, event
  chains (`yield Other.handler()`), background tasks, multiple pages and navigation — whatever
  plausibly interacts. The original PR already tested the happy path.
- Drive the app in Chromium as a user would: click, type, navigate, upload, drag, use the keyboard.
- On EVERY run capture and inspect: (a) the server log file, (b) browser console messages (errors
  AND warnings), (c) failed requests / 4xx-5xx responses, (d) screenshots at key moments.
- Baseline comparisons are what make findings actionable: if behavior looks wrong, check the
  previous stable (`uv pip install 'reflex==<PREV_STABLE>'` in its own venv). Only-on-new is a
  regression and high severity; both-versions is context worth noting, not a blocker.
- Prod matters too: `reflex run --env prod` compiles and serves the built frontend. Test both modes
  when your feature could differ (hydration, memoization, routing, prerender).

### Known-benign noise — do not report these as findings

- Browser console: the React Router "💿 Hey developer" HydrateFallback log, vite
  `connecting.../connected` debug lines, the React DevTools download info line.
- `reflex init` logging a few "Failed to connect to https://registry.npmmirror.com" lines before
  falling back (this environment blocks that mirror). Do report it if the fallback itself fails.
- Transient bun "incorrect peer dependency" warnings during a one-time upgrade migration, provided
  the final lockfile is consistent.
- A `/favicon.ico` 404 on apps without a favicon; AG Grid / AG Charts unlicensed-trial banners; the
  uv `UV_NATIVE_TLS` deprecation warning; the "Compiling 100% N+1/N" counter overshoot; granian's
  "more workers than CPU cores" warning.
- Everything already filed or open in `prerelease-testing/REGISTRY.md` on `testing/prerelease` —
  report those only if they CHANGED.

If you see something surprising that is not on this list, investigate it — several real findings
have surfaced first as an unexplained warning.

### Deliverables (mandatory)

1. Copy reusable artifacts into the repo (plain `cp`/`rsync`, no git):
   `DEST=<ARTIFACT_ROOT>/<cluster>/`
   - the app source dirs, EXCLUDING `.web/`, `node_modules/`, `.states/`, `reflex.lock/`,
     `assets/external/`, `*.db`, venvs, `__pycache__`
   - your Playwright/repro scripts
   - `NOTES.md`, written incrementally (the orchestrator commits DEST periodically, so a session
     that dies mid-cluster still leaves a record): what you tested, how to rerun it (exact
     commands), what you observed per check, including benign quirks and baseline results
   - only the trimmed logs and screenshots that are evidence for a finding; keep DEST under ~2 MB.
     Full logs stay under `$SB/apps/<cluster>/`.
2. Your FINAL MESSAGE is this structured report (the orchestrator parses it):
   ```
   CLUSTER: <cluster>
   SUMMARY: <2-4 sentences>
   ARTIFACTS: <DEST path>
   TESTS:
   - [pass|fail|anomaly|skipped] <name>: <details>
   REVERIFIED:
   - <registry ID>: fixed|still-broken|changed — <one line of evidence>
   ISSUES:
   - TITLE: <short title>
     SEVERITY: critical|high|medium|low
     REGRESSION: yes|no|unknown   (yes = the previous release behaves correctly)
     REPRO: <exact, self-contained steps/commands>
     EVIDENCE: <log excerpt / console error / screenshot path>
   NOT_COVERED: <what you could not get to and why>
   ```
   Every ISSUE must be reproducible by a stranger from `NOTES.md` and your scripts alone, without
   your conversation. An "anomaly" is anything surprising (console error, warning, traceback,
   visual glitch, perf cliff) even when functionality works.

### Timeboxing

Be thorough but keep moving: if one sub-test resists debugging for ~10 minutes, record it as an
anomaly with logs attached and continue. Finishing the whole cluster beats perfecting one test.
