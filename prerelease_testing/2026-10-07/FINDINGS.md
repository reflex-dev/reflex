# Findings — re-verification on reflex 0.10.0a2 train (r/pre-2026.10.06-37579583012), 2026-10-07

**Status: in progress (interim; updated as clusters report).** Scope: re-run every failing repro from the
[2026-10-06 findings](../2026-10-06/FINDINGS.md) against the newly published train, finish the clusters the
spend limit interrupted, and sweep for regressions the fixes may have introduced. Enterprise is tested with
the user-supplied offline `reflex-enterprise 0.9.7a4` wheel.

## Versions under test
reflex / reflex-base 0.10.0a2; components code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2;
dataeditor 0.10.0a1; react-player 0.10.0a1; sonner 0.10.0a1; lucide 1.1.0a1; docgen 0.10.0a2; hosting-cli
0.2.0a1 (0.1.73a1 excluded by reflex's metadata); build-sdk 0.1.0a1; release 0.2.0a1; otel 0.2.0a1;
hatch-reflex-pyi 0.10.0a1. All 20 published with wheel+sdist; `.pyi` audit PASS
([packaging/audit.log](./packaging/audit.log)). Python >= 3.11 (3.10 dropped). Baselines: 0.10.0a1 (previous
train) and 0.9.12.

## Pre-flight facts (orchestrator, verified from metadata and the published packages)
- `reflex[db]==0.10.0a2` resolves `sqlmodel 0.0.48`: the `<0.0.45` cap is gone (#7462). No changelog
  fragment mentions #7462 ("Support SQLModel UTC datetime migrations without downgrades") — documentation gap
  to confirm (FINDING-005 follow-up).
- reflex 0.10.0a2 now floors every component package at its new-train alpha (`reflex-components-core >=
  0.10.0a2`, `-dataeditor >= 0.10.0a1`, `-lucide >= 1.1.0a1`, `-sonner >= 0.10.0a1`, ...) and excludes
  `reflex-hosting-cli 0.1.73a1` (#7464) — addresses FINDING-006; behavioral check pending.
- The 0.10.0a2 changelog documents the class-level backend-var read returning `Field` as a (misc) breaking
  change with the `default_value()` guidance, and #7456 turns a formatted backend var into
  `BackendVarFormatError` — FINDING-001's core half is now intentional-and-documented; the enterprise half
  (`__data_source_params_class__`) should be covered by #7465 (dunder names are plain attributes). Pending.
- Smoke: blank app on 0.10.0a2 in dev, driven in Chromium: clean ([smoke/](./smoke/)).

## Re-verification table (filled in as clusters report)

| finding (10-06) | a1 status | a2 result | cluster |
|---|---|---|---|
| F-001 class-level backend var → Field; enterprise AG Grid model wrapper 500 | HIGH regression | **changed / enterprise half fixed**: class reads still return `Field` (documented as breaking in the a2 CHANGELOG); `f"{S._x}"` now raises `BackendVarFormatError` (#7456) so the 10-06 e2e app fails loudly at compile instead of rendering `Field(...)`; enterprise AG Grid `/model`, `/model-auth`, SSRM and infinite pages return 200 with rows in dev and prod, 0 `from_request` errors (#7465). Gaps: N-006/N-007 | reverify_core |
| F-002 first-load client-storage default write-back | HIGH regression | pending | reverify_hydration |
| F-003 computed-var client-storage rewrite dropped at hydration | MED partial regression | pending | reverify_hydration |
| F-004 class-level assignment replaces descriptor | MED regression | **fixed** (#7461: descriptor kept, fresh/pickled instances read the assigned default, dev writes and `reset()` work, e2e dev and prod+redis) — new gaps N-004/N-005 | reverify_core |
| F-005 sqlmodel<0.0.45 cap | MED regression | **fixed** (sqlmodel 0.0.48 resolves; `UTCDateTime()` migrations apply on a fresh db; aware round trip identical to 0.9.12+0.0.47) — with caveats: N-001 below, and a1→a2 `uv -U` upgraders of a naive-datetime app silently change semantics with no release note for #7462 (N-002) | reverify_db_install |
| F-006 component floors unchanged | MED release-eng | **fixed** (every pip/uv upgrade variant from 0.9.12 moves all 13 component packages; fresh `pip install reflex==0.10.0a2` without `--pre` resolves the full train; formapp submits the fixed #7227 payload) | reverify_db_install |
| F-007 npm SIGTERM hang | MED pre-existing | **still broken on Linux** (3/3 on a2; a1 and 0.9.12 identical; bun clean). On macOS arm64 (other session, `macos_lifecycle`): a1 and a2 exit cleanly in <0.3 s, 0.9.12 still hangs — platform-scoped; the Linux finding stands | reverify_db_install, macos_lifecycle |
| F-008 >1 MB storage reconnect storm | MED pre-existing | pending | reverify_hydration |
| F-010 pre-connect nav on_load | LOW pre-existing | pending | reverify_hydration |
| F-011 forward-ref TypeError | LOW regression | **still broken** | reverify_core |
| F-012 PageContext LookupError message | LOW | **still broken** | reverify_core |
| F-013 rx.Model deprecation location | LOW | **still broken** | reverify_core |
| F-014 `reflex component` message | LOW | **still broken** | reverify_core |
| F-015 duplicate npm notice | LOW | **still broken** (unchanged) | reverify_db_install |
| F-016 ty 0-arg / 5-arg | LOW | **still broken** (ty 0.0.84/0.0.85 and pyright 1.1.414 identical to a1) | reverify_core |
| F-017 redis restart token loss | LOW unknown | pending | reverify_hydration |
| F-018 React 19.3 console error | LOW | **still broken** (2/2) | reverify_core |

## New findings on 0.10.0a2

### N-001: Fresh `reflex[db]` resolves SQLAlchemy 2.1.3 without greenlet; `rx.Model` and every `reflex db` command crash with ImportError (HIGH)
- Cluster: `reverify_db_install` | Regression vs 0.9.12: no in the strict sense (a fresh `reflex[db]==0.9.12`
  fails identically since sqlmodel 0.0.48 was published 2026-10-06 21:44 UTC) | vs 0.10.0a1: yes (a1's
  `sqlmodel<0.0.45` cap kept SQLAlchemy at 2.0.x) | Verifier: orchestrator-confirmed (fresh venv: sqlalchemy 2.1.3, no greenlet, `import reflex.model` → ImportError) in addition to the explorer's 3.11/3.12/3.14 uv+pip runs
- Repro: `uv --no-config venv --python 3.12 v && uv --no-config pip install --python v/bin/python --prerelease=allow 'reflex[db]==0.10.0a2' 'pydantic<2.14'`,
  then any `reflex db migrate` / `reflex run` of an app with an `rx.Model`: `ImportError: The SQLAlchemy asyncio
  module requires that the Python 'greenlet' library is installed`. Probe: `reverify_db_install/scripts/greenlet_probe.py`.
  Workarounds: `pip install greenlet`, or `sqlalchemy[asyncio]`, or `sqlalchemy<2.1`.
- Evidence: `reverify_db_install/freeze/1a-uv-db-prealllow.txt`, `freeze/10-pip-db.txt` (sqlalchemy 2.1.3, no greenlet),
  `logs/11-greenlet-reflex-db-cli.log`, `logs/15-dtapp-a2nogreenlet-run.log`, `logs/36-greenlet-probe-other-pythons.txt`.
- Cause: sqlmodel 0.0.48 widened `SQLAlchemy<2.1.0` to `<2.2.0`; SQLAlchemy 2.1 made greenlet an extra;
  `reflex/model.py:69` imports `sqlalchemy.ext.asyncio` at import time while the `db` extra lists only alembic,
  pydantic and sqlmodel. reflex-local-auth users (`reflex[db]>=0.8.1`) hit it too. Fix options: add `greenlet`
  or `sqlalchemy[asyncio]` to the `db` extra, import the asyncio module lazily, or cap `SQLAlchemy<2.1`.
- Campaign impact: greenlet was added to the shared alpha2 venvs after this report so the other clusters test the framework.
- Fix PR: [reflex-dev/reflex#7466](https://github.com/reflex-dev/reflex/pull/7466) adds `greenlet >=3.2` to the `db` extra (regression test included).

### N-002: No changelog entry for the sqlmodel cap removal (#7462); a1→a2 `uv -U` upgraders of naive-datetime apps silently change semantics (LOW)
- Cluster: `reverify_db_install`. The v0.10.0a2 CHANGELOG has no sqlmodel/datetime/#7462 entry (the PR only
  trimmed the old fragment and added `docs/database/tables.md`). An app written under sqlmodel 0.0.44 (naive
  datetimes) upgraded with `uv pip install -U` moves to 0.0.48 and breaks (naive compare TypeError, naive insert
  rejected, rows read with `+00:00`); the documented `sa_type=DateTime(timezone=False)` / `NaiveDatetime` recipes fix it.
  In-place `pip install [-U]` and uv without `-U` keep 0.0.44. Evidence: `reverify_db_install/logs/19-naive-uvU-run.log`, `out/17-naive/`.

### N-003: AppHarness cannot restart the same multi-module app within one process (LOW, acknowledged in #7359, unchanged)
- Cluster: `reverify_db_install`. The cross-app fix of #7359 works (app B after a multi-module app A with
  `rx.dynamic`: a2 clean, a1 `KeyError`); restarting the SAME app (`plain-restart`, `dynamic-restart`,
  `dynamic-same`) still fails on a2 and a1 (KeyError / frontend `$$typeof` TypeError). Evidence: `reverify_db_install/logs/26-harness-*.log`.

### N-004: State saved by 0.10.0a2 is discarded by 0.9.12 and 0.10.0a1 workers (rolling deploy / rollback silently resets sessions) (MEDIUM)
- Cluster: `reverify_core` | Regression vs 0.10.0a1: yes (a1-saved state still loads on 0.9.12, as the #7312 changelog
  promises; a2's schema hash — "Defaults are no longer part of the saved-state schema", #7461 — breaks that) | Verifier: **CONFIRMED** (medium)
- Verification: full 3×3 save/load matrix reproduced; loading an a2 pickle on 0.9.12/a1 with the hash check skipped works
  completely (values, backend var, mutation, dirty tracking, re-serialization), so the hash is the ONLY incompatibility — a2 even
  ships `_PREVIOUS_RELEASE_PICKLE_KEYS` for old workers, which the new hash makes useless. E2E with one Redis and one token:
  0.9.12→a2, a1→a2, a1→0.9.12, a2→a2 across a default change all keep the session; a2→0.9.12 and a2→a1 lose it (user '', count
  reset) every time an old worker serves the token, the old worker writes the fresh state back and a2 accepts it, so the
  a2-era data is gone for good, with nothing logged. PR #7461 only claims the forward direction. Root cause (alpha2):
  `reflex/state.py:2102-2122` `_to_schema` now hashes only (name, type); `_serialize` (`:2141`) writes `(new_hash, state)`;
  `_deserialize` (`:2210-2218`) accepts the new or the legacy hash, but nothing ever writes the legacy hash; 0.9.12
  (`state.py:2864`) and a1 (`:2213`) only accept their own default-including hash and `istate/manager/redis.py` swallows the
  mismatch into a fresh state. Fix idea: write the legacy hash in the tuple and carry the new hash inside the pickled dict
  (old workers tolerate extra keys); or drop the #7312 rolling-deploy sentence and document that rollback loses sessions.
  Evidence: `reverify_core/verification/n004-schema-rollback/` (fleet_app, bin/phase.sh, drivers/drive_fleet.py, logs/pickle_matrix.txt).
- Repro: `cd reverify_core/scripts/schema; SCHEMA_DEFAULT=0 $SB/envs/alpha2/bin/python derive_h_schema.py alpha2 save s.bin;
  SCHEMA_DEFAULT=0 $SB/envs/stable/bin/python derive_h_schema.py stable load s.bin` → `StateSchemaMismatchError`; an a1-saved
  file loads (count=42). E2E: `core_a2` `/schema` in prod with one Redis: a2 → stop → 0.9.12 comes back fresh (count 5);
  controls 0.9.12→0.9.12 and a1→0.9.12 keep 42. The Redis manager suppresses the mismatch and creates a fresh state.
- Evidence: `reverify_core/logs/derive_h_schema.txt`, `out/core/rb2-x-p2.json` vs `ctl4-a1-p2.json`, `ctl3-stable-p2.json`.
- Decision needed: the maintainer's stated policy is forward-only upgrades, but the a1 changelog sentence about old workers
  loading new states is still in the 0.10.0 notes; either drop/qualify it for a2 or restore compatibility.

### N-005: Assigning a plain default to a LocalStorage/Cookie var (incl. the documented ComponentState `cls.value = initial` pattern) silently drops browser persistence (MEDIUM)
- Cluster: `reverify_core` | Regression: no (new #7461 behaviour; 0.9.12 ignored the assignment and kept storage) | Verifier: **CONFIRMED** (medium)
- Verification matrix (3 storage types × str/storage-type annotation × 6 assignment kinds × 3 versions): with the documented
  `v: str = rx.LocalStorage(...)` declaration, a plain value or a factory returning a plain value silently turns the var into
  an ordinary var (`_is_client_storage` False, absent from the compiled `clientStorage`, never written to the browser, a new
  tab shows the default; a same-token reload hides it); a factory returning `rx.LocalStorage(..., name=...)` or a storage value
  keeps storage; `rx.LocalStorage("x")` without a name keeps storage but drops the declared key name. With a storage-type
  annotation a plain value raises `TypeError: Invalid default` — loud, and inconsistent with the silent `str` path. The
  documented ComponentState example (`docs/state_structure/component_state.md:83-111`) uses a plain var and is NOT affected;
  only that pattern combined with a storage declaration loses storage; `docs/vars/base_vars.md:76-96` warns about nothing.
  Root cause (alpha2): `reflex_base/vars/base.py:4764-4817` `BaseStateMeta.__setattr__` replaces the storage default (the
  only carrier of the storage classification and options); `reflex/state.py:1606-1625` `_is_client_storage` and
  `reflex/compiler/utils.py:308-333` look only at `field.default` or a storage-typed annotation. Fix: wrap an accepted plain
  value/factory result in the declared storage class with its options, or raise like the storage-annotated path.
  Evidence: `reverify_core/verification/n005-storage-assign/` (scripts/storage_assign_matrix.py, app, drivers/drive_stor.py).
- Repro: `class St(rx.State): v: str = rx.LocalStorage("d", name="k")`; `St.v = "x"` → `St._is_client_storage("v")` is False and the
  var is absent from compiled storage; same for `rx.Cookie`, a factory returning a plain str, and `cls.value = initial` in
  `ComponentState.get_component`. Workaround: assign `rx.LocalStorage("x", name="k")`. Scripts: `reverify_core/scripts/derive_g_assign.py`
  (storage section), `derive_i_storage_legacy.py`; e2e `core_a2` `/storage` via `drive_core.py <url> out lbl storage`.
- Evidence: `reverify_core/out/core/core-alpha2-{dev,prod-redis}.json` (`1_browser_storage` lacks `ls_plain_key`, `lscs_key`, cookie `ck_key`).

### N-006: #7456 leaves silent and non-actionable paths for backend vars in the UI (LOW)
- `str(S._size)+"px"`, `"%s" % S._size` and `f"{S._size!s}"` still embed `Field(default=16, ...)`; `rx.box(id=S._label)` → cryptic
  `TypeError: expected string or bytes-like object, got 'Field'`; the `BackendVarFormatError` text ("Use a regular state var instead.")
  never mentions `default_value()` or `ClassVar`. Script: `reverify_core/scripts/derive_e_format.py`.

### N-007: The documented `State._x.default_value()` is not portable to 0.9.x (LOW, docs)
- On 0.9.12 it raises `AttributeError: 'list' object has no attribute 'default_value'`; `State.get_fields()["_x"].default_value()` works
  on 0.9.12, a1 and a2. Packages supporting both lines need the latter.

### N-008: Dev `SetUndefinedStateVarError` guard now accepts any undeclared `_x__y` name (LOW, regression)
- `self._sneaky__name = 1` is accepted in dev on a2 (0.9.12 and a1 raise): `state.py` treats `name.startswith("_") and "__" in name`
  as a private attribute. Script: `derive_f_dunder.py`.

### N-009: Class-default assignment scope surprises are undocumented (LOW)
- Assigning on a mixin only affects states defined afterwards (`U1/U2/U3` → `(5, 1, 7)`); a runtime `type(self).count = 77`
  is per worker process (dev 77, prod with 6 granian workers: a new tab sees 20). Script: `derive_g_assign.py`; e2e `/cs` `reconf_b`.

### N-010: DataEditor `get_cell_content`/data callback escapes the `rx.foreach` variable scope — zero editors render, page falls into the error boundary (MEDIUM, pre-existing)
- Item: `dataeditor` (other session, macOS; Chromium + WebKit) | Regression: no (0.9.12, a1 and a2 identical, dev and prod) | Verifier: that session's own independent control (a memo-wrapped foreach renders)
- Repro: `prerelease_testing/2026-10-07/board/findings-inbox/dataeditor-1.md` (bootstrap_from_freezes.sh, `/de-foreach`, `focused_driver.py --groups de_foreach`).
- Root cause guess: published `reflex_components_dataeditor/dataeditor.py:472-499` `add_hooks` emits a `getData` callback that references the foreach item var outside the map lambda. Evidence: `dataeditor/de/runs/alpha2-dev/results.json`, `shots/alpha2-dev-de-foreach.png`.

### N-011: Starting a DataEditor edit by typing (without Enter) loses the leading characters (MEDIUM, pre-existing)
- Item: `dataeditor` | Regression: no (all trains, dev and prod; human-speed 120 ms/char typing "Slow" yields "low"; pressing one key, waiting 800 ms, then typing works).
- Repro: inbox `dataeditor-2.md`; `typing_driver.py`. Root cause unknown (the first overlay editor is lazily imported in the Glide bundle).

### N-012: DataEditor with `on_delete` bound dispatches the selection, then throws `TypeError: undefined.length` and never clears the cell (MEDIUM, pre-existing)
- Item: `dataeditor` | Regression: no (stable and a2; only with `on_delete` bound).
- Repro: inbox `dataeditor-3.md`. Root cause guess: `dataeditor.py:365` exposes a plain EventHandler; the generated `onDelete` callback returns `addEvents` (async) where Glide expects a boolean/GridSelection, so it calls `shiftSelection` on the promise and reads `columns.length`.

### N-013: Escape right after opening a single-image preview leaves the carousel open (LOW, pre-existing)
- Item: `dataeditor` | Regression: no. Repro: inbox `dataeditor-4.md` (`--groups de_overlay`). Multi-image preview after clicking an arrow, and text-editor Escape, work.

### N-014: Radix form controls' synthetic clicks throw `undefined[0]` when a DataEditor is on the page (LOW, pre-existing)
- Item: `dataeditor` | Regression: no (a1/a2/stable; controls still update; no-grid control clean).
- Root cause guess: Glide's global click handler treats a non-MouseEvent as a TouchEvent and reads `ev.changedTouches[0]`; Radix hidden inputs dispatch a plain `Event('click')`. Repro: inbox `dataeditor-5.md` (`delete_app` fixture + `drive_form_grid.py`).

Also from `dataeditor` (other session): named `rx.select` payloads submit correctly on all three trains and both engines (the 10-06 `f_select` lead was an id-only select: stable submits `null`, the alphas omit the key — usage context, not a release bug); nested-dialog form event propagation predates the train and `stop_propagation` prevents it; exact wheel diffs of dataeditor 0.10.0a1, react-player 0.10.0a1, sonner 0.10.0a1 and lucide 1.1.0a1 show only Python/sibling floor changes.

## Cluster summaries

### `dataeditor` (other session, macOS arm64, Chromium + WebKit) — done
170 editor assertions (139 pass / 31 fail) and 438 forms/misc assertions (392 / 46) on 0.10.0a2 with 0.10.0a1 and 0.9.12
baselines, dev and prod. Five pre-existing component defects (N-010..N-014), no new 0.10 regression. Charts, Plotly,
Shiki/Markdown/Moment, Unicode downloads, match/memo updates, toast/icon all pass. Results: `board/results/dataeditor.md`.

### `macos_lifecycle` (other session, macOS 26.6.2 arm64, Node 26.8.1 / npm 11.19.0) — done
0.10.0a2 passes browser startup, Unicode paths and input, reload, HMR, npm and bun dev, bun prod smoke. F-007 does not
reproduce on macOS with a1 or a2 (clean exit in <0.3 s); 0.9.12 still hangs. Results: `board/results/macos_lifecycle.md`.

### `reverify_core` (pass: 16, anomaly: 6, fail: 2) — done
F-001 changed-and-documented (enterprise half fixed), F-004 fixed; F-011/012/013/014/016/018 unchanged. #7461 (class
defaults, ComponentState per-instance defaults, factories, "defaults not part of the saved schema"), #7465 (dunder
attributes, `rx.field()` dunder backend vars) and #7456 verified in Python and in Chromium (dev, prod+redis). New: N-004
(a2 state discarded by older workers), N-005 (plain default drops storage), N-006..N-009. Enterprise AG Grid model
wrapper, SSRM and infinite pages pass in dev and prod; pre-existing demo failures identical on 0.9.12 + wheel.

### `reverify_db_install` (pass: 15, anomaly: 3, fail: 4) — done
F-005 and F-006 fixed; F-007 and F-015 unchanged. Python 3.10 refused cleanly by uv and pip; 3.11 and 3.14
state app 14/14 in dev and prod; #7210, #7259, the #7359 cross-app AppHarness fix, hosting-cli 0.2.0a1 +
build-sdk 0.1.0a1 smoke (0.1.73a1 excluded at resolution time) all pass. New: N-001 (greenlet), N-002, N-003.
