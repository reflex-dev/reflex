# Cluster `components_bumps` — reflex 0.9.12a1 pre-release QA

Explorer agent notes, written for a stranger. Everything below was run against **published PyPI
packages only** (never the `/home/user/reflex` checkout). Date: 2026-09-19.

## TL;DR

| Change | Verdict |
|---|---|
| recharts `sankey_chart` + custom node/link renderers (#6708) | works, dev + prod |
| `rx.recharts.use_chart_width()` (#6708) | works; `undefined` outside a chart, reacts to resize |
| recharts prop routing `stroke_dasharray` / `tick_formatter` (#6833) | **fixed**, baseline confirms it was broken in 0.9.11.post1 |
| `rx.data_editor` `type="image"` cells (#7081) | thumbnails work; **image-preview overlay never opens in PROD** (issue 1) |
| dataeditor carousel CSS (#7081) | CSS is loaded in dev and prod |
| `rx.plotly(..., id=...)` → `divId` (#6977) | works: static, State-var figure, inside `rx.foreach` |
| sonner toast `action`/`cancel` callbacks (#7157) | works from frontend triggers, `@rx.memo`, `rx.ComponentState`, `rx.foreach`, backend yield, background task; dev + prod |
| code-block copy button a11y + no form submit (#7078) | works; `aria-label="Copy code"`, `type="button"`, clipboard OK, form counter unchanged |
| "Built with Reflex" sticky badge a11y (#7078) | works: `aria-label` present in prod at 360 px where the label text is hidden |
| upload unknown-handler → 400 (#6860) | works; baselined via source diff (was `KeyError` → 500) |
| `reflex_components_core.datadisplay` namespace (#7124) | works: `AttributeError` instead of `ModuleNotFoundError` — but see issue 3 about the changelog wording |
| `rx.vars.use_id()` / `use_hook_var()` (#6708) | works per-component; **duplicate DOM ids inside `rx.foreach`** (issue 2) |
| radix segmented control (#7198), markdown, gridjs data_table | functional, no console errors |

Three issues found; none is a regression against 0.9.11.post1.

## Environment

```
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
```

Own venv (`plotly` + `pandas` + `httpx` are needed beyond the shared venv):

```
cd $SB && uv venv $SB/envs/cb --python 3.11
uv pip install --python $SB/envs/cb/bin/python --prerelease=allow \
    'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
    'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
    'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
    'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
    'reflex-components-sonner==0.9.4a1' 'reflex-components-lucide' plotly pandas httpx
```

Resolved `uv pip freeze --python $SB/envs/cb/bin/python | grep -iE 'reflex|plotly|pandas'`:

```
pandas==3.0.6
plotly==7.1.0
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

Baseline venv `$SB/envs/prev`: `reflex==0.9.11.post1` + matching stable component packages
(`reflex-components-core==0.9.9`, `-code==0.9.5`, `-dataeditor==0.9.2`, `-recharts==0.9.3`, ...).

## Rerun commands

The app is `gallery/` (9 pages, one per feature area). Ports used: frontend **3300**,
backend **8300** for dev, single port **3301** for prod.

```bash
SB=/tmp/.../scratchpad                    # your scratchpad
cp -r <artifact dir>/gallery $SB/apps/components_bumps/gallery
cd $SB/apps/components_bumps/gallery

# dev
REFLEX_TELEMETRY_ENABLED=false $SB/envs/cb/bin/reflex run \
    --frontend-port 3300 --backend-port 8300 --loglevel debug > ../logs/dev_server.log 2>&1 &

# prod (ONE port for both flags)
REFLEX_TELEMETRY_ENABLED=false $SB/envs/cb/bin/reflex run --env prod \
    --frontend-port 3301 --backend-port 3301 --loglevel debug > ../logs/prod_server.log 2>&1 &

# drivers (Playwright venv)
cd $SB/apps/components_bumps
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive.py  http://localhost:3300 ./shots dev
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive2.py http://localhost:3300 ./shots dev http://localhost:8300
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive.py  http://localhost:3301 ./shots prod
NO_PROXY=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python portal_probe.py http://localhost:3301 prod   # issue 1

# no-server checks
cd $SB/apps/components_bumps
$SB/envs/cb/bin/python namespace_check.py      # #7124 namespace
$SB/envs/cb/bin/python props_baseline.py       # #6833, run under $SB/envs/prev too
$SB/envs/cb/bin/python upload_probe.py http://localhost:8300   # #6860
```

`drive.py` / `drive2.py` write `shots/<phase>-results.json` and `shots/<phase>-*.png`; they
record console messages, page errors, failed requests and every response >= 400.

---

## Issue 1 (HIGH) — `rx.data_editor` overlay editor never opens in PROD mode: the `#portal` div is swallowed by the "Built with Reflex" sticky badge

The headline of #7081 is "opens Glide Data Grid's built-in image preview". In **prod** it does not:
double-clicking an image cell logs

```
Cannot open Data Grid overlay editor, because portal not found.
Please add `<div id="portal" />` as the last child of your `<body>`.
```

and `document.getElementById('portal')` is `null`. This also kills the text/markdown/uri cell
editors, not only image preview. In **dev** the same app works (see `shots/dev-editor-overlay.png`
— the carousel opens with "1 of 2" arrows and dot indicators).

**Root cause** (read from the compiled `\.web/app/root.jsx`): `reflex_components_dataeditor`
registers its portal as an app wrap at priority `-1`:

```python
# reflex_components_dataeditor/dataeditor.py:~590
return {(-1, "DataEditorPortal"): Portal.create(id="portal", position="fixed", top=0)}
```

In prod only, `reflex/compiler/compiler.py:1356` runs

```python
if is_prod_mode() and config.show_built_with_reflex:
    app._setup_sticky_badge()          # registers app_wraps[0, "StickyBadge"]
```

The app-wrap chain nests priority `-1` **inside** priority `0`, so the compiled root becomes

```js
jsx(MemoizedBadge_04c36749, {}, jsx("div", {css:{position:"fixed", top:0}, id:"portal"}))
```

`StickyBadge` is an `<a>` built by `StickyBadge.create()` with its own fixed children
(`StickyLogo`, `desktop_only(StickyLabel)`) and ignores children passed to it — so the portal div
is silently dropped from the DOM.

`show_built_with_reflex` defaults to `True` for everyone except pro/team/enterprise deploys, so
**every non-paying user's production app has a broken data_editor overlay**.

Repro (self-contained):

```bash
cd $SB/apps/components_bumps/gallery
REFLEX_TELEMETRY_ENABLED=false $SB/envs/cb/bin/reflex run --env prod \
    --frontend-port 3301 --backend-port 3301 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python \
    $SB/apps/components_bumps/portal_probe.py http://localhost:3301 prod
# -> "portal_exists": false, "overlay_imgs": [], console: "portal not found"
# same probe against the dev server on 3300 -> portal_exists true, carousel opens
```

Purely static check, no browser:

```bash
grep -o 'MemoizedBadge[^)]*portal[^)]*' .web/app/root.jsx
```

**Regression: NO.** Baselined empirically: a minimal data_editor app compiled with
`reflex==0.9.11.post1` (`$SB/apps/components_bumps/baseline_de`, `reflex export --frontend-only
--no-zip` runs the prod compile path) produces the identical
`jsx(MemoizedBadge_04c36749,{},jsx("div",{...,id:"portal"}))` nesting. `app_wrap.py`,
`App._app_root`, `_memoize_stateful_app_wraps` and the `show_built_with_reflex` gate are all
byte-identical between 0.9.11.post1 and 0.9.12a1. So the bug predates this release — but it is
worth flagging now because 0.9.12a1 ships a **new feature whose main interaction is the overlay**,
and the release notes promise an image preview that does not work in production.

Evidence: `shots/prod-portal-probe.png`, `shots/prod-editor-overlay.png` (no carousel),
`shots/dev-editor-overlay.png` (carousel works), `shots/prod-results.json`
(`editor.overlay_imgs: []`, console errors), `logs/portal_probe_prod.log`.

## Issue 2 (MEDIUM) — `rx.vars.use_id()` returns the same id for every item of an `rx.foreach`, producing duplicate DOM ids

`use_id()` is new in 0.9.12a1 and its docstring warns that "the hook is called once in each
compiled component that reads the var". A `rx.foreach` body is compiled into **one** component, so
every iteration renders the same `useId()` value. Using it the obvious way — a unique `id` per row
plus a matching `html_for` on the row's label — produces invalid HTML and broken label targeting:

```python
def id_row(item: str) -> rx.Component:
    ident = rx.vars.use_id()
    return rx.hstack(
        rx.el.label(item, html_for=ident),
        rx.el.input(id=ident, default_value=item),
    )

rx.foreach(MiscState.items, id_row)   # items = ["ia", "ib", "ic"]
```

Observed (dev and prod, `/misc`):

```
foreach_ids        = ["_r_3_", "_r_3_", "_r_3_"]      # all identical
dup_id_check.dups  = ["_r_3_"]
label_resolution   = [{for:"_r_3_", text:"ia", targetValue:"ia"},
                      {for:"_r_3_", text:"ib", targetValue:"ia"},   # <- wrong input
                      {for:"_r_3_", text:"ic", targetValue:"ia"}]
```

Clicking the "ib" or "ic" label focuses the first row's input. Ids are stable across re-render
(good) and are unique per `@rx.memo` instance and per custom sankey link renderer (that is how the
docs' gradient example works, and it does work — 6 unique gradient ids, see
`shots/dev-sankey-initial.png`).

**Regression: NO** — the API is new in this release. This is a documentation/ergonomics gap: the
`use_id()` docstring and the sankey docs page never say "do not call this inside `rx.foreach`",
and the failure is silent (no warning, no console error).

Repro: `$SB/envs/driver/bin/python drive2.py http://localhost:3300 ./shots dev http://localhost:8300`,
see `dup_id_check` / `label_resolution` in `shots/dev-results2.json`; screenshot
`shots/dev-misc-ids.png`.

## Issue 3 (LOW) — the #7124 changelog's suggested import path does not work in the `from ... import` form

Changelog: *"Reach them as before via `rx.code_block` / `rx.data_editor`, or
`reflex.components.datadisplay.code`."*

```python
import reflex.components.datadisplay.code as c        # OK
from reflex.components.datadisplay.code import CodeBlock  # OK
from reflex.components.datadisplay import code        # ImportError: cannot import name 'code'
```

`reflex.components.datadisplay` is aliased onto `reflex_components_core.datadisplay`, whose lazy
loader only advertises `logo`, so the attribute lookup that `from X import Y` performs fails.

**Regression: NO** — identical on 0.9.11.post1. The fix itself works as advertised: on
0.9.11.post1 `reflex_components_core.datadisplay.code_block` raised
`ModuleNotFoundError: No module named 'reflex_components_core.datadisplay.code'`; on 0.9.12a1 it
raises `AttributeError: No reflex_components_core.datadisplay attribute code_block`, and
`dir()` is down to `['logo']`.

Evidence: `logs/namespace_check.log`, `namespace_check.py`.

---

## What was verified working (details)

### recharts sankey (#6708) — `shots/*-sankey-*.png`

* Static dict data, State-var data (`Randomize` changes link widths, `Add node` grows the graph),
  `graphing_tooltip` child, `node=`/`link=` style dicts.
* Custom `@rx.recharts.sankey_chart.node` / `.link` renderers exactly as documented in
  `docs/library/graphing/charts/sankeychart.md` — gradients, per-link `use_id()`, value labels.
  Six `<linearGradient>` elements with six distinct ids, each referenced by its path.
* Two custom-renderer charts inside `rx.foreach` over a State list, each wrapped in `@rx.memo`:
  12 more unique gradient ids, no id collisions with the standalone chart.
* `use_chart_width()` outside a chart renders as empty/`undefined` and is falsy in `rx.cond`
  (documented behaviour). Inside the custom node renderer it drives label placement: resizing the
  viewport 1280 -> 520 moves the label x positions (`317/931/635` -> `127/361/255`).
* Note: the default Recharts sankey node renders as `<path>` (a `Rectangle`), not `<rect>` —
  `svg rect` counts are 0 by design, not a bug.

### recharts prop routing (#6833) — `shots/*-props-*.png`

Rendered (in-process, no server) on both versions with `props_baseline.py`:

```
0.9.12a1  reference_line -> props: ['stroke:"#f00"', 'strokeDasharray:"3 3"', 'y:3000']
0.9.11.p1 reference_line -> props: ['stroke:"#f00"', 'wrapperStyle:({ ["strokeDasharray"] : "3 3" })', 'y:3000']
0.9.12a1  x_axis         -> props: [..., "tickFormatter:(value) => 'X:' + value"]
0.9.11.p1 x_axis         -> props: [..., 'wrapperStyle:({ ["tickFormatter"] : "(value) => \'X:\' + value" })']
```

In the browser: x ticks read `X:Jan … X:May`, y ticks `0k … 10k`, the reference line is dashed
(`stroke-dasharray="3 3"`), `line(stroke_dasharray="5 5")` and
`cartesian_grid(stroke_dasharray="4 4")` are dashed, and the responsive-container `style` is only
`width/height/min-width/min-height` — no `wrapperStyle` anywhere. A State-var
`reference_line(stroke_dasharray=PropsState.dash)` updates live `3 3` -> `8 2`.

Quirk worth knowing (not a defect): `tick_formatter` is typed `Var[str]` and `Axis.create()`
re-wraps a *literal* string as a raw JS expression. Passing a real function Var
(`rx.vars.FunctionStringVar.create("((v) => v)")`) raises
`TypeError: Invalid var passed for prop XAxis.tick_formatter, expected type <class 'str'>`, and a
State `str` var would be emitted as a quoted string rather than a function. Only a Python literal
string works.

### data_editor image cells (#7081)

Columns `[{"title":"pic","type":"image","id":"pic"}, {"title":"name","type":"str","id":"name"}]`
with rows whose first cell is a list of local asset URLs. Thumbnails render next to the text
column in the same grid (`shots/dev-editor-initial.png`) for State-driven rows, after
`Add row`, and inside `@rx.memo`. `on_cell_clicked` fires with `[0, 0]`.
`react-responsive-carousel/lib/styles/carousel.min.css` rules are present in `document.styleSheets`
in **both** dev and prod, so the CSS half of #7081 is fine — only the overlay is blocked (issue 1).

### plotly divId (#6977)

`document.getElementById("myplot")` resolves; `.js-plotly-plot` ids are exactly
`["myplot", "stateplot", "fe-one", "fe-two"]`, covering a literal figure, a `@rx.var(cache=True)`
State figure, and two `rx.foreach` items with per-item ids. After a State bump the `stateplot` div
keeps its id and the bars re-render. Dev and prod identical.

### sonner toast action/cancel (#7157)

`action_hits` / `cancel_hits` State counters incremented for every path, in **dev and prod**:
frontend `rx.toast.success(...)` on a plain button, inside `@rx.memo`, inside `rx.ComponentState`
(its own `cls.bump` fired, `local=1`), inside an `rx.foreach` item, a toast yielded from a normal
backend handler, and a toast yielded from `@rx.event(background=True)`. `duration`, `position`
(`bottom-right`, `top-center`), `close_button` all honoured; `rx.toast.dismiss()` cleared 2 open
toasts to 0. **No `ReferenceError: queueEvents is not defined`** in any console log.

### code block (#7078)

`rx.code_block(..., can_copy=True)` inside `rx.form(on_submit=...)`: the copy button is
`{aria: "Copy code", type: "button"}`, clicking it leaves the submit counter at 0 while the real
submit button takes it to 1, and `navigator.clipboard.readText()` returns the exact source. A code
block ~1500 px below the fold highlights correctly when scrolled into view (10 token spans).
Switching `language` python -> javascript via State and `theme` one-light -> one-dark via
`rx.cond(..., rx.code_block.themes.one_dark, ...)` keeps the text readable.

Prod SSR (`curl -sL --compressed http://localhost:3301/code/`, 15 744 bytes) already contains
`def greet`, `below the fold`, `Copy code` and `type="button"` — readable without JS.
Note: the prod server 307-redirects `/code` -> `/code/`; use `curl -L`.

### sticky badge a11y (#7078)

`sticky()` at 1280 px: `aria-label="Built with Reflex"`, label span visible.
At 360 px: label span `offsetWidth/Height == 0` (hidden by `desktop_only`) and the `aria-label`
still supplies the accessible name. Source diff confirms `aria_label="Built with Reflex"` is the
only change in `reflex_components_core/core/sticky.py` vs 0.9.9, so 0.9.11.post1 had **no**
accessible name there — fix confirmed. It is also present in the prod SSR HTML.
(`rx.logo()` is a different component and is unchanged; its anchor has no `aria-label` but its
text content plus the SVG `<title>Reflex</title>` give it an accessible name.)

### upload 400 (#6860)

`POST /_upload` with `reflex-client-token` + `reflex-event-handler`:

| case | status | body |
|---|---|---|
| unknown handler name | 400 | `Unknown upload event handler: 'gallery.gallery.UploadState.nope'.` |
| missing handler header | 400 | `Missing reflex-client-token or reflex-event-handler header.` |
| missing token header | 400 | same |
| empty handler value | 400 | same |
| path-traversal-ish handler `../../etc/passwd` | 400 | `Unknown upload event handler: '../../etc/passwd'.` |

No 500s, no tracebacks in the server log. A real browser upload through `rx.upload` still works
(`upload_files_text == ["up.txt"]`, `shots/dev-upload.png`).

**Baseline: by source diff** (I did not stand up a 0.9.11.post1 server for this). 0.9.11.post1's
`_upload.py` used `RegistrationContext.get().event_handlers[handler_name]` — an unguarded
`KeyError`, i.e. a 500. 0.9.12a1 adds the `.get(...)` + `HTTPException(400)`.

### misc

* `rx.markdown` with fenced code, a table, inline + block math (KaTeX) and a link — renders, no
  console errors.
* `rx.data_table` (gridjs) with State rows: 4 -> 5 rows after a State append, search "Engineer"
  narrows to 2 rows, sorting/pagination controls present.
* `rx.segmented_control` bound to a State var (#7198): `one` -> `two` -> `three` round-trips.
* `rx.vars.use_hook_var("react", "useId", str)` at page level renders a value and is truthy in
  `rx.cond`; inside `@rx.memo` it yields a distinct stable id.
* Client-side navigation `/` -> `/sankey` -> `/code` -> `/plotly` re-mounts every component
  correctly (copy button present, `myplot` div present).

## Benign / surprising-but-OK observations

* `rx.el.svg.*` props that are also valid CSS properties (`stroke`, `text-anchor`, `stroke-width`)
  are emitted through emotion `css` rather than as SVG attributes, so
  `element.getAttribute('stroke')` returns `null` even though the element paints correctly. Only
  matters if you assert on attributes in a test.
* One unexplained `Failed to load resource: 404` console error appeared in a single prod driver
  run and was **not** reproducible — a follow-up pass over all 7 pages recording every response
  >= 400 produced an empty list. Recorded as an anomaly, no actionable URL.
* `reflex_components_core/base/error_boundary.py` changed `stroke-width`/`stroke-linecap`/
  `stroke-linejoin` to camelCase in 0.9.10a1; not mentioned in the changelog lines for this
  cluster. Cosmetic, no user-visible effect observed.
* Editing the app source to something that raises during page evaluation makes the dev server log
  `[ERROR] Unexpected exit from worker-1`; it recovers on the next valid save. Expected-ish, but
  the message is alarming.
* Compile-time deprecation warnings unrelated to this cluster: implicit Radix Themes enablement,
  `@rx.memo` without explicit `rx.Var[...]` annotations, SitemapPlugin not declared.
* Prod mode 307-redirects extensionless routes to a trailing slash.

## Artifact map

```
gallery/                 the 9-page app (gallery/gallery.py is the whole thing)
gallery/assets/*.png     4 tiny solid-colour PNGs used by the data_editor image cells
drive.py                 main Playwright driver (all 8 feature pages, dev + prod)
drive2.py                badge a11y at 360 px, duplicate-id check, real upload, SSR fetch
portal_probe.py          issue 1: #portal presence + overlay open attempt
namespace_check.py       #7124 namespace assertions (no server needed)
props_baseline.py        #6833 render-level comparison; run under envs/cb and envs/prev
upload_probe.py          #6860 400-response matrix
baseline_de/             minimal data_editor app used for the 0.9.11.post1 prod-compile baseline
logs/                    dev/prod server logs (trimmed), driver output, probe output
shots/                   screenshots + dev-results.json / dev-results2.json / prod-results.json
```
