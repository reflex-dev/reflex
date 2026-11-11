# Findings — reflex 0.10.0a1 train + reflex-enterprise 0.9.7a4, gap-validation campaign (2026-10-06)

**Status: interim report (written 2026-10-06 21:40 UTC).** The campaign was interrupted mid-run by an
org spend limit; four explorer agents (ent_demos, dataeditor_components, events_vars,
ent_auth_mcp_redis) were terminated before they could write their reports. Their partial evidence is
preserved and summarized under "Partial clusters" below and will be completed in a follow-up pass.
Everything above that section went through the full explore → independent adversarial verification loop.

Method: PyPI-only isolated venvs (never the checkout), end-to-end Chromium runs in dev and prod with
console/network/websocket/server-log capture, reflex 0.9.12 baselines for every claimed failure, and an
independent verifier agent re-reproducing each claim from the written repro alone (5 verifier runs,
10 claims adjudicated). Six explorer clusters completed; this is a follow-up to the
[2026-10-05 campaign](../2026-10-05/FINDINGS.md) and only covers the gaps identified there (see
[README.md](./README.md) for the gap map).

## Versions under test

reflex / reflex-base **0.10.0a1**; reflex-components-{code,core,gridjs,markdown,moment,plotly,radix,recharts}
0.10.0a1; reflex-docgen 0.10.0a1; reflex-hosting-cli 0.1.73a1; reflex-release 0.1.2a1; reflex-build-sdk
0.0.5; reflex-otel 0.1.0; lucide 1.0.4; react-player 0.9.2; sonner 0.9.4;
**reflex-components-dataeditor 0.9.3.post1** (published 2026-10-06 16:35 UTC, after the previous
campaign; both the alpha and stable 0.9.12 resolve to it); **reflex-enterprise 0.9.7a4**. Baseline:
reflex 0.9.12 (+ reflex-enterprise 0.9.6). All 19 train packages are published with wheel+sdist and pass
the `.pyi` audit ([packaging/audit.log](./packaging/audit.log)). Environment: Linux x86_64, 4 CPU /
15 GB, Python 3.10–3.14, Node 22.22, bun 1.4.2, Playwright 1.63 + Chromium 1194, local redis-server.

## Executive summary

**What works.** The in-place upgrade path is solid: 14 reflex-examples apps (form-designer with
reflex-local-auth, reflexle with reflex-global-hotkey, github-stats, clock, counter, traversal, json-tree,
twitter, upload, lorem-stream, local-component, nba, quiz, snakegame) were baselined on 0.9.12, upgraded
in place (`.web/`, `reflex.lock/`, `.states/`, sqlite kept), re-driven and cold-rebuilt with no app
regressions; Redis state pickled by 0.9.12 (including SQLModel objects in session state) is restored by
0.10.0a1 without re-login. 22 third-party packages install and import identically; reflex-local-auth
(incl. an AppHarness test) and reflex-magic-link-auth work fully. Python 3.10 and 3.14 pass in dev and
prod. The headline changelog items verified here: #7357 (upload no longer chains other clients' events —
0.9.12 fails the test), #7064 (hydration is ~160–180 ms faster at 80 ms RTT, one boot frame instead of
three), #6996 (dynamic routes 200 in prod static serving), #7259, #7210, #7093, #7226, #7326, #7328,
#7236, #6425 (CLI removal), AppHarness isolation, the dataeditor 0.9.3.post1 floor and image-preview
carousel styles, anonymous and OAuth MCP (including uploads) on Redis.

**What blocks (see RELEASE_PLAN.md).**
- FINDING-001 (HIGH, regression, confirmed): class-level reads of backend State vars return the `Field`
  descriptor. Undocumented. It breaks the published **reflex-enterprise 0.9.7a4 AG Grid model wrapper**:
  every `/abstract-wrapper-data` request fails with `AttributeError: 'Field' object has no attribute
  'from_request'` on 0.10.0a1 (never on 0.9.12 + 0.9.7a4).
- FINDING-002 (HIGH, regression, confirmed): the diffed boot hydrate drops `is_hydrated=false`, so the
  first page load writes client-storage **defaults** into localStorage/sessionStorage/cookies for any
  state sent in full; returning visitors keep stale defaults after an app changes them.
- FINDING-003/004/005 (MEDIUM, regressions, confirmed): a client-storage value rewritten by a computed var
  during hydration never reaches the browser; class-level assignment to a declared backend var corrupts
  the descriptor; the new `sqlmodel<0.0.45` cap breaks fresh-since-2026-09-21 `reflex[db]` installs
  (0.9.12-generated migrations referencing `UTCDateTime` fail on a fresh database).

Severity histogram (verified + explorer-only): critical 0 · high 2 · medium 7 · low 11. Refuted or
reclassified claims: 5 (listed below). Partial, unverified leads from the interrupted clusters: 9.

Index:
- FINDING-001: Class-level read of a backend State var returns the `Field` descriptor; breaks enterprise AG Grid model wrapper (HIGH)
- FINDING-002: First page load persists client-storage defaults into the browser (HIGH)
- FINDING-003: Client-storage var rewritten by a computed var during hydration never reaches the browser (MEDIUM)
- FINDING-004: Class-level assignment to a declared backend var replaces its descriptor (MEDIUM)
- FINDING-005: `sqlmodel<0.0.45` cap downgrades fresh 0.9.12 environments and breaks their migrations (MEDIUM)
- FINDING-006: Component-only fixes never reach in-place upgraders because reflex's component floors stay at 0.9.x (MEDIUM, release engineering)
- FINDING-007: `reflex run` under npm hangs on SIGTERM without a TTY and orphans the node dev server (MEDIUM, pre-existing)
- FINDING-008: A client-storage value over the 1 MB socket payload causes an endless reconnect storm (MEDIUM, pre-existing)
- FINDING-009: reflex-chat `initial_messages` leaks messages across sessions (MEDIUM, pre-existing, package bug)
- FINDING-010: Client-side navigation before the websocket CONNECT runs the left page's on_load (LOW, pre-existing race)
- FINDING-011: Annotation naming an undefined class gives a cryptic `ForwardRef` TypeError instead of NameError (LOW, regression)
- FINDING-012: `PageContext.get()` outside a context raises a LookupError with only the ContextVar repr (LOW)
- FINDING-013: rx.Model deprecation warning location points into pydantic internals (LOW)
- FINDING-014: `reflex component` removal error gives no pointer to the replacement (LOW)
- FINDING-015: #7093 "Preferring npm" notice is printed twice (LOW)
- FINDING-016: ty still rejects a 0-arg handler as `Callable[[], Any]`; 5-arg calls fail under pyright and ty (LOW)
- FINDING-017: Redis prod restart once reassigned a new client token after a granian/pyo3 shutdown panic (LOW, unknown)
- FINDING-018: Extra React 19.3 console error when a route module fails to load (LOW)
- FINDING-019: A stale frontend left open across an upgrade gets no user-visible version-mismatch signal (LOW, pre-existing)
- FINDING-020: Upgrading reflex under a running dev server crashes later hot reloads until restart (LOW, pre-existing, not actionable)

## FINDING-001: Class-level read of a backend State var returns the `Field` descriptor; breaks enterprise AG Grid model wrapper (HIGH)

- Cluster: `thirdparty` (+ `ent_demos` partial) | Regression vs 0.9.12: **yes** | Verifier: **CONFIRMED** (core); enterprise consequence: explorer evidence, verifier pending
- Repro (core): from a neutral directory with the alpha venv:
  ```python
  import reflex as rx
  class S(rx.State):
      _KEY = "label"
      _n: int = 16
  print(repr(S._KEY), repr(S._n))        # alpha: Field(default='label', ...) Field(default=16, ...)   0.9.12: 'label' 16
  rx.text(f"{S._KEY}")                   # alpha renders the Field repr silently; rx.icon(size=S._n) raises TypeError
  ```
  Scripts: `thirdparty/probes/quick_classattr.py <venv>`, `thirdparty/verification/classattr/scripts/derive_a.py`, e2e app
  `thirdparty/verification/classattr/e2e_app` (+ `drive_classattr.py`), run in dev and prod.
- Repro (enterprise): copy `/home/user/reflex-enterprise/demos/ag_grid` out, install `reflex==0.10.0a1` +
  `reflex-enterprise==0.9.7a4` (`ent_demos` venv), `reflex db migrate`, `reflex run`, open `/model` (or
  `/model-auth`): the grid stays empty and the backend logs, on every data request,
  `File ".../reflex_enterprise/components/ag_grid/wrapper.py", line 153, in get_data: params = state_cls.__data_source_params_class__.from_request(` →
  `AttributeError: 'Field' object has no attribute 'from_request'` (9× in dev, 5× in prod). The same demo on
  reflex 0.9.12 + reflex-enterprise 0.9.7a4 has zero tracebacks (the mixed-graph control).
- Evidence: `thirdparty/logs/probe-quick_classattr-thirdparty-{alpha,stable}.txt`, `thirdparty/verification/classattr/`
  (JSON, screenshots showing `label=Field(default=...)` UI text in dev and prod);
  enterprise: `ent_demos/logs/ag_grid-dev-alpha.log` lines 353–414, `ent_demos/out/ag_grid_dev_alpha/ag_grid-smoke.json`
  (`http_errors: 4` on `/model`), `ent_demos/out/ag_grid_prod_mixed/*` (no 500s).
- Root cause (verifier): `reflex_base/vars/base.py:4737-4738` (`namespace.update(own_fields)`) makes the
  `Field` the class attribute and `Field.__get__` (`base.py:4273-4274`) returns `self` when `_var is None`,
  which is always the case for backend fields; 0.9.12's `BaseStateMeta.__new__` left the raw value on the
  class. Changed: unannotated `_X = v`, annotated `_x: T = v`, mixin/inherited backend vars, via `cls.`,
  `type(self).`, `self.__class__.`. Unchanged: `ClassVar[...]`, public unannotated `KEY = ...` (frontend Var
  on both), instance reads. `rx.field()` backend vars read `None` on 0.9.12 and `Field` on alpha.
- Verification notes: not documented in PR #7312, its news fragments, docs, review threads, epic #7302 or
  the CHANGELOG; reflex-enterprise 0.9.7a4 itself ships a private `_compat.get/set_backend_var_default`
  shim and `ClassVar` statics to survive it, but missed `__data_source_params_class__`. Among 37 published
  wheels only reflex-clerk and reflex-dynoselect use the pattern directly (both already broken on 0.9.12
  for other reasons); the main risk is user code (silent wrong UI text, broken equality/truthiness, and
  compile-time `ChildrenTypeError`/`TypeError`/`VarTypeError`) with no deprecation path. Fix direction:
  class access of a backend field returns `default_value()` (optionally with a deprecation warning), or
  document a `ClassVar` migration and audit internal `getattr(cls, name)` callers.

## FINDING-002: First page load persists client-storage defaults into the browser (HIGH)

- Cluster: `hydration` | Regression vs 0.9.12: **yes** | Verifier: **CONFIRMED**
- Repro: minimal app `hydration/verification/f1-client-storage-defaults/apps/f1combo`: one state with
  `rx.LocalStorage("wu-light", name="wu_ls")`, `rx.Cookie("wu-unset", name="wu_ck")`,
  `rx.SessionStorage("wu-x", name="wu_ss")` and `wu_id: str = rx.field(default_factory=lambda: uuid.uuid4().hex)`.
  `reflex run --env prod`, load in a fresh browser profile: on alpha, localStorage `wu_ls=wu-light`,
  sessionStorage `wu_ss=wu-x` and cookie `wu_ck=wu-unset` are now set; on 0.9.12 none are. Change the
  defaults in source, restart, reload with the same storage: alpha still shows the old defaults (and the
  connect packet sends them back as if the user had set them); 0.9.12 shows the new ones. Driver:
  `drivers/f1_check.py http://localhost:<P>/ - state.json out.json wu-ls`. Also `hydration/mini_writeback` + `scripts/mini.sh`.
- Evidence: `hydration/results/*/s1b*.json` (first delta: root without `is_hydrated_rx_state_` + Sub in
  full with reset defaults), `hydration/verification/f1-client-storage-defaults/results/`,
  `hydration/results/reconnect-alpha-memory/result.json` (returning visitor keeps `sub-ls-default` vs stable `sub-ls-NEWDEFAULT`).
- Root cause (verifier): `reflex/state.py:2339-2352` `hydrate_and_load` resets client storage, applies
  the browser values and sets `is_hydrated=False`; `_diff_against_initial_state` (`:2497-2509`) then sends
  hash-mismatched states in full (including reset defaults) and drops vars equal to their default for
  hash-matched states, which removes the root's `is_hydrated_rx_state_` (False equals its default) while the
  root stays in the delta because router vars changed; the frontend's `applyClientStorageDelta`
  (`reflex_base/.templates/web/utils/state.js:1045-1090`) only skips storage writes when
  `is_hydrated_rx_state_` is present and falsy, so it writes every storage var in the delta. Reconnects (no
  hashes) and whole-list hash mismatches keep `is_hydrated:false` and are safe.
- Verification notes: trigger narrowed to states that hold storage vars AND are sent in full
  (a `default_factory`, a time-dependent cached computed var, an env/pid-derived default in the same state);
  a storage-only state with static defaults is not written. Cookies with `max_age` get a real expiry refreshed
  on every boot. `sync=True` across tabs shows a brief stale revert in a forced race (alpha only). The
  written defaults are indistinguishable from user choices, so changed defaults never reach returning
  visitors and cookies are set without user action; browsers keep the values even after a fix. Same code on
  `origin/main`. Fix idea: always keep `is_hydrated_rx_state_: false` in the root of the diffed boot delta,
  or skip storage writes for the boot delta. Related to FINDING-003 (complementary symptom of #7064).

## FINDING-003: Client-storage var rewritten by a computed var during hydration never reaches the browser (MEDIUM)

- Cluster: `thirdparty` | Regression vs 0.9.12: **partial** (0.9.12 already failed on ~half of the
  `PYTHONHASHSEED` values; alpha fails always) | Verifier: **CONFIRMED** (severity lowered from high)
- Repro: app `thirdparty/verification/clientstorage-hydrate/apps/cvstore`:
  ```python
  class ACachedCv(rx.State):
      ls: str = rx.LocalStorage(name="v_a")
      @rx.var(cache=True)
      def check(self) -> str:
          if self.ls == "bad":
              self.ls = ""
              return "cleared"
          return f"value={self.ls!r}"
  ```
  `PYTHONHASHSEED=4 bin/start.sh alpha <app> 3604 8604 <log>`; `drivers/drive_cvstore.py http://localhost:3604 out x a`
  sets `localStorage v_a='bad'` and reloads. Alpha (any seed): storage and UI keep `bad`, `check='cleared'`,
  backend `ls=''`. 0.9.12 with seed 4: storage becomes `''`; with `PYTHONHASHSEED=0` it fails like alpha.
  Real package: reflex-google-auth 0.2.0 upstream demo with a bogus token in localStorage — kept 8/8 on
  alpha, kept on 2/11 seeds on 0.9.12 (`thirdparty/apps/google_auth_demo`, `drivers/drive_google_auth.py`).
- Evidence: `thirdparty/out/patterns/*-report.json`, `thirdparty/verification/clientstorage-hydrate/`
  (variant table: cached/uncached computed var clearing LocalStorage/Cookie/SessionStorage, substate variant
  — alpha FAIL always, stable seed-dependent; `on_load` and clicked-event variants PASS everywhere; a computed
  var writing a *different plain var* FAILs on both versions for every seed).
- Root cause (verifier): `reflex/state.py:2339-2352` applies the browser values, snapshots
  `_resolve_delta(self.dict())` and then `_clean()`s; `BaseState.dict()` (`state.py:1975-1996`) reads base
  vars before it evaluates computed vars, so the computed var's write lands after the value was captured and
  only marks it dirty; `clean_state` (`reflex/istate/delta.py:303-313`) wipes that mark. On 0.9.12 the same
  write went through `update_vars_internal`'s per-event delta, which iterates a `set`, so the outcome depends
  on hash-seeded ordering. Protected pages stay locked on both versions (no auth bypass); the alpha snapshot
  additionally sends values derived from the rejected token to the frontend.
- Verification notes: the pattern (writing state from a computed var) is undocumented and was never
  reliable, but a published package depends on it. Fix directions: flush vars dirtied during `dict()` in a
  follow-up delta that is not marked not-hydrated; or rebuild deltas until no new dirty vars appear (also
  fixes the plain-var variant and the old coin flip); or document that computed vars must not write state.

## FINDING-004: Class-level assignment to a declared backend var replaces its descriptor (MEDIUM)

- Cluster: `thirdparty` | Regression vs 0.9.12: **yes** | Verifier: **CONFIRMED** (worse than claimed)
- Repro: `class C(rx.State): _k: str | None = None`; `C._k = "sk"` (the pattern reflex-clerk's
  `set_fetch_user_on_auth`/`_secret_key` and reflex-dynoselect's `_raw_options` use). A fresh instance reads
  `'sk'`; after `pickle.loads(pickle.dumps(inst))` it reads `None`; in dev `inst._k = "x"` and `inst.reset()`
  raise `SetUndefinedStateVarError`; in prod the write is not dirty-tracked, so Redis drops it. 0.9.12
  consistently ignored the class assignment for instances. Scripts: `thirdparty/probes/classassign_pickle_probe.py`,
  `thirdparty/verification/classattr/scripts/derive_b.py`, `derive_b_reset.py` (run with `REFLEX_ENV_MODE=dev|prod`), e2e app.
- Evidence: `thirdparty/logs/probe-classassign_pickle_probe-*.txt`, `thirdparty/verification/classattr/out/`
  (Chromium runs with the disk manager: the live instance flips back within ~2 s with no reload).
- Root cause (verifier): `BaseStateMeta` (`reflex_base/vars/base.py:4656-4746`) has no `__setattr__`, so
  `cls._x = v` replaces the `Field` data descriptor while `__fields__` keeps the old one; `__getstate__`
  (`reflex/state.py:2046-2054`) writes the stale default into `vars(self)`; the dev `__setattr__` guard
  (`state.py:1489-1504`, `_has_data_descriptor` `:347-362`) rejects the name, which also breaks `reset()`
  (`:1512-1515`); `redis.py:514` persists only touched states. Fix direction: a metaclass `__setattr__` that
  updates the Field default for declared names (as enterprise's `_compat.set_backend_var_default` does), or a clear error.

## FINDING-005: `sqlmodel<0.0.45` cap downgrades fresh 0.9.12 environments and breaks their migrations (MEDIUM)

- Cluster: `upgrades_a` (independently reproduced by `pymatrix_install`) | Regression vs 0.9.12: **yes**, for
  environments that resolved `reflex[db]==0.9.12` fresh after 2026-09-21 (sqlmodel ≥0.0.45) | Verifier: **CONFIRMED**
- Repro: `uv --no-config pip install --python <venv> 'reflex[db]==0.9.12'` → sqlmodel 0.0.47. App with
  `class Post(rx.Model, table=True): title: str; created_at: datetime`; `reflex db init` writes a migration
  containing `sqlmodel.sql.sqltypes.UTCDateTime()`; insert an aware datetime; a handler doing
  `datetime.now(timezone.utc) - p.created_at` works. Then `uv pip install --prerelease=allow -U 'reflex[db]==0.10.0a1'`
  → sqlmodel 0.0.44 (pip and `pip --pre` do the same). Reading the row now gives a naive datetime
  (`TypeError: can't subtract offset-naive and offset-aware datetimes`; `str(dt)` loses `+00:00`; `rx.moment`
  shifts by the viewer's UTC offset); `rm reflex.db && reflex db migrate` fails with
  `AttributeError: module 'sqlmodel.sql.sqltypes' has no attribute 'UTCDateTime'` (new deploy, CI, clone).
  `AwareDatetime`/`NaiveDatetime` fields and `from sqlmodel import UTCDateTime` also fail under 0.0.44.
  Scripts: `upgrades_a/verification/sqlmodel-datetime/scripts/dt_matrix_probe.py`, `dtapp/`, `drive_dtapp.py`;
  `pymatrix_install/apps/dbmig` (`alembic/versions/ace2dea073f9_.py` generated by 0.9.12) + `scripts/dt_probe.py`.
- Evidence: `upgrades_a/logs/sqlmodel-probe.txt`, `upgrades_a/verification/sqlmodel-datetime/`,
  `pymatrix_install/logs/1d-mig-alpha-migrate-fresh.log` (AttributeError) vs `1d-mig-stable-migrate-fresh.log` (pass).
- Root cause: `reflex-0.10.0a1` METADATA `Requires-Dist: sqlmodel<0.0.45,>=0.0.24; extra == 'db'`
  (PR #7424, fragment filed as `misc`: "the newer default UTC storage rejects existing naive datetime
  values"); sqlmodel 0.0.45 maps plain `datetime` to `UTCDateTime` (`sqlmodel/main.py:757-760`,
  `sql/sqltypes.py:9-49`); reflex's alembic render hook (`reflex/model.py:334-357`) emits the
  `sqlmodel.sql.sqltypes.UTCDateTime()` reference; autogenerate uses `compare_type=False` (`model.py:448`) so
  in-place `makemigrations` is a no-op. SQLite-only for the naive-read flip (Postgres tables created under
  0.0.47 are `timestamptz` and keep returning aware values); explicit `sa_column=Column(DateTime(timezone=True))`
  is unaffected (the official examples use it).
- Verification notes: the cap is a deliberate, defensible choice for the pre-2026-09-21 population, but the
  changelog sentence "preserves existing datetime storage behavior" is false for every fresh 0.9.12
  environment; requiring `sqlmodel>=0.0.45` alongside `reflex[db]` is now unsatisfiable (with
  reflex-local-auth the resolver silently drops it to 0.4.0). Needs a breaking-change entry and a recipe:
  replace `sqlmodel.sql.sqltypes.UTCDateTime()` in migrations with `sa.DateTime(timezone=True)`; replace
  `AwareDatetime`/`NaiveDatetime` fields with `sa_type=DateTime(...)`; or drop the `[db]` extra and depend on
  `sqlmodel>=0.0.45` directly.

## FINDING-006: Component-only fixes never reach in-place upgraders because reflex's component floors stay at 0.9.x (MEDIUM, release engineering)

- Cluster: `pymatrix_install` | Regression: no (same policy as 0.9.12) | Verifier: metadata verified by the
  orchestrator (`reflex==0.10.0a1` requires `reflex-components-core>=0.9.6`, `-radix>=0.9.9`, `-moment>=0.9.4`,
  the rest `>=0.9.0` — identical to 0.9.12); behavioral evidence explorer-only.
- Repro: `pip install reflex==0.9.12`, then `pip install -U --pre reflex==0.10.0a1` (or `uv pip install
  --prerelease=allow reflex==0.10.0a1`, or a plain `pip install reflex==0.10.0a1` with no `--pre`): reflex and
  reflex-base move to 0.10.0a1, every component package stays at 0.9.x
  (`pymatrix_install/freeze/1b-pip-upgrade-after.txt`). The #7227 form fix listed in reflex's own changelog
  then has no effect: `pymatrix_install/apps/formapp` submits `{"form_id": "on", "form_content_wrapper": "on",
  "plain_box": ..., "submit": ""}` on that graph (`logs/1b-formapp-upgraded-result.txt`) and
  `{"bool_input": true, "empty_input": "", "name_input": "foo"}` on the full train. The same applies to
  #6675, #7226, #7366 and react-dropzone 17, and `pip install -U reflex` at 0.10.0 final will behave the same.
- Decision needed: raise the floors of the component packages whose changes the reflex changelog advertises
  (the repo's own sibling-floor rule would call for `>=0.10.0.dev0`), or move those entries to the component
  changelogs and tell users to upgrade `reflex[all]`/each component.

## FINDING-007: `reflex run` under npm hangs on SIGTERM without a TTY and orphans the node dev server (MEDIUM, pre-existing)

- Cluster: `pymatrix_install` | Regression vs 0.9.12: no (0.9.12 also hangs) | Verifier: pending (3/3 explorer runs + bun control + 0.9.12 baseline)
- Repro: `pymatrix_install/scripts/npm_sigterm_repro.sh <venv> <app_dir> 3393 8393 1 <log>` (runs `reflex init`,
  `REFLEX_USE_NPM=1 setsid reflex run`, `kill -TERM <reflex pid>`, waits 30 s). The CLI is still running after
  30 s, `[npm run dev] <defunct>`, `node .../react-router dev --host` has PPID 1 and still listens on :3393; a
  second SIGTERM does not help; killing the orphaned node lets the CLI exit in ~3 s. With bun (last arg 0) the
  shutdown is clean.
- Evidence: `pymatrix_install/logs/3d-sigterm-alpha-npm.log`, `3d-sigterm-alpha-bun.log`, `3d-sigterm-stable-npm.log`.
- Why it matters now: #7328 claims `reflex run` "stops its frontend on SIGTERM and SIGINT without a TTY",
  and #7093 now keeps a project on npm automatically when `reflex.lock/` only has `package-lock.json`.

## FINDING-008: A client-storage value over the 1 MB socket payload causes an endless reconnect storm (MEDIUM, pre-existing)

- Cluster: `hydration` | Regression vs 0.9.12: no (0.9.12 loops too) | Verifier: not run (explorer evidence on both versions)
- Repro: with `hydration/hydapp` running, `localStorage.setItem('hyd_big','x'.repeat(1200000))`, reload
  (`hyd_driver.py --only s5`). Alpha: the 1.2 MB value rides in the socket.io CONNECT packet, Engine.IO
  closes the connection (`maxPayload 1000000`), the disconnect handler reconnects immediately with no backoff:
  819 connects / 21.9 s, 982 MB sent, page never hydrates, no UI error, no server log. 0.9.12: 753 connects,
  903 MB, ~750 type-error log lines.
- Evidence: `hydration/results/s5_storm_summary.json`, `hydration/shots/alpha-prod-s5_big_1200000.png`.

## FINDING-009: reflex-chat `initial_messages` leaks messages across sessions (MEDIUM, pre-existing, package bug)

- Cluster: `thirdparty` | Regression: no | Verifier: not run
- Repro: `thirdparty/apps/tp_components` page `/chat-initial`, `drivers/drive_chat_leak.py http://localhost:3105 a1`:
  a fresh session sees another session's messages on both versions (the package sets a mutable `Field.default`
  and the framework hands the same object to every session). On 0.9.12 the leak also reaches the plain
  `/chat` page; alpha confines it to chats created after the mutation.
- Evidence: `thirdparty/out/components/{alpha,stable}-chat-leak.txt`. Downstream issue (reflex-chat), with a
  framework question: should a mutable default shared by reference be copied per session?

## FINDING-010: Client-side navigation before the websocket CONNECT runs the left page's on_load (LOW, pre-existing race)

- Cluster: `hydration` | Regression vs 0.9.12: no (same race window; 0.9.12 runs the *new* page's on_load twice) | Verifier: **CONFIRMED**, severity lowered from medium
- Repro: `hydration/drivers/prenav_test.py <base> <label> out.json 2000` (holds `/_event` for 2 s via
  `route_web_socket`, loads `/slow`, clicks to `/other` before CONNECT): alpha backend trace `slow_load step1` →
  `other_load#1`, with `slow_progress=1` landing on `/other`; 0.9.12: `other_load` ×2. Realistic thresholds
  (verifier's websocket-upgrade delay proxy `verification/f6-prenav-onload/drivers/upgrade_delay_proxy.py`):
  ~300 ms delay with a bot-speed click, ~500 ms with a click 300 ms after interactive; same thresholds on 0.9.12.
  Alpha-only user-visible case: `/redir` (on_load returns `rx.redirect`) → click `/items/2` at 800 ms → alpha
  lands on `/items/2`, runs its on_load, then the stale redirect bounces to `/other` (2/2); 0.9.12 stays.
- Root cause: `state.js:703-708` `bootAuth()` reads the location at call time and `:728` assigns it once at
  mount (`socket.current.auth = bootAuth(true)`); `connect()` returns early when the socket exists (`:687-692`);
  the location effect (`:1284-1318`) queues the new page's `on_load_internal` after the CONNECT. socket.io-client
  4.8.4 supports a function-valued `auth`, but a lazy auth alone would bring back 0.9.12's double on_load.

## FINDING-011: Annotation naming an undefined class gives a cryptic `ForwardRef` TypeError instead of NameError (LOW, regression)

- Cluster: `pymatrix_install` | Regression vs 0.9.12: yes | Verifier: pending
- Repro: `pymatrix_install/apps/fwdref_app` (`from __future__ import annotations`; `items: list[Item] = []`
  with `Item` never imported): alpha `reflex compile --dry` → `TypeError: Unsupported type ForwardRef('list[Item]') for guess_type.`;
  0.9.12 → `NameError: name 'Item' is not defined. Did you mean: 'items'?`. On 3.14 the same happens with a
  bare lazy annotation (`scripts/fwdref_tb.py`). Likely cause: field creation (`reflex_base/vars/base.py` ~L4560)
  uses `types.resolve_annotations`, which swallows NameError (`reflex_base/utils/types.py` ~L1487) and keeps the
  ForwardRef; the new message names neither the state nor the field.

## FINDING-012: `PageContext.get()` outside a context raises a LookupError with only the ContextVar repr (LOW)

- Cluster: `thirdparty` | Regression: no (the type change is documented in #6553; `EventContext` already raised the bare repr on 0.9.12) | Verifier: **CONFIRMED**
- `$SB/envs/alpha/bin/python -c "import reflex; from reflex_base.plugins.compiler import PageContext; PageContext.get()"` →
  `LookupError: <ContextVar name='PageContext' at 0x...>` vs 0.9.12 `RuntimeError: No active PageContext is attached to the current context.`
  (`reflex_base/context/base.py:38-47`). UX polish: re-raise with the friendly message.

## FINDING-013: rx.Model deprecation warning location points into pydantic internals (LOW)

- Cluster: `thirdparty` / `pymatrix_install` | Regression: no (0.9.12 pointed at `<frozen abc>:106`, also wrong) | Verifier: **CONFIRMED**
- A user file containing `class M(rx.Model, table=True): x: int = 0` warns
  `(.../pydantic/_internal/_model_construction.py:133)` on alpha. The #7138 fix works for exec'd, direct,
  `@rx.memo` and deprecated-env-var paths; only the `rx.Model` subclass path is wrong because
  `reflex_base/utils/log.py:1019-1058` `_exclude_paths_from_frame_info` does not exclude pydantic/sqlmodel.
  Because dedupe is keyed on the location, a second model file produces no warning on either version.

## FINDING-014: `reflex component` removal error gives no pointer to the replacement (LOW)

- Clusters: `thirdparty`, `pymatrix_install`, `upgrades_b` | Regression: no (deliberate removal, #6425)
- `reflex component --help` (and `init`/`build`/`share`/`install`) → `Error: No such command 'component'. Did you mean 'compile'?`
  (rc=2). The changelog points to the wrapping-React docs and the component template; the CLI mentions
  neither, so a component package whose CI runs `reflex component build` fails with no hint.

## FINDING-015: #7093 "Preferring npm" notice is printed twice (LOW)

- Cluster: `pymatrix_install` | Regression: no (the notice is new)
- After one `REFLEX_USE_NPM=1 reflex run`, a plain `reflex run` prints two identical
  "Info: Preferring npm because reflex.lock/ has package-lock.json and no bun.lock…" lines
  (`pymatrix_install/logs/3a-npm-run2-plain.log`) although `_log_implicit_npm_notice` is `functools.cache`d
  per lock directory — likely two processes (CLI + compile worker); not traced.

## FINDING-016: ty still rejects a 0-arg handler as `Callable[[], Any]`; 5-arg calls fail under pyright and ty (LOW)

- Cluster: `pymatrix_install` | Regression: no
- `pymatrix_install/apps/typing_fixture/handlers_0_5.py` with ty 0.0.84 and pyright 1.1.414 on 3.10 and 3.14:
  the alpha fixes ty for 1–4-arg handlers passed as callables (0.9.12 flagged lines 75–80) but still flags
  line 75 (`c0: Callable[[], Any] = Shop.h0`); fully applied 5-arg calls (`Shop.h5(...)`, also inside `on_click=`)
  fail under both checkers on both versions (`EventCallback.__call__` overloads accept at most four values).
  The changelog's "up to four arguments" is partially unmet (0-arg) and implies only ty has the 5-arg limit.

## FINDING-017: Redis prod restart once reassigned a new client token after a granian/pyo3 shutdown panic (LOW, unknown)

- Cluster: `hydration` | Regression: unknown (1 of 9 alpha multi-worker stops, 0 of 7 stable; granian 2.8.4 both)
- `hydration/drivers/reconnect_driver.py --venv alpha --port 3221 --manager redis`: once, the stop logged
  `thread 'tokio-rt-worker' panicked at .../pyo3-0.29.2/src/internal/state.rs:330:9: Cannot drop pointer into
  Python heap without the thread being attached`, and the reconnect got `new_token`, counter 0. Clean restarts
  kept token and state 4/4 on both versions (`redis_restart_loop.py`).
- Evidence: `hydration/logs/recon-alpha-redis-1.shutdown-tail.log`, `results/reconnect-alpha-redis/result.json`.

## FINDING-018: Extra React 19.3 console error when a route module fails to load (LOW)

- Cluster: `thirdparty` | Regression: yes (React 19.3.0 vs 19.2.8) | Verifier: not run
- `thirdparty/apps/tp_components` `/clerk` in dev (`drivers/debug_page.py`): alpha logs "Encountered a script
  tag while rendering React component" once per load when the route module fails (the reflex-clerk import);
  stable logs it 0 of 2. Cosmetic; the underlying route failure is the package's.

## FINDING-019: A stale frontend left open across an upgrade gets no user-visible version-mismatch signal (LOW, pre-existing)

- Clusters: `upgrades_a`, `upgrades_b` | Regression: no (0.9.12 has the same warning-only path)
- Prod tab open across stop → upgrade → start: the old 0.9.12 bundle reconnects and keeps working through the
  legacy hydrate/on_load/update_vars events; only the backend logs "Frontend version 0.9.12 … does not match
  the backend version 0.10.0a1". In dev, vite reloads the page by itself. Evidence:
  `upgrades_a/logs/ckprod-up.server.log:299`, `upgrades_a/shots/ckprod/`, `upgrades_b` twitter stale-prod runs.

## FINDING-020: Upgrading reflex under a running dev server crashes later hot reloads until restart (LOW, pre-existing, not actionable)

- Cluster: `upgrades_a` | Regression: no | Verifier: **CONFIRMED** (restart fully fixes; `.web`/`reflex.lock` sane afterwards)
- `uv pip install --prerelease=allow -U 'reflex==0.10.0a1'` into a venv whose `reflex run` (0.9.12) is still
  running, then edit the app: `ImportError: cannot import name 'state_manager_disk_debounce' from
  'reflex_base.environment'` → `Unexpected exit from worker-1`, `/ping` dead, repeats on every edit. The worker
  is forked from the old process and imports the new `reflex/istate/manager/disk.py:14` against the in-memory
  0.9.12 `reflex_base.environment`. At most a future version could detect it and tell the user to restart.

## Refuted / reclassified claims

- **"0.9.12 passes the computed-var/client-storage test deterministically (5/5)"** (`thirdparty`): refuted
  by the verifier — 0.9.12 fails the explorer's own app with `PYTHONHASHSEED=4` (and ~half of all seeds);
  the alpha makes a pre-existing coin flip deterministic (FINDING-003 kept, severity lowered to medium).
- **"Pre-connect navigation runs the wrong on_load — medium regression"** (`hydration`): reclassified low;
  the race window and thresholds are identical on 0.9.12, which misbehaves differently (double on_load) in it.
- **"Class-level backend attribute change breaks published packages broadly"** (`thirdparty`): narrowed —
  only reflex-clerk and reflex-dynoselect use the pattern and both are already broken on 0.9.12 for other
  reasons; the real exposure is user code and reflex-enterprise's AG Grid model wrapper (FINDING-001).
- **`uv pip install 'reflex==0.10.0a1'` without `--prerelease=allow` fails to resolve** (`upgrades_a`,
  `pymatrix_install`): not a defect — uv rejects the transitive `reflex-base==0.10.0a1` pre-release pin for
  every alpha (0.9.12a1 and 0.9.9a1 behave the same); `--prerelease=allow`, an explicit `reflex-base` pin, or pip work.
- **`instance._backend_vars` still exists and returns None** (`thirdparty`): by design — `state.py` reserves it
  as `ClassVar[None]` for pickle compatibility; the consequence (hasattr-based compat shims misdetect it) is informational.

## Partial clusters (agents terminated by the spend limit; evidence preserved, nothing verified)

Working directories are preserved under the scratchpad and will be finished in the follow-up pass; the
reusable parts are not yet copied into this tree.

- **`ent_demos`** (enterprise 0.9.7a4 demos on 0.10.0a1; `/home/user/reflex-enterprise/demos/ag_grid` copied,
  dev + prod on alpha, plus a mixed-graph control reflex 0.9.12 + enterprise 0.9.7a4 and a stable pair 0.9.12 + 0.9.6):
  AG Grid feature pages in dev — master-detail, pivot, tree data, cell selection, fill handle, aligned grids,
  integrated charts, memo/props QA grids — 17/17 checks, no console errors; `ag_grid-smoke` 19/19 routes load.
  **The `/model` and `/model-auth` pages (ModelWrapper) fail on alpha with the `from_request` AttributeError
  (→ FINDING-001); the mixed-graph control is clean.** Prod alpha feature run: 43 checks, 4 not-ok —
  `master_detail: scenario completed` (locator timeout), `clipboard: Ctrl+C/Ctrl+V copies gold row0 -> row4 and
  fires change event` (no toasts), `memo grid: column defs from State.fields.foreach` (empty), `qa_memo: scenario
  completed` (timeout) — all unverified and possibly driver timing under load 6–12. SSRM/infinite datasource:
  `filtered rows all match and count matches db` and `infinite: text filter matches db` / `add dialog inserts row`
  fail on alpha AND the SSRM filter check also fails on the mixed graph (likely pre-existing or a driver
  assumption). The stable pair (enterprise 0.9.6) 404s on `%3F`-encoded datasource URLs (the a1 "datasource URL
  query parameters" fix). dnd started (install only); flow/mantine/highcharts/tickets not reached.
- **`dataeditor_components`** (alpha dev runs only; no stable baseline yet): data editor renders, image preview
  overlay has the carousel styles (#7081 works); not-ok checks to re-examine: `overlay_*_closes_on_escape`
  (2), `first_edit_fast_typing_keeps_all_chars` (got `ed` — characters dropped on the first edit),
  `edit_bool_single_click_toggles`, delete-key `on_delete` payload (2), `foreach_editors_render`
  (data editors inside `rx.foreach` rendered 0 canvases), `static_DataEditorTheme_applied` (flaky: failed
  once, passed on rerun), `cs_b_edit_isolated` (flaky), big grid long tasks (14 tasks >200 ms, max 558 ms);
  forms page: `id_backed_controls_present_when_unset`/`filled_payload_values` — `f_select` (an `rx.select`
  with `name`) absent from the submitted payload; `dialog_submit_does_not_trigger_outer_form` failed;
  recharts tick-formatter checks 12/15 not-ok with empty detail (likely a selector problem — plotly 17/17,
  radix 11/11, code 9/9, download 10/10, match 7/7, memo names 2/2 pass). One memo-param naming crash was
  checked against 0.9.12 and is pre-existing.
- **`events_vars`** (alpha dev 52 checks: 39 pass / 9 anomaly / 4 fail; partial stable runs): supersedes,
  throttle/debounce, Var slicing with Var bounds/steps, `deep_equals`, type-check logging and most state-API
  checks pass; #7326 confirmed (0.9.12's `State.items[-1::-1]` in `rx.foreach` renders empty, alpha correct).
  Leads: `sup.cancelled_unyielded_mutation` — a superseded (cancelled) handler's mutation after its last yield
  still becomes visible; a handler *returning* or *yielding* a nested event list raises `TypeError: Your
  handler NestState....` on alpha (0.9.12 fails those cases too, differently — #7319 flattens *client* lists);
  `temporal.offline_disconnect` inconclusive (the test never closed the socket); `api.bg_get_state_get_var_value_sibling`
  and `api.dataclass_nested_inplace_mutation` not-ok with incomplete detail; string Var slicing/length counts
  UTF-16 units (emoji len 4, reversal splits surrogate pairs — both versions, JS semantics); throttle has no
  trailing call so the last keystrokes never reach the backend (both versions). One probe also showed that
  a failing `__init__` in one substate breaks every later root instantiation in the same process (noted, unverified).
- **`ent_auth_mcp_redis`** (dev, Redis state manager): anonymous MCP (bump/computed/multi-yield/background task,
  session isolation), OAuth MCP (metadata, PRM, registration, invalid-scope rejection, partial consent, consent
  deny, IdP deny, exchange, refresh, granted scope) and MCP uploads (ticket flow; replays, wrong handler, bad
  ticket, bearer-instead-of-ticket all rejected) behave correctly; `/_reflex/mcp` without slash is a 307 in dev.
  OIDC login/logout cycle and cross-tab runs captured but not summarized; prod, multi-worker, expiry and maps not reached.
- **Side lead** (sqlmodel verifier): when a chained handler raises (`add_aware → return State.load → TypeError`),
  its partial state update arrives with the *next* event instead of with the error; the same failure in the
  initial `on_load` delivers immediately (`upgrades_a/verification/sqlmodel-datetime/shots/dt-a1-inplace-display.json`, frames t=20.18 vs 23.92).

## Cluster summaries

### `smoke` / `packaging` (pass)
Blank app on the published train, driven in Chromium: clean. `.pyi` audit of all 19 packages (wheel vs sdist,
no foreign stubs, counts match the manifest): PASS, including dataeditor 0.9.3.post1. Removed-name grep over
23 third-party wheels and the stable component wheels: no references (only enterprise, behind guards).

### `thirdparty` (pass: 14, anomaly: 9, fail: 6)
22 packages installed against the alpha with no conflicts or downgrades; imports identical to 0.9.12
(reflex-chakra and reflex-ag-grid fail on both). reflex-local-auth demo 36/38 both versions + AppHarness test
2/2; reflex-magic-link-auth 10/11 both; global-hotkey, intersection-observer, pyplot, motion, type-animation,
image-zoom, color-picker, qrcode, simpleicons identical. Found FINDING-001/003/004/009/012/013/018 and the
`reflex component` message; downstream State patterns (mixins, package base states, `get_state`, `setvar`,
`event_handlers` reuse, `type()`-created substates, shadowing) all pass, and the alpha fixes 0.9.12 silently
ignoring a substate's override of a mixin computed var.

### `upgrades_a` (pass: 17, anomaly: 6, fail: 1)
form-designer, reflexle, github-stats, clock, counter, traversal, json-tree: 0.9.12 → in-place → cold, dev and
prod, identical flows and console signatures; LocalStorage/Cookie/Redis data written by 0.9.12 restored by
0.10.0a1; package.json diffs exactly the expected pins; SIGTERM clean on alpha vs orphaned vite on 0.9.12
(#7328); hot reload reuses the install (#7236). Found FINDING-005 (verified), 019, 020.

### `upgrades_b` (pass: 20, anomaly: 5, fail: 0)
twitter, upload, lorem-stream, local-component, nba, quiz, snakegame: identical before/after, prod on both
versions (twitter + lorem-stream with Redis and 9 workers), `reflex export` zip lists identical, hostile upload
filenames contained, 12 MB upload sha256 match, #7357 multi-client uploads 9/9, #7226 string plotly titles now
render. No regressions.

### `hydration` (pass: 17, anomaly: 5, fail: 3)
16-page probe app, 15 scenarios × {alpha, stable} × {dev, prod}: client storage of every kind on root/substate/
ComponentState, `sync=True` tabs, on_load variants (redirect, background, raising, superseded), defaults that
differ from compiled ones, dynamic/catch-all routes, pre-connect clicks, reconnect with memory/disk/redis, hot
reload. Confirmed #7357 and the #7064 timing claim. Found FINDING-002 (verified), 008, 010 (verified), 017.

### `pymatrix_install` (pass: 16, anomaly: 9, fail: 5)
Install-path matrix (uv, pip, pip --pre, uv project mode, mixed no-`--pre` graph with 360 modules importing
and a component app clean in dev/prod), Python 3.10 and 3.14 state apps 14/14 each, #7259/#7210/#7093 verified,
`reflex component` removal, AppHarness 21/21 on both versions, templates dashboard app from a clone, ty/pyright
matrix. Found FINDING-005 (dup), 006, 007, 011, 014, 015, 016.

### `ent_demos`, `dataeditor_components`, `events_vars`, `ent_auth_mcp_redis` (partial)
See "Partial clusters" above; `statemgr_perf` not started.
