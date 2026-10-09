# Campaign state (compact context) — re-verification of the 0.10.0a3 train (2026-10-07, evening)

## What is under test
- **reflex 0.10.0a3 + reflex-base 0.10.0a3**, released from `origin/r/pre-2026.10.06-37579583012` at `555b667c1`
  ("Materialize changelogs for reflex@0.10.0a3, reflex-base@0.10.0a3"). Only these two packages were re-released;
  every component package, hosting-cli 0.2.0a1, docgen etc. stay at their a2-train versions (see
  `../2026-10-07/CAMPAIGN_STATE.md`). The release run (`Release from changelog` 37673748075) was waiting for publish
  approval at 19:25 UTC; check PyPI before building venvs (`scripts/bootstrap_envs.sh` fails loudly if a3 is absent).
- **reflex-enterprise 0.9.7a5** (PyPI 18:38 UTC). Use the user-supplied OFFLINE wheel
  (`reflex_enterprise-0.9.7a5-0offline-py3-none-any.whl`, sha256 `aad70d1a…`, bypasses the login gate; NOT in the repo,
  ask the user for it) at `$SB/downloads/enterprise_wheel_a5/`. Its only change from 0.9.7a4 is enterprise#273: the
  `formatColumnDefs` `typeof __reflex === 'undefined'` guard is gone (aggrid.py ~2286), so column definitions are
  formatted on the first render, before reflex assigns `window.__reflex` in its `useEffect`.
  Still requires `reflex[db]>=0.9.6` and declares Python 3.10–3.13 classifiers.

## What a3 changed (a2 → a3; 13 commits; diff `git diff v0.10.0a2 555b667c1`)
| PR | Change | Finding it targets |
|---|---|---|
| #7466 | `greenlet >=3.3` in the `db` extra | N-001 (HIGH) |
| #7493 | boot: client-storage vars applied by `hydrate_and_load` are re-marked dirty after the guarded snapshot so the boot delta goes through `get_delta` overrides | N-032 (HIGH, reflex side) |
| #7494 | breaking: 0.9 and 0.10 instances cannot share a state store; `__getstate__` drops the `_PREVIOUS_RELEASE_PICKLE_KEYS` entries; 0.9→0.10 `__setstate__` upgrade path kept | N-004 (decided: document) |
| #7495 | class assignment: storage wrapper kept on plain-default assignment (incl. declared/assigned factories); patch/restore round trip (`_replaced_defaults` undo stack, depth 16; `__delattr__`); a rejected assignment pushes an undo entry (`_keep_default`); dev guard: mangled-name exemption only for the state's own class/bases/mixins prefixes | N-005, N-039, N-008 |
| #7496 | docs: "Upgrading to Reflex 0.10" guide (`docs/changelog/upgrading/upgrading-to-0-10.md`), #7462 release note, `BackendVarFormatError` message names `default_value()` / `ClassVar` / state var | N-002, N-006, N-007, N-009, N-024, N-040 |
| #7497 | `reflex component` (and old subcommands) exit with a pointer to the wrapping docs + component template | F-014 |
| #7428 | reflex-base log: JSON output drained for slow consumers at shutdown, capped at 30 s | (new, untested) |
| enterprise#273 | AG Grid `formatColumnDefs` no longer waits for `window.__reflex` | N-025 (HIGH; maintainer chose the enterprise-side fix and closed reflex#7492) |

Not changed in a3 (so expected unchanged): N-033 (enterprise cookie-sync 405 on cold workers), every "file as issue" item
in `../2026-10-07/RELEASE_PLAN.md` (filed as reflex#7476–#7490, #7498, #7499, #7491; enterprise#262–#272).

## Must-fix findings to re-verify (full text: `../2026-10-07/FINDINGS.md`; run the ORIGINAL failing repro, not just unit tests)
| id | original repro assets (under `prerelease_testing/2026-10-07/`) | expected on a3 (+a5) | item |
|---|---|---|---|
| N-001 | `reverify_db_install/scripts/greenlet_probe.py`; fresh `reflex[db]==0.10.0a3` venv WITHOUT adding greenlet, `reflex db init/makemigrations/migrate`, `import reflex.model` | greenlet resolves via the extra; all work on 3.11–3.14 | a3_preflight |
| N-025 | `ent_grid/apps/aggrid_min` + `scripts/probe_aggrid_min.py`; verifier fixtures `ent_grid/verification/` (`entv`, `corev`, driver trapping the `window.__reflex` setter; one command per build in its NOTES.md) | a3 + a5 prod: state-grid headers/cells on full load, reload, memo grids, detail grid after expand; a3 + a4 still empty (reflex unchanged, expected); 0.9.12 + a5 still fine | a3_ent_grid |
| N-032 | `ent_auth/scripts/stale_hash_probe.py`, `xtab_probe.py`; verifier `ent_auth/verification/drivers/vdrv.py away|stale|xtab`; core-only `ent_auth/verification/coregd_app` | `away` signed out 3/3 dev and prod (Redis + memory), stale-hash corrected 3/3; core `get_delta` override sees the boot value | a3_ent_auth |
| N-004 | `reverify_core/scripts/schema/derive_h_schema.py`; `reverify_core/verification/n004-schema-rollback/` (fleet_app, bin/phase.sh, drivers/drive_fleet.py) | now DOCUMENTED, not fixed: 0.9.12 → a3 loads (Redis + disk); a3 → 0.9.12 resets cleanly (no crash, nothing worse than a fresh session); a2 → a3 and a3 → a3 keep sessions | a3_class_state |
| N-005 | `reverify_core/verification/n005-storage-assign/` (scripts/storage_assign_matrix.py, app, drivers/drive_stor.py); `reverify_core/scripts/derive_g_assign.py`, `derive_i_storage_legacy.py`; `reverify_hydration/probes/cs_storage_default_probe.py` + `src/csbox` | `cls.v = "x"` on a `str`-annotated LocalStorage/Cookie/SessionStorage var keeps storage, name and options; the e2e ComponentState pattern persists in the browser, dev and prod | a3_class_state |
| N-039 | `thirdparty_a2/pytest_probe/min/test_min.py`; verifier `thirdparty_a2/verification/` (15 var kinds × 7 patch mechanisms, `probes/test_min_t1.py`) | patch/restore round trips everywhere (monkeypatch, mock.patch.object, pytest-mock, substate patch, delattr) with no leak | a3_class_state |
| N-008 | `reverify_core/scripts/derive_f_dunder.py` | `self._sneaky__name = 1` raises `SetUndefinedStateVarError` in dev; `self.__counter` from mixins/bases still allowed | a3_class_state |
| N-006 | `reverify_core/scripts/derive_e_format.py` | message names `default_value()` / `ClassVar` | a3_class_state |
| docs | upgrade guide content in the a3 source tree (`git show 555b667c1:docs/changelog/upgrading/upgrading-to-0-10.md`); every code sample in it must run on a3 as written; reflex.dev is blocked by the sandbox proxy | samples run; statements true | a3_upgrade |

## Regression risk introduced by the fixes (hunt here first)
- **#7493 re-marks client-storage vars dirty at boot.** Risk: F-002 comes back (a fresh browser gets defaults written to
  localStorage/cookies on first load), extra/duplicate deltas, `get_delta` overrides that now see boot values behave
  differently (reflex-local-auth, reflex-google-auth, enterprise auth enforcement filters), protected-field withholding at
  boot, prod prerender + Redis, ComponentState storage vars, many-tab storms (F-008-like reconnect loops).
- **#7495 class assignment.** Risk: subclass/mixin assignment, `ComponentState.create` with per-instance defaults, `reset()`,
  pickling with an undo stack (`_replaced_defaults` must not end up in pickles or the schema hash), >16 assignments,
  rejected assignments (`TypeError`) now push an undo entry, `del State.x` on an unassigned var, storage factories called
  once, prod with multiple workers, AppHarness re-runs.
- **#7494 `__getstate__` change.** Risk: a2-saved state no longer loading on a3 (a2 wrote extra keys), schema hash change
  between a2 and a3 for the same app, disk state manager files from 0.9.12/a2.
- **enterprise#273.** Risk: lambda `cell_renderer` / `value_formatter` / cell components invoked before `window.__reflex`
  exists (ReferenceError on first paint), dev vs prod, master-detail, `@rx.memo` grids, SSR/prerender of the grid markup.
- **#7428** log draining: `reflex run --json` shutdown, `reflex run` Ctrl-C/SIGTERM taking up to 30 s, exit codes.
- **Packaging:** RESOLVED in pre-flight: the published reflex 0.10.0a3 wheel pins `reflex-base==0.10.0a3` exactly (the source
  floor `>= 0.10.0a2.dev0` is rewritten at release), so any install or upgrade of reflex a3 brings reflex-base a3.

## Environment
- SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad on the orchestrator's machine (any
  scratch dir works elsewhere). Build with `scripts/bootstrap_envs.sh $SB --enterprise`:
  `a3` (under test), `alpha2` (previous alpha, greenlet added), `stable` (0.9.12, greenlet added), `driver` (playwright),
  `a3-ent` (a3 + offline a5 [mcp] + oidc-provider-mock), `s912-ent-a5` (0.9.12 + a5), `a3-ent-a4` (a3 + the old a4 wheel).
  `alpha2-ent` (a2 + a4 wheel) from the previous pass is still there on the orchestrator machine.
- Chromium: `/opt/pw-browsers/chromium`. Artifacts: `prerelease_testing/2026-10-07-a3/<item>/` on branch
  `claude/reflex-prerelease-testing-t0sd90`.
