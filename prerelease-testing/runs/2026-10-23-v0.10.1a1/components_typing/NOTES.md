# components_typing — reflex 0.10.1a1 (2026-10-24)

Item: radix (#7345 #7593 #7418 #7438 #7629 #7645), moment (#7591), data_editor (#7607), lucide (#7604),
code (#7437), typing (#7406 #7413 #7419 #7403 #7401, `rx.form.FormData`, `VarData(position=)`), CMP-11, CMP-31.
Status: IN PROGRESS — this file is updated incrementally; the structured report is in the final message.

## Environment

- `SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`
- `envs/new` = reflex 0.10.1a1 (radix/moment/dataeditor/code 0.10.1a1, lucide 1.1.1a1, core 0.10.1a1);
  `envs/components_typing-prev` = reflex[db]==0.10.0 strictly (radix/moment/dataeditor/code/core 0.10.0,
  lucide 1.1.0) + pyright 1.1.414 + ty 0.0.91. NOTE: the orchestrator's `envs/prev` carries moment/lucide/code at
  0.10.1a1 (reflex 0.10.0 only floors them at >=0.10.0), so it is NOT a baseline for those packages.
- `envs/components_typing-new-whl` = reflex[db]==0.10.1a1 + pyright + ty installed with `--only-binary :all:`
  (122 stubs, identical to `envs/new`). `envs/components_typing-new` (first attempt, same command without
  `--only-binary`) got every reflex package BUILT FROM THE SDIST by uv (`uv_build.json` in 9 dist-infos) and is
  missing 6 stubs — see ISSUE CT-3. Typing results below are from the wheels-only venv unless stated.
- Ports: dev 3240/8240, prod 3241 (single port). Browser: Playwright Chromium, context timezone America/New_York.

## Files (this directory)

- `ctapp/` — the app (13 pages, guarded with `NEW = hasattr(rx, "moment_provider")` so it also runs on 0.10.0).
- `probes/probe_compile.py`, `probes/probe_detail.py` — compile-time probes, run on new and prev.
- `typing/typing_user.py`, `typing/typing_new_api.py`, `typing/fd_probe.py`, `typing/fd_probe2.py`,
  `typing/run_typing.sh`, `typing/run_probes.sh` — pyright + ty modules and runners.
- `drive_ct.py` — Playwright driver (per-page checks + console/pageerror/request capture), `run_prod.sh`.
- `results/` — JSON/TXT outputs; `logs/` — trimmed server/driver/typing logs; `shots/` — evidence screenshots.

## Rerun

```
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
cd $SB/apps/components_typing
EXPECT_VENV=new $SB/envs/new/bin/python probes/probe_compile.py > results/probe_compile_new.json
EXPECT_VENV=components_typing-prev $SB/envs/components_typing-prev/bin/python probes/probe_compile.py > results/probe_compile_components_typing-prev.json
NEW_ENV=components_typing-new-whl bash typing/run_typing.sh            # pyright + ty, new and prev
bash typing/run_probes.sh components_typing-new-whl                    # fd_probe*.py
cd ctapp && EXPECT_VENV=new REFLEX_TELEMETRY_ENABLED=false $SB/envs/new/bin/reflex run --frontend-port 3240 --backend-port 8240 --loglevel debug
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_ct.py --base http://localhost:3240 --out results/drive_dev_new.json --shots shots/dev_new
# prod: ./run_prod.sh (stops dev, starts --env prod on 3241, drives all pages)
# prev baseline: same with EXPECT_VENV=components_typing-prev and $SB/envs/components_typing-prev/bin/reflex on 3242/8242
```

## Results so far

(see the sections appended below as each run completes)

### A. Compile-time probes (`results/probe_compile_{new,components_typing-prev}.json`, `probe_detail_*.json`)

| probe | 0.10.1a1 (new) | 0.10.0 (prev) |
|---|---|---|
| #7345 `checkbox_group.root(value=, on_value_change=, disabled=, required=, orientation=, dir=, loop=, name=)` | all render as props (`onValueChange`, `value:`, `disabled:true`); `_is_form_control=True` | `ValueError: CheckboxGroupRoot does not take in an on_value_change event trigger` |
| #7345 `checkbox_cards.root/.item` same props | props; item `value/disabled/required` props | same ValueError |
| #7593 `radio_cards.root(as_child=True)`, `.item(as_child=True)` | **silently becomes CSS**: `css:({"asChild": true})` on root and item, no warning | `asChild:true` forwarded to Radix (the crash case the changelog describes) |
| #7418 `rx.input(auto_complete=...)` | `"off"`→`autoComplete:"off"`, `"email"`, `True`→`"on"`, `False`→`"off"`, bool Var→`(flag ? "on" : "off")`, str Var passthrough | `"off"`/`"email"`/str Var: `TypeError: Invalid var passed for prop TextFieldRoot.auto_complete, expected bool`; `True`→`autoComplete:true` (dropped by React) |
| #7438 primitive `progress(value=Var, max=200)` | Root renders `value:` and `max:` (and Indicator) | Root has only `className` (CMP-41) |
| #7629 accordion item style | `&:first-of-type` | `&:first-child` |
| #7645 libraries | accordion 1.3.1, dialog 1.3.1 (drawer dep too), form 0.3.0, progress 1.2.1, slider 1.6.1 | 1.2.20 / 1.1.23 / 0.1.16 / 1.1.16 / 1.4.7 |
| `rx.form.FormData` | `reflex_base.utils.form.FormData`, subscriptable; `rx.form(...)`→`Form`, `rx.form.root(...)`→`FormRoot` | absent |
| #7591 `rx.moment(utc/calendar/from_/to/ago/element/fallback/filters/renderers)` | all render as props (`from:`, `renderers:[...]`), no `css:` | every one becomes CSS (`css:({"utc": true})`, filters/renderers under a media query) — CMP-15 |
| #7591 `rx.moment_provider(locale="fr", format, timezone)` | props + `moment/locale/fr` side-effect import + `moment.locale("en")` restore in custom code | n/a |
| removed/unknown moment props `filter=`, `settings=`, `form_at=` | still silently CSS (`css:({"filter": ...})`); no actionable error despite the PR description claiming one | same |
| `rx.moment()` default locale | no default (provider or English) | `locale:"en"` literal default |
| #7607 literal columns `[{"title":"Name"}, ..., "Plain"]` | input dicts NOT mutated; rendered with defaults | input dicts mutated in place (`id`,`type`,`overlayIcon` added) |
| #7607 state-backed columns | `useMemo` mapping hook + `useCallback` getData with `[columns_x, state.data]` deps; `list[str]` of titles accepted; `State.data[1:]` depends on `State.data` | plain `function getData(...)`; `list[str]` state var → `TypeError: Invalid var passed for prop DataEditor.columns` |
| `format_data_editor_column` | prints the 0.10.1 deprecation and still works | works, no warning |
| #7604 `rx.icon("wifi_off").import_var` | `ImportVar(tag='WifiOff', is_default=True, alias='LucideWifiOff', package_path='/dist/esm/icons/wifi-off.mjs')`; a same-library prop import (`icons as lucideIcons`) is KEPT next to the icon import, static and dynamic | `import_var` reports the barrel (`is_default=False, package_path='/'`); the prop import is DROPPED |
| #7437 `rx._x.code_block(use_transformers=True)` | `transformers:[transformerCompactLineOptions(), ... 10 sorted]`, imports `@shikijs/transformers@4.5.0`, `.diff/.highlighted` styles on the wrapper box | `transformers:[]`, no transformers import (CMP-29) |
| react-syntax-highlighter | 16.1.2 | 16.1.1 |
| `VarData(position=...)` | runtime deprecation printed ("deprecated in version 0.10.1 ... removed in 1.0"); the `position` attribute no longer exists on the instance | attribute kept |

### B. Browser — dev (0.10.1a1, `results/drive_dev_new*.json`, `logs/drive_dev_new*.log`) and prod (`results/drive_prod_new*.json`)

Prod: 164/167 checks pass (the 3 failures were driver bugs fixed afterwards, see `drive_prod_new_cbg2.json`).
Per page, 0 page errors, 0 failed requests, 0 4xx/5xx in prod on every page; console: only the known moment
`defineLocale` deprecation (CMP-14), my deliberate `garbage` date warning, and one `404` console line on /cbg
without a captured request (favicon, no favicon in the app).

- **cbg** (#7345): controlled `checkbox_group` round-trips (click C → state `["a","c"]`, one `on_value_change`
  with a `list[str]` payload; disabled item ignores clicks; server `clear`/`preset` reach the DOM; root `disabled`
  Var disables every item and blocks clicks); `checkbox_cards` controlled likewise; `default_value` group checked;
  `rx.form` submit with `FormData` handler: `{"grp": ["a","c"], "dgrp": ["d2"], "cards": [...]}` — plus the
  deprecated id-based keys `"cg": ["a"]`, `"cc": [null]`, `"cg_default": ["d2"]` for the `id=` on the group roots
  (compare prev below).
- **radio_aschild** (#7593): page renders 3 radios in a grid container, no page error (on 0.10.0: see prev run).
- **input** (#7418): DOM `autocomplete` = off / email / on / off / off→on after toggling the bool Var / email (str
  Var) / none / off (`rx.el.input`) / off (controlled); controlled input round-trips.
- **progress** (#7438): primitive root `role=progressbar aria-valuenow=25 aria-valuemax=100 data-state=loading
  data-value=25`, updates to 50 after a state change; literal `60/200` and default `0/100` correct; themes progress
  the same (CMP-41 fixed).
- **accordion** (#7629): no Emotion `:first-child` warning in dev; first item keeps `margin-top:0` and the 8px
  top radius, the others `margin-top:1px`/radius 0; multiple/single/default_value/keyboard OK. Known CMP-39 React
  warning `Received true for a non-boolean attribute collapsible` still present (dev only, both versions).
- **dialog/drawer/popover** (#7645 dialog 1.3.1): focus trapped (7 Tabs stay inside), nested dialog opens on top,
  Escape closes only the nested one, outer state stays open, close button/Escape update `on_open_change`; alert
  dialog, drawer (vaul + dialog 1.3.1), popover open/close clean.
- **slider** (#7645 slider 1.6.1): controlled single slider 50→53 with 3 ArrowRight (each press needs a backend
  round-trip when `value=` is controlled — pressing faster than the RTT snaps back, same as any controlled input),
  `on_change` and `on_value_commit` both 53; range slider two thumbs, ArrowLeft on thumb 1 → `[20,79]`, Home moves
  thumb 0 to min (`[0,79]`, Radix semantics), mouse click on track works.
- **rform** (#7645 form 0.3.0): `valueMissing`, `typeMismatch`, `rangeUnderflow` messages show and block submit;
  valid submit reaches state `{"email": "a@b.co", "age": "21", ...}`, `reset_on_submit` clears.
- **moment** (#7591 + CMP-11): un-localed siblings stay English next to `locale="fr"` (dev AND prod), explicit
  `locale="en"` builds and renders in prod; provider: `locale="fr"` + `format` + `timezone="Europe/Paris"` →
  `14 mars 2024`, child `locale="en"` overrides → `14 Mar 2024`, child `format="YYYY"` overrides, `prov-tz`
  `2024-03-15 00:30`, a sibling outside the provider stays `14 Mar 2024`; provider `locale=State.var` switches
  de→es→en live (`Donnerstag`/`jueves`/`Thursday`) while plain siblings stay English and a child `locale="fr"` wins;
  `pool=True interval=1000` clocks tick in sync; `utc` (`23:30` vs local `19:30` in America/New_York), `calendar`
  (`03/14/2024`), `from_` (`in 4 days`), `from_`+`ago` (`4 days`), `to` (`in 6 days`), `from_now`+`ago` (`7 years`),
  `element="span"` (renders `<span>`, default `<time>`), `fallback` (`INVALID` for an invalid date), `filters`
  (`MARCH`), `renderers` (`({datetime}) => ...` → `R:2024`), `on_change` fires with the formatted value.
  Observation: a provider `format` takes precedence over a child's `from_now` (react-moment output precedence) —
  `rx.moment(..., from_now=True)` inside `rx.moment_provider(format=...)` renders the formatted date (`1 janv. 2020`).
- **de** (#7607 + CMP-31): 4 editors render (state dict columns without `type`, `list[str]` title columns, literal
  image columns, sliced `State.rows_[1:]`), no `column.type is undefined` console line, no page error; editing a text
  cell (click + Enter + type + Enter) and a number cell (double-click) fire `on_cell_edited` and update the row;
  `on_row_appended`/add-row → `nrows=4`; adding an untyped column from state re-renders without error; **CMP-31: in
  prod with the default badge (`badge: True`) `#portal` is in the DOM and the image overlay opens (`1 of 2`
  carousel, 4 `<img>`)**; Escape closes it (CMP-48 not reproduced with this sequence).
- **icons** (#7604): static icons in button / input slot / badge / callout; `rx.icon(State.name)` switches
  apple→banana→wifi_off (paths identical to static reference icons); `foreach` icons; `color=rx.color_mode_cond`
  and `on_click=rx.toggle_color_mode` on an icon work (red→blue); `size=State.size` updates; an icon whose `size`
  prop needs an import from the same library (`icons as lucideIcons` from `lucide-react`) renders with no
  `ReferenceError`, static and dynamic (0.10.0 dropped that import — see prev run). Dev note: after a hot reload
  that adds new icon modules, Vite re-optimizes deps (`504 Outdated Optimize Dep`, route-module reload, CMP-44's
  "script tag while rendering" error) once — dev-server behaviour, not a framework error.
- **code** (#7437): `use_transformers=True` block has `.line.highlighted` (styled), `.diff.add`, `.diff.remove`,
  the `[!code ...]` notations stripped; the plain block keeps the notation text and has no `.highlighted`;
  line numbers + copy button; react-syntax-highlighter 16.1.2 python/js/light theme render tokens; markdown fences.
- **radix single copy**: `.web/node_modules` top-level `@radix-ui/react-{accordion 1.3.1, dialog 1.3.1, form 0.3.0,
  progress 1.2.1, slider 1.6.1}` equal the versions pinned by `radix-ui@1.8.1` (dependency of `@radix-ui/themes@3.3.0`);
  0 nested `@radix-ui/*` copies anywhere under `node_modules`.

### C. Typing (pyright 1.1.414, ty 0.0.91; `results/typing_*`, `logs/typing_run_whl.log`, `logs/typing_probes_whl.log`)

Modules: `typing/typing_user.py` (realistic app module), `typing/typing_new_api.py` (0.10.1a1-only APIs),
`typing/fd_probe*.py`. new = `envs/components_typing-new-whl` (wheels), prev = `envs/components_typing-prev`.

Fixed on 0.10.1a1 (error on 0.10.0, clean on 0.10.1a1, both checkers unless noted):
- #7419 `State.handle_upload(rx.upload_files(upload_id=...))` and `handle_chunks(rx.upload_files_chunk(...))`
  (prev: pyright `reportArgumentType` ×4, ty `no-matching-overload` ×4).
- #7403 `LiteralObjectVar.create(Point(1, 2))` (prev: `Point` not assignable to `Mapping`).
- #7401 `EventCallback[str] | None` stored in a dataclass field reads back as the callback; `rx.button(on_click=entry.on_select)` accepted; a state-instance read is `Callable[[str], Any]` (prev: `((str) -> Unknown) | None`).
- #7402 `EventType[()]` accepts `list[EventSpec]` and `tuple[EventCallback[()], ...]`.
- #7406 (ty) `rx.session()`→`Session`, `rx.asession()`→`AsyncSession`, `ModelRegistry.get_metadata/register`, `get_engine()`, `sqla_session()`; `class User(rx.Model, table=True)` no longer `unsupported-base` (prev: all unioned with `_ClassThatErrorsOnInit | Unknown`).
- #7413 (ty) `rx.Field[Point | None]` (dataclass) and `rx.Field[Filters | None]` (TypedDict) → `ObjectVar[Point]`/`ObjectVar[Filters]` (prev `ObjectVar[Point | None]`); pyright unchanged (`ObjectVar[X]`).
- `rx.form.FormData[str, str]` as a handler annotation and as a variable annotation: clean under pyright and ty; `rx.form(...)`→`Form`, `rx.form.root(...)`→`FormRoot`, `rx.form.field(...)`→`FormField` — same as 0.10.0.
- `rx.moment_provider(...)`, the new moment props, `rx.input(auto_complete="off")`, `checkbox_group/cards` props: clean.

Not fixed / observations (identical on 0.10.0 unless noted — none is a regression):
- ty: `rx.Field[User | None]` and `rx.Field[User]` for an `rx.Model` (sqlmodel) subclass read as `Var[User | None]` / `Var[User]`, so `State.user.name` is `unresolved-attribute` under ty (0.10.0: `ArrayVar[User]`, worse). pyright: `ObjectVar[User]`. #7413's test covers a SQLAlchemy `DeclarativeBase` model, not `rx.Model`.
- ty: `on_x: rx.EventHandler[rx.event.no_args_event_spec]` in a custom component → `invalid-type-form: Non-generic class EventHandler cannot be specialized` (both versions; pyright accepts).
- `rx.input(auto_complete=True)` is rejected by both checkers (`Var[str] | str | None`), although the runtime maps it to `"on"` (the PR says the stub deliberately steers to strings; 0.10.0's stub already said `str`).
- `rx.data_editor(columns=["A", "B"])` and `columns=State.titles` (`list[str]`) are rejected by both checkers (`Sequence[dict[str, Any]]`), although #7607 documents title strings and the runtime accepts them.
- `VarData(position=...)` / `Hooks.HookPosition` deprecation is runtime-only: pyright with `reportDeprecated=true` and ty report nothing (no `@deprecated` overload in the stub).
- A plain annotation `plain_user: User | None = None` reads as `User | None` on the class (needs `rx.Field[...]`), as on 0.10.0.
