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
