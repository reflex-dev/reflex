# Agent brief — reflex 0.10.0a3 train re-verification (2026-10-07, second pass)

**Read `/home/user/reflex/prerelease_testing/2026-10-07-a3/CAMPAIGN_STATE.md` first** (what shipped in the new train, which fixes target which findings, venvs, paths).

You are one of several agents independently exercising the **published** reflex `0.10.0a3` + reflex-base `0.10.0a3` pre-release
train (`r/pre-2026.10.06-37579583012` @ `555b667c1`, published 2026-10-07; every other package stays on its a2-train version) plus the user-supplied OFFLINE build of
`reflex-enterprise 0.9.7a5` (a wheel file; it bypasses the enterprise login gate) as a real-world user of the
framework. Many of your checks RE-VERIFY the must-fix findings of the 10-07 a2 pass against the new packages: for each,
report fixed / still broken / changed, with evidence, and ALSO look for new breakage the fixes may have introduced. Previous campaigns (reports under `/home/user/reflex/prerelease_testing/2026-10-05/`, `.../2026-10-06/` and `.../2026-10-07/` (the a2 pass whose findings you re-verify),
read-only — their apps, drivers and `verification/` scripts are yours to COPY and re-run) already covered a lot. Your job: build small
sample apps and repro scripts for your assigned cluster, run them END-TO-END (real server, real
Chromium), and hunt for anomalies. You REPORT issues; you never fix framework code. Work at the
highest level of rigor and thoroughness you can (extra-high effort).

## HARD RULES

1. **NEVER install reflex (or any workspace package) from the local checkout at `/home/user/reflex`
   or from `/home/user/reflex-enterprise`.** No `uv sync`, no `uv run` inside the checkout, no
   `pip install -e`, no `uv pip install .`, no `uv pip install git+...`. Everything installs from PyPI
   (the default index). We are testing what users receive, not what the tree contains.
2. **Never run python with either checkout as your working directory.** `/home/user/reflex/reflex/`
   shadows the installed package, so `import reflex` silently picks up unreleased source. Run
   everything from a neutral directory under your `$SB/apps/<cluster>/` work dir, and start each
   repro/driver with an assertion naming the venv whose python is running it, e.g.
   ```python
   import reflex
   assert "/scratchpad/envs/a3/" in reflex.__file__, reflex.__file__
   ```
   (adjust the venv name to the one you actually use). A guard that names the wrong venv fails every
   run and gets deleted, which leaves no guard at all.
3. Reading the checkouts is fine and encouraged — release source is on branch
   `origin/r/pre-2026.10.06-37579583012` (a3 = `555b667c1`, a2 = tag `v0.10.0a2`) of `/home/user/reflex` (use `git show <ref>:<path>` /
   `git grep`; the working tree is on a different branch). Enterprise release source is checked out
   read-only at `/home/user/reflex-enterprise` (branch `r/pre-2026.10.05`, older than a5: for a5 read the unpacked wheel at `$SB/downloads/enterprise_wheel_a5/x/`; its `demos/` are a good
   source of sample apps — COPY them out before running). For PR context load the GitHub MCP tools
   via ToolSearch (`select:mcp__github__pull_request_read`).
4. Do NOT run any `git` write commands (add/commit/checkout/stash/...) in either checkout. The
   orchestrator commits artifacts.
5. Do NOT fix bugs you find — record precise repro steps instead. Do not file issues or post anywhere.
6. Kill every server, redis and browser you start before you finish (track PIDs; verify with `ps` and
   `ss -ltnp`). Other agents share this 4-CPU machine — run at most ONE dev server (or one prod
   server) at a time unless your cluster explicitly needs two.
7. Never bind ports outside your reserved range; never use 3000/8000.

## Environment

- Scratchpad root: `SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`
  (define `SB=...` in every shell; put ALL temp files under `$SB/apps/<cluster>/`).
- **Prebuilt shared venvs (READ-ONLY — never install into them):**
  - `$SB/envs/a3` — Python 3.12, `reflex[db]==0.10.0a3` + `reflex-base==0.10.0a3` (other sub-packages at their a2-train
    versions), `reflex-hosting-cli==0.2.0a1`, `pydantic<2.14`; greenlet came in through the `db` extra (#7466), nothing
    was added by hand. THIS is the version under test. Use `$SB/envs/a3/bin/reflex` / `$SB/envs/a3/bin/python` directly.
  - `$SB/envs/a3-ent` — a3 + the OFFLINE `reflex-enterprise 0.9.7a5` wheel (`[mcp]`) + `oidc-provider-mock`.
    The wheel is at `$SB/downloads/enterprise_wheel_a5/reflex_enterprise-0.9.7a5-0offline-py3-none-any.whl` (unpacked
    copy for reading: `$SB/downloads/enterprise_wheel_a5/x/`); install it by file path (never `reflex-enterprise` from
    PyPI, never the /home/user/reflex-enterprise checkout).
  - `$SB/envs/a3-ent-a4` — a3 + the OLD offline 0.9.7a4 wheel (what a user who upgrades reflex but not enterprise gets).
  - `$SB/envs/s912-ent-a5` — reflex 0.9.12 + the a5 wheel (enterprise a5 still allows reflex >= 0.9.6).
  - `$SB/envs/alpha2` — Python 3.12, the PREVIOUS alpha (`reflex==0.10.0a2`, greenlet added by hand), for before/after
    comparisons of the a3 fixes. `$SB/envs/alpha2-ent` = alpha2 + the 0.9.7a4 wheel (if present on your machine).
  - `$SB/envs/stable` — Python 3.12, `reflex==0.9.12` + `reflex[db]` + greenlet (previous stable, for baselines).
  - `$SB/envs/driver` — playwright, httpx, websockets, pip (for `pip download`).
  On a machine without them, build them with `prerelease_testing/2026-10-07-a3/scripts/bootstrap_envs.sh $SB --enterprise`.
- Need other deps or versions? Make your OWN venv under `$SB/envs/<cluster>-<name>`:
  ```
  cd $SB && uv --no-config venv --python 3.12 $SB/envs/<yours>
  cd $SB && uv --no-config pip install --python $SB/envs/<yours>/bin/python --prerelease=allow 'reflex==0.10.0a3' 'reflex-base==0.10.0a3' <extras>
  ```
  ALWAYS run `uv` with cwd=`$SB` and `--no-config` (the checkout's pyproject has an `exclude-newer`
  window that would hide freshly published packages). Always pass `--prerelease=allow` for alphas
  (note: it also lets transitive deps resolve to pre-releases, e.g. pydantic 2.14.0b2 — if you want a
  user-like graph, pin `pydantic<2.14` or install the exact pins the cluster brief gives you).
  Python 3.11, 3.12, 3.13, 3.14 are available to `uv venv --python 3.1x` (3.10 is not supported by the 0.10 train).
- **Browser:** `$SB/envs/driver/bin/python` with Playwright; Chromium binary is
  `/opt/pw-browsers/chromium` — launch with `p.chromium.launch(executable_path="/opt/pw-browsers/chromium")`.
  A ready-made driver with console/network capture is
  `/home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py` (read-only use is fine;
  copy it if you want to extend it). Run drivers as
  `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python <driver> ...`.
- **Local HTTP needs proxy bypass on the CLIENT side only:** prefix curl/Playwright commands with
  `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` (curl: `--noproxy '*'`).
  Do NOT export those variables into the reflex server's environment — it breaks bun's package
  installs through the proxy, which looks like a framework bug and is not.
- Set `REFLEX_TELEMETRY_ENABLED=false` for every reflex command. Enterprise apps need `CI=true` to
  bypass the dev login gate.
- Node 22 and bun 1.4.2 are preinstalled on PATH. `redis-server` is installed: start your own on a
  port from YOUR backend range, e.g. `redis-server --port <BP+9> --save '' --appendonly no &`, and
  point the app at it with `REFLEX_REDIS_URL=redis://localhost:<BP+9>` (set `REFLEX_STATE_MANAGER_MODE=redis`
  is implied by the URL in prod). Kill it when done.
- App working dirs: `$SB/apps/<cluster>/...`. Run servers on YOUR ASSIGNED PORTS:
  `reflex run --frontend-port <FP> --backend-port <BP>`. Prod mode (`--env prod`) serves frontend and
  backend from ONE port: use `--frontend-port <P> --backend-port <P>` and set `api_url` in
  `rxconfig.py` accordingly (or `REFLEX_API_URL=http://localhost:<P>`). The first run of an app does a
  bun install (1–2 min); poll the frontend URL (curl, 200) for up to ~6 minutes before concluding failure.
- `--loglevel debug` gives verbose server logs; redirect to a file and actually read it.
- `reflex-examples` (upstream sample apps, commit `ebe19ff`) is cloned at `$SB/downloads/reflex-examples`
  — COPY an app directory out of it before running it (treat the clone as read-only data).
- Older campaigns' artifacts live at `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/` and
  `/home/user/reflex/prerelease-testing/2026-08-27-v0.9.9a1/` (read-only). Their `up_*`/`up_examples_*`
  directories contain Playwright drivers for many reflex-examples apps — reuse/adapt them freely
  (copy, don't edit in place).

## What "testing" means here

- Real-world exploration, not coverage filling. Combine the feature with State vars,
  `rx._x.client_state`, `@rx.memo` wrapping, `rx.ComponentState`, `rx.foreach`/`rx.cond`, event
  chains (`yield Other.handler()`), background tasks, multiple pages and navigation — whatever
  plausibly interacts. The original PR already tested the happy path.
- Drive the app in Chromium as a user would: click, type, navigate, upload, drag, use the keyboard,
  reload, open a second tab/context.
- On EVERY run capture and inspect: (a) the server log file, (b) browser console messages (errors
  AND warnings), (c) failed requests / 4xx-5xx responses, (d) websocket frames where relevant,
  (e) screenshots at key moments.
- Baseline comparisons are what make findings actionable: if behavior looks wrong, check the
  previous stable (`$SB/envs/stable`, reflex 0.9.12). Only-on-new is a regression and high severity;
  both-versions is context worth noting, not a blocker. Say which it is, every time.
- Prod matters too: `reflex run --env prod` compiles and serves the built frontend. Test both modes
  when your feature could differ (hydration, memoization, routing, prerender).

## Known-benign noise — do not report these as findings

- Browser console: the React Router "💿 Hey developer" HydrateFallback log, vite
  `connecting.../connected` debug lines, the React DevTools download info line, a `/favicon.ico` 404
  on apps without a favicon.
- `reflex init` logging a few "Failed to connect to https://registry.npmmirror.com" lines before
  falling back (this environment blocks that mirror). Do report it if the fallback itself fails.
- bun `incorrect peer dependency "react@19.3.0"` warnings during install, provided the install completes.
- AG Grid / AG Charts unlicensed trial banners in the console (enterprise demos).
- A `uv` warning about `UV_NATIVE_TLS` being deprecated.

If you see something surprising that is not on this list, investigate it — several real findings
have surfaced first as an unexplained warning.

## Deliverables (mandatory)

1. Copy reusable artifacts into the repo (plain `cp`/`rsync`, no git):
   `DEST=/home/user/reflex/prerelease_testing/2026-10-07-a3/<cluster>/`
   - the app source dirs, EXCLUDING `.web/`, `node_modules/`, `.states/`, `assets/external/`,
     `*.db`, `reflex.lock/`, venvs, `__pycache__`
   - your Playwright/repro scripts
   - trimmed logs (server logs with the interesting parts, console captures) and screenshots
     (keep the total under ~5 MB)
   - `NOTES.md`: what you tested, exact rerun commands (venv creation, app start, driver
     invocation, ports), what you observed (pass/fail/anomaly per check), including benign quirks,
     and baseline results where you ran one.
2. Your FINAL MESSAGE must be a structured report (it is parsed by the orchestrator):
   ```
   CLUSTER: <key>
   SUMMARY: <2-4 sentences>
   ARTIFACTS: <DEST path>
   TESTS:
   - [pass|fail|anomaly|skipped] <name>: <details>
   ...
   REVERIFIED:
   - F-00N: fixed|still-broken|changed — <one line of evidence>
   ...
   ISSUES:
   - TITLE: <short title>
     SEVERITY: critical|high|medium|low
     REGRESSION: yes|no|unknown   (yes = 0.9.12 behaves correctly)
     REPRO: <exact, self-contained steps/commands>
     EVIDENCE: <log excerpt / console error / screenshot path>
   ...
   NOT_COVERED: <what you could not get to and why>
   ```
   An "anomaly" is anything surprising (console error, warning, traceback, visual glitch, perf cliff)
   even when functionality works. Every ISSUE must be reproducible by a stranger from `NOTES.md`
   plus your scripts alone.

## Timeboxing

Be thorough but keep moving: if one sub-test resists debugging for ~10 minutes, record it as an
anomaly with logs attached and continue. Finishing the whole cluster beats perfecting one test.
Aim to finish within about 2 hours of wall-clock time.

## Interim artifacts

Copy artifacts into DEST as you go (after each sub-test), not only at the end: the orchestrator commits
the branch periodically and other people may read it while you work. Write NOTES.md incrementally.
