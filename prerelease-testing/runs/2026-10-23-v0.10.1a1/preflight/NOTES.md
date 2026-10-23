# Preflight (orchestrator) — 0.10.1a1

Run from `$SB/preflight` (scripts copied from `.claude/skills/prerelease-test/scripts/` on main):

```
uv --no-config run --script check_release_versions.py --ref v0.10.1a1 --repo /home/user/wt-testing     # 20/20 OK
uv --no-config run --script check_release_versions.py --ref v0.10.1a1 --repo /home/user/wt-testing --specs > specs.txt \
  && xargs uv --no-config run --script audit_pyi.py --manifest-ref v0.10.1a1 --repo /home/user/wt-testing < specs.txt   # PASS, 122 stubs
NEW_VERSION=0.10.1a1 PREV_VERSION=0.10.0 ENT_SPEC='reflex-enterprise[mcp]==0.9.8' bash bootstrap_envs.sh "$SB" --enterprise
```

| check | result |
|---|---|
| publish (20 packages, wheel + sdist) | pass |
| `.pyi` audit | pass (`audit.log`) |
| reflex wheel pins | `reflex-base==0.10.1a1`; moment / radix `>=0.10.1a1`; core / code / dataeditor `>=0.10.0`; lucide `>=1.1.0` (mixed-floor install to be checked by `upgrade_packaging`) |
| changed source files tag vs installed `new` venv | 77/77 byte-identical (the 19 "missing" are unpublished workspace packages: components-internal, site-shared, workflow) |
| blank app dev (3100/8100) | clean; first page load in dev takes a few seconds (vite) — drive with `wait_for` |
| blank app prod (single port 3101) | clean, "Built with Reflex" badge present |
| `reflex init --template blank` | also writes `AGENTS.md` and `CLAUDE.md` into the app (check whether this is new since 0.10.0 — `upgrade_packaging`) |

Venvs (`bootstrap_summary.txt`): new / prev / new-ent / prev-ent all resolve sqlalchemy 2.1.6, greenlet 3.5.6, pydantic 2.14.1;
granian 2.8.5, starlette 1.9.0 in `new`.
