# a5 preflight (orchestrator) — 2026-10-08

## Publish check
`uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref v0.10.0a5` (repo root): 20/20
packages OK with wheel + sdist; reflex 0.10.0a5 and reflex-base 0.10.0a5 are the only new versions. reflex-enterprise
0.9.7a5 is still the newest on PyPI. Tag `v0.10.0a5` = `57aee8ccf`; `git log v0.10.0a4..v0.10.0a5` = #7519, #7360, #7504,
the main merge `cc83bc04a` and the changelog commit.

## Wheel contents
- reflex 0.10.0a5 requires `reflex-base==0.10.0a5`.
- Every source file a5 changed in the published packages is byte-identical between `git show v0.10.0a5:<file>` and the
  installed a5 venv: `reflex_base/vars/base.py` (#7519), `reflex/istate/data.py`, `reflex/state.py` (#7360).
- #7504 touches only `reflex-components-internal`, which is not a published train package.

## Packaging audit
`check_release_versions.py --ref v0.10.0a5 --specs > specs.txt && xargs audit_pyi.py --manifest-ref v0.10.0a5 < specs.txt`
→ `audit_pyi.txt`: PASS, 122 stubs in both wheel and sdist, byte-identical, counts match, no foreign stubs.

## Changelogs (source at v0.10.0a5)
- reflex v0.10.0a5: Deprecations (#7360 `State.router.headers.cookie` / `["cookie"]` render ""; use `rx.Cookie`) and Bug
  Fixes (#7360 cookies + standard credential headers no longer sent to frontend router data; on-load events no longer
  copy request router metadata to the frontend). The a4 #7516 entry now reads `set_default(10)` (carried from #7519 by
  the main merge).
- reflex-base v0.10.0a5: Features (#7519 `Field.set_default`; mutable default copied when set and per instance; the
  assignment TypeError points at `set_default` on the declaring state's field).
- Note for the maintainer: #7360's deprecation uses `deprecation_version="0.9.13"` inside a 0.10 alpha (fine if #7360 is
  also going into 0.9.13; otherwise the warning names a version that never deprecated it).

## Blank-app smoke
`$SB/envs/a5`: `reflex init --template blank`, dev on 3100/8100 and `--env prod` on 3101 (REFLEX_API_URL), driven with
`drive_app.py`: both RESULT clean (`dev.json`, `prod.json`, screenshots); no error / traceback / deprecation lines.
