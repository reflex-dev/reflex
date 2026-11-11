# Preflight (orchestrator) — reflex 0.11.0a1

All commands run from `$SB` (=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad), never from the checkout.

| check | command | result |
|---|---|---|
| publish | `uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref v0.11.0a1` | 20/20 OK, wheel+sdist |
| venvs | `NEW_VERSION=0.11.0a1 PREV_VERSION=0.10.1 ENT_SPEC='reflex-enterprise[mcp]==0.9.11' bootstrap_envs.sh $SB --enterprise` | new/prev/new-ent/prev-ent/driver OK; prev all-final 0.10.1 |
| wheel sources | `check_wheel_sources.py --repo /home/user/reflex --base v0.10.1 --ref v0.11.0a1 --site-packages $SB/envs/new/lib/python3.12/site-packages` | PASS, 73 files identical (`wheel_sources.log`) |
| .pyi audit | `check_release_versions.py --specs > specs.txt && xargs audit_pyi.py --manifest-ref v0.11.0a1 < specs.txt` | PASS, 122 stubs (`audit_pyi.log`) |
| sdist rebuild | `$SB/sdist_check.sh` (UV_CACHE_DIR=$SB/uv-sdist-cache, --no-binary per pkg) | core 36/36, radix 65/65, code 2/2, lucide 1/1, reflex 3/3 (`sdist_check.log`) |
| blank dev | `reflex init --template blank; reflex run --frontend-port 3050 --backend-port 8050` + drive_app.py | clean; SIGINT to the CLI stopped bun/node/backend, ports freed |
| blank prod | `REFLEX_API_URL=http://localhost:3051 reflex run --env prod --frontend-port 3051 --backend-port 3051` | clean |

## Requires-Dist of the published reflex 0.11.0a1 (sibling floors)
- `reflex-base==0.11.0a1`; `reflex-components-core/-code/-radix>=0.11.0a1`.
- `reflex-components-lucide>=1.1.1` and `reflex-hosting-cli>=0.2.1`: below the train's 1.1.2a1 / 0.2.2a1, so an
  in-place `pip install -U reflex` keeps lucide 1.1.1 (no #7674 fix) and hosting-cli 0.2.1 (no #7670 fix).
  Maintainer decision for the final.
- radix 0.11.0a1: `reflex-base>=0.10.1`, `reflex-components-core>=0.10.1`; code 0.11.0a1: `>=0.10.0` floors.
- reflex-enterprise 0.9.11: `reflex[db]>=0.9.6`, requires_python `<4.0,>=3.10`.

## reflex-enterprise source
- Cloned at the user's request to `/home/user/reflex-enterprise` (HEAD `b9ec0a9`, tag `v0.9.11`) for upstream demos and
  tests. `REFLEX_ACCESS_TOKEN` is not in this container's environment; prod runs use the account stub.
