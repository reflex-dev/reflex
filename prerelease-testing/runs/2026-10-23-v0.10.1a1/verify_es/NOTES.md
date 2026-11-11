# verify_es — independent verification of ES-1 / ES-2 / ES-3 (events_state, reflex 0.10.1a1 vs 0.10.0)

Verifier run 2026-10-24. Everything ran from `$SB/apps/verify_es` (never from a checkout) with the shared read-only
venvs `events_state-new` (reflex 0.10.1a1), `events_state-prev` (0.10.0), `events_state-sio` (python-socketio 5.17.0),
`driver` (Playwright). Ports 3760 / 8760 only, one app server at a time, dev mode (`reflex run --loglevel debug`).
Source references are `git show v0.10.1a1:<path>` line numbers in `/home/user/wt-testing`.

Verdicts: **ES-1 CONFIRMED (scope widened by a browser path, severity unchanged: low)** — **ES-2 NARROWED (fix is
complete for the filed scenario; the residual warning is the filter's own unclosed coroutine; nothing of the user's
computation leaks)** — **ES-3 CONFIRMED as a deliberate behaviour change, "undocumented" narrowed: in the form docs and
the PR, absent from the CHANGELOG entries, which also misstate what changes now vs in 0.11**.

## Setup / rerun
```bash
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa; V=$SB/apps/verify_es; export SB
# app = the explorer's formsapp plus a /verify page (ES-3 variants + ES-1 name-collision forms) and two chained dict handlers
cp -r <this dir>/formsapp $V/formsapp; cp <this dir>/*.py <this dir>/*.sh $V/
cd $V && bash run_app.sh events_state-prev $V/formsapp prev-dev 3760 8760 --loglevel debug && bash wait_up.sh http://localhost:3760/verify 420 pids/prev-dev.pid
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_verify.py http://localhost:3760 out/verify-prev-dev.json
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/events_state-sio/bin/python probe_sio_verify.py http://localhost:8760
bash stop_app.sh prev-dev; rm -rf formsapp/.web formsapp/.states
bash run_app.sh events_state-new $V/formsapp new-dev 3760 8760 --loglevel debug && bash wait_up.sh http://localhost:3760/verify 420 pids/new-dev.pid
NO_PROXY=... $SB/envs/driver/bin/python drive_verify.py http://localhost:3760 out/verify-new-dev.json
SCHEMA=$(grep -o 'stateSchema = "[^"]*"' formsapp/.web/utils/context.jsx | cut -d'"' -f2)   # 392411f8ad8efcd5d8b013d127df2cd2 for this app
NO_PROXY=... $SB/envs/events_state-sio/bin/python probe_sio_verify.py http://localhost:8760 $SCHEMA
bash stop_app.sh new-dev; rm -rf formsapp/.web formsapp/node_modules formsapp/.states
# ES-2, python-level, both venvs:
for v in events_state-prev events_state-new; do EXPECT_VENV=$v $SB/envs/$v/bin/python -I probe_es2.py; done
```
Outputs: `out/verify-{prev,new}-dev.json` (per-form handler records, ws frames, toasts, console), `out/sio-{prev,new}-dev.txt`
(+ `.serverlog.txt` = the server log during the probe), `out/browser-new-dev.serverlog.txt` (server log during the
0.10.1a1 browser run, holds the `collide_chain` traceback), `out/probe_es2-*.txt`, `logs/new-dev.compile-excerpt.txt`.

## ES-1 — malformed `__reflex_form_data__` envelope raises inside the payload fallback

**Reproduced** (`probe_sio_verify.py`, 0.10.1a1, `out/sio-new-dev.txt` / `.serverlog.txt`): client A sends
`{"form_data": {"__reflex_form_data__": "not-a-list" | [["only-one"]] | [[["x"], "v"]]}}` to the dict-annotated `State.store`
→ per message one `Warning: Error transforming event payload …` line, then one `[Reflex Backend Exception]` with the
three-level traceback (`transform_form_data` `dict(entries)` ValueError/TypeError → `_transform_event_payload` ValueError
→ `_prepare_event_payload` fallback `form_data_as_dict` → `dict(entries)` raises again, `form.py:358` / `:377`,
`base_state_processor.py:211/216`), and an "An error occurred." toast to A. The handler never runs.

Answers to the verification questions:
- **Can a real browser produce such an envelope?** Not a malformed one: `getFormData` (`state.js:2072-2091`) builds every
  entry from `new FormData(form).entries()` (always `[name, value]`, value a string or a File that socket.io ships as a
  binary attachment) plus `Object.entries(refValues)` (ids → `getRefValue` results: string / bool / null / undefined,
  JSON-encoded as 2-tuples). Unusual names (`tags[]`, bracketed, dynamic) are plain strings.
- **Can a user-controlled `name` collide with the envelope key? YES — a real-browser path into the same traceback.**
  `/verify` form `collide_chain`: `rx.input(name="__reflex_form_data__")` + `rx.input(name="a")`, `on_submit=State.collide_first`
  (dict handler that `return State.collide_second(form_data)`). Browser result (`out/verify-{prev,new}-dev.json`):
  - 0.10.0: both handlers record `{"__reflex_form_data__": "x", "a": "1"}` (`seq+2`).
  - 0.10.1a1: `collide_first` records the same dict (the wire envelope decodes fine), but `collide_second` never runs
    (`seq+1`): `_prepare_event_payload` sees a dict whose `__reflex_form_data__` key holds the string `"x"`, treats it
    as an envelope, `dict("x")` raises, the fallback raises again — `out/browser-new-dev.serverlog.txt:118-202`
    (`ValueError: Error transforming event argument 'form_data' with value '{'__reflex_form_data__': 'x', 'a': '1'}'`).
    The non-chained form `collide_plain` works on both versions. Root cause: envelope detection is "dict has this key"
    with no shape check, so the key is not namespaced against user field names once a decoded dict re-enters the
    processor (chained handler, `yield State.other(form_data)`, `app.modify_state`-style re-dispatch).
- **Only the sender's session?** Yes: bystander client B (connected throughout) gets its normal delta right after A's
  three bad messages; A's own next plain event works; the socket stays connected; no state lock or token is left
  dirty. One traceback per bad message, nothing accumulates. No DoS beyond log noise from an authenticated-by-socket
  client that could already spam any unknown event name for a `KeyError` traceback each (explorer's note, same on 0.10.0).
- **Is plain garbage to a typed handler on 0.10.0 similarly noisy?** Yes, same shape: `{"form_data": 5}` or
  `{"form_data": {"zzz": 1}}` to the dataclass-annotated `State.store_dc` gives, on BOTH versions, the
  `Error transforming event payload` warning (dict case), one `[Reflex Backend Exception]` traceback
  (`TypeError: asdict() should be called on dataclass instances`, raised inside the user handler after the fallback
  handed it the raw value) and the same toast (`out/sio-prev-dev.txt`, `.serverlog.txt:38-124`). On 0.10.0 the
  envelope-shaped payloads themselves are plain dicts and run the handler without error (N/A rather than a baseline).
  So ES-1 adds no new class of noise; the differences are that the traceback comes from framework code (a fallback
  that cannot do its job) and that the harmless-looking `name="__reflex_form_data__"` becomes a trap.

Verdict: CONFIRMED, low. Suggested fix: `form_data_as_dict` / `transform_form_data` should accept entries only when
they are a list of 2-item lists (else treat the dict as a plain dict), which also closes the name-collision path for
the chained case (the raw dict would simply pass through).

## ES-2 — #7410 leaves one `coroutine '_drop_unchanged_delta_value' was never awaited`

`probe_es2.py` (`out/probe_es2-*.txt`), an async `@rx.var(cache=False)` withheld by a `@rx.state._override_base_method
get_delta`, three filter styles, with a counter in the var body:

| filter | 0.10.0 | 0.10.1a1 | body runs |
|---|---|---|---|
| `sub.pop(key)` without closing (explorer's repro, also issue #7254's minimal repro) | 2 warnings (`_awaitable_result`, `_drop_unchanged_delta_value`) | **1** (`_drop_unchanged_delta_value`) | 0 / 0 |
| `value = sub.pop(key); value.close()` (PR #7410's tests; reflex-enterprise `auth/enforcement.py:1425,1516,1527` does exactly this) | 1 (`_awaitable_result`) | **0** | 0 / 0 |
| not withheld | 0 | 0 | 1 / 1 |

Source pin (0.10.1a1): `build_delta` (`reflex/istate/delta.py:264-278`) creates the wrapper coroutine
`_drop_unchanged_delta_value(cvar, state, token, …)` and stakes it into `pending` as a `_DeltaRecord`; the user's getter
coroutine is created only inside the wrapper (`delta.py:214`, `await cvar.__get__(instance, type(instance))`), which is
the whole #7410 change (`vars/base.py:3251-3256` `_awaitable_result` is created in `AsyncComputedVar.__get__`). A filter
that drops the key leaves the wrapper never started; `_commit_delta_records` (`delta.py:109-112`) `continue`s on a
withheld key and does not close it, so the wrapper object is collected unstarted → Python's standard warning. The
user's `async def` body therefore never runs when withheld (`body_runs=0` on both versions): no user computation,
DB session or task is leaked — the object collected is a one-frame framework wrapper.

Reading of the claim: issue #7254 (title and body) is about the *inner* `_awaitable_result` coroutine that a filter
could not reach even when it closed the wrapper, "Users of enterprise auth see this"; that is fixed (1 → 0 for a
closing filter, which is what reflex-enterprise ships). What remains is only for a filter that discards the coroutine
without `.close()` — the same warning any Python code gets for dropping a coroutine object, and avoidable by the filter.
The CHANGELOG line ("Fix unawaited coroutine warnings when a state delta filter withholds…") does not say the filter
must close what it withholds, and the framework could close staked wrappers for withheld keys itself in
`_commit_delta_records`; both are polish, not an incomplete fix. Not a regression (2 → 1, 1 → 0).

Verdict: NARROWED, low → trivial/docs. Regression: no.

## ES-3 — `id == name` on a repeated-name control: dict handlers get a different value

**Reproduced in Chromium on both versions** (`/verify`, `out/verify-{prev,new}-dev.json`, dict handler `State.store`):

| form (`/verify`) | 0.10.0 | 0.10.1a1 |
|---|---|---|
| `v_group_id_eq_name`: `rx.checkbox_group.root(c1,c2,c3, id="cg", name="cg")` c1+c3 checked; native `input(type=checkbox, id="topping", name="topping", value="cheese")` + `name="topping" value="olives"`, both checked | `{"cg": "c1", "topping": true}` | `{"cg": "c3", "topping": "olives"}` |
| `v_msel_id_eq_name`: `rx.el.select(multiple=True, id="msel", name="msel")`, o1+o3 selected | `{"msel": "o1"}` | `{"msel": "o3"}` |
| `v_rep_id_eq_name`: `rx.input(id="rep2", name="rep2", "first")` + `rx.input(name="rep2", "second")` | `{"rep2": "first"}` | `{"rep2": "second"}` |
| `v_once_id_eq_name`: same checkbox group with ONE item checked + one `id==name` checkbox | `{"cg1": "c2", "solo": true}` | `{"cg1": "c2", "solo": true}` (identical) |

So the change is exactly the rule in `state.js:2078-2080`: an id ref's value replaces the form's entry only when the
form submitted that `name` at most once (0.10.0: `{...Object.fromEntries(new FormData($form).entries()), ...refs}`,
`forms.py:67-69`, refs always win). Deliberate: PR #7386 body "A name the form submits more than once keeps all its
values"; it is what makes `FormData.getlist` / TypedDict `list[str]` see every value. `checkbox_group.root` already
accepted `name` and was `_is_form_control` on 0.10.0 (`checkbox_group.py:18,38`), so the pattern was possible before.

Documentation status (all read on tag v0.10.1a1):
- `docs/library/forms/form.md:166` states it: "…that value replaces the value submitted under the same `name`, unless
  the form submits that `name` more than once." → documented in the docs and the PR.
- Root `CHANGELOG.md` #7386 feature entry: "a `dict` annotation still keeps each name's last value" — this IS the new
  behaviour for these forms, but "still" claims nothing changed.
- `reflex-components-core/CHANGELOG.md` #7386 deprecation entry: "A control whose `id` differs from its `name` also
  stops adding a field keyed by its `id`, and a checkbox or switch whose `id` equals its `name` submits "on" or nothing
  instead of True or False" reads as present tense but describes the 0.11 removal (the explorer's and my runs show
  `id != name` still adds both keys and an `id == name` checkbox still gives `True` on 0.10.1a1; form.md:168-172 puts
  the same sentences under "From then on"). The one thing that does change now (the repeated-name exception) is not in
  either entry. `reflex-base` and `reflex-components-radix` entries: FormData/TypedDict only.
→ "undocumented" holds for the CHANGELOG, not for the docs; the core entry's wording is the larger documentation defect.

Prevalence: reflex-examples (158 `.py`, 12 `on_submit` forms): no control carries both `id` and `name`, `checkbox_group`
unused, form-designer uses dynamic `name`s only; docs: one `rx.input(id="start", name="start")` (single-submitted →
unaffected). The affected pattern needs a dict handler + a control that submits its name more than once (checkbox
group / multi-select / repeated inputs) + `id == name` on it — rare, and such apps were already reading an
artefact: `getRefValue` returned the *first* checked item (`querySelector(":checked")`), the id'd checkbox's bool
`.checked` (not its `value`), the first selected option. The new value is the last submitted one, the same thing the
explorer's name-only `groups` form returns on BOTH versions (`cg: c3`, `topping: olives`), so dict handlers are now
consistent whether or not the control carries an `id`; every value is available via `rx.form.FormData`.

Verdict: CONFIRMED (deliberate behaviour change, documented in docs/PR, not in CHANGELOG), low. Regression: yes, by
design, scope = dict/unannotated handlers reading an `id == name` control whose name is submitted more than once.
Suggest one sentence in the core deprecation entry and future-tense wording for its 0.11 sentences.

## Cleanup
Servers stopped (`stop_app.sh`, process groups gone), ports 3760/8760 free (`curl` 000, no listeners), `.web/`,
`node_modules/`, `.states/`, `uploaded_files/` removed from `$V/formsapp`.
