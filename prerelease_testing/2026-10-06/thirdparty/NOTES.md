# Cluster `thirdparty`: breaking-change surface and third-party package compatibility

Pre-release under test: **reflex 0.10.0a1** (published 2026-10-05). Baseline: **reflex 0.9.12**.
Everything was installed from PyPI into isolated venvs. Nothing was installed from `/home/user/reflex` or
`/home/user/reflex-enterprise`, and nothing ran with a checkout as the working directory. Every probe and
driver starts with an assertion that names the venv it expects.

## Headline results

| # | Finding | Severity | Regression vs 0.9.12 |
|---|---------|----------|----------------------|
| 1 | Reading an underscore (backend) State attribute on the class (`cls._X`) now returns the `Field` descriptor instead of its value. This breaks published packages: in reflex-clerk the missing-secret-key guard and the JWT-keys guard are silently bypassed, and reflex-dynoselect fails with `VarTypeError`. It also breaks user code such as `rx.text(State._LABEL)` (`ChildrenTypeError`). The changelog does not mention it. | high | **yes** |
| 2 | A computed var that rewrites a client-storage var (`rx.LocalStorage`/`rx.Cookie`) during hydration never reaches the browser, so the frontend and backend disagree on the value. This breaks reflex-google-auth's cleanup of invalid tokens: a bogus token stays in localStorage on every reload. The failure is deterministic: 5/5 runs fail on alpha and 5/5 pass on stable, in both dev and prod. | high | **yes** |
| 3 | Assigning a declared backend var on the class (`cls._x = v`, as reflex-clerk does with `ClerkState._secret_key = ...` and `set_fetch_user_on_auth`) replaces the descriptor. A fresh instance sees the class value, but after a pickle round trip (disk or redis state manager) it falls back to the declared default. 0.9.12 consistently gave instances the default. | medium | yes (behaviour changed and is now inconsistent) |
| 4 | `PageContext.get()` / `CompileContext.get()` outside a context now raise `LookupError: <ContextVar name='PageContext' at 0x…>`. The old message ("No active PageContext is attached to the current context.") is gone. | low | yes (message only; the type change is documented) |
| 5 | Removed names (`backend_vars`, `inherited_vars`, `get_skip_vars`, `is_backend_base_variable`, `RESERVED_BACKEND_VAR_NAMES`, `CustomComponents`) fail with plain `AttributeError`/`ImportError` and give no pointer to `get_fields()`. The instance `_backend_vars` still exists as a reserved `ClassVar` set to `None`, so `hasattr(state, "_backend_vars")` is still True. | low | n/a (by design, UX) |
| 6 | The `rx.Model` subclass deprecation warning now points at `pydantic/_internal/_model_construction.py:156`; 0.9.12 pointed at `<frozen abc>:106`. Neither names the user's model file, which falls short of #7138's "names the first real user file". | low | no (different, still wrong) |
| 7 | When a route module fails to import in dev (e.g. reflex-clerk), alpha also logs a React 19.3 `Encountered a script tag while rendering React component` console error. 0.9.12, on React 19.2.8, does not. | low | yes (console noise only) |

Workaround for #1: annotate class constants as `ClassVar[...]`. On alpha, `_KEY: ClassVar[str] = "label"` stays a plain class attribute and is not a field. This was verified, but the docs do not mention it.

## Environment and exact rerun commands

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
T=/home/user/reflex/prerelease_testing/2026-10-06/thirdparty   # this directory
# alpha venv: the shared alpha env's exact pins, but stable pydantic (pydantic<2.14), plus the packages
cd $SB && uv --no-config venv --python 3.12 $SB/envs/thirdparty-alpha
uv --no-config pip install --python $SB/envs/thirdparty-alpha/bin/python --prerelease=if-necessary-or-explicit \
   -c $T/alpha-pins.txt $(cat $T/packages.txt) authlib pytest uvicorn psutil playwright==1.63.0 'google-api-python-client>=2.184.0'
# stable venv: shared stable env's freeze (reflex 0.9.12, pydantic 2.13.5) + the same packages
uv --no-config venv --python 3.12 $SB/envs/thirdparty-stable
uv --no-config pip install --python $SB/envs/thirdparty-stable/bin/python --prerelease=if-necessary-or-explicit \
   -r $T/stable-freeze.txt $(cat $T/packages.txt) authlib pytest uvicorn psutil playwright==1.63.0 'google-api-python-client>=2.184.0'
```
Resolved graphs: `logs/freeze-thirdparty-{alpha,stable}.txt`. Python 3.12. Chromium `/opt/pw-browsers/chromium`. Driver venv `$SB/envs/driver`.

Servers (reserved ports 3100-3119 / 8100-8119; one server at a time). Copy an app out of `apps/` into a scratch dir first:
```bash
# usage: bin/start_app.sh <alpha|stable> <app_dir> <FP> <BP> <log> [--env prod]   (setsid; pidfile in $SB/apps/thirdparty/pids)
bin/start_app.sh alpha  <copy>/local_auth_demo      3100 8100 logs/x.log --loglevel debug   # stable: 3110/8110
bin/start_app.sh alpha  <copy>/magic_link_auth_demo 3101 8101 logs/x.log                    # stable: 3111/8111
GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com \
bin/start_app.sh alpha  <copy>/google_auth_demo     3102 8102 logs/x.log                    # stable: 3112/8112
bin/start_app.sh alpha  <copy>/tp_patterns          3103 8103 logs/x.log                    # stable: 3113/8113
REFLEX_API_URL=http://localhost:3106 bin/start_app.sh alpha <copy>/tp_patterns 3106 3106 logs/x.log --env prod  # stable prod: 3116
bin/start_app.sh alpha  <copy>/tp_components        3105 8105 logs/x.log                    # stable: 3115/8115
bin/wait_up.sh http://localhost:3100/ 400 $SB/apps/thirdparty/pids/<app>-alpha.pid
bin/stop_app.sh $SB/apps/thirdparty/pids/<app>-alpha.pid      # kills the whole process group
```
Drivers (run from `drivers/`):
```bash
D="NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
$D drive_local_auth.py   http://localhost:3100 out/local_auth  alpha <copy>/local_auth_demo/reflex.db
$D drive_magic_link.py   http://localhost:3101 out/magic_link  alpha <server log of that run>
$D drive_google_auth.py  http://localhost:3102 out/google_auth alpha
$D drive_patterns.py     http://localhost:3103 out/patterns    alpha
$D drive_storage_only.py http://localhost:3103                       # minimal repro for finding 2
$D drive_components.py   http://localhost:3105 out/components  alpha
$D drive_chat_leak.py    http://localhost:3105 a1
```
AppHarness test (the upstream reflex-local-auth repo at a61d50d has **no tests/** directory, so this test was written from scratch). Ports are pinned into the reserved range:
```bash
cd harness && TP_VENV=thirdparty-alpha TP_FP=3104 TP_BP=8104 REFLEX_TELEMETRY_ENABLED=false NO_PROXY=localhost,127.0.0.1 \
  $SB/envs/thirdparty-alpha/bin/python -m pytest -x -s -p no:cacheprovider test_local_auth_harness.py
# stable: TP_VENV=thirdparty-stable TP_FP=3114 TP_BP=8114 with $SB/envs/thirdparty-stable/bin/python
```
Probes (run from `probes/`, argument = venv name): `import_sweep.py`, `removed_names_probe.py`, `quick_classattr.py`,
`classassign_pickle_probe.py`, `clerk_probe.py`, `cv_assign_delta_probe.py`, e.g.
`$SB/envs/thirdparty-alpha/bin/python quick_classattr.py thirdparty-alpha`. Outputs are in `logs/probe-*`, `logs/removed-names-*.json` and `logs/import-sweep-*.json`.

## 1. Install / import / render sweep (alpha vs 0.9.12)

None of the 22 packages caps reflex. Against the alpha base, each `--dry-run` only **adds** packages, so nothing is downgraded or upgraded (`logs/install-dryrun-alpha.log`). Imports behave identically on both versions (`logs/import-sweep-*.json`).

| Package | Install | Import | Browser result alpha | 0.9.12 | Verdict |
|---|---|---|---|---|---|
| reflex-local-auth 0.5.0 | ok (+bcrypt) | ok | upstream demo + extra pages: 36/38 checks pass, the 2 failures being the `/tp-strict-register` pitfall that fails identically on 0.9.12. Flows covered: register, mismatch, duplicate, bad pw, login + redirect_to, require_login, ProtectedState.on_load, user-info, custom register with email/IP, reload, second tab, fresh context, logout, substate computed vars after user switch, 6 s session expiry. AppHarness test 2/2 on both | same | pass |
| reflex-magic-link-auth 0.2.2 | ok | ok | upstream demo: send link, link printed, login via link, LocalStorage(sync=True) syncs login/logout to other tab, OTP not reusable, rate limit | same | pass |
| reflex-google-auth 0.2.0 | ok (+google-auth) | ok | all demo pages render, custom button opens Google popup (Google rejects the dummy client); **bogus token NOT cleared** | cleared | **regression (finding 2)** |
| reflex-global-hotkey 1.2.3 | ok | ok | keys + modifiers delivered (`a,shift+Shift,shift+B,Escape`) | same | pass |
| reflex-intersection-observer 0.0.9 | ok (+jinja2) | ok | on_intersect/on_non_intersect fire (seen=1, unseen=2) | same | pass |
| reflex-pyplot 0.2.1 | ok (+matplotlib) | ok | figure computed var → PNG data URI, updates | same | pass |
| reflex-motion / reflex-type-animation / reflex-image-zoom / reflex-color-picker (`rx_color_picker`) / reflex-qrcode / reflex-simpleicons | ok | ok | all render and interact (hover scale, typed text, zoom modal, picker on_change, QR re-render, icons) | same | pass |
| reflex-chat 0.0.2a1 | ok | ok | default process reply works; `initial_messages` greeting shown | same | pass (see cross-session leak note) |
| reflex-dynoselect 0.1.0 | ok | ok | **build fails** `VarTypeError: Unsupported Operand type(s) for []: ObjectCastedVar, Field` at `cls.selected[cls._KEY_LABEL]` | build fails later: `EventFnArgMismatchError on_open_auto_focus` (and needs `state_auto_setters=True`) | broken on both; alpha fails because of finding 1 |
| reflex-clerk 1.0.3 | ok (does not declare `authlib`) | ok | route fails to load on both: `/utils/state.js does not provide an export named 'Event'`. Python-level: `clerk_provider()` with no secret key **succeeds**, `ClerkState.secret_key`/`jwt_public_keys` return `Field` | raises intended `ValueError`, statics are `None`/`[]` | page broken on both; Python behaviour **regressed (finding 1)** |
| reflex-webcam 0.1.0 | ok | ok | render crash `ReferenceError: muted is not defined` (`special_props=[Var("muted")]` compiles to `...muted`) | same | broken on both |
| reflex-calendar 0.0.6 | ok | ok | renders 35 day tiles; clicking a tile does not fire on_change (warning "Instantiating components directly") | same | package issue, both |
| reflex-audio-capture 0.1.1 | ok | ok | on_error: worker loads lamejs from cdnjs, which this sandbox blocks | same | not testable here |
| reflex-monaco 0.0.3 | ok | ok | editor loads monaco from cdn.jsdelivr.net (blocked) | same | not testable here |
| reflex-google-recaptcha-v2 0.1.0.post1 | ok (+httpx) | ok | page renders; google.com/recaptcha blocked | same | not testable here |
| reflex-chakra 0.8.2.post1 | ok | **ImportError** `cannot import name '_issubclass' from 'reflex.utils.types'` (also writes `assets/chakra_color_mode_provider.js` into the CWD at import) | same | broken on both |
| reflex-ag-grid 0.0.11 | ok | **ModuleNotFoundError** `reflex.base` | same | broken on both |

Package quirks seen on both versions (context, not regressions):
- **reflex-chat cross-session leak.** `Chat.create(initial_messages=...)` does `cls.__fields__["messages"].default = <list>`, and `Field.default_value()` returns that one list object to every session. Messages typed in one browser session then appear in every other session (`out/components/*-chat-leak.txt`). On 0.9.12 the leak also reaches chats created *before* the mutation (`/chat`). On alpha it reaches only the subclass created afterwards (`/chat-initial`), because alpha copies the field per ComponentState subclass. Packages that set a mutable `Field.default` share it across sessions on both versions.
- **reflex-local-auth demo-pattern pitfall.** A subclass that overrides a helper (`_validate_fields`) and delegates with `self.handle_registration(...)` has its override **ignored** on both versions. Inherited handlers bind to the declaring state's instance, as in 0.9.12's `getattr(parent_state, name)`. So a short-password user was created on both (`/tp-strict-register`).
- **magic-link demo.** `/check-your-email` bounces straight back to `/` because `rx.moment(on_change=...)` fires on mount. This happens on both versions with react-moment 2.0.2 on both.
- `setvar()` needs `state_auto_setters=True` (deprecated) on both: `AttributeError: Variable `x` cannot be set on ...`.

## 2. `reflex component` CLI (alpha) — pass

`reflex component`, `component --help`, `init`, `build`, `share` and `install` all exit 2 with `Error: No such command 'component'. Did you mean 'compile'?`, with no traceback. `reflex --help` no longer lists `component`. UX note: nothing points users of old docs to the component template. On 0.9.12 `component init` runs (and fails at `No module named pip` in a uv venv). Log: `logs/cli-component.log`.

## 3. Removed names probe (`probes/removed_names_probe.py`, `logs/removed-names-*.json`)

| Probe | 0.10.0a1 | 0.9.12 |
|---|---|---|
| `from reflex.constants import CustomComponents` / `reflex_base.constants` / `rx.constants.CustomComponents` | `ImportError` / `ImportError` / `AttributeError` (no hint) | class |
| `State.backend_vars`, `.inherited_vars`, `.inherited_backend_vars`, `.get_skip_vars()` | `AttributeError: type object 'Child' has no attribute ...` (no hint to `get_fields()`) | dicts / set |
| `state_instance._backend_vars` | **`None`** (reserved `ClassVar` for pickle compatibility; `hasattr` is True) | `{'_e': []}` |
| `reflex_base.utils.types.is_backend_base_variable`, `RESERVED_BACKEND_VAR_NAMES` (also via `reflex.utils.types`) | `ImportError` | present |
| `reflex.istate.proxy.is_mutable_type` / `reflex_base.utils.types.is_mutable_type` | both ok | proxy ok / base `ImportError` |
| `PageContext.get()` / `CompileContext.get()` outside a context | `LookupError: <ContextVar name='PageContext' at 0x…>` (an old `except RuntimeError` no longer catches it) | `RuntimeError: No active PageContext is attached to the current context.` |
| `get_fields()` keys | user fields + `_reflex_internal_links`; bookkeeping (`parent_state`, `dirty_vars`, `_backend_vars`, `_was_touched`, …) no longer listed; `Field._backend` / `Field._owner` available | includes bookkeeping |
| **`Child._b` / `Child._e` on the class** | **`Field(default=2…)` / `Field(default_factory=…)`** | `2` / `[]` |

## 4. Downstream State patterns (`apps/tp_patterns`, identical source; `out/patterns/*-report.json`)

| Pattern | alpha dev | alpha prod | 0.9.12 dev/prod |
|---|---|---|---|
| Mixin (`mixin=True`) giving two substates a var, a backend var, a computed var, an event and a background handler; counters independent | pass | pass | pass |
| Overriding a mixin computed var in one substate | **override honoured** (doubled=20) | same | override silently ignored (doubled=2); alpha fixes this |
| Package base state subclassed by the user; inherited handler called on the instance; `get_state(PkgOtherState)` from a handler; `get_value`; `setvar` (with auto setters); `event_handlers["clear"]` reused as on_click; `add_var` at import; `type(...)`-created substate | pass | pass | pass |
| Substate redeclaring an inherited var (alpha only) | independent var (`shadow-set` vs base unaffected) | pass | n/a (raises on 0.9) |
| Class-level backend constants (`cls._LABEL`) | **Field objects; `rx.text(ConstState._LABEL)` → ChildrenTypeError** | same | values |
| Class-assigned static read on the instance | `'configured-at-import'`, reverting to `None` after pickling (`probes/classassign_pickle_probe.py`) | same | `None` always |
| LocalStorage reset by a **computed var** during hydration | **stays 'bad' in browser + UI** | same | cleared |
| LocalStorage/Cookie reset in **on_load**; reset to a non-default value; reset in a normal event | pass | pass | pass |
| Marking a handler background after first use (#7370) | `is_background` stays False (documented); handler still completed | same | becomes True |

## Findings: details and repro

### F1 (high, regression): class access to backend vars returns `Field`
`probes/quick_classattr.py`:
```
alpha : class-level: Field(default='label', ...) ...   rx.text(S._KEY): EXC ChildrenTypeError ...   rx.icon('x', size=S._N): EXC TypeError: Invalid var passed for prop Icon.size ... got value Field(default=16...)
stable: class-level: 'label' 16 {'a': 1} 'x'           rx.text(S._KEY): jsx(RadixThemesText,{as:"p"},"label")
```
Real packages:
- `probes/clerk_probe.py`: alpha `clerk_provider()` with no secret key returns a component, and `ClerkState.secret_key` is a `Field`. Stable raises `ValueError: ClerkProvider requires a secret_key`.
- reflex-dynoselect: `/dynoselect` page build traceback ends `reflex_dynoselect/dynoselect.py:172 cls.selected[cls._KEY_LABEL]` → `VarTypeError: Unsupported Operand type(s) for []: ObjectCastedVar, Field` (`out/components/alpha-report.json`).

Cause: since #7312 every unannotated non-callable class attribute becomes a `Field` data descriptor, and `Field.__get__(None, owner)` returns the descriptor itself when there is no Var (backend fields). The reflex-enterprise 0.9.7a4 wheel already needed `_compat.get_backend_var_default` / `set_backend_var_default` for exactly this. Neither the changelog nor the docs mention it, and `ClassVar` is the only escape hatch.

### F2 (high, regression): client-storage value rewritten by a computed var during hydration is lost
Run `apps/tp_patterns` (dev or prod), then `drivers/drive_storage_only.py http://localhost:<FP>`. The driver sets `localStorage.tp_ls_cv='bad'` and reloads `/storage`. There `StoreState.cv_check` (cached computed var) does `if self.ls_cv == "bad": self.ls_cv = ""`.
```
alpha  seed=1/2/3: RESULT tp_ls_cv='bad' ui='ls_cv=bad' cv='cv_check=cleared-in-computed-var' after_2nd_reload_tp_ls_cv='bad'
stable seed=1/2/3: RESULT tp_ls_cv=''    ui='ls_cv='    cv='cv_check=cleared-in-computed-var' after_2nd_reload_tp_ls_cv=''
```
On alpha the backend holds `''` while the browser holds and renders `'bad'`. A new tab re-sends `'bad'`, so the cleanup never completes. The same value set in `on_load` or in a normal event does arrive.

Real package: reflex-google-auth demo, `drivers/drive_google_auth.py` step "inject-bogus-token". The server logs `Error verifying token: MalformedError(...)` on both versions. 0.9.12 then clears the `...google_auth_state.token_response_json_rx_state_` key; alpha keeps the bogus JSON.

Likely cause: 0.10.0a1 `State.hydrate_and_load` (#7064) applies the browser's client-storage vars and snapshots `self.dict()` in one event, then calls `self._clean()`. Writes made by computed vars during the snapshot are dropped. The delta is diffed against compiled defaults, and the frontend skips writing client storage for the not-yet-hydrated delta. 0.9.12 applied client storage in a separate `update_vars_internal` event whose ordinary delta carried the rewrite.

Note: `probes/cv_assign_delta_probe.py` shows that `get_delta()` itself serialises in hash-seed-dependent order on **both** versions (a stale value goes out with some `PYTHONHASHSEED`s). It is context only and does not discriminate between versions; the browser repro above does.

### F3 (medium, regression): class-assigned backend var is inconsistent across a pickle round trip
`probes/classassign_pickle_probe.py`:
```
alpha : class 'sk_test_123' False | instance (fresh) 'sk_test_123' False | instance (pickle) None True
stable: class 'sk_test_123' False | instance (fresh) None True          | instance (pickle) None True
```
`__getstate__` still writes the field default for the replaced descriptor. A value that a package configured at class level (reflex-clerk `set_fetch_user_on_auth(False)`) therefore applies only until the state is first serialised by the disk or redis manager.

### F4–F7: see the headline table; evidence is in `logs/removed-names-*.json`, `logs/magic_link-*-run*.log` (deprecation location lines) and `out/components/alpha-report.json` (`/clerk` console).

## Benign or surprising observations (not reported as issues)
- PydanticDeprecatedSince20 `__fields__` warnings come from `reflex_base/utils/types.py` (around lines 586-591 and 707) when a SQLModel var type is used. Both versions (`logs/harness-*.log`).
- Prod logs on both versions print `Warning: Page <name> is being redefined with the same component.` once per page (`logs/tp_patterns-*-prod.log`).
- Each prod run logs one `Failed to load resource: 404` console error, probably the favicon; the app has none. Both versions.
- The google demo without `GOOGLE_CLIENT_ID` renders "Missing required parameter client_id" through the error boundary. Both versions; expected.
- The stable run logged `[ERROR] Unexpected exit from worker-1` when stopped with SIGTERM. That is 0.9.12 behaviour; alpha stops cleanly (#7328).
- In dev, `reflex.db` sits inside the backend reload paths on both versions. No reload was observed on DB writes.
- `reflex init` logged the latest PyPI version as 0.9.12, because pre-releases are excluded. Debug level only.

## NOT covered
- Real OAuth logins (Google, Clerk) need real credentials.
- Interaction for reflex-audio-capture (lamejs CDN), reflex-monaco (jsdelivr CDN) and reflex-google-recaptcha-v2 (google.com): this sandbox's browser cannot reach those CDNs.
- reflex-chakra and reflex-ag-grid (community) do not import on either version, so they could not be rendered.
- Python versions other than 3.12, and redis-backed runs. F3 was shown with plain `pickle`, the same mechanism the disk and redis managers use.
