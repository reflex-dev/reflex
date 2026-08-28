# 0.9.9a2 framework re-verification — NOTES

Re-verification of the 0.9.9a1 framework defects against **reflex 0.9.9a2** (PyPI,
published 2026-08-28). PyPI-only installs; never from the checkout. Every repro
asserts `reflex.__file__` resolves into a venv `site-packages` before running, and
all Python was run from a neutral cwd (never `/home/user/reflex`, whose `reflex/`
shadows site-packages).

Versions under test: reflex 0.9.9a2, reflex-base 0.9.9a2, reflex-components-core 0.9.9a2.
Venvs: `$SB/envs/smoke2` (py3.11, prebuilt read-only) and `$SB/envs/a2_312` (py3.12,
`uv pip install --prerelease=allow 'reflex==0.9.9a2'`). Driver venvs reused:
`$SB/envs/driver` (Playwright), `$SB/envs/client_error_drv` (python-socketio+aiohttp).
Chromium at `/opt/pw-browsers/chromium`. Reserved ports frontend 3140-3143 /
backend 8140-8143.

Outcome: **ALL 11 items VERIFIED-FIXED.**

## Environment note (not a framework issue)
The npm registry tunnel (`registry.npmjs.org`) was heavily congested during this run
(hundreds of `ws_closed_mid_exchange` failures), so fresh `reflex run` frontend installs
repeatedly failed/stalled on manifest fetches. Worked around by: (a) retrying (pep695app
came up on a retry once its bun cache warmed), and (b) reusing pep695app's completed
`.web/node_modules` for other apps. This is purely an egress-proxy/registry-load artifact,
not an a2 regression.

## How to rerun each item (from a neutral cwd, e.g. `$SB/apps/reverify_fw`)

- **Item 1 (FINDING-002/006, PEP695 alias)** — py3.12 venv.
  - offline: `$SB/envs/a2_312/bin/python repros/repro_alias_setattr.py`  (all 4 alias setattrs OK)
  - offline: `$SB/envs/a2_312/bin/python repros/repro_alias_event_arg.py` (uncalled handlers no longer crash)
  - E2E: run `apps/pep695app` (`reflex run --frontend-port 3140 --backend-port 8140`), then
    `$SB/envs/driver/bin/python repros/item1_drive_pep695.py http://localhost:3140/ shots/pep695_a2`.
    The app binds `on_change=AliasState.choose_key` **uncalled** (the exact a1 compile-crash shape).
- **Item 2 (FINDING-004, client_error no-arg)** — backend-only a2 app at `--loglevel debug`;
  `$SB/envs/client_error_drv/bin/python repros/item2_client_error.py http://localhost:8140`.
  Grep the server log: `TypeError|missing 1 required positional|Task exception` must be 0;
  `malformed client_error payload` debug drops = 5.
- **Item 3 (FINDING-007, upload all-dots)** —
  - offline: `$SB/envs/smoke2/bin/python -c "from reflex_components_core.core._upload import _sanitize_upload_filename as s; print(s('..'), s('./../.'), s('/..'))"` → all `upload`.
  - live: added `upload_probe(files: list[rx.UploadFile])` to pep695app's state and touched
    `.web/backend/upload_is_used` to register `/_upload` without rendering `rx.upload` (avoids the
    flaky react-dropzone install); then
    `$SB/envs/client_error_drv/bin/python repros/item3_upload_dotdot.py http://localhost:8140`.
    All cases → HTTP 200; disk `uploaded_files/` holds only `upload` + `x.txt`; no `..` escape; 0 server 500s.
- **Item 4 (FINDING-027, backslash brackets)** —
  `$SB/envs/smoke2/bin/python repros/item4_compare_onsubmit.py 2>&1 | cat -A`.
  Warning prints `dict[str, typing.Any]` / `dict[str, str]` with **no** `\[`.
- **Item 5 (FINDING-011, node-shim hang)** —
  `apps/item5app` + `fakenode/node` (prints v22.12.0) first on PATH, `REFLEX_USE_NPM=1`,
  `timeout 90 reflex run ...`. Exits **1s / code 1** with the node-version error (a1: hung to 124).
- **Item 6 (FINDING-010, react-router-dom)** —
  `$SB/envs/smoke2/bin/python repros/item6_rrdom.py`. `library="react-router-dom"` raises an
  actionable `ValueError` naming the migration; `library="react-router"` builds+renders.
- **Item 7 (FINDING-012/015/019 + 028, vite warnings)** — `reflex export` on the built pep695app
  (`logs/item7_export.log`). No `Invalid input options`/`jsx`, no `advancedChunks`, no safari-cachebust
  configLoader warning. Generated `.web/vite.config.js` line 4 imports `./vite-plugin-safari-cachebust.js`
  (with `.js`), uses `codeSplitting`, no `jsx:` key (all landed via PR #6959, in the a2 changelog).
- **Item 8 (FINDING-005, granian full logging)** — backend-only with `REFLEX_ENABLE_FULL_LOGGING=1`
  `REFLEX_LOG_FILE=<f>`; dispatch a worker event via `repros/item8_dispatch.py`. Worker `reflex_base`
  records land in the file (a1: 0); with `--json` stdout is strictly JSON-lines (a1: non-JSON leaks).
- **Item 9 (PR #6994 interrupt window)** —
  `$SB/envs/smoke2/bin/python repros/item9_interrupt_window.py` (adapts the two
  `tests/units/utils/test_processes.py` regressions). Both PASS: SystemExit propagates in ~0.001s;
  no stray KeyboardInterrupt after a body exception.
- **Item 10 (changelog + shims)** — `git show v0.9.9a2:CHANGELOG.md` documents the on_load-bg
  cancellation (#6593), second-bare-`rx.App()` ReflexRuntimeError (#6382), and DECORATED_PAGES/
  bundled_libraries deprecation shims (#6985/#6967). Runtime shims verified:
  `$SB/envs/smoke2/bin/python repros/item10_shims.py` — bundled_libraries, DEFAULT_BUNDLED_LIBRARIES,
  DECORATED_PAGES, and `get_config(reload=True)` all now return a value + emit a DeprecationWarning
  (a1: bare AttributeError/TypeError/ImportError).
- **Item 11 (general smoke)** — `$SB/envs/driver/bin/python repros/item11_smoke_sweep.py
  http://localhost:3140/ shots/item11` against a running a2 dev app: 0 non-benign console
  errors/warnings, 0 page errors, 0 failed requests, 0 HTTP≥400; server log 0 tracebacks.

## Key evidence (logs/ in this dir)
- item1_setattr_a2.log, item1_eventarg_a2.log, item1_drive_a2.log
- item2_backend_debug.log (5 malformed drops, 0 TypeError)
- item3_backend.log (0 500s) — live upload saved `uploaded_files/{upload,x.txt}` only
- item4_onsubmit_a2.log (cat -A: no `\[`)
- item5_nodeshim.log (exit 1, "requires node version 22.22.0")
- item6_rrdom_a2.log, item7_export.log
- item8_full.log / item8_full_json.log (worker records present)
- item9_interrupt_a2.log (ALL-PASS), item10_shims_a2.log, item11_sweep.log (CLEAN)
