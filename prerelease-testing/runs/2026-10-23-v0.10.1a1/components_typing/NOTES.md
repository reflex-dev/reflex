# components_typing — reflex 0.10.1a1 (2026-10-24)

Item: radix (#7345 #7593 #7418 #7438 #7629 #7645), moment (#7591), data_editor (#7607), lucide (#7604),
code (#7437), typing (#7406 #7413 #7419 #7403 #7401, `rx.form.FormData`, `VarData(position=)`), CMP-11, CMP-31.
Status: COMPLETE (2026-10-24). All servers stopped, `.web`/`node_modules` deleted; structured report in the final message.

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

### D. ISSUE CT-3 — a wheel built from the 0.10.1a1 sdists ships regenerated, incomplete stubs

Observed first by accident: `uv --no-config pip install --prerelease=allow 'reflex[db]==0.10.1a1' pyright ty`
(cwd `$SB`, no `--only-binary`) produced a venv whose reflex packages all carry `uv_build.json` (built from sdist)
although uv's own log says `Selecting: reflex-components-radix==0.10.1a1 [compatible] (...py3-none-any.whl)` and then
`Registry requirement already cached` — uv reused sdist builds another agent had cached at 01:51
(`/root/.cache/uv/sdists-v9/pypi/reflex-components-{radix,core,dataeditor,...}/0.10.1a1/`). Four venvs of this campaign
are affected (`components_typing-new`, `-repro`, `-sdist`, and `enterprise-ctrl-a2` with 2 sdist-built dist-infos).
`.py` files are byte-identical to the wheels (`diff -rq`), only `.pyi` differ.

Compared with the PyPI wheels (`envs/new`, 122 stubs): the sdist-built install has 116 stubs — MISSING
`reflex_components_radix/primitives/form.pyi`, `reflex_components_dataeditor/dataeditor.pyi`,
`reflex_components_core/{base/error_boundary,core/banner,core/upload,el/elements/forms}.pyi` — and 100+ other stubs
differ in content (e.g. `accordion.pyi`: `TypeAlias` annotations, multi-line imports: a different generator version).

Mechanism (reproduced three ways, `sdists/gen_{full,hook,old}/gen.log`):
1. `hatch-reflex-pyi` (0.10.0, `plugin.py`) deletes every `.pyi` under `src/` and re-runs
   `python -m reflex_base.utils.pyi_generator` whenever `reflex_base` is importable in the build env — and it
   always is, because the hook declares `dependencies = ["ruff", "reflex-base", "reflex-components-core", ...]`
   (unpinned). The stubs shipped inside the sdist are never used.
2. In an isolated build env those unpinned hook dependencies resolve to the latest **stable** release: pip's log
   shows `Collecting reflex-base / Using cached reflex_base-0.10.0.tar.gz` while building
   `reflex-components-radix==0.10.1a1` (`logs/build_pipsdist.log`); uv without `--prerelease=allow` does the same.
3. The 0.10.0 generator cannot import modules that use 0.10.1 base APIs and drops them silently
   (`sdists/gen_old/gen.log`: `ERROR:pyi_generator:Failed to import reflex_components_radix.primitives.form —
   ModuleNotFoundError: No module named 'reflex_base.utils.form'`; exit code 0; 64 stubs instead of 65) and
   reformats the rest (`accordion.pyi` from that run is byte-identical to the sdist-built install's).
   With reflex-base 0.10.1a1 in the env (`gen_full`, `gen_hook`) all 65 stubs are generated.

Repro for a stranger (no uv cache involved):
```
uv venv --python 3.12 /tmp/v && /tmp/v/bin/python -m pip install --no-cache-dir --no-binary :all: --no-deps 'reflex-components-radix==0.10.1a1'
ls /tmp/v/lib/python3.12/site-packages/reflex_components_radix/primitives/form.pyi   # missing
```
(`pip install reflex-components-radix==0.10.1a1` with wheels: present.) Effect for users: any sdist install of
the pre-release (e.g. `--no-binary`, a wheel-less index mirror, or a uv cache primed by one) type-checks against
stubs that lack `rx.form.FormData`, `rx.form(...)`, `rx.data_editor(...)`, `rx.upload(...)`, `rx.el.form(...)`
signatures (pyright then falls back to the `.py` source: `rx.form.FormData[str, str]` becomes
`reportInvalidTypeForm`, `rx.form(...)` types as `RadixPrimitiveComponentWithClassName`). The orchestrator's
preflight ".pyi audit: wheel == sdist" compares archive contents and cannot see this, because the mismatch is
produced at build time. For a stable release the hook deps would resolve to the new stable only if `reflex-base`
is published before the component packages are built by users; nothing pins them to the sibling floor
(`reflex-base>=0.10.1.dev0` is only a runtime dependency).

### E. 0.10.0 baseline (`results/drive_dev_prev.json`, `logs/drive_dev_prev.log`, `logs/dev_prev.log`; `prevapp` = the
same app with the `NEW=False` branches, `EXPECT_VENV=components_typing-prev`, dev on 3242/8242)

68/97 checks pass; every failure is the pre-fix behaviour the 0.10.1a1 changelog describes (positive controls):
- `/radio_aschild` never renders: `Error: Primitive.div failed to slot onto its children. Expected a single React
  element child or Slottable` (#7593 — `asChild` reached Radix). 0.10.1a1: renders, no error.
- `/input`: `auto_complete=True/False/BoolVar` → no `autocomplete` attribute at all plus React's "Received `true`
  for a non-boolean attribute" (#7418). 0.10.1a1: `on`/`off`.
- `/progress`: primitive root `aria-valuenow=None data-state=indeterminate` (CMP-41 / #7438). 0.10.1a1: real values.
- `/accordion`: 3× Emotion `The pseudo class ":first-child" is potentially unsafe when doing server-side rendering`
  (CMP-13 / #7629). 0.10.1a1: none.
- `/de` never renders: `TypeError: Cannot read properties of undefined (reading 'includes') at truncateString
  (@glideapps/glide-data-grid)` — a state-backed column without `type` (#7607). 0.10.1a1: renders, editable.
- `/icons` never renders: `ReferenceError: lucideIcons is not defined` — the same-library prop import dropped by
  the old `_get_imports` override (#7604). 0.10.1a1: renders.
- `/code`: `use_transformers=True` block has no `.highlighted`/`.diff` lines, notation text left in place (CMP-29 /
  #7437). 0.10.1a1: transformed.
- `/moment`, `/dialog`, `/slider`, `/rform`, `/radio`: identical to 0.10.1a1 (CMP-11 was already fixed in 0.9.4;
  dialog/slider/form behaviour unchanged across the primitive bumps).
- `/cbg` dict-handler submit on 0.10.0: `{"grp": "a", "dgrp": "d2", "cg": "a", "cg_default": "d2"}` — no entry for
  the `id="cc"` cards root with nothing checked; 0.10.1a1 (`FormData` handler) emits `"cc": [null]` for it
  (`drive_prod_new_cbg2.json`), and `"cg": [null]` once the group is emptied (`drive_dev_new_cbg_final.json`).
  The id-based path is deprecated by #7386 (events_state covers the deprecation warnings); recorded as an observation.

### F. Re-verification

- **CMP-11** (moment locale isolation): fixed, still fixed — dev and prod, `#plain`/`#plain2`/`#english`
  `Thursday 14 March 2024` next to `#french` `jeudi 14 mars 2024`; `from_now` sibling `7 years ago`; explicit
  `locale="en"` compiles in prod (no `moment/locale/en` import); a provider `locale=State.var` switch leaves plain
  siblings English. Also holds on 0.10.0 (control: fixed since 0.9.4; the 0.9.11a1 leak is not re-creatable here).
- **CMP-31** (prod badge swallows `#portal`): fixed, still fixed — prod with the default badge (`badge: True` in the
  DOM), `#portal` present, data_editor image overlay opens with the carousel (`1 of 2`, 4 `<img>`),
  `shots/prod_new_de_overlay.png`.
- CMP-41 (primitive progress ARIA): fixed by #7438 (control: 0.10.0 indeterminate).
- CMP-13 (accordion Emotion `:first-child` SSR warning): fixed by #7629 (control: 0.10.0 logs it 3×).
- CMP-29 (`use_transformers=True` empty list): fixed by #7437 (control: 0.10.0 renders nothing transformed).
- CMP-15 (unsupported moment props silently CSS): fixed for the react-moment 2.x options #7591 exposes; unknown
  props (`filter`, `settings`, `form_at`) still become CSS silently — the PR text's "actionable errors" are not in
  the published package (compile probe `moment_bad_*`). Unchanged behaviour, low.
- CMP-14 (duplicate `defineLocale` warnings): 1 warning per page load with a literal locale import — unchanged.
- CMP-39 (`collapsible=True` React warning): unchanged (dev only).
- CMP-48 (overlay stays open on Escape): not reproduced with click → Enter → Escape (overlay closes, 0 imgs left).
- CMP-44 (React 19.3 "script tag while rendering" error on a failed route-module load): seen once in dev right
  after a hot reload forced a Vite dep re-optimisation (`504 Outdated Optimize Dep`), unchanged context.

### G. Issues and observations (details above)

1. **CT-3 (medium, not a regression of runtime behaviour; packaging)** — wheels built from the 0.10.1a1 sdists carry
   stubs regenerated by whatever `reflex-base` the isolated build env resolves (the stable 0.10.0 for a pre-release);
   6 stubs are silently dropped (radix `primitives/form.pyi`, `dataeditor.pyi`, core `error_boundary/banner/upload/
   el/elements/forms.pyi`) and the rest differ from the wheel. Section D; repro `pip install --no-cache-dir
   --no-binary reflex-components-radix --no-deps reflex-components-radix==0.10.1a1` → 64 stubs, no `form.pyi`
   (`logs/build_pipsdist2.log`: pip's isolated build env resolved the hook deps to `reflex_base-0.10.0`, `reflex_components_core-0.10.0`, `reflex_components_lucide-1.1.0`, `reflex_components_sonner-0.10.0`). Campaign note: uv on this
   machine reused those sdist builds for later installs ("Registry requirement already cached") — 4 venvs affected,
   including `enterprise-ctrl-a2`.
2. **CT-1 (low)** `rx.radio_cards.root(as_child=True)` / `.item(as_child=True)`: the removed prop is now accepted
   silently and emitted as a CSS property `asChild: true` (compile probe `rc_aschild`); no deprecation or error.
   0.10.0 forwarded it and crashed. Not a regression; a `console.warn`/error for a removed prop would help migration.
3. **CT-2 (low)** `rx.moment(filter=...)` / `settings=` / `form_at=`: still silently CSS, contrary to the #7591 PR
   description ("actionable errors for the removed filter prop and the reported settings/form_at inputs").
4. **CT-4 (low, docs)** a provider `format` overrides a child's `from_now`/`to_now` (react-moment output
   precedence `format > from > fromNow > ...`), so `rx.moment_provider(format=...)` children cannot show relative
   times; the docs say "a prop set on a component overrides the provider", which is true only for the same prop.
5. **CT-5 (low, typing)** on the wheels: (a) ty types `rx.Field[rx.Model-subclass | None]` as `Var[Model | None]`
   (pyright: `ObjectVar[Model]`), so `State.user.name` is an error under ty — #7413 covers DeclarativeBase models,
   dataclasses and mappings, not `rx.Model`; 0.10.0 gave `ArrayVar[Model]` (worse, so an improvement, not a
   regression). (b) `rx.input(auto_complete=True)` and `rx.data_editor(columns=["A", "B"])` / `columns=State.titles`
   are rejected by pyright and ty although the runtime and the 0.10.1a1 changelog accept them (same on 0.10.0).
   (c) `VarData(position=...)` / `Hooks.HookPosition` deprecation is invisible to type checkers (`reportDeprecated`
   shows nothing); runtime warns. (d) ty rejects `rx.EventHandler[spec]` in custom components (`Non-generic class
   EventHandler cannot be specialized`), both versions.
6. **CT-6 (low, forms; events_state domain)** with a `FormData` handler, an `id=` on a checkbox group/cards root
   with nothing checked contributes `"<id>": [null]` to the submitted data (0.10.0 dict handler: key absent).

No regression found in the component behaviour covered by this item: every targeted fix reproduces as broken on
0.10.0 and works on 0.10.1a1 in dev and prod; dialogs, sliders, radix form validation, accordion, progress, moment,
data_editor, lucide and code blocks behave the same or better than on 0.10.0.
