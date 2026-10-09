# a4 preflight (orchestrator) — 2026-10-08

## Publish check (Phase 0)
`uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref f6e070ef4` (repo root):
20/20 packages OK with wheel + sdist; reflex 0.10.0a4 and reflex-base 0.10.0a4 are the only new versions (every other
package at its a2-train version). reflex-enterprise: 0.9.7a5 is still the newest on PyPI. Tag `v0.10.0a4` = `f6e070ef4`
on `r/pre-2026.10.06-37579583012`; `git log v0.10.0a3..v0.10.0a4` = #7505, #7513, #7516 + merge + changelog commit.

## Wheel contents
- Published reflex 0.10.0a4 requires `reflex-base==0.10.0a4` (exact pin), `reflex-components-core>=0.10.0a2`.
- Every source file a4 changed is byte-identical between `git show f6e070ef4:<file>` and the installed a4 venv:
  `reflex_base/.templates/web/utils/state.js` (#7505), `reflex_base/vars/base.py` (#7516), `reflex/istate/storage.py`,
  `reflex/state.py`.
- The removed #7495 layer (`_with_value`, `_keep_client_storage`, `_accepts_default`, `_assign_default`,
  `_restore_default`, `_REPLACED_DEFAULTS*`) is absent from the installed reflex / reflex_base; `_state_var_assignment_error`
  and the new `__setattr__` / `__delattr__` are present.

## Packaging audit (Phase 5)
`check_release_versions.py --ref f6e070ef4 --specs > specs.txt && xargs audit_pyi.py --manifest-ref f6e070ef4 < specs.txt`
→ `audit_pyi.txt`: PASS, 122 stubs ship in both wheel and sdist, byte-identical, counts match `pyi_hashes.json`, no
foreign stubs.

## Changelog / docs (source at v0.10.0a4)
- reflex `CHANGELOG.md` v0.10.0a4: one Breaking Changes entry for #7516 (assignment raises; `__fields__`; patch the field;
  `ClassVar`). The a3 section was edited in place: the #7312 entry now also covers writing an inherited var (#7513, A3-06),
  the two #7495 class-assignment entries are gone and the #7461 entry no longer mentions `cls.count = 10` (both describe
  behaviour #7516 removed).
- reflex-base `CHANGELOG.md` v0.10.0a4: #7516 breaking entry; #7505 bug fix ("`sync=True` `rx.LocalStorage` vars no longer
  bounce between open tabs forever ...").
- `docs/changelog/upgrading/upgrading-to-0-10.md`: "Assigning a state var through its class" section; the background-task
  section now says writing an inherited var outside `async with self` raises (#7513). `docs/vars/base_vars.md`: Changing
  Defaults via `__fields__`, ClassVar per-worker note, SharedState pointer.

## Blank-app smoke (Phase 1)
`$SB/envs/a4` (Python 3.12, `reflex[db]==0.10.0a4`, greenlet 3.5.6 via the extra, SQLAlchemy 2.1.4):
`reflex init --template blank` (requirements.txt pins `reflex==0.10.0a4`), `reflex run` dev on 3100/8100 and
`reflex run --env prod` on 3101 (REFLEX_API_URL=http://localhost:3101), driven with `drive_app.py`: both RESULT clean
(`dev.json`, `prod.json`, screenshots). The "Compiling 100% 18/17" counter overshoot is pre-existing (a2/a3 logs show it).
