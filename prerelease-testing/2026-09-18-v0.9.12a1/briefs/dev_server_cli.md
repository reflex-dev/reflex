# Cluster `dev_server_cli` — SIGTERM (#6981), nocompile marker (#7089), backend port during reload (#7114), bun/npm lockfiles (#7129), local package specifiers (#7117), node-less crash / react-router 8.4 (#7202), JSON logs (#7193), deprecation logging (#7152), build-sdk logging (#7166), rxconfig reload (#7075), startup imports (#7049, #7112), hosting-cli 0.1.72

Changelog lines (verbatim):
- Stopping `reflex run` with SIGTERM no longer reports "Starting frontend failed with exit code 143" and now exits cleanly. (#6981)
- Backend-only development runs no longer leave a compile-skip marker that can cause the next full run to skip frontend compilation. (#7089)
- Keep the development backend port open while hot reload restarts the worker, so requests made during a reload wait for the new worker instead of being refused. (#7114)
- Fixed local package specifiers such as `@masenf/hello-react@../hello-react` and `@masenf/hello-react@../hello-react.tgz` being truncated at the first slash... (#7117)
- Switching between bun and npm (`REFLEX_USE_NPM`) no longer leaves `reflex.lock/` in a state that makes the next run fail with `bun install --frozen-lockfile: lockfile had changes`. Only the lockfile of the package manager that actually ran is kept. (#7129)
- Avoid crash when node is not installed (`error: restartWithMergedOptions() was called, but the process has already been restarted.`). (#7202) / (reflex-base) Bumped react-router to 8.4.0. (#7202)
- Emit Granian lifecycle logs as JSON records when Reflex JSON logging is enabled, keeping `reflex run --json` stdout valid JSON lines. (#7193)
- (reflex-base) Consolidate deprecation warnings behind the shared logging pipeline while preserving the public `console.deprecate` API. (#7152)
- (reflex-base) Route log records from the new `reflex-build-sdk` package through the Reflex logger, so they follow the configured log level and sinks. (#7166)
- (reflex-base) Keep the project-local modules imported by `rxconfig.py` when the config is reloaded from the same project root, so classes they define are not duplicated and states are not registered twice. (#7075)
- Reduce development startup and reload time and memory by deferring unused database, admin, and compiler imports in the backend launcher and state mutation tracking, and by avoiding redundant app preloads in spawned Granian supervisors. (#7049)
- (reflex-build-sdk 0.0.2) clients renamed `ReflexBuild`/`AsyncReflexBuild`/`ReflexBuildError`; reads `REFLEX_BUILD_BACKEND_URL`/`REFLEX_BUILD_URL` falling back to `REFLEX_CLOUD_*`. (#7201)

## Exercise (each item: 0.9.12a1 first, then 0.9.11.post1 where the entry claims a fix)

1. Signals: `reflex run` (dev) → `kill -TERM <pid>`: record exit code, time to exit, whether any
   "exit code 143" line appears, and whether vite/granian/bun children are gone and the ports free.
   Repeat with SIGINT, with `--backend-only`, with `--env prod`, and with SIGTERM to the process
   GROUP (as docker/systemd do). Baseline.
2. `reflex run --backend-only` then a normal `reflex run` → the frontend must be compiled fresh
   (edit a page between runs; the new text must appear). Inspect `.web/` for a `nocompile` marker
   after the backend-only run. Baseline.
3. Hot reload: run dev, start a `curl --noproxy '*' http://localhost:BP/ping` loop at 20 Hz,
   edit a state module to trigger a backend reload; count refused/failed requests and max latency;
   also keep a Playwright page open and send an event during the reload window. Baseline.
4. `REFLEX_USE_NPM=1 reflex run` (until 200), stop; plain `reflex run` (bun) → must not fail with
   "lockfile had changes"; inspect `reflex.lock/` contents after each run; then back to npm.
   Baseline (the previous campaign's FINDING-021 said one npm run converts a project permanently).
5. Local package: create `../hello-react/` (package.json `name: @masenf/hello-react`, `main`
   exporting a `Hello` component that renders its `children` and a `label` prop) and a `.tgz` of it
   (`bun pm pack`/`npm pack`); wrap it with `class Hello(rx.Component): library = "@masenf/hello-react@../hello-react"; tag = "Hello"`
   and the `.tgz` variant; run dev and prod; inspect `.web/package.json` for the full specifier.
   Baseline (expect truncation to `@..`).
6. Node-less: run with `PATH` stripped of every dir containing `node` (and `bun`) — does reflex
   install/handle it or error cleanly? No `restartWithMergedOptions` crash. Confirm `.web/package.json`
   has `react-router` 8.4.0 (and its `@react-router/*` siblings — record all versions).
7. `reflex run --json --loglevel debug` (dev and prod, backend-only too): capture stdout for 60 s
   including startup and a hot reload; parse EVERY line as JSON — list any non-JSON line. Also
   `reflex export --json`, `reflex init --json`. The previous campaign (FINDING-016) found 9 plain
   granian lines.
8. Deprecations: trigger `deps=["router"]`, a deprecated component/prop (find one via
   `grep -rn "console.deprecate" /home/user/reflex/reflex /home/user/reflex/packages/*/src | head`)
   and a user-code `from reflex_base.utils import console; console.deprecate(...)`: each should log
   ONCE per process at warning level, be suppressed by `--loglevel error`, and appear as a JSON
   record under `--json`. Check nothing double-logs.
9. Build SDK: own venv with `reflex-build-sdk==0.0.2` + the train; `from reflex_build_sdk import ReflexBuild, AsyncReflexBuild, ReflexBuildError`;
   do the OLD names still import (what error)? Instantiate with a bogus `REFLEX_BUILD_BACKEND_URL`
   pointing at a local port; make a call → the SDK's log records must appear through the reflex
   logger (configure `reflex` logging level) and not as duplicate root-logger output.
10. rxconfig reload (#7075): `rxconfig.py` imports a sibling `settings.py` that defines a State
    class and a module-level counter that logs its id; run dev, edit the app file to trigger a
    reload, check the log for duplicate registration warnings / a second import of `settings`.
11. Startup: `time` from `reflex run --backend-only` launch to `/ping` 200, and the backend
    worker's `sys.modules` (render `len(sys.modules)` and whether `sqlalchemy`, `alembic`,
    `starlette_admin`, `pandas`, `httpx` are present) on both versions; RSS of the backend worker.
12. `reflex cloud --help`, `reflex cloud apps list --json` and `reflex deploy --help` with no token,
    stdout piped: exit code and message (0.1.72 semantics: non-interactive refused with exit 1).

## Lead handed over from the `ent_map_dnd_flow_mantine` cluster (please baseline)

While iterating on an app in dev, a module that raised at page-evaluation time (a `TypeError` from a component
constructor, then an `AttributeError`) logged the traceback followed by `[ERROR] Unexpected exit from worker-1`,
and the backend did NOT come back after the source was fixed — the server had to be restarted by hand. Seen on
0.9.12a1, not baselined. Reproduce deliberately (introduce a page-evaluation error, save, fix, save) on both
versions and record whether the reload worker recovers; #7114 ("keep the backend port open while hot reload
restarts the worker") makes this path more visible. Related, both versions: when the app module raises at
import, `reflex run` still prints "Backend running at …" and keeps running with a dead backend.
