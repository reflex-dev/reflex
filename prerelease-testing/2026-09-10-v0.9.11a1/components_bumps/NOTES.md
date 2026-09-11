# Cluster `components_bumps` — reflex 0.9.11a1 pre-release testing

Component-library version bumps shipped by this train, exercised end to end in a real browser:

| package | this train | previous stable | frontend pin |
|---|---|---|---|
| reflex-components-moment | 0.9.4a1 | 0.9.3 | `react-moment` 1.2.2 → **2.0.2** (+ `moment-duration-format@2.2.2`, `moment-timezone` 0.6.3) |
| reflex-components-code | 0.9.5a1 | 0.9.4 | `shiki` / `@shikijs/transformers` 4.3.1 → **4.4.3** |
| reflex-components-plotly | 0.9.6a1 | 0.9.5 | `react-plotly.js` 4.0.0 → **4.1.0** (plotly.js 3.7.0 unchanged) |
| reflex-components-radix | 0.9.9a1 | 0.9.8 | accordion 1.2.18 → **1.2.20**, dialog 1.1.21 → **1.1.23**, form 0.1.14 → **0.1.16** |
| reflex-components-recharts | 0.9.3a1 | 0.9.2 | `recharts` 3.8.1 → **3.10.1** |
| reflex-components-sonner | 0.9.3a1 | 0.9.2 | `sonner` 2.0.7 → **2.0.8** |

Everything below was installed from PyPI only (never from the checkout), run with `reflex run`
in **dev and prod**, and driven in headless Chromium (Playwright) with console / page-error /
failed-request / 4xx-5xx capture on every run.

**Headline:** one regression — a `locale=` on a single `rx.moment` now changes the language of
*every* `rx.moment` on the page (react-moment 2.0.2). Minimal repro included, bisected to the
`reflex-components-moment` bump alone. Everything else in the six bumped libraries behaved the
same as, or better than, the previous stable.

## Environments

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad

# alpha train (the one under test)
cd $SB   # NEVER /home/user/reflex — its exclude-newer hides the alphas
uv venv $SB/envs/compbumps --python 3.11
uv pip install --python $SB/envs/compbumps/bin/python --prerelease=allow \
  'reflex==0.9.11a1' 'reflex-components-code==0.9.5a1' 'reflex-components-plotly==0.9.6a1' \
  'reflex-components-radix==0.9.9a1' 'reflex-components-recharts==0.9.3a1' \
  'reflex-components-sonner==0.9.3a1' 'reflex-components-moment==0.9.4a1' plotly

# baseline: previous stable + plotly (the shared $SB/envs/base0910 has no plotly)
uv venv $SB/envs/base0910p --python 3.11
uv pip install --python $SB/envs/base0910p/bin/python 'reflex==0.9.10.post2' plotly
#   -> reflex-components-{moment 0.9.3, code 0.9.4, plotly 0.9.5, radix 0.9.8,
#      recharts 0.9.2, sonner 0.9.2}

# bisect env: alpha core, previous stable moment wrapper
uv venv $SB/envs/alpha_oldmoment --python 3.11
uv pip install --python $SB/envs/alpha_oldmoment/bin/python --prerelease=allow \
  'reflex==0.9.11a1' 'reflex-components-moment==0.9.3' plotly
```

Ports used (reserved range): frontend 5220–5227, backend 9620–9627. Prod runs use the same
port for frontend and backend.

## Apps in this directory

- `cbapp/` — the main six-page app (`/moment`, `/code`, `/plotly`, `/recharts`, `/toast`, `/radix`).
- `cbapp_base/` — byte-identical copy of `cbapp` with two edits so it compiles on
  reflex-components-moment 0.9.3: `trim="large"` → `trim=True`, `parse=["DD/MM/YYYY", …]` →
  `parse="DD/MM/YYYY"` (the list/str widening is new in 0.9.4a1). Used for every baseline run.
- `leakapp2/` — **minimal repro** of the locale regression: three `rx.moment`s, one with
  `locale="fr"`.
- `leakapp/` — larger locale probe (memo component, `Var` locale, tz probe) that does *not*
  reproduce; kept because it shows the bleed depends on which `moment/locale/*` side-effect
  import runs last.
- `scripts/` — the Playwright drivers and probes (run with `$SB/envs/driver/bin/python`).
- `results/` — one JSON per page per run: `out_dev` (alpha dev), `out_prod` (alpha prod),
  `out_base` (0.9.10.post2 dev), `out_base_prod` (0.9.10.post2 prod), `out_mixed`
  (alpha core + moment 0.9.3), plus repeat runs `out_prod2`, `out_base2`.
  Each JSON has `results`, `console`, `page_errors`, `failed_requests`, `bad_responses`.
- `shots/` — full-page screenshots, prefixed with the run they came from.
- `logs/` — trimmed server logs.

## Exact rerun commands

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
APPS=$SB/apps/components_bumps          # copy this directory's app dirs there
DRV="NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"

# 1. alpha, dev
cd $APPS/cbapp && REFLEX_TELEMETRY_ENABLED=false setsid nohup \
  $SB/envs/compbumps/bin/reflex run --frontend-port 5220 --backend-port 9620 \
  > $APPS/logs/dev_run.log 2>&1 < /dev/null & disown
# wait for "App running at", then:
cd $APPS && eval $DRV drive_all.py http://localhost:5220 $APPS/out_dev
#   (no page argument = all six pages; or pass e.g. `moment code`)

# 2. alpha, prod (ONE port for both)
cd $APPS/cbapp && REFLEX_TELEMETRY_ENABLED=false setsid nohup \
  $SB/envs/compbumps/bin/reflex run --env prod --frontend-port 5221 --backend-port 5221 \
  > $APPS/logs/prod_run.log 2>&1 < /dev/null & disown
cd $APPS && eval $DRV drive_all.py http://localhost:5221 $APPS/out_prod

# 3. baseline 0.9.10.post2, dev then prod (kill the alpha server first)
cd $APPS/cbapp_base && REFLEX_TELEMETRY_ENABLED=false setsid nohup \
  $SB/envs/base0910p/bin/reflex run --frontend-port 5222 --backend-port 9622 \
  > $APPS/logs/base_dev_run.log 2>&1 < /dev/null & disown
cd $APPS && eval $DRV drive_all.py http://localhost:5222 $APPS/out_base
cd $APPS/cbapp_base && ... reflex run --env prod --frontend-port 5224 --backend-port 5224
cd $APPS && eval $DRV drive_all.py http://localhost:5224 $APPS/out_base_prod

# 4. minimal locale repro, alpha vs baseline
cd $APPS/leakapp2 && ... $SB/envs/compbumps/bin/reflex run --frontend-port 5226 --backend-port 9626
cd $APPS && eval $DRV drive_leak2.py http://localhost:5226/ $APPS/out_dev/leak2_alpha.json
cp -r $APPS/leakapp2 $APPS/leakapp2_base   # same source, run with the baseline venv
cd $APPS/leakapp2_base && ... $SB/envs/base0910p/bin/reflex run --frontend-port 5227 --backend-port 9627
cd $APPS && eval $DRV drive_leak2.py http://localhost:5227/ $APPS/out_base/leak2_base.json

# 5. bisect: alpha core + react-moment 1.2.2
cp -r $APPS/cbapp_base $APPS/cbapp_mixed
cd $APPS/cbapp_mixed && ... $SB/envs/alpha_oldmoment/bin/reflex run --frontend-port 5225 --backend-port 9625
cd $APPS && eval $DRV drive_all.py http://localhost:5225 $APPS/out_mixed moment

# extra probes (all take a URL)
$SB/envs/compbumps/bin/python $APPS/probe_moment_props.py      # from $APPS, prints prop handling
eval $DRV probe_copy.py http://localhost:5220/code             # shiki copy button -> clipboard
eval $DRV probe_toaster.py http://localhost:5220/toast         # sonner Toaster roots
eval $DRV probe_global_locale.py http://localhost:5220/moment  # moment's global locale (dev only)
eval $DRV probe_console_loc.py http://localhost:5221/moment    # console messages with source URL
```

## Results table

| # | check | dev | prod | baseline 0.9.10.post2 | verdict |
|---|---|---|---|---|---|
| M1 | moment: static date + `format` | ok | ok | same | pass |
| M2 | moment: date from a State var (`str` and `datetime.datetime`), updated by an event | ok | ok | same | pass |
| M3 | moment: `date=` kwarg vs child date | ok | ok | same | pass |
| M4 | moment: date from `rx._x.client_state`, updated client-side | ok | ok | same | pass |
| M5 | moment: `from_now`, `to_now`, `from_now_short` | ok | ok | same | pass |
| M6 | moment: `from_now_during` above/below the threshold | ok | ok | same | pass |
| M7 | moment: `duration` + `trim="large"` (`"30 mins"`), `format="hh:mm:ss"` (`"02:03:04"`), `trim=False` | ok | ok | same output | pass — `moment-duration-format@2.2.2` really is wired up |
| M8 | moment: `duration_from_now` | ok | ok | same | pass |
| M9 | moment: `unix=True` with an int state var | ok | ok | same | pass |
| M10 | moment: `tz` for America/New_York, Asia/Tokyo, Europe/Paris + a state-driven tz | ok (EDT/JST/CET correct) | ok | same | pass |
| M11 | moment: `locale="fr"`, `locale="es"`, state-driven locale rotation | the localized components are correct | same | same | pass |
| M12 | **moment: components WITHOUT `locale` render in the locale of a sibling** | **French** | **French** | **English** | **FAIL — ISSUE-1** |
| M13 | moment: `interval=1000` live update; `interval=0` static | ok | ok | same | pass |
| M14 | moment: `add` / `subtract` with `rx.MomentDelta` | ok | ok | same | pass |
| M15 | moment: `parse` as list and as str | ok | ok | list form needs 0.9.4a1 | pass |
| M16 | moment: `with_title` + `title_format` (title attr = `2024/03/14`) | ok | ok | same | pass |
| M17 | moment: `diff` + `unit` + `decimal` (13 / 13.5) | ok | ok | same | pass |
| M18 | moment: `local=True` | ok | ok | same | pass |
| M19 | moment inside `rx.foreach` | ok | ok | same | pass |
| M20 | moment inside `@rx.memo` (re-renders on state change) | ok | ok | same | pass |
| M21 | moment inside `rx.ComponentState` (`add=` from the component state) | ok | ok | same | pass |
| M22 | moment: console clean apart from one moment deprecation warning | 1 warning | 1 warning | identical warning | anomaly — ISSUE-4 (pre-existing) |
| M23 | moment: `filter=` (dropped by react-moment 2.x), `calendar=`, `settings=` | silently become CSS | — | same | anomaly — ISSUE-5 (pre-existing, by design) |
| C1 | `rx._x.code_block` (shiki 4.4.3): python/typescript/sql/rust/bash, 5 themes | ok | ok | same | pass |
| C2 | shiki: `show_line_numbers` (CSS grid counters), `can_copy` button | ok | ok | same | pass |
| C3 | shiki: copy button writes the exact source to the clipboard | ok | — | — | pass |
| C4 | shiki: `use_transformers=True` (@shikijs/transformers 4.4.3) | ok | ok | same | pass |
| C5 | shiki: code + theme bound to State vars, changed by events | ok (bg 36,41,46 → 40,44,52) | ok | same | pass |
| C6 | shiki: 400-line block (2400 highlighted spans) inside a scroll box | ok | ok | same | pass |
| C7 | `rx.code_block` (react-syntax-highlighter, NOT bumped) + state-bound code | ok | ok | same | pass |
| C8 | `rx.markdown` with two fenced blocks | ok | ok | same | pass |
| C9 | code page: hydration / console warnings | none | none | none | pass |
| P1 | plotly: figure from a `go.Figure` State var, replaced by an event | ok | ok | same | pass |
| P2 | plotly: `layout` prop from a State var, changed by an event (`paper_bgcolor` → `#fee`) | ok | ok | same | pass |
| P3 | plotly: `layout={"title": "…"}` as a **string** renders no title | placeholder title | same | same | anomaly — ISSUE-6 (plotly.js 3.x, pre-existing) |
| P4 | plotly: `on_click` / `on_hover` payloads (`extractPoints`) | ok | ok | same | pass |
| P5 | plotly: `on_selected` (box drag) + `on_deselect` (double click) | ok | ok | same | pass |
| P6 | plotly: `config` (`displaylogo: False` → no logo, modebar present) | ok | ok | same | pass |
| P7 | plotly: `use_resize_handler=True` (748.8 → 400.8 → 748.8 px on viewport change) | ok | ok | same | pass |
| P8 | plotly: 4 plots on one page, all interactive | ok | ok | same | pass |
| P9 | plotly: `id=` prop never reaches the DOM (needs `divId`) | reproduced | reproduced | reproduced | anomaly — campaign FINDING-017, unchanged by 4.1.0 |
| P10 | plotly: prod hydration (NoSSR wrapper) | — | clean | clean | pass |
| R1 | recharts 3.10.1: line / bar / area / pie / composed with state-bound data | ok | ok | same | pass |
| R2 | recharts: data replaced and appended by events (curve `d` changes, new ticks) | ok | ok | same | pass |
| R3 | recharts: tooltip on hover, legend items, responsive container | ok | ok | same | pass |
| R4 | recharts: pie `label=True` slice labels | rendered | rendered | **not rendered on 3.8.1** | pass (improvement) |
| R5 | recharts: axis `unit="u"` / `tick_count` formatting | ok | ok | same | pass |
| R6 | recharts: custom tick formatter — no `tick_formatter` prop exists; works via `custom_attrs` | ok via workaround | ok | same | anomaly — ISSUE-7 (pre-existing API gap) |
| R7 | recharts: `is_animation_active=False` accepted | ok | ok | same | pass |
| T1 | sonner 2.0.8: info / success / error / warning toasts from handlers | ok | ok | same | pass |
| T2 | sonner: `rx.toast.loading` + `rx.toast.dismiss("id")` and `rx.toast.dismiss()` | ok | ok | same | pass |
| T3 | sonner: action button (`action={"label":…, "on_click":…}`) fires a State event | ok | ok | same | pass |
| T4 | sonner: toasts from a `background=True` task (3/3 delivered) | ok | ok | same | pass |
| T5 | sonner: toast from `on_load` | ok | ok | same | pass |
| T6 | sonner: `rx.toast.provider` options (position, rich_colors, close_button, expand, duration, visible_toasts, toast_options) | applied | applied | same | pass |
| T7 | sonner: an explicit `rx.toast.provider` on a page renders every toast **twice** | reproduced | reproduced | reproduced | anomaly — ISSUE-8 (pre-existing) |
| T8 | sonner: `ToastAction` named in the docs is not importable from `rx` | n/a | n/a | same | anomaly — ISSUE-9 (pre-existing docs gap) |
| A1 | radix accordion 1.2.20: `type="single"` + `collapsible` (open, switch, collapse) | ok | ok | same | pass |
| A2 | radix accordion: controlled by a State var (`value` + `on_value_change` both directions) | ok | ok | same | pass |
| A3 | radix accordion: `type="multiple"` (two items open at once) | ok | ok | same | pass |
| D1 | radix dialog 1.1.23: open/close driven by a State var | ok | ok | same | pass |
| D2 | radix dialog: nested dialog opens/closes without closing the outer one | ok | ok | same | pass |
| D3 | radix dialog: Escape closes and syncs `on_open_change` back to state | ok | ok | same | pass |
| D4 | radix dialog: open driven by `rx._x.client_state` | ok | ok | same | pass |
| D5 | radix dialog: `rx.form.root` inside a dialog, submit closes it and lands the data | ok | ok | same | pass |
| F1 | radix form 0.1.16: `match="valueMissing"` / `"typeMismatch"` block submit and show messages | ok | ok | same | pass |
| F2 | radix form: `server_invalid` + `force_match` paired with `match` (documented pattern) | ok | ok | same | pass |
| F3 | radix form: `force_match` **without** `match` — message never hides + React DOM error | reproduced | message shows (React error is dev-only) | reproduced identically | anomaly — ISSUE-2 (pre-existing, documented workaround) |
| F4 | radix form: `on_submit` payload | ok, but includes every child `id=` as a null key | same | same | anomaly — ISSUE-10 (pre-existing) |
| X1 | dev console: 3 emotion `":first-child" is potentially unsafe … SSR` errors on the radix page | reproduced | absent (prod) | reproduced identically | anomaly — ISSUE-3 (pre-existing) |
| X2 | server log: bun `warn: incorrect peer dependency "react@19.3.0"` on first install | seen | seen | seen | benign (react-side-effect ≤18, a react-helmet dep) |
| X3 | prod: no hydration errors, no page errors, no failed requests on any of the six pages | — | clean | clean | pass |

## Issues

### ISSUE-1 (MEDIUM, regression, downstream `reflex-components-moment 0.9.4a1`) — one `rx.moment(locale=…)` changes the language of every other `rx.moment` on the page

`leakapp2/` is the whole repro — three moments, one of which sets `locale="fr"`:

```python
rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", id="plain")     # no locale prop
rx.moment("2020-01-01T00:00:00", from_now=True, id="fromnow")               # no locale prop
rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", locale="fr", id="french")
```

| stack | `plain` | `fromnow` | `french` |
|---|---|---|---|
| reflex 0.9.11a1 + components-moment **0.9.4a1** (react-moment 2.0.2) | `jeudi 14 mars 2024` | `il y a 7 ans` | `jeudi 14 mars 2024` |
| reflex 0.9.10.post2 + components-moment 0.9.3 (react-moment 1.2.2) | `Thursday 14 March 2024` | `7 years ago` | `jeudi 14 mars 2024` |

Reproduced on both the minimal app and the six-page app, in **dev and prod**, and it survives a
reload. Bisected: reflex **0.9.11a1 core with components-moment 0.9.3** does *not* leak
(`results/out_mixed/moment.json` → `Mar 14, 2024`, `7 years ago`), so the moment wrapper /
react-moment bump owns it, not core.

Mechanism: for a literal `locale=`, the wrapper emits a side-effect `import "moment/locale/fr"`,
and moment's `defineLocale` makes that the process-wide default locale. Both react-moment
versions fall back to `moment.locale()` when a component has no `locale` prop
(2.0.2: `locale ?? settings.locale ?? moment.locale()`), but with 1.2.2 the app-wide default was
still `en` at render time and with 2.0.2 it is `fr`. In the six-page app the bleed is visible on
`m-date-prop`, `m-fromnow`, `m-tonow` and `m-title`
(`results/out_dev/moment.json` vs `results/out_base/moment.json`,
screenshots `shots/out_dev-moment.png` vs `shots/out_base-moment.png`); a `probe_global_locale.py`
run reads moment's global locale as `fr` on the alpha and `en` on the baseline
(dev only — it walks the Vite dep modules).

Ordering matters, which is why it is silent and looks random: in `leakapp/` (a `Var` locale pulls
in `moment/min/locales`, whose bundle ends by restoring `en`) the same page does *not* leak. So an
app can start leaking just by adding or removing an unrelated moment component.

Impact: any app that localizes one date and leaves the rest to the default now renders every date,
"time ago" string and title attribute in that language. Nothing warns.

Suggested fix direction: have the wrapper stop relying on the global — pass an explicit
`locale` (or wrap in react-moment 2.x's `<MomentProvider locale=…>`), or restore the default
locale after importing a locale file.

### ISSUE-2 (LOW, pre-existing, upstream radix) — `rx.form.message(force_match=…)` without `match` is always visible and logs a React DOM error

`radix_page.py`, field `nickname`:

```python
rx.form.message("nickname rejected (force_match only)", force_match=RadixState.email_invalid,
                id="form-msg-nomatch")
```

The message renders unconditionally (visible before any submit, still visible when
`email_invalid` is `False`) and dev-mode React logs
`React does not recognize the 'forceMatch' prop on a DOM element … spell it as lowercase 'forcematch'`.
Cause is upstream: `@radix-ui/react-form`'s `FormMessage` only destructures `forceMatch` in its
`FormBuiltInMessage` / `FormCustomMessage` branches; with `match === undefined` it renders
`FormMessageImpl` with `...messageProps` (still containing `forceMatch`) straight onto the DOM
(`node_modules/@radix-ui/react-form/dist/index.mjs`).

Identical on 0.1.14 (0.9.10.post2) — **not** a regression from the 0.1.16 bump. `docs/library/forms/form-ll.md`
already tells users to pair `force_match` with a dummy `match`; the docs do not mention the React
error, and the framework could drop `forceMatch` when `match` is unset. Evidence:
`results/out_dev/radix.json` and `results/out_base/radix.json` (same console entry in both).

### ISSUE-3 (LOW, pre-existing) — three emotion `":first-child" … server-side rendering` console errors on the radix page in dev

Every dev load of `/radix` logs three
`The pseudo class ":first-child" is potentially unsafe when doing server-side rendering. Try changing it to ":first-of-type".`
errors (console level *error*, not warning). Identical count on 0.9.10.post2; absent in prod.
Evidence: `results/out_dev/radix.json`, `results/out_base/radix.json`.

### ISSUE-4 (LOW, pre-existing) — moment locale imports log a `defineLocale` deprecation warning in the browser *and* the server log

Any page that mixes a literal `locale=` (imports `moment/locale/xx`) with a `Var` locale
(imports `moment/min/locales`) logs
`Deprecation warning: use moment.updateLocale(localeName, config) to change an existing locale …`
once per render, in the browser console and in the SSR server log
(`logs/dev_run.trimmed.log`). Same on 0.9.10.post2. Harmless, but it is the visible symptom of the
import-order fragility behind ISSUE-1.

### ISSUE-5 (LOW, pre-existing, by design) — unsupported `rx.moment` props are silently turned into CSS

`scripts/probe_moment_props.py` (run with the alpha venv from the app dir) shows what a user
migrating with react-moment 2.x notes in hand gets:

```
filter (dropped in react-moment 2.x): OK props=['css:({ ["filter"] : "uppercase" })']
calendar (react-moment prop, not wrapped): OK props=['css:({ ["calendar"] : true })']
settings (react-moment 2.x global config prop): OK props=['css:({ ["settings"] : … })']
typo: form_at: OK props=['css:({ ["formAt"] : "YYYY" })']
supported: format: OK props=['format:"YYYY"']
```

No error, no warning — the prop becomes an emotion style entry and is dropped by the browser.
This is reflex's general "unknown prop is a style prop" behaviour (same on 0.9.10.post2, and the
same reason `tick_formatter` lands in `wrapperStyle` in ISSUE-7), but it means the react-moment
2.x migration surface (`filter` removed, global config moved to `settings`/`MomentProvider`) gives
users zero feedback. Also unwrapped, and therefore unreachable, in 2.x: `utc`, `calendar`, `from`,
`to`, `ago`, `element`, `fallback`, `filters`, `renderers`.

### ISSUE-6 (LOW, pre-existing, upstream plotly.js 3.x) — `layout={"title": "…"}` as a plain string renders no title

`rx.plotly(data=…, layout={"title": "layout-from-state", "height": 300})`: the rest of the layout
applies (verified by toggling `paper_bgcolor`), but `_fullLayout.title.text` is plotly's editable
placeholder `"Click to enter Plot title"` and no title is drawn. plotly.js 3.x requires
`{"title": {"text": "…"}}`. Identical on 4.0.0/0.9.10.post2. Evidence: `probe_initial` /
`probe_after_layout` in `results/out_dev/plotly.json`.

### ISSUE-7 (LOW, pre-existing API gap) — recharts axes have no `tick_formatter`, and the unsupported prop is swallowed as a style

`rx.recharts.y_axis(tick_formatter="function(v){…}")` compiles to
`YAxis,{stroke:…,wrapperStyle:({ ["tickFormatter"] : "function(v){…}" })}` — the axis renders with
default ticks and nothing warns. `YAxis.get_props()` has no `tick_formatter` (only `unit`, `tick`,
`tick_count`, …). Workaround that does work on 3.10.1:
`custom_attrs={"tickFormatter": rx.Var("((v) => `${v}k`)")}` (verified: ticks render `0k / 250k / 500k`).
Same on recharts 0.9.2/3.8.1.

### ISSUE-8 (LOW, pre-existing) — adding `rx.toast.provider` to a page renders every toast twice

`rx.App`'s default overlay already mounts a sonner `Toaster` (`connection_toaster()`), so a page
that also renders `rx.toast.provider(...)` (to set position / rich colors / duration) ends up with
two Toaster roots and sonner renders **every** toast in both: 4 toasts → 8 DOM nodes, the `on_load`
toast appears twice, `bg_count=3` but six toast nodes (`results/out_dev/toast.json`,
`scripts/probe_toaster.py`). Identical on sonner 2.0.7 / 0.9.10.post2. The docs warn "in most cases
you will not need to include this component directly" but do not mention the duplication, and there
is no supported way to reconfigure the default toaster short of replacing `overlay_component`.

### ISSUE-9 (LOW, pre-existing docs gap) — `ToastAction` is not importable from `rx`

`docs/library/overlay/toast.md` says "By passing a `ToastAction` to the `action` or `cancel`
prop…", but `rx.ToastAction` does not exist, `rx.toast.action` does not exist, and only
`from reflex_components_sonner.toast import ToastAction` works. The dict form
`action={"label": "do it", "on_click": State.handler}` works and is what this app uses.

### ISSUE-10 (LOW, pre-existing) — `on_submit` form data includes every child `id=` as a null key

Submitting the radix form yields
`{"email": "user@example.com", "nickname": "", "age": "42", "form_email": "user@example.com",
"form_msg_required": null, "form_msg_type": null, "form_msg_server": null, "form_nick": null,
"form_msg_nomatch": null, "form_age": "42", "form_msg_range": null, "form_submit": null}` —
i.e. the `id` of every element inside the form (labels, messages, the submit button) becomes a key
with a `null` value. Same on 0.9.10.post2. Harmless but noisy for handlers that iterate the payload.

## Benign / surprising but fine

- `Disconnect websocket on page navigation` (console log) on every SPA navigation — reflex's own log.
- `/favicon.ico` 404 on the moment page in prod: this scratch app has no `assets/favicon.ico`
  (`reflex init` normally provides one). Traced with `scripts/probe_console_loc.py`.
- bun `warn: incorrect peer dependency "react@19.3.0"` during the first install: `react-side-effect`
  (a `react-helmet` dependency) caps at react ^18. Pre-existing, unrelated to this train.
- `rx.moment` `on_change` fires at mount (twice in dev under StrictMode, once in prod) —
  campaign FINDING-002, already confirmed by another cluster; re-observed here
  (`change_count_t0` = 5 dev / 4 prod after ~3 interval ticks vs 3 on the baseline) and **not**
  re-reported. react-moment 2.0.2's own type docs describe `onChange` as "invoked with the
  displayed content **on mount** and after each interval tick", i.e. upstream-intended.
- react-moment 1.2.2 bundled moment-duration-format internally; 2.0.2 made it an optional peer,
  which #7006 adds explicitly. Duration formatting produces identical output on both, so the new
  dependency is correctly wired (`import "moment-duration-format"` is enough).
- `rx.recharts` pie `label=True` labels render on 3.10.1 but not on 3.8.1 — a fix that came with
  the bump.
- `State.setvar("x")` raises `AttributeError: Variable 'x' cannot be set` for ordinary state vars
  on **both** versions: auto-setters are off by default (`Config.state_auto_setters=False`, itself
  deprecated), so `setvar` only works for vars with an explicit `set_*` handler or dynamically
  added vars. Not a finding, but it is what forced the explicit `set_dialog_open` handlers in
  `radix_page.py`.
- `rx.toast.provider(toast_options={...})` rejects a plain dict with a clear
  `TypeError: Invalid var passed for prop Toaster.toast_options, expected type …ToastProps`;
  `rx.toast.options(style={...})` is the accepted form. Good error, worth keeping.

## Process hygiene

Every server started for this cluster (dev 5220/9620, prod 5221, baseline dev 5222/9622, baseline
prod 5224, leak repros 5223/9623, 5226/9626, 5227/9627, mixed 5225/9625) was killed; a final
`ps` showed no granian / react-router / bun / chromium process of this cluster alive and no
listener left in the 5220-5239 / 9620-9639 range.

## VERIFICATION: rx.moment: one component's locale= now sets the language of every other rx.moment on the page (react-moment 2.0.2)

**Verdict: CONFIRMED (independent repro), severity MEDIUM, regression TRUE (with one correction), downstream TRUE.**
Independent adversarial verification, rebuilt from the written repro in a separate working dir
(`$SB/apps/verify2_components_bumps_0/`), with the shared venvs, my own ports (frontend 5920-5923,
backend 10320-10323) and my own Playwright driver. The claimant's numbers reproduce exactly.

**Correction to the claim (not a refutation):** the locale bleed itself is *not* new — it is
pre-existing in the wrapper's design and 0.9.10.post2 only *masked it in one common ordering*.
On 0.9.10.post2 the identical bleed appears as soon as a user navigates from a page without a
locale to a page with `locale="fr"` and back (verified below, `results/twopage_base.json`).
What 0.9.11a1 changes is that the masking is gone, so a single page now leaks on first load with
no navigation at all. The headline table in ISSUE-1 is accurate as written.

### Environments / commands (all from `$SB`, never from /home/user/reflex)

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
W=$SB/apps/verify2_components_bumps_0
DRV="NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"

# venvs: $SB/envs/smoke (reflex 0.9.11a1 + reflex-components-moment 0.9.4a1),
#        $SB/envs/base0910 (reflex 0.9.10.post2 + reflex-components-moment 0.9.3),
#        $SB/envs/verify2_components_bumps_0 = bisect env, built with:
cd $SB && uv venv $SB/envs/verify2_components_bumps_0 --python 3.11 && \
  uv pip install --python $SB/envs/verify2_components_bumps_0/bin/python --prerelease=allow \
  'reflex==0.9.11a1' 'reflex-components-moment==0.9.3'

# 1 alpha dev            (app W/leak, three moments, one locale="fr")
cd $W/leak       && REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run --frontend-port 5920 --backend-port 10320
cd $W && eval $DRV drive.py http://localhost:5920/ $W/out/alpha_dev.json
# 2 baseline dev         (byte-identical source, run with 0.9.10.post2)
cd $W/leak_base  && REFLEX_TELEMETRY_ENABLED=false $SB/envs/base0910/bin/reflex run --frontend-port 5921 --backend-port 10321
cd $W && eval $DRV drive.py http://localhost:5921/ $W/out/base_dev.json
# 3 alpha prod           (one port for both)
cd $W/leak       && REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run --env prod --frontend-port 5922 --backend-port 5922
cd $W && eval $DRV drive.py http://localhost:5922/ $W/out/alpha_prod.json
# 4 bisect: alpha CORE + moment wrapper 0.9.3 (react-moment 1.2.2)
cd $W/leak_mixed && REFLEX_TELEMETRY_ENABLED=false $SB/envs/verify2_components_bumps_0/bin/reflex run --frontend-port 5920 --backend-port 10320
cd $W && eval $DRV drive.py http://localhost:5920/ $W/out/mixed_dev.json
# 5 two-page probe (control + blast radius): "/" has NO locale prop anywhere, "/fr" has one
cd $W/twopage      && ... $SB/envs/smoke/bin/reflex    run --frontend-port 5921 --backend-port 10321
cd $W/twopage_base && ... $SB/envs/base0910/bin/reflex run --frontend-port 5922 --backend-port 10322
cd $W && eval $DRV drive_twopage.py http://localhost:5921 $W/out/twopage_alpha.json   # home -> /fr -> home
```

### Results (my runs)

| run | stack | `plain` (no locale prop) | `fromnow` (no locale prop) | `french` (locale="fr") |
|---|---|---|---|---|
| alpha dev | 0.9.11a1 + moment 0.9.4a1 | **jeudi 14 mars 2024** | **il y a 7 ans** | jeudi 14 mars 2024 |
| alpha prod | 0.9.11a1 + moment 0.9.4a1 | **jeudi 14 mars 2024** | **il y a 7 ans** | jeudi 14 mars 2024 |
| baseline dev | 0.9.10.post2 + moment 0.9.3 | Thursday 14 March 2024 | 7 years ago | jeudi 14 mars 2024 |
| bisect dev | **0.9.11a1 core** + moment **0.9.3** | Thursday 14 March 2024 | 7 years ago | jeudi 14 mars 2024 |

Identical after a full reload. Console clean in every run (only the known-benign HydrateFallback /
vite / React-DevTools lines); no page errors, no failed requests. So: the `reflex-components-moment`
0.9.3 -> 0.9.4a1 bump (react-moment 1.2.2 -> 2.0.2) owns it, core reflex does not — the bisect is
confirmed independently.

Two-page probe (`W/twopage`, home has no locale prop at all, `/fr` has one):

| stack | home, fresh load | /fr | home again after client-side nav |
|---|---|---|---|
| alpha | Thursday 14 March 2024 / 7 years ago | jeudi 14 mars 2024 | **jeudi 14 mars 2024 / il y a 7 ans** |
| baseline 0.9.10.post2 | Thursday 14 March 2024 / 7 years ago | jeudi 14 mars 2024 | **jeudi 14 mars 2024 / il y a 7 ans** |

Two things follow: (a) the alpha is not "French by default" — a page with no locale import renders
English, so the `locale=` component really is the cause; (b) the cross-page bleed is **pre-existing**
(same on 0.9.10.post2), i.e. once the locale module has been evaluated the whole SPA session
switches language, and the same URL renders differently depending on navigation history.

### Mechanism (file:line)

1. `packages/reflex-components-moment/src/reflex_components_moment/moment.py:127-128` (identical in
   0.9.3 and 0.9.4a1; installed copy `$SB/envs/smoke/lib/python3.11/site-packages/reflex_components_moment/moment.py:127`)
   emits a bare side-effect import for a literal locale:
   ```python
   if isinstance(self.locale, LiteralVar):
       imports[""] = f"moment/locale/{self.locale._var_value}"
   ```
   Compiled page (`W/leak/.web/app/routes/_index.jsx:5`): `import "moment/locale/fr"`.
   moment's `defineLocale()` sets the **process-wide default locale** as a documented side effect,
   so the app default becomes `fr` the moment that module is evaluated.
2. Both react-moment versions resolve a *missing* `locale` prop to that global:
   - 2.0.2 `node_modules/react-moment/dist/index.mjs`, `getDatetime` (minified `tt`):
     `let s = props.locale ?? settings.locale ?? i.locale();` then `u = i(r, m, s)`.
   - 1.2.2 `node_modules/react-moment/dist/index.js`, `getDatetime`:
     `i = t.globalLocale ? t.globalLocale : i || t.globalMoment.locale()`.
3. The behavioural difference is an accident of 1.2.2's bundle: react-moment 1.2.2 **bundles
   moment-duration-format inside its dist** and runs its init at import time
   (`…function D(e){…e.updateLocale("en",c)}…,D(e),D},o=[n(1)]` in `dist/index.js`), and moment's
   `updateLocale(name, …)` also re-sets the global locale to `name` — i.e. importing react-moment
   1.2.2 silently resets the default back to `en`. In the single-page app the page module's
   `import "moment/locale/fr"` runs *before* react-moment is dynamically imported (`ClientSide(() =>
   import('react-moment'))`), so on 0.9.10.post2 the reset lands last and hides the bleed.
   react-moment 2.0.2 instead loads duration-format optionally through an esbuild `require` shim
   (`ct()` -> `et("moment-duration-format")`), which throws in the browser and is swallowed
   (`moment-duration-format` is an *optional* peer dep and is not even installed unless
   `duration=`/`duration_from_now=` is used), so no `updateLocale("en")` happens and `fr` stays the
   default. This also explains the ordering sensitivity in ISSUE-1: whichever locale-touching module
   is evaluated last wins, which is why the two-page case leaks on both versions.

Refutations considered and ruled out: environment/proxy (all local, `--noproxy`, console+network
clean); cwd shadowing (apps live under `$SB/apps/...`, run only with venv binaries); API misuse or
documented behaviour (`docs/library/data-display/moment.md` says nothing about locale being global;
the prop doc is "The locale to use when rendering", i.e. per component); pre-existing on
0.9.10.post2 (baseline run by me — English for the single-page case, so the first-load behaviour is
genuinely new); demo-app bug (repro is 3 lines of framework API); flakiness (reproduced on 6
independent server runs, dev and prod, plus reloads).

Severity: medium. Silent, no console warning, purely a localization/correctness defect (no crash,
no data loss) but it hits any app that localizes one date and leaves the rest at the default, and
0.9.11a1 makes it reachable without navigation. A fix direction that stays inside the wrapper: pass
the resolved locale explicitly on every `Moment` (or wrap the app in react-moment 2.x's
`MomentProvider`), or restore the previous default after the locale side-effect import.

Evidence (my own): `verification/moment_locale/leak/` (minimal repro app),
`verification/moment_locale/twopage/` (control + cross-page probe),
`verification/moment_locale/drive.py`, `.../drive_twopage.py`,
`verification/moment_locale/results/{alpha_dev,base_dev,alpha_prod,mixed_dev,twopage_alpha,twopage_base}.json`
plus the matching `.png` screenshots, `verification/moment_locale/logs/*.tail.log`.
All servers/browsers started for this verification were killed; ports 5920-5923 / 10320-10323 are free.
