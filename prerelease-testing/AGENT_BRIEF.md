# Agent brief — reflex pre-release pass (template)

The orchestrator copies this file to `prerelease-testing/runs/<run>/AGENT_BRIEF.md` at the start of a pass and fills in
every `<...>` placeholder (version, tag/commit, enterprise build, scratch root). Everything else applies as written.

**Read `prerelease-testing/runs/<run>/CAMPAIGN_STATE.md` first** (what shipped, what changed since the previous
release, which findings to re-verify, venvs, paths), then the README of your fixture area under
`prerelease-testing/fixtures/<area>/`.

You are one of several agents independently exercising the **published** reflex `<NEW>` pre-release train
(`<pre-release branch>` @ `<commit>` = tag `v<NEW>`) plus reflex-enterprise `<ENT_VERSION>` as a real-world user of
the framework. Part of your work RE-VERIFIES findings listed in `prerelease-testing/REGISTRY.md` against the new
packages (report fixed / still broken / changed, with evidence), and part HUNTS for new breakage in what changed since
the previous release. Reuse the fixtures in `prerelease-testing/fixtures/` (copy them to your scratch dir first) and the
records in `prerelease-testing/history/`. You REPORT issues; you never fix framework code. Work at the highest level of
rigor you can.

## HARD RULES

1. **NEVER install reflex (or any workspace package) from a local checkout** (`/home/user/reflex`, a worktree of it,
   or `/home/user/reflex-enterprise`). No `uv sync`, no `uv run` inside a checkout, no `pip install -e`, no
   `uv pip install .`, no `uv pip install git+...`. Everything installs from PyPI (or a user-supplied wheel file).
   We are testing what users receive, not what the tree contains.
2. **Never run python with a checkout as your working directory.** `<checkout>/reflex/` shadows the installed
   package, so `import reflex` silently picks up unreleased source. Run everything from a neutral directory under
   `$SB/apps/<item>/`, and start each repro/driver with an assertion naming the venv that runs it, e.g.
   ```python
   import os, reflex
   assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in reflex.__file__, reflex.__file__
   ```
   A guard that names the wrong venv fails every run and gets deleted, which leaves no guard at all.
3. Reading the checkouts is fine and encouraged: release source via `git show v<NEW>:<path>` / `git grep` (fetch tags
   first). PR context: GitHub MCP tools via ToolSearch (`select:mcp__github__pull_request_read`). Enterprise source:
   read the installed or unpacked wheel (its `demos/` are good sample apps — COPY them out before running).
4. Do NOT run any `git` write command (add/commit/checkout/stash/...). The orchestrator commits artifacts.
5. Do NOT fix bugs you find — record precise repro steps instead. Do not file issues or post anywhere.
6. Kill every server, redis, proxy and browser you start before you finish (track PIDs; verify with `ps` and a curl to
   your ports). Other agents share the machine — run at most ONE app server set at a time unless your item needs two.
   Delete your apps' `.web/` and `node_modules/` when you are done with them (disk is limited).
7. Never bind ports outside your item's range (see `fixtures/README.md`); never use 3000/8000.

## Environment

- Scratch root: `SB=<scratch dir>` (define it in every shell; put ALL temp files under `$SB/apps/<item>/`).
- **Venvs** (built by `prerelease-testing/scripts/bootstrap_envs.sh`; READ-ONLY — build your own for extra deps):
  - `$SB/envs/new` — `reflex[db]==<NEW>` (+ matching reflex-base). THIS is the version under test.
  - `$SB/envs/prev` — `reflex[db]==<PREV>`, the previous release: the baseline for "is this a regression".
  - `$SB/envs/ctrl-<X>` — positive controls: versions on which a finding you re-verify reproduced. Run the control
    FIRST; a re-verification without a reproducing control proves nothing.
  - `$SB/envs/new-ent` / `prev-ent` — + reflex-enterprise (offline wheel, or PyPI with `CI=true`) and
    `oidc-provider-mock`.
  - `$SB/envs/driver` — playwright, httpx, websockets, pip.
  Extra venvs: `cd $SB && uv --no-config venv --python 3.12 $SB/envs/<item>-<name>` then
  `cd $SB && uv --no-config pip install --python $SB/envs/<item>-<name>/bin/python --prerelease=allow 'reflex[db]==<NEW>' <extras>`.
  ALWAYS run `uv` with cwd=`$SB` and `--no-config` (the checkout's pyproject has an `exclude-newer` window that hides
  freshly published packages). `--prerelease=allow` also lets transitive deps resolve to pre-releases (e.g. a pydantic
  beta): pin `pydantic<X` for a user-like graph. Python 3.11–3.15 are available via `uv venv --python 3.1x`.
- **Browser:** `$SB/envs/driver/bin/python` with Playwright; Chromium at `/opt/pw-browsers/chromium`
  (`p.chromium.launch(executable_path="/opt/pw-browsers/chromium")`). A ready-made driver with console/network capture is
  `.claude/skills/prerelease-test/scripts/drive_app.py`. Chromium does not apply Playwright `extra_http_headers` to
  the websocket upgrade and rejects `Proxy-Authorization`: inject headers through a forwarding proxy
  (`fixtures/hydration` has one).
- **Proxy bypass on the CLIENT side only:** prefix curl/Playwright commands with
  `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` (curl: `--noproxy '*'`). Do NOT export those into the
  reflex server's environment — it breaks bun's package installs through the proxy, which looks like a framework bug.
- Set `REFLEX_TELEMETRY_ENABLED=false` for every reflex command. Enterprise apps need `CI=true` with the PyPI wheel.
- Node and bun are preinstalled. `redis-server` is installed: start your own on a port from YOUR backend range
  (`redis-server --port <BP+9> --save '' --appendonly no &`) and point the app at it with
  `REFLEX_REDIS_URL=redis://localhost:<BP+9>`. Prod with Redis runs 2×CPU+1 granian workers by default.
- Run servers on your ports: `reflex run --frontend-port <FP> --backend-port <BP>`. Prod (`--env prod`) serves both
  from ONE port: `--frontend-port <P> --backend-port <P>` with `REFLEX_API_URL=http://localhost:<P>`. A first run does a
  bun install (1–2 min); poll the frontend (curl 200) for up to ~6 minutes before concluding failure.
- `--loglevel debug` gives verbose server logs; redirect to a file and actually read it.
- `reflex-examples` is cloned at `$SB/downloads/reflex-examples` (commit recorded in `fixtures/upgrade/README.md`) —
  COPY an app out before running it.

## What "testing" means here

- Real-world exploration, not coverage filling. Combine the change with State vars, `rx._x.client_state`, `@rx.memo`,
  `rx.ComponentState`, `rx.foreach`/`rx.cond`, event chains, background tasks, multiple pages and navigation, dev AND
  prod, memory AND Redis. The original PR already tested the happy path.
- Drive the app in Chromium as a user would: click, type, navigate, upload, reload, open a second tab.
- On EVERY run inspect: the server log, browser console (errors AND warnings), failed requests / 4xx-5xx, websocket
  frames where relevant, and screenshots at key moments.
- Baselines make findings actionable: if behavior looks wrong, run `prev` (and the last 0.9.x stable when relevant).
  Only-on-new is a regression; both-versions is context. Say which, every time.

## Known-benign noise — do not report these as findings

- Browser console: the React Router "💿 Hey developer" HydrateFallback log, vite `connecting.../connected` lines, the
  React DevTools info line, a `/favicon.ico` 404 on apps without a favicon.
- `reflex init` logging "Failed to connect to https://registry.npmmirror.com" before falling back (report it only if the
  fallback fails); bun `incorrect peer dependency` warnings when the install completes.
- AG Grid / AG Charts unlicensed trial banners; the uv `UV_NATIVE_TLS` deprecation warning; the "Compiling 100% N+1/N"
  progress counter overshoot; granian's "more workers than CPU cores" warning and `[ERROR] Unexpected exit from worker`
  at shutdown.
- Everything listed as known in `prerelease-testing/fixtures/<area>/README.md` and as filed/open in `REGISTRY.md`
  (report only if it CHANGED).

If you see something surprising that is not on this list, investigate it — several real findings surfaced first as
an unexplained warning.

## Deliverables (mandatory)

1. Copy reusable artifacts into the repo (plain `cp`/`rsync`, no git): `DEST=<repo>/prerelease-testing/runs/<run>/<item>/`
   — app sources (EXCLUDING `.web/`, `node_modules/`, `.states/`, `reflex.lock/`, `*.db`, venvs, `__pycache__`), your
   drivers and probes, small trimmed logs and only the screenshots that are evidence for a finding (keep the item under
   ~2 MB), and `NOTES.md`: what you tested, exact rerun commands, what you observed (pass/fail/anomaly per check) and
   baseline results.
2. Your FINAL MESSAGE must be this structured report (the orchestrator parses it):
   ```
   CLUSTER: <item>
   SUMMARY: <2-4 sentences>
   ARTIFACTS: <DEST path>
   TESTS:
   - [pass|fail|anomaly|skipped] <name>: <details>
   REVERIFIED:
   - <ID>: fixed|still-broken|changed — <one line of evidence>
   ISSUES:
   - TITLE: <short title>
     SEVERITY: critical|high|medium|low
     REGRESSION: yes|no|unknown   (yes = the previous release behaves correctly)
     REPRO: <exact, self-contained steps/commands>
     EVIDENCE: <log excerpt / console error / screenshot path>
   NOT_COVERED: <what you could not get to and why>
   ```
   Every ISSUE must be reproducible by a stranger from `NOTES.md` plus your scripts alone.

## Timeboxing

If one sub-test resists debugging for ~10 minutes, record it as an anomaly with logs and continue. Finishing the item
beats perfecting one test. Copy artifacts into DEST as you go and write NOTES.md incrementally.
