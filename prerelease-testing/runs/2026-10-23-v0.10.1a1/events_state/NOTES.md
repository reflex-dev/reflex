# events_state — reflex 0.10.1a1 vs 0.10.0 (2026-10-23/24)

Item: #7386 forms, #7402 #7401 #7415 #7585 #7447 #7500 #7636 #7592 #7410 #7443 #7547 #7626 #7606 (+ #7622 revert),
re-verify EVT-06, STATE-05, STATE-11…19, STATE-20/21, CMP-01, EVT-02. Ports 3300-3319 / 8300-8319 (Redis 8319).

## Setup (everything from `$SB/apps/events_state`, never from a checkout)
```bash
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa; W=$SB/apps/events_state
cp -r <this dir>/class_state $W/class_state          # fixtures copy (prerelease-testing/fixtures/class_state)
UV_PRERELEASE=allow W=$W/cs_work bash $W/class_state/build_venvs.sh events_state-new 0.10.1a1
W=$W/cs_work bash $W/class_state/build_venvs.sh events_state-prev 0.10.0
# freeze: $W/cs_work/logs/venv/freeze-events_state-{new,prev}.txt (pydantic 2.14.1, py3.12)
cd $SB && uv --no-config venv --python 3.12 $SB/envs/events_state-sio && uv --no-config pip install --python $SB/envs/events_state-sio/bin/python 'python-socketio[client]' websocket-client
```
Apps/scripts in this directory (copied from `$W`): `formsapp/` (forms), `drive_forms.py`, `compare_forms.py`,
`probe_form_compile.py`, `probe_form_annotations.py`, `probe_sio_payload.py`, `run_app.sh` / `stop_app.sh` / `wait_up.sh`.

## 1. #7386 forms — what an existing (0.10.0-style, dict handler) app receives
App `formsapp` page `/legacy`: 25 forms covering id-only / name-only / id==name / id!=name controls (rx.input, text_area,
checkbox, switch, select, radio_group, slider, hidden, native checkbox), checkbox_group + repeated native checkboxes +
multi-select, two-thumb sliders (`range[]`), controlled inputs (DebounceInput), `reset_on_submit`, forms in `rx.foreach`,
`rx.el.form`, `rx.form.root`+`form.field`, dynamic `name` from a var, unannotated / `dict[str, Any]` / `Mapping` /
`dict | None` / `Any` handlers, lambda, chain (handler returns another handler with the data), file input, bracketed names.
Every handler records `type(form_data)` + JSON (key order kept) into `pre#results` and `form_log.jsonl`.
```bash
cd $W && bash run_app.sh events_state-prev $W/formsapp prev-dev 3300 8300 --loglevel debug && bash wait_up.sh http://localhost:3300/legacy 420 pids/prev-dev.pid
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_forms.py http://localhost:3300 out/forms-prev-dev.json --file $W/wait_up.sh
bash stop_app.sh prev-dev; rm -rf formsapp/.web
FORMS_NEW=1 bash run_app.sh events_state-new $W/formsapp new-dev 3300 8300 --loglevel debug && bash wait_up.sh http://localhost:3300/legacy 420 pids/new-dev.pid
NO_PROXY=... $SB/envs/driver/bin/python drive_forms.py http://localhost:3300 out/forms-new-dev.json --new --file $W/wait_up.sh
python3 compare_forms.py out/forms-prev-dev.json out/forms-new-dev.json      # per-form diff prev vs new
```
Result (dev, `out/forms-{prev,new}-dev.json`, `compare_forms` output in `out/compare-dev.txt`): **every dict-handler form
receives exactly the same dict on 0.10.1a1 as on 0.10.0 (same keys, values, python types and key order), except one**:

| form | 0.10.0 | 0.10.1a1 |
|---|---|---|
| `group_id_eq_name`: `rx.checkbox_group.root(id="cg", name="cg")` with c1+c3 checked; native `rx.el.input(type="checkbox", id="topping", name="topping", value="cheese")` + a second `name="topping"` checkbox, both checked | `{"cg": "c1", "topping": true}` (the id ref's value: first checked item / the bool `checked` of the id'd checkbox) | `{"cg": "c3", "topping": "olives"}` (the form's own last value for the repeated name) |

This is the #7386 rule "an id ref replaces a submitted name only when the form submitted that name at most once" (needed so
`FormData.getlist` / TypedDict list fields keep every value). It is described in the form docs ("…unless the form submits
that `name` more than once") but **not in CHANGELOG** (the reflex-components-core deprecation entry only describes the 0.11
future). Any app with a checkbox group / repeated-name control carrying `id == name` and a dict handler sees a different
value today. Low severity (the old value was the first checked item / a bool for a multi-value control, arguably wrong).

Everything else identical, including: checkbox/switch `id==name` still `True`/`False` (bool), `name`-only still `"on"`;
`id != name` still both keys; `rangeid` (two-thumb slider with id) still the first thumb; `range[]` dict still last
value; disabled input with id still submitted by id (`disabled_id: "dis"`) on both; `rx.select(id=...)` without name
submitted on neither; `rx.form.field(name=)` propagates the name at runtime on both; reset_on_submit clears on both.

Wire format (new): `{"form_data": {"__reflex_form_data__": [["cg","c1"],["cg","c3"],...]}}` — see `ws_sent` in
`out/forms-new-dev.json`. File inputs still arrive as `bytes` (socket.io binary attachment path works with the envelope).

Deprecation warnings (new, `logs/new-dev.log`): exactly one `DeprecationWarning: Submitting the form control with id '<id>'
by its id has been deprecated in version 0.10.1 …` per distinct id-only control whose form handler takes form data, deduped
across pages/forms (19 on this app; `probe_form_compile.py` rows "deprecation: …"). Not warned: disabled id-only control
(but it IS submitted by id today, so that user loses the field silently in 0.11 — minor), `rx.select(id=)` (never submitted
anyway), buttons/submit inputs, `rx.upload(id=)`, forms whose handler takes no form data. Warned: `rx.input(id="femail")`
inside `rx.form.field(name="email")` (correct: the id-keyed duplicate goes away).

Pre-existing (both versions, not regressions): `on_submit=State.store("x_" + it)` inside `rx.foreach` → page error
`it_rx_state_ is not defined` (the submit hook is hoisted out of the foreach scope); dataclass / pydantic-model `form_data`
annotations are rejected at compile time (0.10.0 `TypeError: Could not compare types ~FORM_SUBMIT_MAPPING…`, 0.10.1a1
`EventHandlerArgTypeMismatchError … expects dict[str, Any]`); `rx.form.control` only accepts `rx.input`; console warning
"Checkbox is changing from uncontrolled to controlled" ×7 on the legacy page on both versions.

### New API (`/new`, `/future`, new venv only; `out/forms-new-dev.json`)
- `rx.form.FormData[str, str]`: ordered `multi_items`, `getlist`/`getAll`, indexing = last value, `len` = distinct keys;
  id-only control appended (`idonly`), `id==name` checkbox contributes the ref's `True`. `FormData | None` OK. Passing a
  FormData on to a `dict` handler → dict of last values; to a TypedDict handler → coerced; to a FormData handler → same.
- TypedDict `Prefs`: `list[str]` collects all; `bool` False when unchecked, `"false"`/`"no"` → False; `bool | None` → None;
  `list[str] | None` → list when submitted; `NotRequired` unsubmitted → left out; `range: list[str]` ← `range[]`, bracket
  key dropped; `Annotated`, `Required[Annotated[...]]` fine; `int` field stays `str` ("7"); `Literal` not validated;
  controlled `rx.checkbox_group.root(value=…, on_value_change=…)` (#7345) submits the checked items; generic TypedDict
  (`GBase[list[str]]` subclass) coerced; TypedDict with dynamic names: unsubmitted required list fields → `[]`.
- `from __future__ import annotations` module (`td_future.py`): NotRequired (also inside Annotated) honoured, Required OK.
- Compile time (`probe_form_compile.py`, `out/probe_form_compile-*.txt`): missing required field → `EventHandlerValueError`
  (17-line message); fields provided by `id` only, by `tags[]`, by a controlled input, TYPE_CHECKING-only field types, generic
  TypedDicts all compile on new (several of these failed on 0.10.0); `rx.form.field(name=)` does NOT satisfy the TypedDict
  check (both versions). Wrong annotations (`int`, `str`, `list[str]`, `FormData[int, str]`) → `EventHandlerArgTypeMismatchError`.
- `transform_form_data` with a malformed envelope (`{"__reflex_form_data__": "str" | 5 | [["one"]]}`) raises
  ValueError/TypeError — and `form_data_as_dict` (the fallback in `_prepare_event_payload`'s except branch) calls
  `dict(entries)` again, so the exception escapes; see §2 for the over-the-socket result.

## 2. Crafted socket payloads / EVT-02
(see below — filled in as the run proceeds)
Crafted socket payloads (`probe_sio_payload.py`, run against the dev backend with the real CONNECT auth shape:
`?token=<uuid>` query + `auth={"event": <hydrate_and_load>, "state_schema": <hash from a browser CONNECT frame>}`;
output `out/sio_payload-new-dev.txt`, server log `out/sio_payload-new-dev.serverlog.txt`):
- a valid `{"__reflex_form_data__": [[k, v], ...]}` envelope sent by hand reaches a dict handler as the last-value dict.
- `{"__reflex_form_data__": "not-a-list" | 5 | [["one"]] | [[1,2,3]] | [[["x"],"v"]]}` in a `dict`-annotated OR
  unannotated handler arg: `_transform_event_payload` raises (ValueError/TypeError from `dict(entries)`), the
  `_prepare_event_payload` fallback calls `form_data_as_dict(value)` which calls `dict(entries)` AGAIN, so the
  exception escapes: `[Reflex Backend Exception]` with a 3-level traceback in the server log and an "An error occurred"
  toast to the client (6 tracebacks for 6 messages); the handler never runs; the connection survives and the next normal
  event works. Any connected websocket client can trigger this per message (no auth needed beyond a socket). 0.10.0 has
  no such envelope (not applicable). Low severity (log noise / a dead fallback branch), not a crash.
- a dict nested one level down containing the key is untouched (only top-level args are decoded).
- EVT-02 (`probe_client_error.py`, `out/client_error-new-dev*.txt`): socket.io-level `client_error` with no payload, `{}`,
  None, a string, a list, a dict without the expected keys, a 100 kB stack: no traceback, connection kept, the server
  logs `[Reflex Frontend Exception] [SID…] unknown: No error message provided` (3 lines for 7 emits: rate-limited); a
  normal event afterwards works. **fixed (unchanged)**. Note: sending a *state* event named `…state.client_error` (not a
  registered handler) logs a full `KeyError: 'No registered handler found for event'` traceback per message — same on
  0.10.0 (any unknown event name does), not new.

## 3. Re-verification (class_state fixtures, copied to `$W/class_state`, work dir `$W/cs_work`)
```bash
export W=$SB/apps/events_state/cs_work NEW=events_state-new PREV=events_state-prev; CS=$SB/apps/events_state/class_state
bash $CS/bin/run_python_suite.sh $NEW; bash $CS/bin/run_python_suite.sh $PREV      # logs: $W/logs/py/<venv>/
bash $CS/bin/n004_matrix.sh $W/logs/n004 $NEW $PREV                               # schema/pickle/disk interchange
```
- **STATE-11…19 (item 8)**: `rc.txt` identical between venvs; every probe log identical after normalizing version /
  paths / timings / `base.py` line numbers (4822 → 5035) / a random numpy length (`probe_docs`). pytest: moot 25 passed,
  converted 25, converted_attr 21, n039 204 + 1 skipped, undo_edge / v7 collection ERROR (expected), patch_substate 2F/2P,
  test_min 1F/1P, backend_var 4F/2P, other_attrs 1F/9P — exactly the 0.10.0 record. Dev guard (`guard7495`,
  `guard_local_rename`) unchanged. → still fixed / moot.
- **STATE-20/21 (item 9)**: schema hash `bbd147dc3cdaec5701080b994dc1875a` on both versions; shape hashes
  HBase=2efae2635f7cb10f HChild=f2d2a961f646368d HCfg=472cb6c56187afeb HSd=cb3b619998cde91c identical; pickles saved by
  either version load on the other at defaults 0 and 5 (field values only); disk sessions continue writer/reader in all
  4 combinations (`$W/cs_work/logs/n004/*.txt`). → unchanged (STATE-21 Python-version dependence not re-tested).
- **STATE-05 (item 7)** (`probe_state05_meta.py`, `out/probe_state05_meta-{new,prev}-ent.txt`, venvs `new-ent`/`prev-ent`
  with rxe 0.9.8): `type(rx.State) is BaseStateMeta` True; a `BaseStateMeta`-derived metaclass on a State subclass and
  its substate constructs and instantiates; `mixin=True` works and a mixin cannot be instantiated; `_reflex_state_root`
  is rejected as a reserved name (`StateValueError`); 113 rxe modules import (only `reflex_enterprise.testing.plugin`
  needs pytest), 0 deprecation warnings during import; an rxe State subclass constructs. Identical on prev. → fixed.
  (#7626 contract: `state_root=True` could not be exercised because `reflex_base.vars.base.BaseState` is not importable
  from there; the keyword is only meaningful on the root class.)
- **CMP-01 (item 17)** (`probe_upload_names.py`, `out/upload_names-new-dev.txt`; page `/upload` of formsapp with a
  handler writing `rx.get_upload_dir() / file.name`): 17 hostile filenames (`..`, `../../etc/passwd`, `....`, `.. `,
  `/abs/evil.txt`, `C:\x\y.txt`, `a/../../b.txt`, backslash traversal, `sub/dir/file.txt`, NUL byte, `. .`, `~/x.txt`,
  `%2e%2e/%2e%2e/x`, empty, invalid UTF-8) all resolve inside the upload dir (`name` = basename or `upload`; `path` keeps
  relative dirs with `..` segments removed, e.g. `etc/passwd`, `a/b.txt`, `~/x.txt` literal); HTTP 200 for all, no server
  traceback. The NUL-byte name and an empty filename (`name=None`) only fail inside the user handler. → fixed (no 0.9.8
  control venv available for the positive control).
- **EVT-06 (item 6)**: see §4 (evapp `/filtered`).

## 4. Python-level hunts (`probe_state_misc.py`, `out/probe_state_misc-<venv>.txt`; run on events_state-{new,prev} and
the py3.14 venvs `process_model-py314-{new,prev}`)
- **#7500** dict views: on new, mutation through `d.values()`, `d.items()`, `list(d.values())[0]`, `next(iter(...))`,
  `reversed(d.values())`, `[*d.values()]`, `sorted(...)`, `max(...)`, `d.values().mapping[k]`, `dict(d.items())[k]`,
  `for inner in nd.values(): inner[k] = v` all mark the var dirty and the cached var recomputes in the delta (0.10.0
  missed every one of these). Still MISSED on both versions (pre-existing): `d.copy()[k].append(...)` (while
  `dict(d)[k]` and `{**d}[k]` ARE tracked — inconsistent) and in-place operators on a value obtained without
  `__setitem__` (`v = d["a"]; v += [1]`, `for v in d.values(): v += [..]`). Same on 3.14.
- **#7636 / #7592**: handler args annotated `rx.Model` (also `Item | None`, `list[Item]`), pydantic v2 model, dataclass:
  0 warnings on new; 0.10.0 emitted 2 × `PydanticDeprecatedSince20: The __fields__ attribute is deprecated` per rx.Model
  payload key and 28 for assigning / delta / var access of model-typed state vars. `pydantic.v1` does not exist in
  pydantic 2.14.1, so the v1-compat path could not be exercised.
- **#7410**: with `@rx.state._override_base_method def get_delta` dropping an async `@rx.var(cache=False)` from the
  delta: 0.10.0 → 2 `RuntimeWarning … never awaited` (`AsyncComputedVar.__get__.<locals>._awaitable_result` and
  `_drop_unchanged_delta_value`); 0.10.1a1 → still 1: `coroutine '_drop_unchanged_delta_value' was never awaited`
  (the wrapper created in `build_delta` is appended to `pending` and never closed when `_commit_delta_records` finds the
  key withheld). Checked in a real app too: evapp `/filtered` (`atick`), see §5.
- **#7443**: `app.modify_state("bare")`, `"tok_unknown___state"`, `"tok_<root>.nope"`, `""` → `ValueError: Invalid legacy
  state token: no state found for the state path. Expected '<client_token>_<state_full_name>'. Use
  rx.BaseStateToken(ident=client_token, cls=StateClass) instead.` (0.10.0: `ValueError: Invalid path: ('',)`); valid
  legacy strings and `rx.BaseStateToken` work; no deprecation warning is emitted for the legacy string form (EVT-09's
  "still un-deprecated" remark stands: 0 DeprecationWarnings recorded).
- **#7547**: `items: list[Item] = []` / no default / backend `_items` / computed `-> Item` / `'list[Item]'` string /
  `mod.Thing` → `NameError: name 'Item' is not defined` on 3.12 and 3.14, with and without `from __future__` (0.10.0:
  `TypeError: Unsupported type ForwardRef(...)`, `AttributeError: 'ForwardRef' object has no attribute '__name__'`, or
  silently created the class — backend var, `list['Item']`, and on 3.14 even the plain annotation). An undefined name in
  a *handler* argument annotation still creates the class silently on both (not covered by #7547).
- **#7606** `reflex_base.vars.get_leaf_vars`: slices, joins, arithmetic, casts, `d[k]`, literal containers, `foreach`
  lambdas (loop var excluded, closed-over state var included), `rx.cond` all return the state leaf vars; literals → `[]`;
  a non-Var input raises AttributeError (`'list' object has no attribute '_hash_key'`).
- **#7622 revert**: a `frozenset[int]` state var raises `VarTypeError: State vars must be of a serializable type …`
  on BOTH 0.10.0 and 0.10.1a1 (identical; #7622 was never released). See the probe for `Var.create(frozenset)`.
