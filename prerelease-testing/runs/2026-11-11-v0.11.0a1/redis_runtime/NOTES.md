# redis_runtime — 0.11.0a1 (redis locks / redis-py 8 / bg-task cancel / hot reload / spawn)

## Status / resume here
- [setup] venvs built: `$SB/envs/redis_runtime-{stock,r7,py311,py311r7,drv}` (see Environment). App + drivers: in progress.

## Environment
- `SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`; ports fe 3220-3239, be 8220-8239, redis 8236-8239.
- A stock `pip install reflex==0.11.0a1` (no `--pre`) resolves **redis 8.1.0** (final), reflex-components-lucide 1.1.1,
  reflex-hosting-cli 0.2.1 (`pip --dry-run --report`, logs/pip_report.json). uv needs `--prerelease=allow` (reflex-base
  pre pin is transitive), which pulls **redis 8.2.0b1** (a beta) — that is what the shared `new` venv has. Users of
  `uv pip install --prerelease=allow` get a redis-py beta; pip users get 8.1.0.
- Venvs (all PyPI, `--only-binary :all:`, cwd=$SB, `--no-config`):
  - `redis_runtime-stock`: py3.12, reflex[db]==0.11.0a1, redis==8.1.0, lucide 1.1.1, hosting-cli 0.2.1 (= pip stock graph)
  - `redis_runtime-r7`: same + redis==7.4.1
  - `redis_runtime-py311`: py3.11.18, redis 8.1.0; `redis_runtime-py311r7`: py3.11, redis 7.4.1
  - `redis_runtime-drv`: python-socketio[asyncio_client], aiohttp, redis (raw socket.io load clients)
  - shared: `new` (redis 8.2.0b1), `prev` (0.10.1, redis 7.4.1), `driver` (playwright)
