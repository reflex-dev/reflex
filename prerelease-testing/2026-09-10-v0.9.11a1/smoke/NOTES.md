# smoke — Phase 1 de-risk of reflex 0.9.11a1 (orchestrator, 2026-09-10)

Venv: `uv venv envs/smoke --python 3.11 && uv pip install --python envs/smoke/bin/python --prerelease=allow 'reflex==0.9.11a1'`
(run from a neutral cwd — see the `exclude-newer` trap in AGENT_BRIEF.md).

Resolved graph (all PyPI): reflex 0.9.11a1, reflex-base 0.9.11a1, radix 0.9.9a1, code 0.9.5a1,
moment 0.9.4a1, plotly 0.9.6a1, recharts 0.9.3a1, sonner 0.9.3a1, hosting-cli 0.1.72a1,
core 0.9.9, dataeditor 0.9.2, gridjs 0.9.1, lucide 1.0.4, markdown 0.9.3, react-player 0.9.2,
granian 2.8.2, python-socketio 5.16.4, starlette 1.6.0, wrapt 2.3.0. No pydantic/sqlmodel in the
bare install (0.9.9 optional-dependency change holds).

## Commands

```
cd apps/smoke && REFLEX_TELEMETRY_ENABLED=false envs/smoke/bin/reflex init --template blank --name smoke_app
REFLEX_TELEMETRY_ENABLED=false envs/smoke/bin/reflex run --loglevel debug --frontend-port 3050 --backend-port 8050
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 envs/driver/bin/python \
  /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py http://localhost:3050/ \
  --actions '[{"wait":1500},{"expect_text":"Welcome to Reflex"}]' --report logs/index.json
REFLEX_TELEMETRY_ENABLED=false envs/smoke/bin/reflex run --env prod --loglevel debug --frontend-port 3051 --backend-port 3051
```

## Observations

- `reflex init`: 4.9 s wall, 3 benign "Failed to connect to https://registry.npmmirror.com" lines.
- First `reflex run` (dev): reflex installed its own **Bun 1.4.0** to `~/.local/share/reflex/bun`
  (log: `[Bun 1.4.0 (Minimum: 1.4.0)]`, `[Node 22.22.2 (Minimum: 22.22.0)]`); `bun add` of the
  pinned packages; `reflex.lock/bun.lock` written with **`lockfileVersion: 2`** (matches the
  reflex-base changelog). Frontend answered 200 within ~5 s of the install finishing.
- Install log line worth a look (handed to the `frontend_pins` cluster):
  `warn: incorrect peer dependency "react@19.3.0"` while react is pinned 19.2.8 (logs/smoke_run.log:100).
- Generated `.web/package.json` (logs/web_package.json) carries the announced pins: react-router
  8.3.1, @react-router/node|dev|fs-routes 8.3.1, isbot 5.2.2, postcss 8.5.26, postcss-import 17.0.0,
  vite 8.2.2, sonner 2.0.8; tailwindcss/@tailwindcss/postcss held at 4.3.0; `overrides` is empty.
- `.web/utils/` now contains `context-registry.js` and `context.jsx` (PR #7071), no `context.js`.
- Dev page load: clean — 0 console messages, 0 page errors, 0 failed requests, 0 4xx/5xx
  (logs/index.json). Prod (`--env prod`, single port): also clean (logs/index_prod.json);
  build completed and served 200 within ~10 s; no vite/rolldown warnings in the prod log
  (logs/smoke_prod.log). Split ports in prod mode exit with "In prod mode, frontend and backend
  must run on the same port" — present since 0.9.8, not a finding.
- CLI (from `/tmp`): `reflex --version` 0.134 s on 0.9.11a1 vs 0.662 s on 0.9.10.post2 (#7050);
  `component/cloud/deploy/run --help` all exit 0 via the lazy proxies; `reflex cloud apps list`
  off-TTY exits 1 with "Token is required for non-interactive mode." (#6917), same with `--json`.
- Published `reflex-enterprise==0.9.5` installs against reflex 0.9.11a1 (`envs/ent`) and every
  `reflex_enterprise.*` module imports except the `mcp`/`pytest` extras (expected without the
  extras). `grep` of the enterprise wheel found no use of names this train deprecates
  (`_load_config`) — `vars.py` reads bundled libraries through `RegistrationContext` with a
  `dynamic.bundled_libraries` fallback (the 0.9.9 breakage is fixed downstream).
- `reflex-otel==0.1.0a1`: absent from PyPI when the campaign started (see FINDINGS), published
  09:10 UTC; `envs/otel` installs it with reflex 0.9.11a1 (opentelemetry-api 1.44.0,
  instrumentation 0.65b0); `reflex_base.otel.enabled` is False by default and the
  `opentelemetry_instrumentor` entry point `reflex` is registered.
