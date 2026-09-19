# Cluster `memo_aschild` — reflex 0.9.12a1 pre-release QA

Exercises: transparent auto-memo wrappers under `as_child` (#6850), `@rx.memo` app-wrap
collection (#7176), `rx.el.svg` single-memo render scope (#6708), shared event chains (#7122),
compile fast paths (#7121), `rx.form.message` `force_match` (#7133), error-boundary SVG icon
(#7130).

Everything below was run against **packages published to PyPI** — never the checkout.

## Resolved environment

```
$ uv pip freeze --python $SB/envs/shared/bin/python | grep -i reflex
reflex==0.9.12a1
reflex-base==0.9.12a1
reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1
reflex-hosting-cli==0.1.72
```

Baseline venv: `reflex==0.9.11.post1` with the matching stable component packages
(`$SB/envs/prev`).

### Recreate the venvs from scratch

```bash
SB=/tmp/qa            # any neutral dir; NEVER /home/user/reflex
cd $SB
uv venv $SB/envs/shared --python 3.11
uv pip install --python $SB/envs/shared/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
  'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
  'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
  'reflex-components-sonner==0.9.4a1'
uv venv $SB/envs/prev --python 3.11
uv pip install --python $SB/envs/prev/bin/python 'reflex==0.9.11.post1'
# playwright driver
uv venv $SB/envs/driver --python 3.11 && uv pip install --python $SB/envs/driver/bin/python playwright
```

## App

`memoaschild/` is a single reflex app with seven pages, one per change under test:

| route | covers |
|---|---|
| `/forms` | #6850 Slot prop/ref/class/style injection into memoized inputs, #7133 `force_match` |
| `/triggers` | radix `dialog`/`popover`/`tooltip`/`dropdown_menu`/`hover_card` triggers around stateful buttons, plus `rx.foreach` and `rx.ComponentState` variants |
| `/memoapp` | #7176 `@rx.memo` bodies needing app wraps: `rx.upload` (plain / nested memo / `ComponentState`), toaster provider, `rx.color_mode_cond`, memo under `rx.foreach` |
| `/svg` | #6708 `rx.el.svg` + `defs`/`linearGradient` at top level, under `rx.foreach`, inside `@rx.memo`, with a State-driven `stop_color` |
| `/chains` | #7122 100 bare-handler buttons + 100 arg-bearing buttons + `stop_propagation`/`prevent_default`/`throttle`/`debounce` + one element binding the same handler to `on_click` and `on_mouse_enter` |
| `/boom` | #7130 default error-boundary fallback (crash gated behind `QA_BOOM=1`, see below) |

## Exact rerun commands

```bash
SB=/tmp/qa   # wherever you put the venvs
cd <this dir>/memoaschild

# dev, reflex 0.9.12a1
REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex run \
    --frontend-port 3140 --backend-port 8140 --loglevel debug | tee dev_server.log

# drive it (separate shell)
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python ../scripts/drive.py http://localhost:3140 ../shots/dev

# prod, reflex 0.9.12a1 (ONE port for both flags)
REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex run --env prod \
    --frontend-port 3142 --backend-port 3142
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python ../scripts/drive.py http://localhost:3142 ../shots/prod

# baseline 0.9.11.post1 — copy the app to a fresh dir first so .web is not shared
REFLEX_TELEMETRY_ENABLED=false $SB/envs/prev/bin/reflex run \
    --frontend-port 3141 --backend-port 8141
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python ../scripts/drive.py http://localhost:3141 ../shots/prev

# focused probes
$SB/envs/driver/bin/python ../scripts/probe.py      http://localhost:3140 ../shots/dev
$SB/envs/driver/bin/python ../scripts/focus_probe.py http://localhost:3140
$SB/envs/driver/bin/python ../scripts/boom_probe.py  http://localhost:3141 ../shots/prev

# compile-time comparison (~500-component page, python compile only, no bundler)
cd perf/perfapp      && $SB/envs/shared/bin/python ../time_compile.py
cd perf/perfapp_prev/perfapp && $SB/envs/prev/bin/python ../../time_compile.py
```

`QA_BOOM=1` makes `/boom` render a component that throws (see the caveat below); without it the
page renders a placeholder so `reflex run --env prod` can prerender the site.

## What was verified (0.9.12a1 vs 0.9.11.post1)

### #6850 — Slot props reach auto-memoized components — FIXED, verified

`rx.form.control(rx.input(value=State.x, on_change=..., id="inp_name",
class_name="own-class", style={"border": "2px solid teal"}), as_child=True)`

| observation | 0.9.11.post1 | 0.9.12a1 |
|---|---|---|
| `input#inp_name` `name` attribute | absent | `full_name` (Slot-injected) |
| `aria-describedby` | absent | `radix-_r_1_ radix-_r_2_` |
| className on the TextField root | `rt-TextFieldRoot … ` | `rt-TextFieldRoot … Control own-class css-…` (radix `Control` **concatenated with** the own class) |
| own `style` (2px teal border) | lost | applied (`borderTopWidth: 2px`, `rgb(0,128,128)`) |
| `on_submit` payload | `full_name`/`controlled`/`nickname` **missing** | all three present |
| `rx.set_focus("inp_name")` | n/a | focuses the real `<input>` → `refs['ref_inp_name']` survives ref composition |

Raw attribute dumps: `logs/dev_drive_report.json` / `logs/prev_drive.log` (`INP_NAME_ATTRS=`),
ancestry dump in `logs/probe_dev.log` (`ANCESTRY=`).

Note for anyone re-testing: `class_name`/`style` on `rx.input` land on the **TextFieldRoot
`<div>`**, not on the inner `<input>` — check the parent element, not the input.

Also verified working under the Slot: `rx._x.client_state`-bound input, a fully-controlled
(`debounce_input`) input, and a user `@rx.memo`-wrapped input inside the same form.

### #7176 — `@rx.memo` bodies keep their app wraps — FIXED, verified

- 0.9.11.post1: `/memoapp` **crashes the whole page** — `TypeError: useContext is not a function
  or its return value is not iterable at MemoUpload`, zero `input[type=file]` in the DOM
  (`logs/prev_boom_probe.log`, `shots/prev/memoapp.png`). Worse than "silently does nothing".
- 0.9.12a1: all three uploads (plain memo, memo-inside-memo, memo inside a `ComponentState`)
  render, `rx.selected_files(...)` populates on `set_input_files`, and `rx.upload_files()`
  delivers the bytes to the handler (`out_files` shows `sample_upload.txt:69` three times).
  Toaster provider works from inside a memo; `rx.color_mode_cond` inside a memo flips
  LIGHT→DARK; a memo under `rx.foreach` works per row.

### #6708 — `rx.el.svg` single memo scope — verified (no regression either way)

`Svg` gained `_memoization_mode = MemoizationMode(recursive=False)` in
`reflex_components_core/el/elements/media.py`. In both versions the gradient `defs` ends up in
the same `<svg>` as the referencing `rect`, and a State-driven `stop_color` updates live inside
the memo scope. Verified at top level, inside `rx.foreach` (5 gradients / 5 defs), and inside
`@rx.memo`; dev and prod. Screenshots `shots/dev/svg_before.png`, `shots/dev/svg_after.png`.

### #7122 — shared event chains — verified

200 buttons on `/chains`: first and last bare-handler call site both dispatch; `bump_by(7)` and
`bump_by(42)` each carry their own argument with no leakage; `stop_propagation`,
`prevent_default`, `throttle(500)` (5 rapid clicks → 1 event) and `debounce(300)` (5 → 1) all
behave; one element with the same handler on `on_click` **and** `on_mouse_enter` fires both.

Compiled output note: each call site still gets its own memo component because each button has a
distinct `id` (209 `Button` memo components, 105 bodies referencing `bump`, 100 referencing
`bump_by`). The sharing in #7122 is compile-side chain identity, not JS-side component dedupe.

### #7121 — compile fast paths — perf claim holds

`app._compile(dry_run=True)` on a ~500-component page, 4 reps each, same machine, back to back:

| version | reps (s) | median |
|---|---|---|
| 0.9.11.post1 | 0.639 / 0.552 / 0.607 / 0.558 | **0.582 s** |
| 0.9.12a1 | 0.576 / 0.470 / 0.513 / 0.472 | **0.493 s** |

≈15% faster python-side compile. Harness: `perf/time_compile.py`, app `perf/perfapp/`.

### #7133 — `form.message` `force_match` — FIXED, verified

Compile-level (`scripts/render_check.py`, plus a 3-liner):

```
0.9.11.post1: rx.form.message("Required", force_match=True)
              -> jsx(RadixFormMessage,{className:"Message ",forceMatch:true},"Required")
0.9.12a1:     -> jsx(RadixFormMessage,{className:"Message "},"Required")
both:         with match="valueMissing", forceMatch is still emitted
```

DOM check on `/forms`: zero elements carrying a `forcematch` attribute in 0.9.12a1.

### #7130 — error-boundary fallback SVG — FIXED, verified

With `QA_BOOM=1`, loading `/boom` throws at render and the default fallback renders.

- 0.9.11.post1 browser console: 3 errors —
  ``Invalid DOM property `stroke-linecap`. Did you mean `strokeLinecap`?`` and the same for
  `stroke-linejoin` and `stroke-width` (`logs/prev_boom_probe.log`).
- 0.9.12a1: **0** such messages; only the expected app `ReferenceError` from the crashing
  component itself.

## Observations / benign quirks (not bugs in this release)

1. **`rx.dropdown_menu.trigger` swallows the child button's `on_click`.** The overlay opens but
   `TrigState.bump("dropdown")` never runs. `dialog`, `popover`, `tooltip` and `hover_card`
   triggers all run the child handler. **Identical on 0.9.11.post1**, so it is pre-existing Radix
   `DropdownMenu.Trigger` behaviour (it opens on `pointerdown` and the menu's
   `disableOutsidePointerEvents` layer eats the subsequent `click`), not a 0.9.12a1 regression.
   Repro: `/triggers`, click `#t_dropdown`, watch `#out_clicks`.
2. **`rx.cond` evaluates both branches eagerly.** The compiled page passes both rendered
   branches as children of a `Cond_comp_*` memo, so a component that throws in the *false*
   branch still crashes the page at first render — and, in prod, fails the React-Router
   prerender step so `reflex run --env prod` exits 1 with
   `Prerender: Request failed for /boom/`. Same in both versions; this is why the crash is gated
   behind `QA_BOOM=1`. Worth knowing: a render-time exception anywhere in an app is a hard
   production **build** failure, the error boundary only covers the client.
3. **`on_submit` form data contains id-keyed duplicates.** Submitting `/forms` yields both the
   `name`-keyed entries and one entry per element `id`, plus odd ones:
   `"the_form":"banana"` (the `<form>`'s own id picking up the select value),
   `"field_full_name":"None"`, `"btn_submit":"None"`, `"inp_fruit":"None"`. Identical on
   0.9.11.post1 — pre-existing, low severity, but noisy for anyone typing `form_data`.
4. Startup warnings seen on every run of this app (all pre-existing / by design):
   `SitemapPlugin is enabled by default but not explicitly added`,
   `rx._x contains experimental features`, `Implicit Radix Themes enablement has been
   deprecated`, and `Event handler on_change expects (list[float]) -> () but got (list[int])`
   for `rx.slider` bound to `list[int]` (the slider's declared type is `list[float]`).
5. `@rx.memo` without `rx.Var[...]` annotations logs the 0.9.3 deprecation notice; annotating
   the parameters silences it.

## Files here

```
memoaschild/            the reflex app (no .web/, no node_modules/)
scripts/drive.py        full end-to-end Playwright driver (console/network/pageerror capture)
scripts/probe.py        DOM-ancestry probe for the Slot class/style merge + dropdown trigger
scripts/focus_probe.py  rx.set_focus through a Slot-composed ref
scripts/boom_probe.py   error-boundary console capture (used for the 0.9.11 baseline)
scripts/render_check.py compile-level form.message force_match check (no server needed)
perf/                   ~500-component app + time_compile.py
logs/                   trimmed server + driver logs, driver report.json
shots/{dev,prev,prod}/  screenshots
```
