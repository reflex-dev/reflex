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

## VERIFICATION — class-level backend attributes

Independent verifier, 2026-10-06. Covers headline findings 1 (claim A), 3 (claim B), 4 (claim C) and 6 (claim D). I did not read the explorer's transcript. Work dir: `$SB/apps/verify_thirdparty_0/`. Ports: 3600/8600 (dev), 3601 (prod, single port) and redis on 8603. All servers and redis were stopped afterwards; a `/proc/net/tcp` check shows nothing listening on 3600-3603/8600-8603. Scripts, logs, screenshots and the e2e app are in `verification/classattr/` (`scripts/`, `logs/`, `out/`, `e2e_app/`, `bin/`). Every script asserts the venv it runs in. Run them from a scratch copy, never from inside the checkout:

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
V=/home/user/reflex/prerelease_testing/2026-10-06/thirdparty/verification/classattr
mkdir -p $SB/apps/x && cp -r $V/scripts/. $SB/apps/x/ && cd $SB/apps/x
for v in alpha stable; do for m in dev prod; do REFLEX_ENV_MODE=$m $SB/envs/$v/bin/python derive_a.py $v; done; done   # also derive_b.py, derive_b_reset.py, derive_workarounds.py
$SB/envs/{alpha,stable}/bin/python derive_c.py {alpha,stable}
cd derive_d && $SB/envs/alpha/bin/python -u derive_d.py alpha <direct|exec|model_here|model_import|both_models|memo|env>   # one scenario per process
$SB/envs/thirdparty-{alpha,stable}/bin/python derive_a_dynoselect.py thirdparty-{alpha,stable}
```

### 1. Written repros re-run as-is
I copied `probes/quick_classattr.py`, `classassign_pickle_probe.py` and `clerk_probe.py` to a neutral directory and ran them on `alpha` (pydantic 2.14.0b2), `thirdparty-alpha` (pydantic 2.13.5), `stable` and `thirdparty-stable`; `clerk_probe.py` only on the two thirdparty venvs. The output matched `logs/probe-*.txt` exactly on every venv (`verification/classattr/logs/orig-*.txt`). The written repro is sufficient. One caveat: NOTES says to run the probes "from `probes/`". That directory is inside the `/home/user/reflex` checkout, so copy the probes out first.

### 2. Claim A: which declaration patterns changed
Source: `scripts/derive_a.py`, log `logs/derive_a.txt`. Dev and prod gave identical results on each version.

| Declaration on an `rx.State` | Class-level read on 0.9.12 | Class-level read on 0.10.0a1 | Changed? |
|---|---|---|---|
| `_X = "label"`, `_N = 16`, `_D = {...}` (unannotated backend) | the value | `Field(default=...)` | **yes** |
| `_x: str = "label"` (annotated backend) | the value | `Field` | **yes** |
| backend var declared in a `mixin=True` state, read via the mixin or the using state | the value | `Field` | **yes** |
| backend var inherited by a substate (`Child._inh`) | the value | `Field` | **yes** |
| reads via `cls._x` in a classmethod, `type(self)._x`, `self.__class__._x` | the value | `Field` | **yes** |
| `_x: str = rx.field("v")` / `_x = rx.field("v")` | **`None`** (0.9.12 `Field.__get__` is a typing stub with no body, stable `reflex_base/vars/base.py:3925-3931`) | `Field` | neither returns the value; truthiness flips False to True |
| `_X: ClassVar[str] = "v"` and `X: ClassVar[str] = "v"` | the value (not a field) | the value (not a field) | no |
| `KEY = "label"` (unannotated, public) | a frontend `StringCastedVar`; it **is** a state var on both versions, and `KEY_rx_state_` is in `dict()` sent to the client | same | no |
| `pub: str = "v"` | Var | Var | no |
| instance read `self._x` | the value | the value | no |

Effects of the alpha behaviour at the Python level: `S._X == "label"` is False; `f"{S._X}"` gives `"Field(default='label', ...)"`; `S._N + 1` and `S._D["a"]` raise TypeError; `bool(S._fld)` is True. In `rx.ComponentState.get_component`, `f"+{cls._step}"` silently renders `+Field(default=5, is_var=True, ...)` (`logs/derive_a_componentstate.txt`). `rx.foreach(Counter._OPTIONS, ...)` raises `TypeError: Unsupported type ... Field for LiteralVar`.

Real browser (`e2e_app/`, Chromium, dev and prod with redis): alpha renders `label=Field(default='label-const', ...)` and a button labelled `+Field(default=5, ...)`, with no error in the server log or the console (`out/alpha-dev.png`, `out/alpha-prod-redis.png`). 0.9.12 renders `label=label-const` and `+5`. Instance reads work on both versions (counter goes to 5).

Mechanism (alpha site-packages):
- `reflex_base/vars/base.py:4737-4738`: `namespace.update(own_fields)` installs each Field as the class attribute.
- `base.py:4273-4274` (`Field.__get__`): `if instance is None: return self if self._var is None else self._var`. Backend fields never get a `_var`, so the docstring at `:4269` ("The Var (or this field, if it has none) for class access") describes exactly this.
- 0.9.12's `BaseStateMeta.__new__` built `own_fields` but never put them in the namespace (stable `base.py:4287-4291`). The raw value stayed the class attribute, and instances read backend vars from `_backend_vars` (stable `reflex/state.py:869-873`, `:1955-1957`).

Intended? Nothing says so.
- The PR #7312 body, its five news fragments (`news/+field-descriptors.{breaking,performance}.md`, `news/+inherited-var-proxy.bugfix.md`, `packages/reflex-base/news/+field-descriptors.{breaking,feature}.md`), its docs edits (`docs/state/overview.md`, `docs/state_structure/overview.md`) and all its review threads are silent on class-level reads of backend vars.
- Epic #7302 only says "Class access returns the `Var`".
- The 0.10.0a1 CHANGELOGs only say "`Field` is now the descriptor holding a state var's value".
- `docs/` on the release branch never mentions `ClassVar`.
- The only related review thread was greptile's "ClassVar becomes state field" ("Class access no longer behaves as a class constant"), and it was fixed. That suggests class constants were meant to keep working.

So this is an undocumented side effect, not a documented design. The org did know about it: reflex-enterprise 0.9.7a4 ships `_compat.get_backend_var_default` / `set_backend_var_default` ("Update a backend-var default without replacing a field descriptor") and declares every class-level static as `ClassVar`. The behaviour is still present on `origin/main` 62a56ba7f (2026-10-06): `base.py:4274` is unchanged and no commit has touched `base.py` or `state.py` since the release branch.

The previous campaign's `2026-10-05/core_state` covered descriptor ownership, shadowing and pickling, but always read backend vars on **instances** (`owner._private`, `shadow._private`). It never read or assigned one at class level, so this was a real coverage gap.

Workarounds, identical on both versions and modes (`logs/derive_workarounds.txt`):
- `_KEY: ClassVar[str | None]`: class read, class assignment, fresh-instance read, pickle round trip and `rx.text(W._KEY)` are all consistent.
- `S.get_fields()[name].default_value()` reads a declared backend default.

### 3. Claim A: real-world prevalence (`logs/wheel-grep-raw.txt`)
I grepped all 37 wheels in `$SB/downloads/wheels` with `unzip -p` (no extraction or execution) for `(cls|<Name>|self.__class__|type(self))._<name>` and classified each hit:
- **Affected:** reflex-clerk 1.0.3 reads and assigns the annotated `_secret_key`, `_jwt_public_keys`, `_clerk_api_client` and `_fetch_user` at class level (`clerk_provider.py:122-168,180,396`). reflex-dynoselect 0.1.0 reads the unannotated `_KEY_LABEL`, `_KEY_KEYWORDS`, `_icon_size`, `_DEFAULT` and `_COLOR_PLACEHOLDER` in a ComponentState (`dynoselect.py:85-180`), and assigns to the declared `_raw_options: list[...]` with `component.State._raw_options = options` (`:443`, which is claim B).
- **Not affected:**
  - reflex-ag-grid 0.0.11: `_grid_component` and `_model_class` are `ClassVar`, and the package fails to import on both versions anyway.
  - reflex-enterprise 0.9.7a4: uses `ClassVar` plus the `_compat` shim.
  - Every `reflex_components_*`, `reflex_hosting_cli` and `reflex_chakra` hit is a Component or helper classmethod, or `Var._js_expr`.
  - `reflex_dynoselect.options.Option._SEARCH_DELIMITER` is on a `dict` subclass, not a State.
- reflex-examples (158 `.py` files) has 0 hits, and the release docs have 0 (the only hits are `PropDocsState._create_setter(...)` method calls).
- Caveat on the named packages: both are already broken on 0.9.12 for other reasons. reflex-dynoselect, re-checked here (`logs/derive_a_dynoselect.txt`): alpha fails at `dynoselect.py:172` with `VarTypeError ... ObjectCastedVar, Field`. 0.9.12 fails at `:192` (`set_search_phrase` missing) and, with `REFLEX_STATE_AUTO_SETTERS=true`, at `:188` with `EventFnArgMismatchError on_open_auto_focus`. reflex-clerk's route already fails in the browser on 0.9.12, per this cluster's table. Also, the clerk change fails **closed**: with a `Field` as the key set, `jwt.decode` cannot verify anything, so this is not an auth bypass. The real exposure is user code, including the silent `f"{cls._X}"` and truthiness cases.

### 4. Claim B: class-level assignment to a declared backend var
Re-derived with `scripts/derive_b.py`, `scripts/derive_b_reset.py` and the e2e app.

On alpha, after `Cfg._key = "sk_live"` (declared `_key: str | None = None`), `type(Cfg.__dict__["_key"])` goes from `Field` to `str`, while `get_fields()["_key"]` is still `Field(default=None)`. Then:
- A fresh instance reads `'sk_live'`.
- **The same live instance** reads `None` right after `pickle.dumps(inst)`. `__getstate__` (`reflex/state.py:2046-2052`) writes `f.default_value()` into `vars(self)`, the live instance dict, and with no data descriptor left that entry shadows the class attribute.
- The unpickled copy reads `None`.

New consequences the explorer did not report:
- **Dev mode:** an instance write `self._key = ...` raises `SetUndefinedStateVarError`. The dev-only guard at `state.py:1474-1506` passes only names backed by a data descriptor (`_has_data_descriptor`, `:347-362`), and a `str` has none. `self.reset()` raises the same error, because it calls `setattr` for every own field (`:1512-1515`).
- **Prod mode** (no guard): the write lands in the instance dict but is not dirty-tracked (`dirty_vars=[]`, `_was_touched=False`). The redis manager persists only touched states (`reflex/istate/manager/redis.py:514`), so the write is lost.

On 0.9.12 the class attribute changes, but instances always read the declared default (`None`), writes are dirty-tracked and `reset()` works, in both modes.

Real server and Chromium (`e2e_app/`, `out/*.json`, `logs/e2e-*.log`):

| step | alpha dev (default disk manager) | alpha prod + redis | 0.9.12 dev | 0.9.12 prod + redis |
|---|---|---|---|---|
| `show` | `key='sk_live'` | `key='sk_live'` | `key=None` | `key=None` |
| `show` 3.5 s later, no reload | **`key=None`** (debounced disk save flipped the live instance) | **`key=None`** (state reloaded from redis) | `key=None` | `key=None` |
| `set_instance` then `show` | **server `SetUndefinedStateVarError`**; `key=None` | no error, **write lost**; `key=None` | `key='set-on-instance'` | `key='set-on-instance'` |
| `reset` | **server `SetUndefinedStateVarError`** (no `reset-done`) | ok | ok | ok |

Supported pattern? No. Nothing in the release branch's docs or tests assigns a declared non-ClassVar var on the class. The framework tests that assign at class level declare the attribute `ClassVar`: `BackgroundTaskState._started` (test_state.py:2994), `OnLoadCancelState._gates` (:6274) and `Table._data` (:6055, assigned at :6085). The requested grep `git grep -n "_secret_key\|cls\._" origin/r/pre-2026.10.05-37378928999 -- tests/units/test_state.py` returns only `cls._data = data` (ClassVar) and two `state_cls._var_dependencies` / `_potentially_dirty_states` framework internals.

### 5. Claim C: `PageContext.get()` outside a context
`scripts/derive_c.py`: alpha raises `LookupError: <ContextVar name='PageContext' at 0x...>` (same for CompileContext). 0.9.12 raised `RuntimeError: No active PageContext is attached to the current context.`. But **0.9.12's `EventContext.get()` already raised the identical bare-repr `LookupError`**. PR #6553 consolidated PageContext and CompileContext onto `BaseContext` on purpose. The reflex-base 0.10.0a1 CHANGELOG lists it as a breaking change ("now raise `LookupError` instead of `RuntimeError` ... the same as every other `BaseContext` subclass ... should catch `LookupError`"), and the previous campaign asserted it as a pass (`core_state/backend_checks.py:181-184`). Only the friendlier message text was lost: alpha `reflex_base/context/base.py:38-47` returns `cls._context_var.get()` directly.

### 6. Claim D: deprecation locations
Source: `scripts/derive_d/`, logs `logs/derive_d.txt` and `logs/derive_d_stack.txt`. One scenario per process, because warnings are deduped per feature and location.

| deprecated call made from user code | 0.10.0a1 location | 0.9.12 location |
|---|---|---|
| direct `rx.Var.create([1,2]).foreach(...)` | `derive_d.py:18` | `derive_d.py:18` |
| the same call inside `exec(...)` | `derive_d.py:20` (the line with the `exec`) | `<string>:2` |
| `@rx.memo` without annotations | `derive_d.py:32` | same |
| `REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS=1` + `state_manager_disk_debounce()` | `derive_d.py:42` | n/a (no such function) |
| `class M(rx.Model, table=True)` in the script, in an imported user module, or in a package (`reflex_magic_link_auth`) | `pydantic/_internal/_model_construction.py:133` (pydantic 2.14.0b2) / `:156` (2.13.5) | `<frozen abc>:106` |
| two models in two user files, one process | one warning only (same pydantic location, deduped) | one warning only (`<frozen abc>:106`) |

So the #7138 fix works: `<string>` and `<frozen ...>` frames are skipped (`reflex_base/utils/log.py:1082`). The gap is specific to `rx.Model` subclassing. The frame chain is user file → `sqlmodel/main.py:619` → `pydantic/_internal/_model_construction.py` (`ModelMetaclass.__new__`) → `<frozen abc>:106` → `reflex/model.py:580` `__init_subclass__` → `:555`. `_exclude_paths_from_frame_info` (`log.py:1019-1058`) excludes only click, reflex, typing_extensions, socketio, granian, reflex_base and the stdlib, so pydantic and then sqlmodel count as "user" frames. This is not a regression: both versions are wrong, alpha's location is a real file and 0.9.12's is a pseudo-file.

### Verdicts
```
ISSUE: A. Class-level read of a backend State var returns the Field descriptor instead of its value
CONFIRMED: true
REGRESSION: yes
SEVERITY: high
NOTES: Reproduced from the written probes on 4 venvs and with my own derivation in dev and prod. Changed: unannotated and annotated backend vars, including ones from mixins, inherited by substates, or read via cls/type(self)/self.__class__. Unchanged: ClassVar (the value on both versions), unannotated public KEY = ... (a frontend Var on both), instance reads. rx.field() backend vars read as None on 0.9.12 and Field on alpha. Real browser: silent "label=Field(default=...)" and "+Field(default=5, ...)" UI text in dev and prod, no error. Undocumented: not in PR #7312, its fragments, docs, reviews, epic #7302 or the CHANGELOG, and reflex-enterprise needed a private _compat shim. Still on main 62a56ba7f. Package impact is narrower than claimed: only reflex-clerk and reflex-dynoselect use the pattern, both already broken on 0.9.12 for other reasons, and the clerk change fails closed (no auth bypass). The main risk is user code: silent wrong text, equality and truthiness, plus loud ChildrenTypeError, TypeError and VarTypeError at compile time, with no deprecation path.
ROOT_CAUSE_GUESS: reflex_base/vars/base.py:4737-4738 (namespace.update(own_fields)) makes the Field the class attribute, and Field.__get__ at base.py:4273-4274 returns self when _var is None, which is always true for backend fields. 0.9.12's BaseStateMeta.__new__ (stable base.py:4287-4291) left the raw value on the class. Fix direction: for class access of a backend field, return default_value() (with a deprecation warning) or document a ClassVar migration. Audit internal getattr(cls, name) callers that expect a Field.
MINIMAL_REPRO: class S(rx.State): _KEY = "label" ; then print(repr(S._KEY)) and print(rx.text(f"{S._KEY}")). Alpha prints Field(default='label', ...) and renders the Field repr; 0.9.12 prints 'label'. Scripts: verification/classattr/scripts/derive_a.py <venv>; e2e: e2e_app + drive_classattr.py.
```
```
ISSUE: B. Class-level assignment to a declared backend var replaces its descriptor: inconsistent reads, dev-mode SetUndefinedStateVarError on instance writes and reset(), lost writes in prod
CONFIRMED: true
REGRESSION: yes
SEVERITY: medium
NOTES: Confirmed as claimed (fresh instance sees the class value, a pickled one the default), and it goes further. The live instance flips to the default as soon as it is serialized: in a default dev app the debounced disk save flips it within about 2 s with no reload. After the replacement, instance writes raise SetUndefinedStateVarError in dev, and so does State.reset(). In prod the writes are not dirty-tracked, so redis drops them. All of this was shown in Chromium with a real disk or redis manager. On 0.9.12 the class assignment was silently ignored for instances, consistently and without breakage. The pattern is unsupported and undocumented (framework tests use ClassVar for class-assigned statics), but reflex-clerk (set_fetch_user_on_auth, _secret_key) and reflex-dynoselect (_raw_options) use it. Kept at medium because it needs that unsupported pattern.
ROOT_CAUSE_GUESS: BaseStateMeta (base.py:4656-4746) has no __setattr__, so cls._x = v replaces the Field data descriptor in the class __dict__ while __fields__ keeps the old Field. __getstate__ (reflex/state.py:2046-2054) then writes the stale default into vars(self). The dev __setattr__ guard (state.py:1489-1504) rejects the name because _has_data_descriptor (state.py:347-362) is False, which also breaks reset() (state.py:1512-1515). Prod writes skip Field.__set__ and _mark_dirty, and redis.py:514 persists only touched states. Fix direction: a metaclass __setattr__ that updates the Field default for declared field names (as reflex-enterprise _compat.set_backend_var_default does), or raises a clear error.
MINIMAL_REPRO: class C(rx.State): _k: str | None = None ; C._k = "sk" ; s = rx.State(_reflex_internal_init=True).get_substate(C.get_full_name().split(".")[1:]) ; print(s._k) ; pickle.dumps(s) ; print(s._k) ; s._k = "x". Alpha prints 'sk' then None and the write raises in dev; 0.9.12 prints None, None and the write works. Scripts: verification/classattr/scripts/derive_b.py and derive_b_reset.py (run with REFLEX_ENV_MODE=dev and prod); e2e: e2e_app.
```
```
ISSUE: C. PageContext.get()/CompileContext.get() outside a context raise LookupError whose message is only the ContextVar repr
CONFIRMED: true
REGRESSION: no
SEVERITY: low
NOTES: Reproduced. The type change is intentional and documented (PR #6553; reflex-base 0.10.0a1 CHANGELOG breaking entry with migration advice), and the previous campaign asserted it as a pass. The bare-repr message is identical to what EventContext.get() already raised on 0.9.12. Only the friendlier text for these two contexts was lost. The ContextVar repr still names the context. UX nit, not a release blocker.
ROOT_CAUSE_GUESS: reflex_base/context/base.py:38-47, where BaseContext.get() returns cls._context_var.get() directly. 0.9.12 had a custom RuntimeError in reflex_base/plugins/compiler.py:600-614. Optional polish: catch LookupError and re-raise LookupError(f"No active {cls.__name__} is attached to the current context.").
MINIMAL_REPRO: $SB/envs/alpha/bin/python -c "import reflex; from reflex_base.plugins.compiler import PageContext; PageContext.get()" (from a neutral dir). Script: verification/classattr/scripts/derive_c.py.
```
```
ISSUE: D. rx.Model subclass deprecation warning location points into pydantic instead of the user's model file
CONFIRMED: true
REGRESSION: no
SEVERITY: low
NOTES: The #7138 fix works: an exec'd call names the user line on alpha (0.9.12: <string>:2), and direct calls, @rx.memo and the superseded env var all name the user line. Only rx.Model subclassing is wrong: it reports pydantic/_internal/_model_construction.py:133 or :156 (depending on pydantic version) on alpha versus <frozen abc>:106 on 0.9.12. Both are wrong, so this is not a regression. Because dedupe is keyed on the location, a second model file produces no warning on either version. The CHANGELOG claim "the location now names the first real user file" does not hold for this one case.
ROOT_CAUSE_GUESS: reflex_base/utils/log.py:1019-1058, where _exclude_paths_from_frame_info does not exclude pydantic or sqlmodel. The warning is emitted from reflex/model.py:555 via __init_subclass__ (:580), called from pydantic ModelMetaclass.__new__, itself called from sqlmodel/main.py:619. Exclude both roots, or attribute the warning to the class definition site.
MINIMAL_REPRO: a user script containing class M(rx.Model, table=True): x: int = 0. Alpha warns "(.../pydantic/_internal/_model_construction.py:133)"; 0.9.12 warns "(<frozen abc>:106)". Script: verification/classattr/scripts/derive_d/derive_d.py <venv> model_here|exec|direct.
```

## VERIFICATION — client-storage rewritten during hydration

Independent verifier. Artifacts: `verification/clientstorage-hydrate/` (my own app `apps/cvstore`, drivers, start/sweep scripts, seed probe, driver summaries and server logs in `logs/`, websocket captures in `frames/`). Venvs: shared `$SB/envs/alpha` (0.10.0a1) and `$SB/envs/stable` (0.9.12) for the plain apps. For reflex-google-auth 0.2.0 I built my own venvs from PyPI: `$SB/envs/verify_thirdparty_1-galpha` (reflex 0.10.0a1) and `-gstable` (reflex 0.9.12), both without pydantic. Ports 3604-3607 / 8604-8607, one server at a time. All servers were stopped afterwards.

**Verdict: confirmed, but the regression is narrower than reported.** On 0.10.0a1 the computed-var rewrite never reaches the browser on a full page load or reconnect: 100% of server processes, dev and prod. On 0.9.12 it already failed for a hash-seed-dependent share of server processes: about half for simple states and about 14% for reflex-google-auth's state. The explorer's statement that 0.9.12 clears it deterministically ("5/5") is wrong. With `PYTHONHASHSEED=4`, reflex 0.9.12 shows the explorer's exact failure on the explorer's own app and driver, in both dev and prod (`tp_ls_cv='bad' ui='ls_cv=bad' cv='cv_check=cleared-in-computed-var'`). `PYTHONHASHSEED` 1, 2 and 3 all happen to be "fresh" seeds for tp_patterns' var names; the first stale one is 4. The release turns an intermittent failure into a permanent one.

### Repro of the written steps
I copied `apps/tp_patterns` unchanged and ran `drivers/drive_storage_only.py` plus `drive_tp_ws.py` (the same flow with websocket capture). The written repro was enough; the only gap is that NOTES never says how "seed" was applied.

| run | result |
|---|---|
| alpha dev, unseeded (3 runs) | `tp_ls_cv='bad' ui='ls_cv=bad'`, cv says cleared: **FAIL** |
| alpha prod, unseeded / `PYTHONHASHSEED=0` | FAIL / FAIL |
| stable dev, unseeded (3 runs, one process) / seed 1 / **seed 4** | PASS / PASS / **FAIL** (identical to alpha) |
| stable prod, seed 0 / **seed 4** | PASS / **FAIL** |

Wire evidence (`frames/tp-*-ws.json`, decode with `drivers/decode_frames.py <file> reload store_state`):
- alpha sends one CONNECT packet `40/_event,{"event":{"name":"reflex___state____state.hydrate_and_load","payload":{"vars":{"…store_state.ls_cv_rx_state_":"bad"},"hashes":[…]}}}`. The snapshot it gets back holds `{"cv_check_rx_state_":"cleared-in-computed-var","ls_cv_rx_state_":"bad"}`, which contradicts itself. No later frame carries `ls_cv`.
- stable seed 4: the `update_vars_internal` delta is `{"ls_cv_rx_state_":"bad","cv_check_rx_state_":"cleared-in-computed-var"}`, stale because `ls_cv` was serialized first. With seed 1 it is `{"cv_check…":"cleared…","ls_cv_rx_state_":""}`.

### Own minimal app (`apps/cvstore`, identical source on both versions)
Each variant has its own state and storage key. The driver (`drivers/drive_cvstore.py`) sets the key to `bad`, reloads, then runs the steps in the table below. A `probe` event copies the backend's value into a plain var (`seen=backend …`), so backend truth is visible without relying on the delta under test. FAIL means that after the reload the browser storage and the UI hold `bad` while the backend holds `''`. Seed 0 is "stale" for every computed-var variant on the per-event delta path, and seed 4 is "fresh" for all of them (verified in the worker with `drivers/drive_diag.py`).

| variant | alpha dev s0 / s4 | alpha prod s0 / s4 | stable dev s0 / s4 | stable prod s0 / s4 |
|---|---|---|---|---|
| (a) cached cv clears `rx.LocalStorage` (direct `rx.State` subclass) | FAIL / FAIL | FAIL / FAIL | FAIL / PASS | FAIL / PASS |
| (b) uncached cv clears LocalStorage | FAIL / FAIL | – / FAIL | FAIL / PASS | – / PASS |
| (c) `on_load` clears LocalStorage + Cookie + SessionStorage | PASS / PASS | PASS / PASS | PASS / PASS | PASS / PASS |
| (d) clicked event clears LocalStorage + Cookie + SessionStorage | PASS / PASS | PASS / PASS | PASS / PASS | PASS / PASS |
| (e1) cached cv clears `rx.Cookie` | FAIL / FAIL | – / FAIL | FAIL / PASS | – / PASS |
| (e2) cached cv clears `rx.SessionStorage` | FAIL / FAIL | – / FAIL | FAIL / PASS | – / PASS |
| (f) cached cv on a SUBSTATE clears its own LocalStorage | FAIL / FAIL | – / FAIL | FAIL / PASS | – / PASS |
| (g) cached cv sets a DIFFERENT plain var | FAIL / FAIL | – / FAIL | FAIL / FAIL | – / FAIL |
| (h1) after a FAIL: the next ordinary event fixes the browser | no / no | no / no | no / n.a. | no / n.a. |
| (h2) after a FAIL: a client-side navigation (link out and back) fixes it | no / **yes** | no / yes | no / n.a. | no / n.a. |
| (h3) after a FAIL: a second full reload fixes it | no | no | no | no |

Seed sweep of (a), dev, seeds 0-7 (`bin/seed_sweep.sh`; `logs/seed-sweep-*.txt`):
- alpha: reload FAILs on 8/8 seeds. Navigation heals it on seeds 1, 4, 5 and 6.
- stable: FAILs on seeds 0, 2, 3 and 7, and PASSes on 1, 4, 5 and 6.
- All 8 stable outcomes match the offline prediction from set iteration order.

The offline model (`probes/seed_scan_probe.py`, `logs/seed-scan-stable-0-63.txt`) has 0.9.12 stale on 34/64 seeds for (a)'s var names, 32/64 for tp_patterns and 9/64 for a GoogleAuthState-shaped state.

Answers to the specific questions:
- **(c) is not affected.** `hydrate_and_load` sends the snapshot (with the browser's `bad`), then `on_load_internal` triggers `on_load` as a separate event. Its delta `{"…c_on_load":{"ck_rx_state_":"","ls_rx_state_":"","ss_rx_state_":"", …}}` has no root `is_hydrated:false`, so the frontend writes the cleared values to storage (`frames/cvstore/alpha-dev-seed4-c.json`).
- **(g) fails on both versions, for every seed.** A write a computed var makes to a var that was not already dirty never enters the in-flight delta, and is then `_clean()`ed. The UI shows `plain=initial` while the backend holds `set-by-cv`, until the next full snapshot.
- **(h): no self-heal on ordinary events** (the var is no longer dirty). A full reload re-sends `bad` and fails again. A client-side navigation still uses `update_vars_internal`, so it heals only on "fresh" seeds.

### reflex-google-auth 0.2.0 (upstream demo copied from `apps/google_auth_demo`; `drivers/drive_gauth.py`, `bin/gauth_sweep.sh`)
- alpha dev: the bogus `token_response_json` survives full reloads of `/protected` and `/` on 8/8 runs (seeds 0, 1, 2, 3, 4, 5, 10 and unseeded). The first client-side navigation clears it except on seeds 4 and 10.
- stable dev: it is cleared on reload on 9/11 seeds and kept on **seeds 4 and 10**, the two seeds in 0-10 that the offline model predicted. Frames: the `update_vars_internal` delta lists `token_response_json` = BOGUS first.
- Both versions: `/protected` never unlocks (`token_is_valid` stays False), and the server prints `Error verifying token: MalformedError(...)` on each load. No auth bypass.
- On alpha the hydrate snapshot also ships values derived from the rejected token (`access_token:"ya29.bogus"`, `id_token`, `scopes`) while the backend holds `''`.
- Even on a passing 0.9.12 seed the delta carried `id_token_json` derived from the bogus token.

### Mechanism (published alpha source under `$SB/envs/alpha/lib/python3.12/site-packages`)
1. `reflex/state.py:2339-2352` `hydrate_and_load`: resets client storage (2339), applies the browser values (2341 → `_apply_client_storage_vars`, `setattr` at 2526), sets `is_hydrated=False` (2345), runs `delta = await _resolve_delta(self.dict())` (2348), diffs against compiled defaults (2350), emits (2351), then calls **`self._clean()` (2352)**.
2. `reflex/state.py:1975-1996` `BaseState.dict()` reads base vars (1975-1977) **before** it evaluates computed vars (1991-1996). The computed var's assignment therefore lands after `ls` was captured, and it only adds `ls` to `dirty_vars`.
3. `_clean()` (state.py:1928-1930 → `reflex/istate/delta.py:303-313` `clean_state`) wipes that dirty mark. Neither the chained delta (`reflex_base/event/processor/base_state_processor.py:243`) nor any later delta ever carries the new value. The browser keeps the old value and re-sends it on every load.
4. Even a value placed in a full snapshot would not be persisted: `applyClientStorageDelta` (`reflex_base/.templates/web/utils/state.js:1045-1059`) skips client-storage writes when the root delta has `is_hydrated_rx_state_ === false`. Reconnect snapshots carry that flag. The first-load diffed snapshot drops it because it equals the default.
5. The pre-existing half: per-event deltas iterate a `set` (alpha `reflex/istate/delta.py:226,236-237`; 0.9.12 `reflex/state.py:2462-2477`), and `chain_updates` cleans afterwards (alpha `base_state_processor.py:243-247`; 0.9.12 `226-230`). A computed var's write reaches the client only if the written var is iterated after the computed var, and never if the var was not dirty beforehand. 0.9.12 applied browser values in the separate `update_vars_internal` event (`state.py:3070`) through this path, which is the hash-seed coin flip. Alpha still uses this path for client-side navigations.

PR #7064 (via GitHub MCP) merged `hydrate`, `update_vars_internal` and `on_load_internal` into one `hydrate_and_load` event and adds the diff against compiled defaults. Neither its description nor its 24 review threads mention computed vars that write state.

**Supported pattern?** `docs/vars/computed_vars.md` (release branch) says only "Computed vars have values derived from other properties on the backend". No doc forbids or blesses assignments inside a computed var, and the requested grep found nothing on side effects. Given (g) and the 0.9.12 coin flip, the pattern was never reliable. It still matters: reflex-google-auth 0.2.0 depends on it, and on 0.9.12 it worked for most server processes (~86%). On 0.10.0a1 it never works on page load.

Suggested fix directions (not implemented):
- (i) In `hydrate_and_load`, flush the vars dirtied during `self.dict()` in a follow-up delta that is not marked `is_hydrated=False`, instead of `_clean()`ing them.
- (ii) More generally, rebuild deltas to a fixed point while new dirty vars appear. This also fixes (g) and the old coin flip.
- (iii) Or document that computed vars must not assign state, and move reflex-google-auth's token cleanup into an event.

Secondary observations:
- (b) on alpha: the uncached computed var's own UI value also stays stale (`cleared-by-uncached-cv`) after later events. The snapshot path does not update the per-client "last sent" record of uncached computed vars. The record left by the first load (`check:"value=''"`) makes `_record_or_drop_delta_value` withhold the recomputed `value=''` as unchanged (`frames/cvstore/alpha-dev-seed4-b.json`). Same root cause.
- `[ERROR] Unexpected exit from worker-1` also appears on **alpha dev** when the process group is SIGTERMed (my logs and the explorer's `logs/tp_patterns-alpha-seed1.log`), not only on 0.9.12. Alpha prod stops cleanly. This is shutdown noise from the kill method and unrelated to this issue.
- Method pitfall: `python -I`/`-E` makes Python ignore `PYTHONHASHSEED`. My first offline scan used `-I` and was discarded; run `probes/seed_scan_probe.py` without it.

### Rerun
```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; V=$PWD/verification/clientstorage-hydrate
W=$SB/apps/verify_thirdparty_1   # the bin/*.sh scripts expect W/{pids,logs,out,drivers,apps/<venv>/<app>}
mkdir -p $W/{pids,logs,out,drivers} && cp $V/bin/*.sh $W/ && cp $V/drivers/*.py $W/drivers/
for e in alpha stable; do mkdir -p $W/apps/$e && cp -r $V/apps/cvstore $W/apps/$e/; done
PYTHONHASHSEED=4 $W/start.sh alpha  $W/apps/alpha/cvstore  3604 8604 $W/logs/a.log && $W/wait_up.sh http://localhost:3604/ 400 $W/pids/cvstore-alpha.pid
cd $W/drivers && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_cvstore.py http://localhost:3604 $W/out x a   # FAIL
$W/stop.sh $W/pids/cvstore-alpha.pid
PYTHONHASHSEED=4 $W/start.sh stable $W/apps/stable/cvstore 3606 8606 $W/logs/s.log   # same driver: PASS; with PYTHONHASHSEED=0: FAIL like alpha
# prod: REFLEX_API_URL=http://localhost:3605 PYTHONHASHSEED=4 $W/start.sh alpha $W/apps/alpha/cvstore 3605 3605 $W/logs/p.log --env prod
# explorer's app on 0.9.12 failing: PYTHONHASHSEED=4 + apps/tp_patterns + drivers/drive_storage_only.py
# seed sweeps: $W/seed_sweep.sh <alpha|stable> <fp> <bp> a 0 1 2 3 ; google-auth: $W/gauth_sweep.sh <galpha|gstable> <fp> <bp> 0 4 10
```
