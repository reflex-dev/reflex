# a3_preflight — publish, metadata, packaging, smoke, N-001 (orchestrator)

SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad, W=$SB/apps/a3_preflight. Run from the repo root
for the two skill scripts (they only read git and PyPI); everything else from W.

| check | result | evidence |
|---|---|---|
| all 20 train packages on PyPI (wheel+sdist) at `555b667c1` | pass (reflex/reflex-base 0.10.0a3 appeared 19:52 UTC, after the publish approval) | `logs/01-check_release_versions.txt` |
| `.pyi` audit (wheel vs sdist, counts vs `pyi_hashes.json`, no foreign stubs) | pass, 122 stubs | `logs/02-audit_pyi.txt` |
| published metadata | reflex 0.10.0a3 pins `reflex-base==0.10.0a3` exactly; `db` extra = alembic, `greenlet>=3.3`, pydantic, `sqlmodel>=0.0.24`; Requires-Python `>=3.11,<4.0` | `out/metadata.txt` |
| N-001: fresh `reflex[db]==0.10.0a3` (+`pydantic<2.14`), nothing added by hand, uv and pip × 3.11/3.12/3.13/3.14 | pass 8/8: sqlalchemy 2.1.4 + greenlet 3.5.6 resolve, `import reflex.model` OK | `logs/03-n001-fresh-installs.txt` |
| N-001 original repro: `greenlet_probe.py`, `reflex db init / makemigrations / migrate / makemigrations (noop)` on pip-3.12 and uv-3.14 | pass: `rx.Model` subclass created, every command exits clean, `note` table created, no-op makemigrations generates nothing | `logs/04-n001-db-cli.txt`, `apps/dbcli` |
| `rx.Model` CRUD in prod (pip-3.12 venv): add ×2, reload | pass: 2 rows, both rendered after reload; only console error is the favicon 404 of an app without assets (benign) | `logs/dbcli-prod.{log,json}` |
| blank-app smoke (`reflex init --template blank`, dev 3500/8500, prod single port 3501) on `$SB/envs/a3` | pass, drive_app RESULT clean in dev and prod; dev log has granian's known "Unexpected exit from worker-1" at shutdown (seen on every version in the a2 pass) | `logs/smoke312/` |

Enterprise 0.9.7a5: offline wheel vs PyPI wheel differ only in `constants.py` `IS_OFFLINE`; a4 → a5 = the `formatColumnDefs` guard.

## Rerun
```
cd /home/user/reflex
uv --no-config run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref 555b667c1
uv --no-config run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref 555b667c1 --specs > $SB/specs.txt \
  && xargs uv --no-config run --script .claude/skills/prerelease-test/scripts/audit_pyi.py --manifest-ref 555b667c1 < $SB/specs.txt
# N-001 fresh installs (per python / tool):
uv --no-config venv --python 3.14 $W/envs/db-uv-3.14 && uv --no-config pip install --python $W/envs/db-uv-3.14/bin/python --prerelease=allow 'reflex[db]==0.10.0a3' 'pydantic<2.14'
uv --no-config venv --seed --python 3.12 $W/envs/db-pip-3.12 && $W/envs/db-pip-3.12/bin/python -m pip install --pre 'reflex[db]==0.10.0a3' 'pydantic<2.14'
cp -r a3_preflight/apps/dbcli $W/dbcli-x && cd $W/dbcli-x && $W/envs/db-pip-3.12/bin/python -I <repo>/prerelease_testing/2026-10-07-a3/a3_preflight/scripts/greenlet_probe.py /envs/db-pip-3.12/ \
  && $W/envs/db-pip-3.12/bin/reflex db init && .../reflex db makemigrations --message init && .../reflex db migrate
# smoke:
SB=$SB a3_preflight/scripts/smoke.sh $SB/envs/a3 $W/smoke312 3500 $W/logs/smoke312
```
