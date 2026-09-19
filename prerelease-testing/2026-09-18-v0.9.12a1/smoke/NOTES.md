# smoke — Phase 1 de-risk of reflex 0.9.12a1 (orchestrator, 2026-09-19)

Venv: `cd $SB && uv venv envs/shared --python 3.11 && uv pip install --python envs/shared/bin/python --prerelease=allow 'reflex==0.9.12a1' <every component alpha named explicitly>`
(the full spec list is in `../AGENT_BRIEF.md`). A bare `uv pip install --prerelease=allow 'reflex==0.9.12a1'` into a
fresh venv ALSO resolves every component alpha (checked with `--dry-run`: radix 0.9.10a1, core 0.9.10a1, code 0.9.6a1,
dataeditor 0.9.3a1, gridjs 0.9.2a1, markdown 0.9.4a1, plotly 0.9.7a1, recharts 0.9.4a1, sonner 0.9.4a1; moment 0.9.4,
lucide 1.0.4, react-player 0.9.2, hosting-cli 0.1.72 stable). Without a prerelease flag `reflex==0.9.12a1` is not found.

Resolved non-reflex highlights: granian 2.8.3, python-socketio 5.17.0, starlette 1.6.0, wrapt 2.3.0, redis 7.4.1,
rich 15.0.0, click 8.5.0, httpx 0.28.1. No pydantic/sqlmodel in the bare install.

## Commands (see `run_smoke.sh`)

```
cd apps/smoke && REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex init --template blank --name smoke_app
REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex run --loglevel debug --frontend-port 3050 --backend-port 8050
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py http://localhost:3050/ \
  --actions '[{"wait":2000},{"expect_text":"Welcome to Reflex"},{"click":"text=Docs"},{"wait":500}]' --report logs/dev_report.json
REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex run --env prod --loglevel debug --frontend-port 3051 --backend-port 3051
```

## Observations

- `reflex init`: exit 0, no errors (the usual npmmirror fallback lines).
- Dev: reflex installed its own **Bun 1.4.0** (`[Bun 1.4.0 (Minimum: 1.4.0)]`; the system bun 1.3.11 on PATH is below
  the minimum and is ignored), Node 22.22.2. Frontend answered 200 **10 s** after launch (bun install included).
  Page load: 0 console messages, 0 page errors, 0 failed requests, 0 4xx/5xx (`logs/dev_report.json`). `/ping` → "pong",
  `/_health` → 200.
- `.web/package.json` (`logs/web_package.json`): react 19.2.8, **react-router 8.4.0 / @react-router/node 8.4.0** (#7202),
  **mergician v2.0.2** (new base dependency from #6850), isbot 5.2.2, lucide-react 1.26.0, @radix-ui/themes 3.3.0,
  react-error-boundary 6.1.2, react-helmet 6.1.0, socket.io-client 4.8.3, sonner 2.0.8, universal-cookie 8.1.2; `overrides` empty.
- Dev install log: one `warn: incorrect peer dependency "react@19.3.0"` (react pinned 19.2.8) — same as the previous
  campaign, benign.
- Stopping the dev server with SIGTERM to the process group: the log ends with `Debug: error: script "dev" exited with
  code 143` (a debug-level line from bun) and `Info: Reflex app stopped.` — no "Starting frontend failed" error (#6981);
  the `dev_server_cli` cluster examines exit codes and orphaned processes in detail.
- Prod (`--env prod`, single port): built and served 200 **4 s** after launch; page clean (`logs/prod_report.json`);
  the "Built with Reflex" badge renders. No vite/rolldown warnings.
- All ports released after the run (no leftover `reflex run`/vite/granian processes).

Verdict: environment and the published train are healthy; fan-out unblocked.
