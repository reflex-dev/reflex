# Cluster `thirdparty_a2`: third-party package compatibility on reflex 0.10.0a2 + re-verification of the 10-06 thirdparty findings

Pre-release under test: **reflex / reflex-base 0.10.0a2** (train `r/pre-2026.10.06-37579583012`, all packages from PyPI).
Baselines: **0.10.0a1** (previous train, `thirdparty-alpha` venv) and **0.9.12** (`thirdparty-stable` venv).
Everything was installed from PyPI into isolated venvs; nothing was installed from `/home/user/reflex` or
`/home/user/reflex-enterprise`, and nothing ran with a checkout as the working directory. Every probe/driver asserts
the venv it expects. This run RESUMED an interrupted agent: the venv, the a2 install log, the pip/uv dry-runs and the
a2 import sweep from that agent are kept (`logs/install-a2.log`, `logs/install-dryrun-a2-*.log`,
`logs/import-sweep-thirdparty_a2-a2.json`); everything else (browser runs, harness, probes, verdicts) was done here.

## 1. Headline

| | result |
|---|---|
| 22 third-party packages (import sweep + tp_components browser app, dev and prod) | **identical to 0.10.0a1 and 0.9.12**: 20 import, 2 do not (`reflex-chakra`, community `reflex-ag-grid`, on every version/Python). Same 6 failing page checks on a2, a1 and 0.9.12 (CDN-blocked audio/monaco/recaptcha, webcam `muted`, calendar on_change, dynoselect, clerk route) |
| reflex-local-auth demo (38 browser checks, dev, prod, prod+redis) + AppHarness test | 36/38 in every mode, the 2 failures are a demo-pattern pitfall that fails identically on a1 and 0.9.12; AppHarness test 2/2 on a2, a1 and 0.9.12 |
| reflex-magic-link-auth demo (dev, prod via `ML_FORCE_DEV`, real prod) / reflex-google-auth demo (dev, prod) / reflex-global-hotkey | pass (magic-link: the known `/check-your-email` bounce, identical on all versions); **google-auth bogus-token cleanup is FIXED** (a1 kept the token, a2 and 0.9.12 clear it) |
| 10-06 findings | F-003 and F-004 **FIXED**; F-001 core **UNCHANGED but documented, silent text now a loud compile error, enterprise half FIXED**; F-007, F-008, F-009, F-010, F-011, F-012, F-013, F-014, F-018 **UNCHANGED** (table in section 2) |
| New on a2 | (1) class-level `monkeypatch.setattr` / `mock.patch.object` of a State var default cannot be undone: teardown `TypeError`, patched default leaks into later tests (5.1); (1b) class-level assignment to an unannotated `_x = None` placeholder raises `TypeError: Invalid default for field` for any non-None value and callables are executed (5.2); (2) a second AppHarness app that shares an installed package's states in one process loses the package's handlers (all versions, pre-existing); (3) three of the 22 packages break `reflex run --env prod` on every version (pre-existing); (4) Python 3.14: `state_auto_setters=True` from `rxconfig.py` yields no setters in the backend worker (all versions, 6.5) |
| N-001 (greenlet) | confirmed from the third-party angle: fresh `reflex==0.10.0a2 reflex-local-auth reflex-magic-link-auth` has `sqlalchemy 2.1.3` and no `greenlet`; `import reflex_magic_link_auth` and `reflex db migrate` / `reflex compile` of the local-auth demo raise the SQLAlchemy greenlet ImportError (section 6). Every venv used here has `greenlet` installed |

## 2. Re-verification of the 10-06 findings (per-finding verdict)

Verdict vocabulary: FIXED / UNCHANGED / CHANGED. "a2", "a1", "09" = 0.10.0a2, 0.10.0a1, 0.9.12.

| id | 10-06 status (a1) | verdict on a2 | evidence (paths under this directory) |
|---|---|---|---|
| **F-001** class-level read of a backend var returns `Field`; enterprise AG Grid `__data_source_params_class__` | HIGH regression | **CHANGED**. Core: UNCHANGED, every declaration pattern still reads as `Field` at class level (`probes/quick_classattr.py`, `verification_src/classattr_scripts/derive_a.py`: only diff vs a1 is below), now documented in the a2 changelog. What changed: `f"{S._KEY}"` raises `BackendVarFormatError` (#7456) and the 10-06 e2e app now FAILS TO COMPILE with `BackendVarFormatError: Backend var 'ConstState._LABEL' exists only on the server ... Use a regular state var instead. Happened while evaluating page 'index'` instead of rendering `label=Field(default=...)`; the message names neither `ClassVar` nor `default_value()`. `rx.text(S._KEY)` is still `ChildrenTypeError`, `rx.icon(size=S._N)` still `TypeError`, `rx.foreach(Counter._OPTIONS)` still `TypeError`. **Enterprise half FIXED**: an ANNOTATED dunder default on a mixin/state (the shape of reflex-enterprise's `__data_source_params_class__: Type[...] = ...`) is `Field` on a1 (`'Field' object has no attribute 'from_request'`) and a plain class attribute on a2 and 09 (#7465) | `logs/probe-quick_classattr-*.txt`, `logs/derive_a-*-{dev,prod}.txt`, `logs/derive_a_componentstate-*.txt`, `logs/probe-dunder_probe-*.txt`, `logs/classattr_app-a2-dev.log` (compile error), `out/classattr/`, `out/patterns/{a2,a1,s0912}*-report.json` |
| **F-003** computed-var rewrite of client storage dropped during hydration | MED partial regression | **FIXED** (page loads; the cvstore driver also reloads twice and navigates client-side, reconnect/redis-restart not covered here): `tp_ls_cv` is cleared in the browser on a2 dev seeds {unset,0,1,2,3,4,5,7,11}, prod seeds {0,4}, prod+redis; a1 keeps `bad`; 09 depends on the seed (seed 0 clears, seed 4 keeps `bad` for the tp_patterns app). cvstore variants a, b, e_cookie, e_session, f pass on a2 dev (seeds 0, 4) and prod (seed 0) and FAIL on a1; variant g (computed var writing a plain var) now delivers `plain=set-by-cv` on a2 and `plain=initial` on a1. Real package: reflex-google-auth bogus token cleared on a2 dev and prod, kept on a1, cleared on 09. Display change: the cached computed var shows `value=''` after the clear on a2 (recomputed) where 09 showed the stale `cleared-in-computed-var` (benign, arguably more correct) | `logs/seed-loop-a2-dev.txt`, `logs/seed-loop-a2-prod.txt`, `logs/patterns-suite-{a1-dev,s0912-dev}.txt`, `out/cvstore-*.txt`, `out/cvstore/`, `out/google_auth/{a2-dev,a2-prod,a1-dev,s0912-dev}-report.json` |
| **F-004** class-level assignment to a declared backend var replaces the descriptor | MED regression | **FIXED**. After `Cfg._key = "sk_live"` the descriptor stays a `Field` with `default='sk_live'`; a fresh instance, the SAME instance after `pickle.dumps` and an unpickled copy all read `'sk_live'`; instance writes are dirty-tracked in dev AND prod; `reset()` works and returns to the assigned default. Browser e2e (disk manager, 3.5 s past the debounce, and prod+redis): key stays `sk_live`, instance write, reset, reload all consistent; a1 flips to `None` after serialization (`SetUndefinedStateVarError` on instance writes in dev). Side effects (not defects of the fix, but visible to packages): class-level read after assignment is `Field(default=<assigned>)`, where a1 and 09 returned the raw value (reflex-clerk `ClerkState.secret_key` is a `Field` after `clerk_provider(secret_key=...)`); an assignment whose type does not match the annotation raises `TypeError: Invalid default for field ...` (09/a1 accepted it silently); 09 never applied the class assignment to instances (`None`) | `probes/classassign_pickle_probe.py` + `logs/probe-classassign_pickle_probe-*.txt`, `logs/derive_b-*-{dev,prod}.txt`, `logs/derive_b_reset-*.txt`, `out/patterns/*-classassign.json`, `out/classattr/{a2-dev-classvar,a2-prod-redis-classvar,a1-dev,s0912-dev}.json` |
| **F-007** `reflex run` under npm hangs on SIGTERM without a TTY | MED pre-existing | **UNCHANGED** on Linux: `REFLEX_USE_NPM=1` a2, a1 and 09 all leave the CLI running 30 s after SIGTERM with `[npm run dev] <defunct>` and an orphaned node dev server (PPID 1) on the frontend port; bun control exits cleanly | `f007/npm_sigterm_repro.sh`, `logs/f007-summary.txt`, `logs/f007-{a2-npm,a2-bun,a1-npm,s0912-npm}.log` |
| **F-008** >1 MB client storage reconnect storm | MED pre-existing | **UNCHANGED**: a2 prod, `localStorage.hyd_big` of 1.2 M chars: 723 websocket open/close pairs in ~20 s, never hydrates (`H:no`), no UI error, no server log; 300 k chars hydrates in 0.21 s | `hyd/drivers/hyd_driver.py --only s5`, `out/hyd/a2-prod/s5.json` |
| **F-009** reflex-chat `initial_messages` leaks messages across sessions | MED pre-existing, package | **UNCHANGED**: session B sees session A's `/chat-initial` message on a2 and a1 (only the chat created after the mutation), on 09 it leaks into `/chat` as well. Framework level: a mutable list assigned as `Field.default` (`cls.__fields__["messages"].default = lst`, which still works on a2) is shared by every instance on all three versions | `out/components/{a2,a1,s0912}-dev-chat-leak.txt`, `probes/mutable_default_probe.py` + `logs/probe-mutable_default_probe-*.txt` |
| **F-010** client-side nav before the websocket CONNECT runs the left page's on_load | LOW pre-existing race | **UNCHANGED**: a2 prod `/slow` -> `/other` held 2000 ms: backend trace `slow_load run1 step1`, `other_load#1` (2/2); `/items/1` -> `/items/2`: `item_load id=1`, `item_load id=2` (2/2) | `hyd/drivers/prenav_test.py`, `out/hyd/prenav-a2-prod.json` |
| **F-011** undefined class in a postponed annotation gives a cryptic `ForwardRef` TypeError | LOW regression | **UNCHANGED**: `from __future__ import annotations` + `items: list[Item] = []` -> `TypeError: Unsupported type ForwardRef('list[Item]') for guess_type.` on a2 and a1; 09 -> `NameError: name 'Item' is not defined. Did you mean: 'items'?` | `f011/`, `logs/f011-fwdref.txt` |
| **F-012** `PageContext.get()` outside a context raises a bare `LookupError` | LOW | **UNCHANGED**: `LookupError: <ContextVar name='PageContext' at 0x...>` (also `CompileContext`); 09 `RuntimeError: No active PageContext is attached to the current context.` | `logs/derive_c-*.txt`, `logs/removed-names-*.json` |
| **F-013** rx.Model deprecation warning location points into pydantic | LOW | **UNCHANGED**: `(.../pydantic/_internal/_model_construction.py:156)` in the `rx.Model` scenarios (`model_here`, `model_import`, `both_models`, `pkg_model`) and in every server log and import sweep; 09 `<frozen abc>:106`. The #7138 location logic still names the user file for `direct` (`derive_d.py:18`), `exec` (`:20`), `memo` (`:32`) and `env` (`:42`) | `logs/derive_d-*-*.txt`, `logs/import-sweep-*.stderr`, `logs/magic_link-a2-dev.log` |
| **F-014** `reflex component` removal error has no pointer to the replacement | LOW | **UNCHANGED**: `component`, `--help`, `init`, `build`, `share`, `install` -> `Error: No such command 'component'. Did you mean 'compile'?`, exit code 2, no traceback; `reflex --help` does not list it | `logs/cli-component-a2.txt` |
| **F-018** extra React 19.3 console error when a route module fails to load | LOW | **UNCHANGED**: `/clerk` logs `Encountered a script tag while rendering React component...` on 3/3 loads on a2 and on a1, 0/3 on 09 | `drivers/debug_page.py`, `out/components/*-dev-report.json` (compared with `bin/compare_console.py`: a2 == a1 exactly, 09 lacks only this message) |

Related 10-06 items touched by this cluster (verdicts belong to other clusters): F-002 (no client-storage default write-back on a fresh profile for the local-auth, magic-link and google-auth demos on a2 and a1, `out/fresh_storage/`), F-005/F-006 (the a2 venv resolved `sqlmodel 0.0.48` and every component package at its 0.10 alpha, `a2-freeze.txt`).

## 3. Package sweep: 22 packages on 0.10.0a2 (dev and prod) vs 0.10.0a1 and 0.9.12

Install: the a2 venv resolves 112 packages (`a2-freeze.txt`); every package installs without downgrading or upgrading anything of the train (the per-package `--dry-run` against the shared alpha2 venv only adds packages: `logs/install-dryrun-a2-uv-default.log`, `logs/install-dryrun-a2-pip-default.log`; none of the packages caps reflex: `logs/wheel-requires-dist.txt`). Import sweep (`probes/import_sweep.py`): identical result on a2, a1, 0.9.12 and on Python 3.11, 3.13 and 3.14 (`logs/import-sweep-*.json`, venvs `thirdparty_a2-py311`, `-py313`, `-py314`). `apps/tp_patterns` on Python 3.14 (a2 dev): same as 3.12 except the setvar check (6.5); 3.14 baselines a1 and 0.9.12 fail the same checks as on 3.12 plus the same setvar check. Browser: `apps/tp_components` (one page per package, each page build wrapped so a failing package shows its error instead of breaking the app) driven by `drivers/drive_components.py`.

| package | a2 dev | a2 prod | a1 / 0.9.12 | note |
|---|---|---|---|---|
| reflex-local-auth 0.5.0 | pass (see 4) | pass | same | |
| reflex-global-hotkey 1.2.3 | pass: keys `a`, `shift+Shift`, `shift+B`, `Escape` delivered with modifiers | pass | same | |
| reflex-google-auth 0.2.0 | pass, bogus token cleared | pass | a1 FAIL (F-003), 09 pass | popup to Google opens (Google rejects the dummy client id) |
| reflex-magic-link-auth 0.2.2 | pass (10/11) | pass (10/11) | same | `rx.moment(on_change=...)` fires on mount so `/check-your-email` bounces to `/` on every version |
| reflex-intersection-observer 0.0.9 | pass (`seen=1 unseen=2`) | pass | same | |
| reflex-pyplot 0.2.1 | pass (PNG data URI, updates) | pass | same | |
| reflex-motion, -type-animation, -image-zoom, -color-picker (`rx_color_picker`), -qrcode, -simpleicons | pass | pass | same | |
| reflex-chat 0.0.2a1 | pass (default reply, `initial_messages` greeting) | pass | same | F-009 leak; React "order of Hooks" console error on `/chat` in dev on all three versions |
| reflex-calendar 0.0.6 | renders 35 tiles; click does not fire `on_change` | same | same | package issue |
| reflex-audio-capture 0.1.1 | worker loads lamejs from cdnjs (blocked here) | same | same | not testable here |
| reflex-monaco 0.0.3 | editor loads from cdn.jsdelivr.net (blocked) | **build fails** | same | see section 6 |
| reflex-google-recaptcha-v2 0.1.0.post1 | renders, google.com blocked | same | same | |
| reflex-webcam 0.1.0 | render crash `ReferenceError: muted is not defined` | **build fails** | same | see section 6 |
| reflex-clerk 1.0.3 | route fails: `/utils/state.js does not provide an export named 'Event'` | **build fails** (`MISSING_EXPORT Event`) | same; 09 lacks the F-018 console line | Python level: see F-001 and section 6 |
| reflex-dynoselect 0.1.0 | page build fails `VarTypeError: Unsupported Operand type(s) for []: ObjectCastedVar, Field` (`cls.selected[cls._KEY_LABEL]`) | same | a1 same; 09 fails differently (`EventFnArgMismatchError on_open_auto_focus`) | broken everywhere |
| reflex-chakra 0.8.2.post1 | `ImportError: cannot import name '_issubclass' from 'reflex.utils.types'` | n/a | same | also writes `assets/chakra_color_mode_provider.js` into the CWD at import |
| reflex-ag-grid 0.0.11 (community) | `ModuleNotFoundError: No module named 'reflex.base'` | n/a | same | |

a2 dev: 35 checks, 6 failed (audio, webcam, monaco, calendar, dynoselect, clerk) with exactly the same non-benign console/page errors as a1 (`bin/compare_console.py`); 09 has the same 6 failures. a2 prod (clerk, monaco, webcam left out with `TP_SKIP=clerk,monaco,webcam`, section 6): 34 checks, 3 failed (audio CDN, calendar, dynoselect).

## 4. Auth demos and the AppHarness test (reflex-local-auth 0.5.0, upstream demo + extra pages)

`apps/local_auth_demo` = upstream demo + `tp_extra.py` (short 6 s session, `_validate_fields` override via `self.handle_registration`, `get_state` + inherited computed vars probe). `drivers/drive_local_auth.py`: 38 checks (register, mismatch, duplicate, bad password, login with `redirect_to`, `require_login`, `ProtectedState.on_load`, user-info, custom register with email and IP, reload, second tab, fresh context, logout, substate computed vars after switching user, 6 s session expiry).

| run | result |
|---|---|
| a2 dev / a2 prod / a2 prod + redis | 36/38; failures `/tp-strict-register`: `subclass override of _validate_fields honoured via self.handle_registration()` and `short-password user NOT created` |
| a1 dev, 0.9.12 dev | identical 36/38 (same two checks): inherited handlers bind to the declaring state, so the subclass override is ignored on every version. Not a regression |
| AppHarness `harness/test_local_auth_harness.py` (ports pinned to 3504/8504) | 2 passed on a2 (15.7 s), a1 (12.8 s), 0.9.12 (13.2 s); only the framework's own `PydanticDeprecatedSince20 __fields__` warnings (`reflex_base/utils/types.py:581-585`) |

The upstream repo has no `tests/`; the AppHarness test was written from scratch (register, login with redirect, protected data, reload, user-info, logout).

Extra: dev hot reload while logged in (`drivers/drive_hmr_auth.py`: register + login, append a comment to the app file, wait for the backend to answer `/ping` again (4.1 s), reload the tab, open a second tab, log out): 7/7 checks, no traceback in the server log, no console error (`out/local_auth/a2-dev-hmr-report.json`). Fresh-profile storage check (`drivers/drive_fresh_storage.py`): the local-auth, magic-link and google-auth demos leave only `theme`/`last_compiled_theme` (and the per-tab `token` in sessionStorage, plus Google's own `g_state` cookie) in a fresh profile on both a2 and a1, i.e. no client-storage default write-back from these apps (`out/fresh_storage/`).

## 5. Downstream-style State patterns (`apps/tp_patterns`, identical source on all versions)

| pattern | a2 dev | a2 prod | a2 prod + redis | a1 | 0.9.12 |
|---|---|---|---|---|---|
| mixin (`mixin=True`) giving two substates a var, backend var, computed var, event, background handler | pass | pass | pass | pass | pass |
| overriding the mixin computed var in one substate | override honoured (doubled=20) | same | same | same | silently ignored (doubled=2) |
| package base state subclassed by the user, `get_state(PkgOtherState)`, `get_value`, `setvar`, `event_handlers["clear"]` reused as on_click, `add_var` at import, `type(...)` substate, substate redeclaring an inherited var | pass | pass | pass | pass | pass (redeclare n/a) |
| computed var rewrites a LocalStorage var during hydration (F-003) | **pass** | pass | pass | FAIL | seed-dependent |
| LocalStorage/Cookie reset in `on_load`, to a non-default value, in a clicked event | pass | pass | pass | pass | pass |
| class-level backend constants `cls._LABEL` (F-001) | `Field`, `rx.text(S._LABEL)` -> `ChildrenTypeError` (the app catches it) | same | same | same | values |
| class-assigned static survives serialization (F-004) | **pass** (4/4 incl. second client, +4.5 s) | pass | pass | FAIL (None after 4.5 s) | `None` always |
| handler marked background after first use (#7370) | `is_background` stays False (documented) | same | same | same | |

### 5.1 NEW on a2: class-level patching of a State var default cannot be undone (pytest `monkeypatch`, `mock.patch.object`)

Minimal repro (`pytest_probe/min/test_min.py`, two tests, `logs/pytest-min-*.txt`): `monkeypatch.setattr(Svc, "_limit", 99)` in one test, `assert Svc.get_fields()["_limit"].default == 5` in the next. a2: `1 failed, 1 passed, 1 error` (teardown `TypeError: A Field cannot overwrite another field...`, then `AssertionError: assert 99 == 5`); a1 and 0.9.12: `2 passed`.

`pytest_probe/test_monkeypatch_backend_var.py` and `test_monkeypatch_other_attrs.py` (Python only, no server; run with `-p no:cacheprovider`):

| | a2 | a1 | 0.9.12 |
|---|---|---|---|
| `monkeypatch.setattr(Svc, "_limit", 99)` (also a public var, or `mock.patch.object(Svc, "_client", new=Client(...))`; a `Mock()` value is rejected up front with `TypeError: Invalid default for field`) | a value that fits the annotation is visible to instances during the test; **teardown raises `TypeError: A Field cannot overwrite another field. Define a computed var to read the field at runtime instead.`**; the patched default stays (`Svc._limit` is 99/41 in later tests, `assert inst()._limit == 5` fails) and later tests error too | works and is restored (6/6 and 10/10 tests pass) | patch has no effect on instances (assertion fails) but nothing leaks |
| patching a method, an `@rx.event` handler, an `@rx.var` computed var, a `ClassVar` | pass, restored | pass | pass |
| `Svc._client = <stub of another type>` / `Svc._limit = "x"` | `TypeError: Invalid default for field '_client': expected <class Client> | None, got <Mock ...>` (new validation) | accepted silently | ignored for instances |

Cause (published `reflex_base/vars/base.py`, a2): `BaseStateMeta.__setattr__` (`:4764-4817`) updates `declared.default` / `default_factory` of the EXISTING `Field` in place, and `mock` / `monkeypatch` "restore" by assigning back the saved original, which is that same (already mutated) `Field` object; `_accepts_default` (`:4684-4703`) rejects any `Field` value, so the restore raises and the patched default is never undone. (A zero-argument callable that the annotation does not accept is taken as the default FACTORY, so patching a var with a callable stub is interpreted differently again.) The error text points users at computed vars. Downstream test suites that patch State defaults on the class (a1 allowed it) break and, worse, pollute each other.

### 5.2 NEW on a2: class-level assignment to an UNANNOTATED `None` placeholder raises, and callables are executed

The "declare now, configure later" idiom (`class Cfg(rx.State): _client = None` then `Cfg._client = make_client()` at import or app start) now fails: the unannotated declaration is typed from its default, so the field is `NoneType` and #7461's default validation rejects every other value (`probes/none_slot_probe.py`, `logs/probe-none_slot_probe-*.txt`):

| assignment on the class | a2 | a1 | 0.9.12 |
|---|---|---|---|
| `_client = None` <- `Client()` / `'a string'` / `42` | **`TypeError: Invalid default for field '_client': expected <class 'NoneType'>, got <Client object> of type ...`** | accepted (instances read it) | accepted, ignored by instances |
| `_opt: Optional[Client] = None` <- `Client()` (annotated control) | ok | ok | ok (ignored by instances) |
| `_n = 0` <- `'five'` / `2.5`; `_s = ''` <- `None` | `TypeError: Invalid default ...` | accepted | accepted, ignored by instances |

`probes/callable_assign_probe.py` (`logs/probe-callable_assign_probe-*.txt`): a callable that the annotation does not accept is treated as a default FACTORY and is CALLED to validate what it produces (this is documented in `BaseStateMeta.__setattr__`, `reflex_base/vars/base.py:4764`). For dependency-injection style assignments this means (a) `Cfg._send = send_email` on an unannotated `None` slot executes `send_email()` once as a side effect and then raises `Invalid default ... got <result>` (zero-arg function) or `Default factory for field '_send' failed: send_email() missing 1 required positional argument` (functions with arguments, lambdas); (b) `Cfg._str = hook` on a `str` var is accepted and the instance then reads `hook()`'s RESULT (and `hook` ran twice); (c) annotated `Callable[..., Any] | None` and `Any` slots accept the function and instances read the plain function (a1 gave a bound method). Workaround: annotate the slot (`Optional[Client]`, `Callable[..., Any] | None`, `Any`) or use a `ClassVar`.

## 6. Other observations

### 6.1 `reflex run --env prod` fails to build with reflex-monaco, reflex-webcam or reflex-clerk (every version, pre-existing)
`bin/prod_probe.sh` builds tp_components in prod with only one of the three pages left in (`TP_SKIP`): identical on a2, a1 and 0.9.12 (`logs/tp_components-prod-build-matrix.txt`, `logs/tp_components-*-only-*-prod.log`):
- `/monaco`: `Prerender: Request failed for /monaco/ ... 500` (`Element type is invalid: expected a string ... but got: object` during react-dom/server prerender).
- `/webcam`: `ReferenceError: muted is not defined` during prerender.
- `/clerk`: `[MISSING_EXPORT] "Event" is not exported by "utils/state.js"` (rolldown build error).
The dev server only shows these pages' errors on their own routes; prod aborts the whole build. With the three pages removed the a2 prod build passes.

### 6.2 N-001 seen through the packages (greenlet)
`uv venv envs/thirdparty_a2-nogl && uv pip install --prerelease=allow 'reflex==0.10.0a2' 'pydantic<2.14' reflex-local-auth==0.5.0 reflex-magic-link-auth==0.2.2` resolves `sqlalchemy 2.1.3` + `sqlmodel 0.0.48` and no `greenlet` (`logs/freeze-nogl.txt`). `import reflex_magic_link_auth`, `import reflex.model`, `reflex db migrate` and `reflex compile --dry` in the local-auth demo all die with `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed` (`logs/nogl-import.txt`); `import reflex_local_auth` alone still works. Installing `greenlet` fixes it. All venvs used for the runs here include `greenlet`.

### 6.3 reflex-clerk at the Python level (F-001 consequence, also on a1)
`probes/clerk_jwt_probe.py` (valid RS256 session JWT, stub `ClerkAPIClient` subclass assigned at class level, `set_fetch_user_on_auth(False)`): a2 and a1: `ClerkState.set_clerk_session` raises `TypeError: 'Field' object is not iterable` (the JWKS read at class level is a `Field`); 0.9.12 validates the token (`is_signed_in=True user_id='user_123'`; a later `fetch_user` error is a separate package bug that 0.9.12 reaches because it ignores `set_fetch_user_on_auth(False)` for instances). `clerk_provider()` without a secret key still returns a component on a2 and a1 (`ClerkState.secret_key` is a truthy `Field`) where 0.9.12 raises the intended `ValueError` (`probes/clerk_probe.py`). The package is unusable in the browser on every version anyway (the `Event` import).

### 6.4 AppHarness: a second app in one pytest process loses the handlers of a package both apps use (all versions)
`harness/test_two_apps.py` starts the local-auth demo and then a second small app (`apps/local_auth_min`, its own db url) that also uses `reflex_local_auth`, each in its own `AppHarness` in the SAME process (`TWO_ORDER=ab` or `ba`). The first app always passes. The second app's `require_login` redirect never happens: server log `KeyError: 'No registered handler found for event: reflex___state____state.reflex_local_auth___local_auth____local_auth_state.reflex_local_auth___login____login_state.redir'`. Identical on a2, a1 and 0.9.12, both orders (`logs/harness-two-apps-{a2,a1,s0912}-{ab,ba}.log`). #7359's cross-app fix ("forgets the states of all app modules") covers app modules, not packages the first app already imported, so downstream suites with several `AppHarness` apps over one package need separate processes. (With both apps on the same relative `sqlite:///reflex.db` url the second app failed even earlier, with alembic `Can't locate revision identified by ...` on all three versions, i.e. it ended up using the first app's database; `local_auth_min` therefore uses `sqlite:///reflex_min.db`.)

### 6.5 Python 3.14: `state_auto_setters=True` from `rxconfig.py` generates no setters in the backend worker (all versions, dev and prod)
Found because `apps/tp_patterns` (`rxconfig.py` has `state_auto_setters=True`, `/inherit` uses `UserState.setvar("extra", ...)`) fails its setvar check on Python 3.14 with `AttributeError: 'UserState' object has no attribute 'set_extra'` (`logs/tp_patterns-py314-dev.log`) on a2, a1 (`pymatrix_install-py314`) and 0.9.12 (`pymatrix_install-stable314`), and passes on 3.12 and when `REFLEX_STATE_AUTO_SETTERS=true` is exported to the server. `apps/cfgprobe` + `drivers/drive_cfgprobe.py` read the config inside an event handler (backend process): on 3.14 `get_config().state_auto_setters` is `True` but `has_set_extra=False`; on 3.12 both are True (`logs/cfgprobe-*.log`; also with `--env prod`). Cause (published code): `get_state_auto_setters()` (`reflex_base/config.py`, "Cached state_auto_setters so State-class creation never re-enters get_config()") returns the flag cached when a `Config` was constructed in THIS process, else the env var, else False. A worker that imports the app module before anything built the Config therefore defines its States without setters. Proof without a server: `cd <app dir>; python -c "import tp_patterns.tp_patterns as m; print('set_extra' in m.UserState.event_handlers)"` is False on a2 and on 0.9.12 on Python 3.12 as well; calling `get_config()` first makes it True. On Python <= 3.13 the backend worker is forked from the CLI process after it built the Config, so the flag is inherited; on 3.14 the default start method differs, so the worker starts clean (macOS, which spawns, is expected to behave like 3.14; not tested). Affects packages that need generated setters (reflex-dynoselect's `set_search_phrase`) and any app that enables the deprecated option in `rxconfig.py`; `import_sweep` and every other 3.14 check were identical to 3.12.

## 7. Known / benign (not findings)
- Prod logs print `Warning: Page <name> is being redefined with the same component.` once per page (all versions); every prod page load logs one `Failed to load resource: 404` console error (the app has no favicon).
- `DeprecationWarning: state_auto_setters ...` (the tp apps need generated setters); `Warning: SitemapPlugin plugin is enabled by default ...` and `Implicit Radix Themes enablement has been deprecated` for the magic-link demo (no `plugins` in its rxconfig), identical on a1.
- reflex-chat: `Event handler on_submit expects (dict[str, Any]) -> () but got (dict[str, str]) -> ()` warning at build (all versions).
- Google GSI script/CDN requests blocked by the sandbox proxy (`ERR_TUNNEL_CONNECTION_FAILED`), `gis is not defined` page errors on the google-auth pages (same on every version).
- local-auth driver: one `net::ERR_ABORTED` on `app/routes/_index.jsx?import` during the logout navigation (seen on a2 dev, a1 dev and 0.9.12 dev; none in prod).
- Hash seeds: 0.9.12 is the one that depends on `PYTHONHASHSEED` for computed-var writes (see F-003 row); a2 passed every seed tried.

## 8. Not covered
- Real OAuth logins (Google, Clerk): need real credentials; reCAPTCHA, lamejs and Monaco assets cannot be fetched from this sandbox.
- reflex-chakra and community reflex-ag-grid do not import on any version, so no page could be built.
- The enterprise AG Grid model wrapper itself (reverify_core covers it); only the underlying dunder-attribute mechanism was probed here (`probes/dunder_probe.py`).
- redis-restart behaviour (F-017): other clusters. Python 3.11 and 3.13: import sweep only; Python 3.14: import sweep + tp_patterns (dev) + cfgprobe, not the other apps.
- F-002/F-005/F-006/F-015..F-017: not this cluster's findings.

## 9. Environment and exact rerun commands

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
T=/home/user/reflex/prerelease_testing/2026-10-07/thirdparty_a2          # this directory
W=$SB/apps/thirdparty_a2; mkdir -p $W && cp -r $T/. $W/                   # work copy (never run inside the repo checkout)

# a2 venv (resolves to exactly a2-freeze.txt: 112 packages; greenlet is added on purpose, see 6.2)
cd $SB && uv --no-config venv --python 3.12 $SB/envs/thirdparty_a2-a2
uv --no-config pip install --python $SB/envs/thirdparty_a2-a2/bin/python --prerelease=allow \
   'reflex[db]==0.10.0a2' 'reflex-hosting-cli==0.2.0a1' 'pydantic<2.14' greenlet $(cat $T/packages.txt) \
   authlib pytest uvicorn psutil playwright==1.63.0 'google-api-python-client>=2.184.0'
# baselines: venvs thirdparty-alpha (0.10.0a1) and thirdparty-stable (0.9.12) from the 10-06 run, recreate with
#   uv --no-config pip install --python <venv>/bin/python -r $T/logs/freeze-thirdparty-{alpha,stable}.txt
# Python 3.11/3.13 sweep: same install with --python 3.11 / 3.13 into thirdparty_a2-py311 / -py313
```

Ports: dev frontend 3500 / backend 8500; prod single port 3510 (`REFLEX_API_URL=http://localhost:3510`); AppHarness 3504/8504; redis 8509 (`redis-server --port 8509 --save '' --appendonly no`, `REFLEX_REDIS_URL=redis://localhost:8509`); one server at a time.

```bash
cd $W
# bin/start_app.sh <venv> <app_dir> <FP> <BP> <log> [reflex run args]   (setsid, pidfile in pids/)   bin/wait_up.sh <url> <secs> <pidfile>   bin/stop_app.sh <pidfile>
D="NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
cp -r apps/tp_patterns run/a2/ && bin/start_app.sh thirdparty_a2-a2 $W/run/a2/tp_patterns 3500 8500 logs/x.log
(cd drivers && env $D drive_patterns.py http://localhost:3500 $W/out/patterns a2-dev; env $D drive_classassign.py http://localhost:3500 $W/out/x.json a2-dev; env $D drive_storage_only.py http://localhost:3500)
bin/patterns_suite.sh <venv> <rundir> <label> <dev|prod> [seed]       # start + 3 drivers + stop;  bin/seed_loop.sh <venv> <rundir> <label> <dev|prod> <seed...>   (F-003)
# prod: REFLEX_API_URL=http://localhost:3510 bin/start_app.sh ... 3510 3510 <log> --env prod ; prod+redis adds REFLEX_REDIS_URL
# tp_components (prod: TP_SKIP=clerk,monaco,webcam, same variable for the driver):
(cd drivers && env $D drive_components.py http://localhost:3500 $W/out/components a2-dev; env $D drive_chat_leak.py http://localhost:3500 a2; env $D debug_page.py http://localhost:3500/clerk 3000)
bin/prod_probe.sh <venv> <rundir> <label> <skip-list>                   # which page breaks the prod build
# demos (GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com for google_auth_demo; ML_FORCE_DEV=1 lets the magic-link demo run its dev flow under --env prod)
(cd drivers && env $D drive_local_auth.py http://localhost:3500 $W/out/local_auth a2-dev $W/run/a2/local_auth_demo/reflex.db
               env $D drive_magic_link.py http://localhost:3500 $W/out/magic_link a2-dev <server log>
               env $D drive_google_auth.py http://localhost:3500 $W/out/google_auth a2-dev
               env $D drive_magic_prod_real.py http://localhost:3510 $W/out/magic_link/a2-prod-real.json   # real prod, no ML_FORCE_DEV
               env $D drive_fresh_storage.py http://localhost:3500 a2-local_auth $W/out/fresh_storage/x.json / /login
               env $D drive_hmr_auth.py http://localhost:3500 $W/run/a2/local_auth_demo/local_auth_demo/local_auth_demo.py <server log> $W/out/local_auth/hmr.json)
# AppHarness
(cd harness && TP_VENV=thirdparty_a2-a2 TP_FP=3504 TP_BP=8504 REFLEX_TELEMETRY_ENABLED=false NO_PROXY=localhost,127.0.0.1 $SB/envs/thirdparty_a2-a2/bin/python -m pytest -x -s -p no:cacheprovider test_local_auth_harness.py
                  TWO_ORDER=ab ... test_two_apps.py)      # 6.4
# F-003 cvstore variants: cvstore/app (VERIFY_VENV=<venv name>), cvstore/drivers/drive_cvstore.py <url> <out> <label> [variants]
# F-001/F-004 e2e: e2e/classattr_app (original; fails to compile on a2) and e2e/classattr_app_cv (ClassVar variant) + drivers/drive_classattr.py <url> <out> <label>
# F-007: f007/npm_sigterm_repro.sh <venv_dir> <app_dir> 3501 8501 <1=npm|0=bun> <log>   (needs lsof; deletes <app_dir>)
# F-011: cd f011/fwdref_app && <venv>/bin/reflex compile --dry
# F-008 / F-010 (hydapp from the 10-06 hydration cluster, venv assertion adapted):
mkdir -p run/a2/hydapp/hydapp run/a2/hydapp/assets && cp hyd/hydapp_src/rxconfig.py run/a2/hydapp/ && cp hyd/hydapp_src/hydapp/*.py run/a2/hydapp/hydapp/ && cp -r hyd/hydapp_src/assets/. run/a2/hydapp/assets/
REFLEX_API_URL=http://localhost:3510 bin/start_app.sh thirdparty_a2-a2 $W/run/a2/hydapp 3510 3510 logs/h.log --env prod
(cd hyd/drivers && env $D hyd_driver.py --base http://localhost:3510 --label a2-prod --out $W/out/hyd/a2-prod --only s5; env $D prenav_test.py http://localhost:3510 a2-prod $W/out/hyd/prenav.json 2000)
# Python probes (copy probes/ to a scratch dir first, run with the venv's python, argument = venv dir name):
#   quick_classattr classassign_pickle_probe clerk_probe clerk_jwt_probe removed_names_probe dunder_probe mutable_default_probe mock_patch_probe none_slot_probe callable_assign_probe import_sweep
#   verification_src/classattr_scripts/{derive_a,derive_b,derive_b_reset,derive_c,derive_workarounds,derive_a_componentstate}.py <venv> (REFLEX_ENV_MODE=dev|prod for a and b), derive_d/derive_d.py <venv> <scenario>
# pytest probes: (cd pytest_probe && <venv>/bin/python -m pytest -p no:cacheprovider -q -rA test_monkeypatch_backend_var.py test_monkeypatch_other_attrs.py)
# summaries: bin/summarize_reports.py <out_dir>, bin/compare_console.py <report_a> <report_b> ...
```

## 10. Layout
`apps/` (tp_patterns, tp_components, local_auth_demo, local_auth_min, magic_link_auth_demo, google_auth_demo, cfgprobe), `drivers/`, `harness/`, `probes/`, `pytest_probe/`, `verification_src/` (10-06 classattr scripts re-run), `cvstore/`, `e2e/`, `hyd/`, `f007/`, `f011/`, `bin/`, `logs/` (server logs, probe outputs, import sweeps, freezes, install logs), `out/` (driver reports and a trimmed set of screenshots; baseline screenshots and raw websocket dumps were dropped to keep the directory small), `a2-freeze.txt`, `packages.txt`.

## VERIFICATION (T-1 = section 5.1, T-2 = section 5.2; independent verifier, appended)
Full write-up, probes, per-version outputs and rerun commands: `verification/NOTES.md` (own venvs `verify_tp_0-*`, PyPI pins in `verification/reqs/`).
* **T-1 CONFIRMED** (regression vs a1 and 0.9.12): 15 var kinds (private/public/`rx.field`/unannotated/mutable/factory/mixin/substate/ComponentState/`x: int = None`) x
  `monkeypatch.setattr` / `mock.patch.object` / `pytest-mock` / manual restore all fail on a2 (teardown `TypeError`, default leaks; through a substate `AttributeError` and the leak reaches the declaring parent
  and its other substates); identical on Python 3.11-3.14. Cause is two-part: in-place mutation of the shared `Field` (`reflex_base/vars/base.py:4803-4804, 4815-4817`) so the saved snapshot is the mutated object, plus the
  `Field` rejection (`_accepts_default` is `:4676-4701`, Field branch `:4695-4700`, not 4684-4703); relaxing only the rejection hides the error and keeps the leak. Re-assigning the original value works except when the annotation
  rejects the original default (`x: int = None`). The controls (methods incl. `AsyncMock` private methods, handlers, computed vars, ClassVars) are fine; note that `test_monkeypatch_other_attrs.py` as written shows 3 FAILED + 1 ERROR
  for those controls on a2 only because its own leaking `count` test pollutes them (they pass in isolation). Severity: medium, low prevalence (declared-var-default patching is not seen in public suites; Reflex's own tests patch ClassVars and methods).
* **T-2 NARROWED**: all facts reproduce (179/255 class assignments raise on a2 vs 0 on a1 and 0.9.12; user code ran in 42; `MagicMock()` is called) but this is the documented/review-requested #7461 design, limited to unannotated or too-narrow
  slots; none of the 22 packages trips it (reflex-clerk assigns class-level into annotated slots and is broken by the read side F-001; dynoselect works; ag-grid uses `ClassVar`). Extra: a permissive slot accepts a live client/lock and then every first read
  raises `cannot pickle '_thread.RLock' object`; `ClassVar` is the faithful migration (the "annotate the slot" workaround makes per-instance copies). Severity: low.
