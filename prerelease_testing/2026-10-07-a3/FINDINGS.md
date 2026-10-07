# Findings — re-verification on reflex 0.10.0a3 / reflex-base 0.10.0a3 + reflex-enterprise 0.9.7a5, 2026-10-07 (second pass)

**Status: IN PROGRESS.** Board: [board/](./board/). Protocol: [COORDINATION.md](./COORDINATION.md). Context: [CAMPAIGN_STATE.md](./CAMPAIGN_STATE.md).
Previous pass (a2 train): [../2026-10-07/FINDINGS.md](../2026-10-07/FINDINGS.md), plan [../2026-10-07/RELEASE_PLAN.md](../2026-10-07/RELEASE_PLAN.md).

## Versions under test
- reflex 0.10.0a3, reflex-base 0.10.0a3 (`r/pre-2026.10.06-37579583012` @ `555b667c1`); all other train packages unchanged from a2.
- reflex-enterprise 0.9.7a5 (offline wheel `reflex_enterprise-0.9.7a5-0offline-py3-none-any.whl`, sha256 aad70d1a…; PyPI wheel 5e394ddb…).
- Baselines: reflex 0.10.0a2 (+ enterprise 0.9.7a4), reflex 0.9.12 (+ enterprise 0.9.7a5 / a4).

## Pre-flight (orchestrator)
- 19:25 UTC: `Release from changelog` run 37673748075 built reflex-base 0.10.0a3; its `publish` job waits for environment
  approval, so reflex / reflex-base 0.10.0a3 are not on PyPI yet (discovery script: 18/20 OK, the two a3 packages
  "NOT ON PYPI"). Agents started with positive controls on a2 / 0.9.12 meanwhile. After the maintainer approved the
  publish jobs, reflex-base 0.10.0a3 and reflex 0.10.0a3 (uploaded 19:51:42 UTC) resolved on PyPI at 19:52 UTC.
- 19:52 UTC: all 20 train packages published with wheel + sdist; `.pyi` audit PASS (122 stubs, wheel == sdist, counts match
  `pyi_hashes.json`, no foreign stubs). Published reflex 0.10.0a3 pins `reflex-base==0.10.0a3` exactly, so any install
  or upgrade of reflex a3 brings the reflex-base fixes with it. `db` extra: alembic, `greenlet>=3.3`, pydantic, sqlmodel.
- Blank-app smoke on a3 (`reflex init --template blank`, dev and prod): clean in Chromium.
- reflex-enterprise 0.9.7a5: the offline wheel and the PyPI wheel differ only in `constants.py` (`IS_OFFLINE = True`).
  a4 → a5 changes only `formatColumnDefs` in `components/ag_grid/aggrid.py` (the `typeof __reflex === 'undefined'` early
  return and the unused `jsx`/`Fragment` lookups are gone) plus the CHANGELOG entry (enterprise#260). Metadata unchanged:
  `reflex[db]>=0.9.6`, `Requires-Python >=3.10,<4.0`.

## Re-verification table (must-fix findings of the a2 pass)
| id | a2-pass status | a3 result | evidence | item |
|---|---|---|---|---|
| N-001 greenlet missing from `reflex[db]` | HIGH, all fresh installs | **fixed**: fresh `reflex[db]==0.10.0a3` with uv and pip on 3.11–3.14 resolves greenlet 3.5.6 + SQLAlchemy 2.1.4 through the extra (8/8); `rx.Model`, `reflex db init/makemigrations/migrate` and prod CRUD work | `a3_preflight/logs/03-*`, `04-*`, `dbcli-prod.*` | a3_preflight |
| N-025 prod AG Grid Var `column_defs` empty | HIGH regression | _pending_ | | a3_ent_grid |
| N-032 OIDC cross-tab logout | HIGH regression | _pending_ | | a3_ent_auth |
| N-004 0.10 state unreadable by 0.9 | MEDIUM, decided: document | **behaves as documented** (#7494): 0.9.12 → a3 keeps sessions; a3 → 0.9.12 resets cleanly (fresh state, nothing logged) on Redis and disk; a2 ↔ a3 interchangeable (schema hash identical); a3 pickles hold only field values (no `_PREVIOUS_RELEASE_PICKLE_KEYS`, no undo stack) | `a3_class_state` pickle matrix, disk store, fleet e2e | a3_class_state |
| N-005 plain default drops storage | MEDIUM | **fixed** for `str` values: 3 storage types × str/storage annotation × 6 assignment kinds keep storage, name and options; e2e dev + prod/Redis (9 workers) writes `ls_plain_key`, `lscs_key`, `ck_key`, n005 8/8 (a2 4/8). Gap: `None` / non-str values still drop storage (A3-02) | `a3_class_state/out/e2e/`, `logs/` | a3_class_state |
| N-039 patch/restore of a var default | MEDIUM | **fixed**: monkeypatch / mock.patch.object / pytest-mock / substate / delattr round trips, 15 var kinds, 0 errors and 0 leaks on Python 3.11–3.14 (a2: 15/15 fail); edge cases in A3-01 | `a3_class_state/logs/` | a3_class_state |
| N-008 `_x__y` accepted by the dev guard | LOW regression | **fixed**: `self._sneaky__name = 1` raises in dev; own/base/mixin/`_Under`/ComponentState mangled names still accepted | `a3_class_state` | a3_class_state |
| N-006 `BackendVarFormatError` message | LOW docs | **changed**: message names `default_value()` / `ClassVar` / a state var; `str(S._x)`, `"%s" % S._x`, `f"{S._x!s}"` still embed the `Field` repr silently (as the guide now states) and `rx.box(id=S._label)` is still a cryptic TypeError | `a3_class_state` | a3_class_state |
| N-002/N-007/N-009/N-024/N-040 docs | LOW docs | _pending_ (N-040 itself unchanged on a3: 179/255 assignments raise, 42 run user code — now documented) | | a3_upgrade, a3_class_state |
| F-014 `reflex component` message | LOW | _pending_ | | a3_upgrade |

## New findings on 0.10.0a3
Numbered A3-xx. "Pending verification" until a `verify_*` item reports.

### A3-01: #7495's undo stack restores the latest entry, not what the patch saved: a rejected patch, `monkeypatch.delattr`, or an assignment inside a patch window loses a configured default or leaks the patched one (LOW, regression vs a2 in 3 of 4 cases; pending verification)
- Item `a3_class_state` (inbox 7). With `Svc.limit = 10` configured at import: (a) `mock.patch.object(Svc, "limit", Other.y)` raises
  TypeError but mock's exit still restores, popping the configuration → later tests see 0; (b) same for `mocker.patch.object(Svc, "_quota",
  rx.field(5))`; (c) `monkeypatch.setattr(Svc, "limit", 99)` then code under test assigns `Svc.limit = 50` → teardown undoes the 50 and
  leaves 99 for later tests; (d) `monkeypatch.delattr(Svc, "_quota")` pops the configuration and teardown pops again → 0 for good.
  a3: 4 failed / 4 passed; a2: (c) only, loudly. Also: `S.x = S.x` after a configuration silently reverts it; a `str` var with a
  non-storage declared `default_factory` now has that factory called when a plain str is assigned.
- Cause (published reflex-base 0.10.0a3 `vars/base.py`): `_keep_client_storage` / `_accepts_default` raise before `_keep_default`
  pushes the "failed assignment" entry (4895–4903, 4918); `__delattr__` pops (4926–4939); identity restore pops whatever is on top (4888).
- Repro: `a3_class_state/probes/undo_edge/test_undo_edge.py` (needs reflex[db]==0.10.0a3, pytest, pytest-mock).

### A3-02: The N-005 fix covers only `str` values: assigning `None` to an `Optional[str]` storage var (or a non-str to a Union var) still silently drops browser storage (LOW, regression vs 0.9.12, same as a2; pending verification)
- Item `a3_class_state` (inbox 8). `opt: Optional[str] = rx.LocalStorage("d", name="k_opt")`; `St.opt = None` → no client-storage entry;
  e2e `apps/clse2e`: `k_opt` never written, a new tab shows "". 0.9.12 ignored the assignment and kept storage.

### A3-03: ComponentState + named storage var + `cls.x = initial` (the a3 changelog's example) makes every instance share one browser key (LOW, pre-existing on 0.9.12; pending verification)
- Item `a3_class_state` (inbox 9). csbox on a3 dev and prod/Redis: one `box_pref` key for all instances; after a reload one instance
  shows another's choice. 0.9.12 shares the key too; a2 hid it only because N-005 dropped storage.

### A3-04: Concurrent class-default assign/restore from several threads leaves a stale patched default (LOW, pre-existing on a2)
- Item `a3_class_state` (inbox 10). 8 threads × 1500 assign/restore: final default corrupted on 3.11/3.12/3.14 (a2 too, plus TypeErrors).

### A3-05: AppHarness: a second app in one pytest process rendering a state from a shared module crashes on first render on 0.10 (`useContext` of a missing StateContext); 0.9.12 renders (LOW, regression vs 0.9.12, same on a2; pending verification; related to N-041/N-003, reflex#7479)
- Item `a3_class_state` (inbox 11). `a3_class_state/harness/test_shared_state_harness.py`: 2 failed, 1 passed on a3 and a2; 0.9.12 passes.

## Cluster summaries

### `a3_class_state` — done (positive controls on a2 all reproduced first)
N-005, N-039 and N-008 fixed; N-006 changed (message fixed, silent `str()` paths remain); N-004 behaves exactly as the #7494 note says
(Redis, disk and pickle level; a2 ↔ a3 interchangeable); N-040 unchanged and now documented. #7495 adversarial hunt: `del State.x`
with nothing assigned is a no-op, parent/child/mixin/ComponentState patches restore, `reset()` after assignment and restore, storage
factories called exactly once, storage options kept, pickles carry no undo stack, schema unchanged by assignment, bounded stack across
20 module reloads. New: A3-01 (regression vs a2, low), A3-02, A3-03, A3-04, A3-05. Notes: `a3_class_state/NOTES.md`.
