# Cluster `forms` — reflex 0.10.1a1 pre-release testing notes

Tested changelog lines: reflex #7386 (FormData / TypedDict coercion), reflex-base #7386
(Required/NotRequired under `from __future__ import annotations`), reflex-components-core #7386
(id-only deprecation, controlled input `name`), reflex-components-radix #7386 (`rx.form.FormData`),
#7345 (controlled `checkbox_group` / `checkbox_cards`), #7418 (`rx.input` `auto_complete`).

Everything was installed from PyPI: `$SB/envs/shared` (0.10.1a1, Python 3.11) and `$SB/envs/prev`
(0.10.0) for the baseline. Browser: Playwright Chromium via `$SB/envs/driver`.

## Layout

- `forms/` — the 0.10.1a1 app (6 pages). `forms/forms/forms.py` (no future annotations) and
  `forms/forms/typed_future.py` (`from __future__ import annotations`).
  - `/` untyped handler + `dict` handler + `rx.form.FormData[str, str]` handler; Enter-key and
    button submit, `reset_on_submit=True`, `yield` chain into a second handler + `rx.toast`,
    form data echoed with `rx.foreach` over a dict.
  - `/typed` TypedDict with `list[str]`, `Annotated[list[str], ...]`, `bool`, `bool | None`,
    `list[str] | None`, `NotRequired`, `Required` inside `rx.cond`, controlled
    `rx.input(value=..., on_change=...)`, `rx.foreach`-generated inputs sharing a name,
    two-thumb `rx.slider(name="range")`, select submitting `"false"`.
  - `/future` same under postponed annotations, `total=False` with `Required[...]`,
    `Annotated[NotRequired[list[str]], ...]` with no control.
  - `/deprecated` id-only input / checkbox / textarea / select / slider, `id != name`,
    checkbox+switch `id == name`, disabled id-only input, `type="submit"` input with id.
  - `/controlled` controlled `checkbox_group` + `checkbox_cards` (`value` + `on_value_change`),
    `radio_cards` with `name`, `auto_complete="email" | "off" | True | False`.
  - `/cs` two instances of a form inside an `rx.ComponentState`.
- `forms_prev/` — the same app trimmed so it compiles on 0.10.0 (FormData annotation -> `dict`,
  `checkbox_group`/`checkbox_cards` uncontrolled, no string `auto_complete`, `controlled` and `cc`
  made `NotRequired`, plus `forms/__init__.py` which 0.10.0 needs — see quirks).
- `forms/scripts/test_forms.py` — the end-to-end driver (prints observed form data per page, checks
  expectations, captures console/pageerror/failed requests/4xx-5xx, writes a JSON report).
- `forms/scripts/isolate_warning.py` — clicks controls one at a time and prints console warnings.
- `forms/scripts/check_future_notrequired.py` — compile-only check for reflex-base #7386.
- `forms/scripts/drive_app.py` — copy of the shared single-page driver (used for per-page loads).
- `forms/logs/` — `dev.log`, `prod.log` (server logs, deprecation warnings at compile time),
  `dev-run1.txt` / `prod-run.txt` (driver output), `*-report.json`, `pyright.txt`,
  `check_future_notrequired.txt`, `pageload-*.json`.
- `forms_prev/logs/` — 0.10.0 baseline: `dev.log`, `dev-no-init-py.log`, `prev-run.txt`,
  `prev-report.json`, `prev-isolate-warning.txt`.
- `forms/shots/{dev,prod}/`, `forms_prev/shots/prev/` — screenshots.

## How to rerun

```
SB=/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt   # or any dir holding envs/{shared,prev,driver}
export REFLEX_TELEMETRY_ENABLED=false
# 0.10.1a1 dev
cd <artifact>/forms && $SB/envs/shared/bin/reflex run --loglevel debug --frontend-port 3100 --backend-port 8100 > logs/dev.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/test_forms.py http://localhost:3100 shots/dev logs/dev-report.json
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/isolate_warning.py http://localhost:3100/ "#remember" "text=hobby c" "text=hobby a"
# 0.10.1a1 prod (prod mode requires one port for both)
$SB/envs/shared/bin/reflex run --env prod --loglevel debug --frontend-port 3100 --backend-port 3100 > logs/prod.log 2>&1 &
# 0.10.0 baseline
cd <artifact>/forms_prev && $SB/envs/prev/bin/reflex run --loglevel debug --frontend-port 3101 --backend-port 8101 > logs/dev.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python ../forms/scripts/test_forms.py http://localhost:3101 shots/prev logs/prev-report.json
# compile-only checks
cd /tmp && $SB/envs/prev/bin/python <artifact>/forms/scripts/check_future_notrequired.py
cd /tmp && $SB/envs/shared/bin/python <artifact>/forms/scripts/check_future_notrequired.py
# pyright on the app
cd <artifact>/forms && uvx pyright --pythonpath $SB/envs/shared/bin/python forms/
```

The driver's `test_forms.py` accepts page names after the report path (`index typed future
deprecated controlled cs`) to run a subset.

## Results (0.10.1a1, dev and prod identical unless noted)

Observed form data, verbatim from the driver (`logs/dev-run1.txt`, `logs/prod-run.txt`):

- `/` untyped: `{"dark": true, "first": "Ann", "group": "g3", "hobby": "c", "notes": "line1\nline2",
  "pick": "y", "radio": "r2", "range[]": "60", "range_slider": "20", "remember": true, "second": "typed-second"}`
  — last value per name, `range[]` keeps the last thumb, id refs add `range_slider` (id
  `range-slider` formatted) and replace `remember`/`dark` with `true`/`false`.
- `/` FormData: `multi_items() == [["hobby","h1"],["hobby","h2"],["hobby","h3"],["solo","only"],["range[]","1"],["range[]","9"]]`,
  `getlist("hobby") == ["h1","h2","h3"]`, `dict(fd)` keeps last; passing the FormData on via `yield`
  to a `dict`-annotated handler gives the last-value dict. OK.
- `/typed`: `{"bio": "bio text", "color": ["blue"], "controlled": "ctrl-edited", "controlled_input": "ctrl-edited",
  "foreach_val": ["f1","f2","f3"], "hobby": ["h1","h3"], "name": "Bob", "opt_flag": null, "opt_list": null,
  "range": ["10","30"], "size": "m", "strflag": false, "subscribe": false, "toggled": true}` and after
  checking `subscribe` / revealing the cond: `subscribe: true`, `hidden_req: "now visible"`. All
  changelog sentences hold: list fields collect all values, `range` absorbs `range[]` (and the
  `range[]` key is removed), `bool` is False when unchecked or `"false"`, `X | None` is None when
  the control submits nothing, `NotRequired` without a control is left out.
- `/future`: `{"agree": true, "extras": null, "maybe_flag": null, "title": "hello"}`; unchecking gives
  `agree: false`. `nickname` / `Annotated[NotRequired[list[str]]]` left out. Compile check
  (`check_future_notrequired.txt`): 0.10.0 raises "Form field mismatch ... missing nick, tags",
  0.10.1a1 compiles — bugfix confirmed.
- `/deprecated`: `{"cb": true, "cbid_only": true, "disabled_id": "d", "only_id": "idval", "slider_id": "5",
  "sub_id": "go", "sw": false, "ta_only": "ta", "the_id": "both", "the_name": "both"}` — byte-identical
  on 0.10.0. Compile-time `DeprecationWarning` (4x, in `logs/dev.log` and `logs/prod.log`) for
  `only_id`, `cbid_only`, `ta_only`, `slider_id`. No warning for `sel_only` (it never submitted
  anything, on either version), `disabled_id`, `sub_id` (both DO submit by id, see issues).
- `/controlled`: autocomplete DOM attributes `email`, `off`, `on`, `off` (0.10.0: attribute absent and
  React console error "Received `true` for a non-boolean attribute `autoComplete`"). Controlled
  `checkbox_group` fired `on_value_change` twice (`cg=b,a,c changes=2`), `checkbox_cards` once; submit
  gives `cg: ["a","b","c"]`, `cc: ["x","y"]`, `rc: "q"` plus id-ref noise `cg_root: "a"`, `cc_root: "x"`.
- `/cs`: alpha `{"checks": ["c1"], "flag": true, "flag_alpha": true, "item": "alpha"}`, beta
  `{"checks": ["c1","c2"], "flag": false, "flag_beta": false, "item": "beta"}`, independent counters.
- Enter in a text input submits the form like the button; `reset_on_submit=True` clears inputs and
  unchecks; `yield` chain + `rx.toast` both fire.
- pyright (`logs/pyright.txt`): `rx.form.FormData[str, str]` annotation and `rx.form(...)` calls
  type-check. Errors are only on `yield Other(form_data)` where the receiver is annotated `dict`
  (FormData is a Mapping, not a dict) and on `auto_complete=True/False` (stub says `str`), plus
  `.join` on a `list[str]` state var (pre-existing Var typing, not this cluster).
- Prod mode: same data; the dev-only React warning below does not appear; one console
  "Failed to load resource: 404" with no matching >=400 response captured (see anomalies).

## Issues / anomalies

1. Changelog (reflex-components-core deprecation line) describes behaviour that 0.10.1a1 does not
   have: "A control whose `id` differs from its `name` also stops adding a field keyed by its `id`,
   and a checkbox or switch whose `id` equals its `name` submits `"on"` or nothing instead of
   `True` or `False`". Observed (both versions): `the_id` AND `the_name` present, `cb: true`,
   `sw: false`, `remember: true/false`. PR #7386's description says this is intentional
   ("non-breaking ... A control with an `id` still adds a field read from its ref, and that value
   still replaces the value submitted under the same `name`"; removal is stacked in #7540 for 0.11).
   So the code matches the PR, the changelog sentence is wrong for 0.10.1. Not a regression.
2. Deprecation warning gaps: `rx.input(id="disabled_id", disabled=True)` and
   `rx.input(type="submit", id="sub_id", value="go")` are skipped by `_deprecate_id_only_form_controls`
   ("a disabled control is never submitted"), yet both DO submit by id today (`disabled_id: "d"`,
   `sub_id: "go"`) and will silently vanish in 0.11. Low. Not a regression.
3. Required `list[str] | None` / `bool | None` fields with NO control fail compile-time validation
   ("Fields missing from the form") even though the runtime maps "unsubmitted" to None. The changelog
   sentence "for `list[str] | None` and `bool | None` fields an unsubmitted value is `None`" is only
   true when a control with that `name` exists but submits nothing (unchecked checkbox/switch). The
   error's hint still says "Add controls with matching static `name` or `id` values" although `id`
   is now deprecated. Doc/UX anomaly, low.
4. Radix checkbox with an `id` whose formatted ref key collides with another field's `name`
   (id `opt-list` -> key `opt_list`) injects the ref's JS boolean: a `list[str]` TypedDict field
   became `[False]` and a `bool | None` field `False` instead of `None`. Only reachable through the
   deprecated id path; recorded for completeness (first run in `logs/dev-run1.txt`).
5. Console warning on every first click of an `rx.checkbox` that has no `default_checked`:
   "Checkbox is changing from uncontrolled to controlled" (dev only; `logs/dev-report.json`,
   `forms_prev/logs/prev-isolate-warning.txt`). Present identically on 0.10.0 — not a regression.
6. Prod run logged one console "Failed to load resource: 404" with no >=400 response in the report
   (likely a sourcemap/worker fetch outside the page's response events). Not reproduced in dev.
7. (0.10.0 baseline only) `forms_prev` needed `forms/__init__.py`: without it the granian worker died
   with "attempted relative import with no known parent package" (`forms_prev/logs/dev-no-init-py.log`).
   0.10.1a1 ran the same package without `__init__.py` — matches changelog #7258.
8. (0.10.0 baseline only) the `rx.toast` yielded after submit did not render on 0.10.0 in the driver's
   window; it does on 0.10.1a1. Not investigated further (outside this cluster).
9. `rx.cond` hiding a `Required[str]` control passes compile-time validation (the control is
   statically in the tree) and the handler then gets a `KeyError` at runtime when the cond is false.
   Expected given static analysis; noted for docs.
