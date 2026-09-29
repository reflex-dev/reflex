# The agent brief

Copy this into the campaign scratchpad (e.g. `$SB/AGENT_BRIEF.md`), fill the `<...>` placeholders,
and tell every test agent to read it first. It carries the rules that keep results trustworthy and
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

1. **NEVER install reflex (or any workspace package) from the local checkout at `<REPO>`.** No
   `uv sync`, no `uv run`, no `pip install -e`, no `uv pip install .` anywhere under it.
   Everything installs from PyPI. We are testing what users receive, not what the tree contains.
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
3. Reading the checkout is fine and encouraged — release source is on branch `<PRERELEASE_BRANCH>`.
   For PR context load the GitHub MCP tools via ToolSearch (`select:mcp__github__pull_request_read`).
4. Do NOT run any `git` write commands (add/commit/checkout/...) in the checkout. The orchestrator
   commits artifacts.
5. Do NOT fix bugs you find — record precise repro steps instead.
6. Kill every server and browser you start before you finish (track PIDs; verify with `ps`). Other
   agents share this machine — run at most ONE dev server at a time unless your cluster needs two.

### Environment

- Scratchpad root: `SB=<SCRATCHPAD>`
- **Prebuilt shared venv (READ-ONLY — never install into it):** `$SB/envs/<SHARED_VENV>` has
  `reflex==<VERSION>` and the alpha sub-packages. Use `$SB/envs/<SHARED_VENV>/bin/reflex` directly.
- Need other deps or versions? Make your OWN venv:
  ```
  uv venv $SB/envs/<yours> --python 3.11
  uv pip install --python $SB/envs/<yours>/bin/python --prerelease=allow 'reflex==<VERSION>' <extras>
  ```
  Always pass `--prerelease=allow` for alphas; PyPI is the default index — never point it at the
  checkout. Python 3.12/3.13/3.14 are available via `uv venv --python 3.14` etc.
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
- Node and bun are preinstalled. Enterprise apps need `CI=true` to bypass the dev login gate.
- App working dirs: `$SB/apps/<cluster>/...`. Run servers on YOUR ASSIGNED PORTS:
  `reflex run --frontend-port <FP> --backend-port <BP>`. The first run does a bun install (1–2 min);
  poll the frontend URL until it returns 200 for up to ~6 minutes before concluding failure.
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

If you see something surprising that is not on this list, investigate it — several real findings
have surfaced first as an unexplained warning.

### Deliverables (mandatory)

1. Copy reusable artifacts into the repo (plain `cp`/`rsync`, no git):
   `DEST=<ARTIFACT_ROOT>/<cluster>/`
   - the app source dirs, EXCLUDING `.web/`, `node_modules/`, `.states/`, `assets/external/`,
     `*.db`, venvs
   - your Playwright/repro scripts
   - `NOTES.md`: what you tested, how to rerun it (exact commands), what you observed, including
     benign quirks
2. Return structured findings: every discrete check as a test entry (pass/fail/anomaly/skipped)
   with enough repro detail that another agent can reproduce a failure from `NOTES.md` and your
   scripts alone, without your conversation. An "anomaly" is anything surprising (console error,
   warning, traceback, visual glitch, perf cliff) even when functionality works.

### Timeboxing

Be thorough but keep moving: if one sub-test resists debugging for ~10 minutes, record it as an
anomaly with logs attached and continue. Finishing the whole cluster beats perfecting one test.
