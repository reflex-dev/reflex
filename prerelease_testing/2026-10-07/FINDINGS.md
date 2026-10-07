# Findings — re-verification on reflex 0.10.0a2 train (r/pre-2026.10.06-37579583012), 2026-10-07

**Status: in progress (interim; updated as clusters report). Blocker candidate: N-025 (HIGH regression, prod AG Grid State-var column_defs empty since a1) — independent verification running.** Scope: re-run every failing repro from the
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
| F-001 class-level backend var → Field; enterprise AG Grid model wrapper 500 | HIGH regression | **changed / enterprise half fixed**: class reads still return `Field` (documented as breaking in the a2 CHANGELOG); `f"{S._x}"` now raises `BackendVarFormatError` (#7456) so the 10-06 e2e app fails loudly at compile instead of rendering `Field(...)`; enterprise AG Grid `/model`, `/model-auth`, SSRM and infinite pages return 200 with rows in dev and prod, 0 `from_request` errors (#7465). Gaps: N-006/N-007. `ent_grid` confirms: /model, /model-auth, /model-ssrm, /qa-model-workaround load and serve data on a2 dev and prod, 0 `from_request` errors; the 5 remaining model-page not-ok checks are identical on 0.9.12 + wheel | reverify_core, ent_grid |
| F-002 first-load client-storage default write-back | HIGH regression | **fixed** (#7460, backend-only: the boot delta root now carries `is_hydrated_rx_state_: false`; fresh profile writes nothing; returning visitor sees changed defaults; user choices still persist; `sync=True` two-tab race clean; `reflex/state.py:2368-2383`; `ent_grid`: the enterprise kanban demo's first load writes no `kanban_data_json` default on a2 dev and prod) | reverify_hydration, ent_grid |
| F-003 computed-var client-storage rewrite dropped at hydration | MED partial regression | **fixed for page loads and reconnects** (#7460: all variants a–g + two new ones pass on every seed, dev, prod and prod+redis; a follow-up delta carries the corrected value; reflex-google-auth bogus token cleared on the first reload). Still open, pre-existing: the same write during an ordinary event or client-side navigation stays seed-dependent (N-015) and an uncached computed var's display stays stale (N-016) | reverify_hydration |
| F-004 class-level assignment replaces descriptor | MED regression | **fixed** (#7461: descriptor kept, fresh/pickled instances read the assigned default, dev writes and `reset()` work, e2e dev and prod+redis) — new gaps N-004/N-005 | reverify_core |
| F-005 sqlmodel<0.0.45 cap | MED regression | **fixed** (sqlmodel 0.0.48 resolves; `UTCDateTime()` migrations apply on a fresh db; aware round trip identical to 0.9.12+0.0.47) — with caveats: N-001 below, and a1→a2 `uv -U` upgraders of a naive-datetime app silently change semantics with no release note for #7462 (N-002) | reverify_db_install |
| F-006 component floors unchanged | MED release-eng | **fixed** (every pip/uv upgrade variant from 0.9.12 moves all 13 component packages; fresh `pip install reflex==0.10.0a2` without `--pre` resolves the full train; formapp submits the fixed #7227 payload) | reverify_db_install |
| F-007 npm SIGTERM hang | MED pre-existing | **still broken on Linux** (3/3 on a2; a1 and 0.9.12 identical; bun clean). On macOS arm64 (other session, `macos_lifecycle`): a1 and a2 exit cleanly in <0.3 s, 0.9.12 still hangs — platform-scoped; the Linux finding stands | reverify_db_install, macos_lifecycle |
| F-008 >1 MB storage reconnect storm | MED pre-existing | **still broken** (602–654 websocket opens / ~22 s, 720–780 MB uploaded, no UI error, no server log) | reverify_hydration |
| F-010 pre-connect nav on_load | LOW pre-existing | **still broken** (8/8; redirect hijack case 2/2) | reverify_hydration |
| F-011 forward-ref TypeError | LOW regression | **still broken** | reverify_core |
| F-012 PageContext LookupError message | LOW | **still broken** | reverify_core |
| F-013 rx.Model deprecation location | LOW | **still broken** | reverify_core |
| F-014 `reflex component` message | LOW | **still broken** | reverify_core |
| F-015 duplicate npm notice | LOW | **still broken** (unchanged) | reverify_db_install |
| F-016 ty 0-arg / 5-arg | LOW | **still broken** (ty 0.0.84/0.0.85 and pyright 1.1.414 identical to a1) | reverify_core |
| F-017 redis restart token loss | LOW unknown | **not reproduced** (0/9 clean stops on a2, no pyo3 panic; 1/9 on 10-06 — flaky/unknown, not closable) | reverify_hydration |
| F-018 React 19.3 console error | LOW | **still broken** (2/2) | reverify_core |
| F-009 reflex-chat `initial_messages` leaks across sessions | MED pre-existing (package bug) | pending (`thirdparty_a2` re-run in progress) | thirdparty_a2 |
| F-019 stale frontend across an upgrade gets no user-visible signal | LOW pre-existing | **still broken** (stale 0.9.12 prod tab against the a2 backend keeps working with only the server-side "Frontend version 0.9.12 ... does not match the backend version 0.10.0a2" warning) | upgrade_sweep |
| F-020 upgrading under a running dev server breaks later hot reloads | LOW pre-existing, not actionable | not re-tested (every upgrade here stopped the server first) | upgrade_sweep |

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

### N-015: A computed var's write to state during an ordinary event or client-side navigation is dropped depending on PYTHONHASHSEED; a write to a var that was not already dirty is always dropped (LOW, pre-existing)
- Cluster: `reverify_hydration` | Regression: no (identical on 0.9.12 and 0.10.0a1; #7460 fixed only the `hydrate_and_load` path).
- Repro: `reverify_hydration/cv/drivers/drive_cvnav.py` against cvstore with `PYTHONHASHSEED=0` (variants a/b/e1/e2/f fail; seed 4 passes; (g) always fails). Evidence: `results/f003/cvnav.txt`.
- Mechanism: per-event deltas iterate a `set` and are cleaned afterwards (see FINDING-003 of 10-06); the pattern (computed vars writing state) is undocumented.

### N-016: An uncached computed var keeps showing the value it computed during hydration until the next full reload (LOW, regression unknown)
- Cluster: `reverify_hydration`. cvstore variant (b): after reload, probe, no-op event and client nav, `check` still shows `cleared-by-uncached-cv` while the backend computes `value=''`; the per-client dedup record is not updated by the boot snapshot. 0.9.12 showed the correct value on the seeds where its write worked. Related open PR #7436 (not in this train). Evidence: `results/f003/a2-dev-seed0.summary.txt`, `frames/a2-dev-seed0-b.json`.

`browser_cache_bundle` (other session) ran a pure read-only `@rx.var(cache=False)` control (external value read from a file outside the app; refresh and reload on stable/a1/a2, dev and prod, Chromium and WebKit): 40/40 pass. The staleness is therefore limited to the side-effectful pattern (a computed var writing to state during hydration); it is not a general uncached-var freshness regression (inbox `board/findings-inbox/browser_cache_bundle-3.md`).

Also confirmed by `reverify_hydration` independently: N-005's ComponentState form (`cls.pref = "dark"` on an `rx.LocalStorage` var in `get_component` silently drops persistence; `probes/cs_storage_default_probe.py`, `src/csbox`).

### N-017: Mutating nested dict entries through `dict.values()`/`items()` bypasses dirty tracking — rendered values and cached vars go stale (MEDIUM, pre-existing)
- Cluster: `browser_cache_bundle` (other session, macOS, Chromium + WebKit), independently verified with a second fixture. A public handler running `for item in self.inventory.values(): item["stock"] -= 1` changes the backend (audit 9/19) but the rendered inventory and a cached total stay 10/20/30; after a reload the raw values are right but the cached total is still 30; reassigning the field fixes it. Key iteration plus indexed mutation (`self.inventory[k]["stock"] -= 1`) is the passing control. Identical on 0.9.12, a1 and a2. Root-cause guess: the published `reflex/istate/proxy.py` only wraps `get`/`setdefault` return values and `__getitem__`; the `values()`/`items()` views hand out unwrapped nested dicts. Evidence: `browser_cache_bundle/verify_inventory/` (`runs/{stable,alpha2}/results.json`, screenshots, server logs); inbox `board/findings-inbox/browser_cache_bundle-1.md`.

### N-018: npm users still get a package reinstall on source-only hot reloads (`devDependencies: {}` vs absent key) (LOW, pre-existing)
- Cluster: `browser_cache_bundle`. With npm, a label-only edit raises the install count 1→2 on stable, a1 and a2 although both lockfile hashes are unchanged; the only manifest difference is `devDependencies: {}` in the rendered `package.json` versus no key in the one on disk. Adding that empty object by hand stops the extra installs on both alphas (stable's byte comparison still reinstalls). Bun is unaffected. Root-cause guess: the `package.json` sync/compare in `reflex/utils/frontend_skeleton.py` and the install-cache invalidation in `reflex/utils/js_runtimes.py`. Evidence: `browser_cache_bundle/reload_cache/minimal_results/`, inbox `browser_cache_bundle-2.md`.

### N-019: A background task that completes after session expiry sends only the root delta; untouched child/ComponentState values stay stale until the next foreground event (LOW, pre-existing)
- Cluster: `statemgr_perf` (other session, macOS); independent verifier reproduces 8/8 (stable and a2 × memory and disk × Chromium and WebKit) with 8/8 foreground controls passing. A background handler that releases the lock for 8 s with a 5 s TTL reacquires an expired tree; its completion delta carries only the changed root state, so the page shows root=100 next to the pre-expiry child/component values (11/13/17) while `get_state` reports 0/0/0; the next foreground event rehydrates everything. Not tested on a1, prod or redis. Evidence: `statemgr_perf/verify_expiry/` (`report.json`, screenshots, frames), inbox `statemgr_perf-1.md`.

### N-020: A foreground handler that raises sends no delta; its state changes reach the open page only with the next unrelated event (MEDIUM, pre-existing; verification in progress)
- Cluster: `events`. Disk/memory state manager, dev and prod, a2 = a1 = 0.9.12. `self.status = "partial"; raise RuntimeError` → the error toast arrives at ~+0.05 s, the value is persisted (a reload shows it) but the page keeps the old value until the next event (a "ping" ~3 s later carries it together with its own delta). Same for handler A returning handler B where B raises and for a generator that yields then raises. `on_load` and background tasks deliver their changes immediately with the error. This generalises the 10-06 "chained-raise delta timing" side lead to every raising foreground handler. Repro: `events/src/mini` (`bash bin/start.sh alpha2 dev mini_a2_dev mini`, click "direct raise" then "ping"); driver `driver/drive_mini.py`. Evidence: `events/out/mini_{a2_dev,a2_prod,a1_prod,s_dev,s_prod}/*_report.json` (`first_recv_frame_with_marker.after_ping=true`), frame timeline in `events/NOTES.md` §6.

### N-021: The Redis state manager discards a failed or superseded event entirely, including changes it already delivered to the browser (MEDIUM, pre-existing; verification in progress)
- Cluster: `events`. Dev, a2 = 0.9.12. (a) A generator that yields (page shows `gen-flushed`) then raises → reload shows the pre-event value; (b) two rapid clicks within 1 s on a superseding handler: the page shows `a:start` from the first call, reload shows an empty log; (c) a raise inside `async with self` in a background task after a flushed change → reload shows the old value. Under disk/memory the same cases keep the changes (N-022). Client and server diverge silently; Redis is the production manager. Repro: `redis-server --port 8479`, `bash bin/start.sh alpha2 dev r mini redis`, driver cases `gen_yield_then_raise,sup_split,bg_raise_inside`. Evidence: `events/out/mini_{a2,s}_dev_redis*/` (`client_server_diverged: true`, `ui_after_reload.status: idle`). Not tested in prod.

### N-022: A superseded (cancelled) handler's changes after its last yield are committed and ride in the superseding call's delta (LOW, pre-existing)
- Cluster: `events` (the 10-06 `sup.cancelled_unyielded_mutation` lead). Disk/memory, dev and prod, a2 = a1 = 0.9.12: click "split a", wait 0.6 s, click "split b"; b never touches `log`, yet its delta is `{"other":"b-ran","log":["a:start","a:after-yield"]}` and a reload keeps `a:after-yield`. Evidence: `events/out/mini_*/`*`_report.json` (`sup.split_cancelled_mutation_surfaces`), evapp `/sup` "partial" row.

### N-023: String Vars use UTF-16 code units; a split surrogate pair in prerendered prod HTML triggers React hydration error #418 (LOW, pre-existing)
- Cluster: `events`. `len("a😀b")` renders 4 and `[::-1]` splits the pair on every version, dev and prod (JS semantics). In prod the prerendered `/emoji-rev` page contains `b\xef\xbf\xbd\xef\xbf\xbda` and the browser logs "Minified React error #418"; dev shows no error. 0.9.12 and a1 prod identical. Evidence: `events/out/mini_{a2,s,a1}_prod/*_report.json` (`prerender.emoji_hydration`), evapp `out/{a2,s}_prod` `t_vars [console]`.

### N-024: Calling another handler as a method from a background task outside `async with self` now raises `ImmutableStateError`; inside the lock `type(self)` is `StateProxy` — undocumented behaviour change since 0.9.12 (LOW)
- Cluster: `events`. evapp `/bind` "child.bg_call_parent": a2 and a1 give `bump:self=StateProxy`, `bg_outside=ImmutableStateError`, `p_count=2`; 0.9.12 gives `bump:self=BindParent` twice, `bg_outside=no-error`, `p_count=3` (an unlocked write). The new behaviour is the safer one but the changelog does not mention it. Evidence: `events/out/{a2_dev,a2_prod,s_dev,s_prod}/*_report.json` (`bind.instance_access_and_inheritance.bind-bg-parent`).

### N-025: Prod: an enterprise AG Grid whose `column_defs` come from a State var renders no columns on full page load (HIGH, regression since 0.10.0a1; independent verification in progress)
- Cluster: `ent_grid`. `rxe.ag_grid(column_defs=GridState.cols, row_data=GridState.rows)` renders an empty box (no header, no cells) on full load and reload in prod on a2 and a1 (+ the offline 0.9.7a4 wheel); a literal-`column_defs` grid on the same page renders. Passes in a2 dev and on 0.9.12 prod with the same wheel. Affects the demo's /master-detail State grid, `@rx.memo` + `State.fields.foreach` grids and both ComponentState grids (3/3 runs + probe). Claimed mechanism: enterprise's `formatColumnDefs` returns `[]` while `typeof __reflex === 'undefined'`; reflex assigns `window.__reflex` in a `ReflexProviders` useEffect after the children rendered; before #7064 the first boot delta carried every substate so every consumer re-rendered after hydration, while 0.10's combined `hydrate_and_load` sends only the changed substates, so a consumer of an unchanged substate renders once and stays stale. Core-only repro without enterprise: `ent_grid/apps/core_rerender` (a render-time `window.__reflex` reader of an unchanged substate stays `NO_REFLEX` on a2 prod, `HAS_REFLEX` on 0.9.12 prod and a2 dev; boot frames: 0.9.12 delta = all 7 substates, a2 = root then touched only). `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` fixes the grids but breaks /formatters with React #130 (documented caveat). Minimal repro: `ent_grid/apps/aggrid_min` + `scripts/probe_aggrid_min.py`. Evidence: `ent_grid/out/aggrid_min_prod_alpha2ent/`, `out/ag_prod_{a2,a1,s912}/probe_state_coldefs-*`, `ent_grid/NOTES.md` §1a. Fix direction (not applied): assign `window.__reflex` before the first render (as the lazy-libraries path does) and/or drop the render-time `__reflex` dependency in `formatColumnDefs`.

### N-026: Controlled React Flow edits are reverted by a page reload in prod (MEDIUM, pre-existing)
- Cluster: `ent_grid`. In the flow demo in prod, drag "Default Node" on /overview and reload: the node is back at (0,100) and the backend state is reset too. A `set_nodes` event is sent during boot with the compiled-default positions: React Flow emits mount-time dimension changes and `apply_node_changes(State.nodes, …)` runs on the prerendered defaults before the hydrate arrives. a2 prod 5/5, 0.9.12 prod 3/3; dev passes 3/3. Evidence: `ent_grid/out/flow_prod_{a2,s912}_reload*/`, `scripts/probe_flow_reload.py`.

### N-027: rxe `EventHandlerAPIPlugin` `/_reflex/events/openapi.yaml` returns 500 on a clean install (PyYAML not declared) (MEDIUM, pre-existing, enterprise)
- Cluster: `ent_grid`. The api-catalog advertises the URL; on a fresh venv it answers 500 with `AssertionError: pyyaml must be installed to use parse_docstring` (starlette `SchemaGenerator`). With `pip install pyyaml` it returns a valid OpenAPI 3.0 document with 35 paths, in which the index page is listed as `/index` instead of `/`. Same on 0.9.12. Evidence: `ent_grid/logs/tickets-dev-a2.log` (~line 253), `out/tickets_*_api.json`, `out/tickets_prod_a2_openapi.yaml`.

### N-028: reflex's `window.onerror` throws when the error event has no Error object (e.g. the benign ResizeObserver loop), so nothing reaches `handle_frontend_exception` (LOW, pre-existing)
- Cluster: `ent_grid`. Opening a mantine MultiSelect and clicking an option fires "ResizeObserver loop completed…" with `error=null`; `.web/utils/state.js` (`info: error.name + …`) throws `TypeError: Cannot read properties of null (reading 'name')` at `window.onerror (utils/state.js:1195)`. Same code on 0.9.12. Evidence: `ent_grid/out/mantine_{dev,prod}_a2/`, `out/mantine_prod_s912/` (`page_errors`), `scripts/probe_mantine_pageerror.py`.

### N-029: rxe Event API: a malformed JSON body returns 500; handler argument errors return HTTP 200 with an error body (LOW, pre-existing, enterprise)
- Cluster: `ent_grid`. `{not json` raises `JSONDecodeError` at `event_handler_api.py:1344` → 500; missing/wrong-type/unknown args → 200 `{"error": "... bogus.."}` (doubled period) and "Attempting to send delta to disconnected client" in the log. Same on 0.9.12. Evidence: `ent_grid/out/tickets_dev_a2_api.json`, `out/tickets_prod_s912_api.json`, `scripts/api_tickets.py`.

### N-030: rxe ModelWrapper SSRM/infinite text filter leaves ~20 permanent "Loading rows..." placeholders; the infinite-model add dialog fails on the datetime field (LOW, pre-existing, enterprise)
- Cluster: `ent_grid`. With `REFLEX_DB_URL=sqlite:///reflex.db`, filtering /model-ssrm by name shows the matching rows followed by "Loading rows..." placeholders (stale cached rowCount); the /qa-model-workaround add dialog raises `StatementError: SQLite DateTime type only accepts Python datetime` because "met" is posted as a string. Same on 0.9.12 prod with the same wheel. Evidence: `ent_grid/out/ag_prod_a2/ag_model-ent_grid-a2-ssrm-filtered.jpg`, `out/ag_prod_s912/ag_model-ent_grid-s912.json`, `logs/ag_grid-prod-s912.log`.

### N-031: `rxe.mantine.autocomplete` has no `on_change` trigger, so a controlled Autocomplete cannot be built (LOW, pre-existing, enterprise wheel)
- Cluster: `ent_grid`. `rxe.mantine.autocomplete(value=S.v, on_change=S.set_v)` fails at compile with `ValueError: The Autocomplete does not take in an on_change event trigger`; the only value event is `on_option_submit`. Property of the wheel, independent of the reflex version. Evidence: `ent_grid/logs/mantine-dev-a2.log` (first start), comment in `ent_grid/apps/mantine/mantine/qa_mantine.py`.

## Cluster summaries

### `reverify_hydration` (pass: 14, anomaly: 5, fail: 0 new) — done
F-002 and F-003 fixed (backend-only #7460; `state.js` byte-identical to a1); hydapp s1–s13 sweep matches a1 field by
field except s1b which now passes; reconnect with redis and memory, HMR, timing (a2 = a1; ~170–180 ms faster than
0.9.12 at 80 ms RTT) all good. F-008/F-010 unchanged, F-017 not reproduced. New lows N-015, N-016; N-005 confirmed
again. One prod s10 anomaly (a pre-hydration click lost 1/32, browser timing, not reproducible with a React-ready check).

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

### `upgrade_sweep` (form-designer, github-stats, clock, twitter, twitter+redis prod; stock smoke) — done
No upgrade regression 0.9.12 → 0.10.0a2, in place or cold, dev and prod: every check that passes on 0.9.12 passes on a2; console and network signatures identical to 0.9.12 and to the 10-06 a1 run; client storage written under 0.9.12 is restored and nothing is written on first load (the #7460 positive control still catches the a1 bug); DB rows and alembic heads unchanged, `makemigrations` generates nothing; redis-pickled sessions survive; one-context clock stop/upgrade/restart clean; a1 → a2 in place clean; stock blank-app smoke clean with `.web/package.json` byte-identical to a1. Re-verified F-002, F-003, F-005, F-006 fixed; F-014, F-019 unchanged; N-001 reproduced independently on fresh 0.9.12 and a2 installs. Notes: `upgrade_sweep/NOTES.md`.

### `browser_cache_bundle` (other session, macOS Chromium + WebKit) — done
Production bundle and network payloads (cold home transfer +2.9 % stable→a2, generated JS +0.5 %, initial websocket payload 79 % smaller), gzip/ETag reuse, lazy route deferral, HMR/rebuild cache invalidation (87/88), nested-state matrix (607 checkpoints; the failures are N-017 plus stable-only inherited-background cases that both alphas pass), backend-only and mixed-version deployments (323 assertions), history/BFCache. No new 0.10 regression; N-017 (medium) and N-018 (low) are pre-existing; N-016 narrowed. Results: `board/results/browser_cache_bundle.md`.

### `statemgr_perf` (other session, macOS) — done
Expiry matrix 245/249 (the four failures are stable-only retained disk locks, i.e. the a2 disk-lock cleanup works), 1,200-session churn (a2 disk locks return to zero, stable retains 301), disk persistence boundary documented (a CLI restart wipes `.states` on both versions), duration parsing and App warnings, redis capped pool (no timeouts; 21 state saves in one EVAL vs 21 SETs on stable), performance (handler CPU 33→21 ms, click→DOM 36→23 ms, scalar reads 4.4–4.7× and writes 8.7–10.9× faster, no a2 median more than 20 % slower). One new low, N-019. Results: `board/results/statemgr_perf.md`.

### `events` (61 records × a2 dev / a2 prod / 0.9.12 dev / 0.9.12 prod, + a1 dev from 10-06; pass: most, anomaly: 7, fail: 1 documented) — done
No a2-specific regression: a2 = a1 in every row; the only differences from 0.9.12 are documented 0.10 changes (#7370 "is_background read once" — `deco.late_marker_after_is_background_read` fails on 0.10 by design; #7353 outer-type-only logging; #7312 prod keeps undeclared attributes), the #7319 client nested-list fix (0.9.12 still storms the websocket with 245k–729k frames) and the #7326 slice fix (6890 slice forms match Python on a2/a1; 0.9.12: 204 mismatches + 3180 RecursionErrors), #7465 private attributes verified in mixins, ComponentState and background tasks (dev and prod), and one undocumented change (N-024). The 10-06 `events_vars` partial leads are resolved: `sup.cancelled_unyielded_mutation` → N-022 (pre-existing, state-manager dependent); handler returning/yielding a *nested* list → identical `TypeError` on every version, unsupported, not a lead; `temporal.offline_disconnect` → redone with a pausable TCP proxy, correct on a2 and 0.9.12 (socket closes ~0.1 s after the drop, temporal events dropped, `N3,N4` delivered 0.45–0.54 s after reconnect); `api.bg_get_state_get_var_value_sibling` and `api.dataclass_nested_inplace_mutation` pass everywhere; failing substate `__init__` breaking later roots → by design (eager substate tree), identical on all versions; the sqlmodel verifier's "chained-raise delta timing" side lead → N-020 (every raising foreground handler, identical on 0.9.12 and a1). New: N-020, N-021 (medium, pre-existing, independent verification running), N-022, N-023, N-024. Throttle has no trailing call (documented). Not covered: a single-process 0.9.12 run of the `nested` group, evapp on a1 in prod, Redis in prod. Notes: `events/NOTES.md`, table `events/out/suite_table.md`.

### `ent_grid` (AG Grid dev 20/20 smoke, 46/47 features, 24/29 model; dnd 27/27 dev+prod; flow 22/22 dev, 20/22 prod; mantine 22/22 dev, 23/23 prod; highcharts 12/12 dev, 13/13 prod; tickets 18/18 dev+prod; rxe.App + `reflex export` pass) — done
Enterprise demos on a2 + the offline 0.9.7a4 wheel, dev and prod, baselined on 0.9.12 + wheel (and a1 + wheel for AG Grid). **One new HIGH regression: N-025** (prod AG Grid with State-var `column_defs` renders no columns on full load, since a1; verification running). Everything else passes or is identical on 0.9.12: AG Grid ModelWrapper pages work (F-001 enterprise half fixed), kanban first load writes no LocalStorage default (F-002 fixed), sqlmodel 0.0.48 + SQLAlchemy 2.1.3 migrations and CRUD work (F-005 fixed; greenlet added by hand, N-001); pre-existing N-026..N-031. `rxe.App`: google_font preconnect/css2 links prerendered, badge absent in dev / present fixed-position in prod, `show_built_with_reflex=False` honoured (offline wheel reports tier "enterprise"), no login gate. `reflex export` of dnd: exit 0, backend.zip 13 files, frontend.zip 649, identical file list to 0.9.12 after hash normalisation. Not covered: maps and oidc demos (ent_auth cluster), full AG Grid runs on a1, dnd/highcharts on 0.9.12 (nothing failed), Redis and multi-worker prod. Notes: `ent_grid/NOTES.md`.
