# Cluster: TYPING & NEW PYTHON VERSIONS — reflex 0.9.9a1

Tested changelog items: #6944 (PEP 695 type aliases in Var.guess_type),
#6890/#6896 (event handler annotations cached before 3.14 class patches),
#6846 (builtin-shadowing annotations qualified for type checkers).

Environments (all installed from PyPI with `--prerelease=allow 'reflex==0.9.9a1'`):
- `envs/typ312` Python 3.12.3, `envs/typ313` Python 3.13.12, `envs/typ314` Python 3.14.7
- `envs/typ312_098` Python 3.12 + reflex==0.9.8 (baseline)
- shared `envs/smoke` Python 3.11.15 (0.9.9a1) as 3.11 control
- pyright 1.1.413 via `npm i pyright` (scratchpad `npm_pyright/`)

## Apps / scripts in this directory

- `pep695app/` — app whose state vars + event handler args are all annotated via
  PEP 695 `type` statements: plain alias, Literal alias, `Items[str]` for
  `type Items[T] = list[T]`, `Pair[K, V]` dict alias, `Key | None` union,
  alias-of-alias (`type MaybeKey = Key | None`), variadic `type Tup[*Ts]`,
  aliases through `rx.foreach`/`rx.cond`. Requires Python 3.12+.
- `builtinsapp/` — "busy" app with many handlers annotated with builtin names
  (`dict`, `list`, `set`, `tuple`, `bool`, `str`, `dict[str,int]`, `list[str]`),
  a background task (`@rx.event(background=True)` with `payload: dict`), an
  event chain (`yield take_bool(...)`), and an upload handler
  (`files: list[rx.UploadFile]`). Runs on 3.11 and 3.14 unchanged.
- `drive_pep695.py` / `drive_busy.py` — Playwright drivers (Chromium at
  /opt/pw-browsers/chromium; use the shared `envs/driver` venv).
- `repro_alias_event_arg.py` — BUG 1 repro (see below).
- `repro_alias_setattr.py` — BUG 2 repro (see below).
- `repro_alias_backport_311.py` — BUG 2 via `typing_extensions.TypeAliasType`
  backport on Python 3.11.
- `pyright_user/` — user-side pyright project (`main.py` Var.create inference,
  `components_check.py` typical component/state code).
- `shots/` — screenshots; `logs/` — server logs from the runs.

## How to rerun

```
SB=<scratchpad>; APP=$SB/apps/typing_python
uv venv $SB/envs/typ312 --python 3.12
uv pip install --python $SB/envs/typ312/bin/python --prerelease=allow 'reflex==0.9.9a1'
cd $APP/pep695app && REFLEX_TELEMETRY_ENABLED=false $SB/envs/typ312/bin/reflex run \
    --frontend-port 3340 --backend-port 8340 --loglevel debug > log 2>&1 &
$SB/envs/driver/bin/python $APP/drive_pep695.py http://localhost:3340/ <shotdir> <logfile>
# builtinsapp: same with envs/typ314 (or envs/smoke for 3.11), ports 3341/8341,
# driver: drive_busy.py <url> <shotdir> $APP/upload_sample.txt
# repros (no server needed):
$SB/envs/typ312/bin/python $APP/repro_alias_event_arg.py
$SB/envs/typ312/bin/python $APP/repro_alias_setattr.py
# pyright:
npm i pyright --prefix $SB/npm_pyright
$SB/npm_pyright/node_modules/.bin/pyright --pythonpath $SB/envs/typ312/bin/python $APP/pyright_user/main.py
```

## Findings

### BUG 1 (medium): PEP695 alias annotating an event handler arg crashes page compile when the handler is passed UNCALLED to a trigger

`on_change=State.choose` where `def choose(self, value: Key)` and
`type Key = Literal["a", "b"]` kills `reflex run` at page eval:

- bare alias -> `TypeError: Could not compare types <class 'str'> and Key for
  argument value of S.choose for on_change.` (underlying:
  `typehint_issubclass` -> `issubclass() arg 2 must be a class...`)
- parameterized alias (`form_data: Pair[str, str]`) -> fatal
  `EventHandlerArgTypeMismatchError: ... expects dict[str, typing.Any] ... but
  got Pair[str, str]` (typehint_issubclass returns False instead of resolving).

Root cause: PR #6944 added `resolve_type_alias` to `Var.guess_type` only;
`reflex_base.utils.types.typehint_issubclass` (used by
`_check_event_args_subclass_of_callback`) does not resolve TypeAliasType.
Workarounds: pre-called handler (`S.choose("a")`) or lambda wrapper
(`lambda v: S.choose(v)`) both work. NOT a regression: 0.9.8 fails identically
on an event-handler-only app, but 0.9.9a1 advertises alias support, and any
user who annotates handlers with the same alias as their state var hits this
immediately. Repro: `repro_alias_event_arg.py` (3.12/3.13/3.14 identical).

### BUG 2 (high): runtime assignment to a PEP695-alias-annotated state var raises TypeError — alias-annotated vars compile but cannot be mutated

Any `self.key = value` inside an event handler where `key: Key` (alias) raises

```
File "reflex/state.py", line 1544, in __setattr__
    if not _isinstance(value, field_type, nested=1, treat_var_as_type=False):
File "reflex_base/utils/types.py", line 872, in _isinstance
    return isinstance(obj, cls)
TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union
```

The `_isinstance` guard in `BaseState.__setattr__` is only meant to LOG a type
mismatch, but it does not resolve TypeAliasType, so it raises instead — every
event that assigns such a var dies server-side and the UI silently never
updates (no browser console error, no dev-mode toast; only the backend log
shows `[Reflex Backend Exception]`). This makes #6944's headline feature
("state vars annotated `type Key = Literal[...]` compile") effectively
unusable for any var that is ever reassigned. Affects: plain alias, Literal
alias, parameterized generic alias, alias-in-union — on 3.12/3.13/3.14 native
`type` statements AND the `typing_extensions.TypeAliasType` backport on 3.11.
In-place container mutation (`self.pair["k"] = v`) bypasses `__setattr__` and
works. Not a strict regression (0.9.8 crashed one stage earlier, at class
definition), but it guts the new feature. Repros: `repro_alias_setattr.py`
(3.12+), `repro_alias_backport_311.py` (3.11); end-to-end evidence:
`drive_pep695.py` run + `logs/pep695_312_server.log` +
`shots/pep695_312/02_after_clicks_no_update.png`.

### PASS: everything else

- pep695app on 3.12: compiles, renders, hydrates — all 7 alias var shapes show
  correct values and correct Var kinds (StringVar/ArrayVar/ObjectVar; verified
  both via `_var_type` introspection and in-browser rendering, incl. foreach
  over alias-typed list and dict and rx.cond on alias|None). 0.9.8 baseline
  fails to even import the module (`TypeError: Unsupported type Name for
  guess_type`) — the #6944 fix is real.
- builtinsapp on 3.14.7: full end-to-end pass. All builtin-named annotations
  resolve to real builtins (`payload: dict` -> `<class 'dict'>`, not
  BaseState.dict), set/tuple payloads arrive converted to real `set`/`tuple`,
  background task + event chain + upload all work, zero tracebacks or
  annotation errors in the server log. Python 3.11 control: identical pass.
- 3.13 smoke: reflex imports, both app page components compile, bugs reproduce
  identically (expected parity).
- pyright as a user (1.1.413): 0 errors on both files vs 0.9.9a1;
  `Var.create(5)` infers `LiteralNumberVar[int]`, `create("hello")` ->
  `LiteralStringVar`, `create([1,2,3])` -> `LiteralArrayVar` — NOT
  LiteralBooleanVar. `BaseState.dict()`/`PropsBase.dict()` return real dicts.
  No installed .pyi references unqualified `builtins.` without importing it.

## Benign / surprising observations

- pyright 1.1.413 vs reflex 0.9.8 ALSO infers Var.create correctly (0 errors),
  even though #6846 is not in v0.9.8 — the LiteralBooleanVar collapse described
  in that PR does not manifest with this pyright version, so the fix could not
  be differentiated user-side here (it may target another checker/version,
  e.g. Pylance or ty).
- `rx.checkbox("label", on_change=handler)` (no `checked` prop) logs React
  warning "Checkbox is changing from uncontrolled to controlled" on first
  toggle — identical on 3.11 and 3.14, unrelated to this cluster's changes.
- DeprecationWarning at startup: "Implicit Radix Themes enablement has been
  deprecated in 0.9.0 ... configure rx.plugins.RadixThemesPlugin()" — expected
  deprecation, fires for any app using radix components without the plugin.
- Backend exceptions from event handlers (BUG 2) produce NO frontend-visible
  feedback in dev mode — the click just does nothing. Made debugging
  non-obvious; only `--loglevel debug` server logs revealed the cause.
- Test-harness footguns (not reflex bugs, for future agents): an app package
  without `__init__.py` produces "Cannot process state update: no dispatch
  function for substate ..." at runtime because frontend and backend derive
  different module paths for the state; and overriding NO_PROXY with just
  `localhost,127.0.0.1` breaks bun installs in this container (the inherited
  NO_PROXY already includes localhost AND registry.npmjs.org — don't override).

## VERIFICATION (independent, adversarial — 2026-08-28)

BUG 2 (alias setattr TypeError) is **CONFIRMED** as a genuine 0.9.9a1 framework defect.
Reproduced from the repro steps alone in a FRESH venv (`uv venv --python 3.12` +
`uv pip install --prerelease=allow 'reflex==0.9.9a1'` from PyPI; reflex-base 0.9.9a1):

1. `repro_alias_setattr.py`: all four assignments (plain alias, Literal alias,
   `Items[str]`, `Key | None`) crash with
   `TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union`;
   in-place dict mutation passes — exactly as claimed.
2. End-to-end with an INDEPENDENT minimal app (`verification/aliasapp/`, ports
   3840/8840, driven by Playwright/Chromium — `verification/drive_verify.py`):
   a control button assigning a plain `str` var updates the UI fine (rules out
   env/app-structure issues); the button assigning `k: Key = "b"`
   (`type Key = Literal["a","b"]`, "b" is a VALID member, so this is not even a
   type mismatch) silently does nothing in the browser — zero console errors —
   while the backend logs the full traceback:
   `reflex/state.py:1544 __setattr__` -> `reflex_base/utils/types.py:872
   _isinstance` -> `return isinstance(obj, cls)` -> TypeError
   (`verification/server.log` lines ~243-290, `verification/shots/`).
3. 3.11 backport variant reproduced on the shared smoke env
   (`repro_alias_backport_311.py`: compile OK, `_var_type` correctly resolved to
   `Literal['a','b']`, setattr crashes).
4. Baseline: reflex==0.9.8 in a fresh 3.12 venv fails at class DEFINITION
   (`TypeError: Unsupported type Name for guess_type`) — so this is not a
   regression of previously-working code, but the feature #6944 ships (alias-
   annotated state vars) is unusable for any var that is ever reassigned.

Refutation attempts that failed: not an environment quirk (fresh PyPI-only venv,
control var works in the same app/session); not API misuse (a real `@rx.event`
handler doing `self.k = "b"` through the real websocket event pipeline crashes
identically to the `_reflex_internal_init` repro); not pre-existing behavior a
user could have relied on (0.9.8 rejects the class outright). Root cause check
against the installed 0.9.9a1 wheels: `resolve_type_alias` exists in
`reflex_base/utils/types.py` but its only call site is
`reflex_base/vars/base.py:1080` (`Var.guess_type`); `_isinstance` (and
`typehint_issubclass`) never resolve TypeAliasType, and the `__setattr__` guard
at `reflex/state.py:1544` — intended only to `logger.error` a mismatch — lets
the TypeError escape, killing every event delta. Severity "high" is fair.

BUG 1 was not re-verified in depth (out of scope for this pass), but its
mechanism (typehint_issubclass not resolving aliases) is consistent with what
the BUG 2 root-cause inspection showed.

All verifier processes killed; ports 3840/8840 confirmed free.
