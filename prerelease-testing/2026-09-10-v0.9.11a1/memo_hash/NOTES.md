# Cluster: memo_hash — #6947 auto-memoization naming collisions and hashing changes

reflex **0.9.11a1** (reflex-base 0.9.11a1) vs baseline **0.9.10.post2**, both installed from
PyPI into the shared read-only venvs `$SB/envs/smoke` and `$SB/envs/base0910`. Nothing was
installed or run from the checkout. Every app was run for real (`reflex run`, dev **and** prod)
and driven in headless Chromium via Playwright with console / pageerror / HTTP capture and
screenshots.

Changelog lines under test:

> **reflex-base, Bug Fixes** — Auto-memoized components that render identically no longer share a
> generated memo name, which silently dropped one of the two compiled bodies. The name now
> accounts for: module-level code emitted by `add_custom_code`; dynamic imports; app-wrap
> components, including `rx.text` and the other `MarkdownComponentMap` components that all hashed
> alike; the defining module, so same-named components from different modules stay apart; the
> identity of dataclasses and enum members.
>
> **reflex-base, Performance** — Component content hashing … encodes roughly 1.2–1.3x faster on
> large pages. Generated memo module names change as a result.
>
> **reflex, Performance** — Clear auto-memoization naming caches after compiling app.

Bottom line: **every claim holds, and the bug it fixes reproduces in a browser on 0.9.10.post2.**
Three defects turned up alongside it, all **pre-existing on 0.9.10.post2** (none is a regression):
generated memo names are not reproducible across identical compiles; two same-named
`rx.ComponentState` subclasses in different modules cannot coexist; and `rx._x.client_state(...,
global_ref=False)` breaks with a `ReferenceError` once auto-memoization splits its readers and
writers into different memo bodies.

---

## Layout

```
memoapp/                the main app (six pages) — the collision table, end to end
memoapp_0910/           NOT SHIPPED — recreate with `cp -r memoapp memoapp_0910 && rm -rf
                        memoapp_0910/.web`; a byte-identical copy compiled/run on 0.9.10.post2
ptapp/                  the PR's "Not in this PR" passthrough-memo import gap
probes/                 hash-level probes (no server needed)
drive_memo.py           the Playwright driver (29 checks)
hot_edit_rss.sh         25 source edits under a live `reflex run`, sampling compiler RSS
name_stability.sh       3 identical compiles + 2 exports, diffing the memo export names
mod_template.py.in      generator for memoapp/mod_a.py and mod_b.py (proves they are twins)
custom_template.py.in   generator for memoapp/custom_a.py and custom_b.py
evidence/               the A/B artefacts quoted below
logs/, shots/           run logs, driver reports, screenshots
```

`mod_a.py`/`mod_b.py` and `custom_a.py`/`custom_b.py` are **generated** from the two `.in`
templates by a single `sed` substitution, so the only thing that differs between each pair is the
marker letter. Regenerate with:

```
sed -e 's/@X@/A/g' -e 's/@STEP@/1/g'  mod_template.py.in    > memoapp/memoapp/mod_a.py
sed -e 's/@X@/B/g' -e 's/@STEP@/10/g' mod_template.py.in    > memoapp/memoapp/mod_b.py
sed -e 's/@X@/A/g' -e 's/@Y@/B/g' -e 's/@x@/a/g' -e 's/@N@/1/g' -e 's/@WRAPTEXT@/a/g'     custom_template.py.in > memoapp/memoapp/custom_a.py
sed -e 's/@X@/B/g' -e 's/@Y@/A/g' -e 's/@x@/b/g' -e 's/@N@/2/g' -e 's/@WRAPTEXT@/bbbbb/g' custom_template.py.in > memoapp/memoapp/custom_b.py
```

## What the app contains

`memoapp/memoapp/custom_a.py` and `custom_b.py` each define **the same four class names**
(`CodeWidget`, `DynWidget`, `CssWidget`, `WrapWidget`, all `rx.el.Div` subclasses) with **the same
render** — each takes `title=Shared.label`, which is what makes the compiler auto-memoize the
widget node itself rather than only a `Bare` child. Each pair differs in exactly one non-rendered
artifact:

| pair | differs only in | observable at runtime |
|---|---|---|
| `CodeWidget` | `add_custom_code` | `globalThis.MEMO_CODE_A` / `..._B` |
| `DynWidget` | `_get_dynamic_imports` | `globalThis.MEMO_DYN_A` / `..._B` |
| `CssWidget` | a tagless `ImportVar` (side-effect CSS import) | computed style of `.memo-css-target`: `memo_a.css` sets `color`, `memo_b.css` sets `background-color`, so both can apply at once |
| `WrapWidget` | `_get_app_wrap_components` | the strings `a` and `bbbbb` in the DOM at the app root |

`mod_a.py`/`mod_b.py` each define a same-named `@rx.memo def card(...)` with the same JSX shape and
a different handler, plus a same-named `Counter(rx.ComponentState)` (never instantiated — see
ISSUE-2) and a distinctly-named twin `CounterA`/`CounterB` that the pages do use.

Pages: `/` `/samename` `/custom` `/props` `/foreach` `/page2`.

---

## Rerun commands

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad   # or any dir
export REFLEX_TELEMETRY_ENABLED=false

# hash-level collision table (no server, ~5 s each)
cd <artifacts>/                     # NOT inside the reflex checkout
$SB/envs/smoke/bin/python    probes/hash_probe.py smoke        # 0.9.11a1  -> FAILED: none
$SB/envs/base0910/bin/python probes/hash_probe_0910.py         # 0.9.10.post2 -> 8 collisions

# two same-named ComponentState subclasses in two modules (ISSUE-2)
$SB/envs/smoke/bin/python    probes/componentstate_collision.py smoke
$SB/envs/base0910/bin/python probes/componentstate_collision.py base0910

# compile-only A/B of the generated .web output
cp -r memoapp memoapp_0910 && rm -rf memoapp_0910/.web
cd memoapp         && $SB/envs/smoke/bin/reflex compile
cd ../memoapp_0910 && $SB/envs/base0910/bin/reflex compile
grep -n "MEMO_CODE_\|MEMO_DYN_" */.web/app_components/memoapp/memoapp.jsx

# dev run + browser (ports 5340/9740)
cd memoapp && $SB/envs/smoke/bin/reflex run --frontend-port 5340 --backend-port 9740
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_memo.py \
    http://localhost:5340 logs/dev-a1 --shots shots

# baseline dev run (ports 5341/9741) — reproduces the dropped memo body in a browser
cp -r memoapp memoapp_0910 && rm -rf memoapp_0910/.web
cd memoapp_0910 && $SB/envs/base0910/bin/reflex run --frontend-port 5341 --backend-port 9741
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_memo.py \
    http://localhost:5341 logs/dev-0910 --shots shots

# prod (ONE port for both)
cd memoapp && $SB/envs/smoke/bin/reflex run --env prod --frontend-port 5342 --backend-port 5342
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_memo.py \
    http://localhost:5342 logs/prod-a1 --shots shots

# 25 source edits under a live dev server, sampling every reflex process's RSS
./hot_edit_rss.sh memoapp logs/hot_edit_rss.csv 25

# in-process repeated compile (the hash caches are the thing being watched)
cp -r memoapp memoapp_probe && rm -rf memoapp_probe/.web
cd memoapp_probe && $SB/envs/smoke/bin/python ../probes/recompile_rss.py smoke 30

# memo-name stability: 3 identical compiles then 2 exports, names diffed
./name_stability.sh $PWD/memoapp_probe $SB/envs/smoke/bin/reflex logs/stability_a1

# the PR's "Not in this PR" passthrough-memo gap
cd ptapp && $SB/envs/smoke/bin/reflex compile
```

---

## Results

### 1. The collision table, at the hash level (`probes/hash_probe.py`)

Nine probes, each isolating one row of the PR's table. On **0.9.11a1 all pass**; run the
0.9.10.post2 counterpart and eight of them collide — that is the mutation check, done by version
rather than by patching:

| probe | 0.9.11a1 | 0.9.10.post2 |
|---|---|---|
| `Alpha(a="x")` vs `Beta(a="x")` (identical layout, distinct types) | distinct | **same digest** |
| `IntEnum.ONE` vs `1` | distinct | **same digest** |
| `Level.ONE` vs `OtherLevel.ONE` | distinct | n/a (API absent) |
| str-valued `Enum.RED` vs `"red"` | distinct | distinct |
| two function-local dataclasses of identical shape | distinct | **same digest** |
| function-local dataclass types released after `clear_hash_caches()` | 50 → 0 alive | 0 alive (no type cache existed) |
| same qualname, two modules | distinct tags | **same tag** |
| only `add_custom_code` differs | distinct | **same tag** |
| only `_get_dynamic_imports` differs | distinct | **same tag** |
| only a tagless `ImportVar` differs | distinct | distinct |
| app-wrap `rx.text("a")` vs `rx.text("bbbbb")` | distinct | **same tag** |
| `deterministic_hash(rx.text("a"))` vs `rx.text("bbbbb")` | distinct | **same digest** |
| tag stable across `clear_hash_caches()` | stable | n/a |

Logs: `logs/hash_probe_a1.log`, `logs/hash_probe_0910.log`.

### 2. The collision in the generated `.web` output (`evidence/collision_ab.txt`)

Same app source, two reflex versions, `reflex compile`:

```
### 0.9.11a1 — .web/app_components/memoapp/memoapp.jsx
 6:import {} from "$/public/memo_a.css"
 7:import {} from "$/public/memo_b.css"
11:const MEMO_DYN_A = (globalThis.MEMO_DYN_A = 'dyn-A');
12:const MEMO_DYN_B = (globalThis.MEMO_DYN_B = 'dyn-B');
14:globalThis.MEMO_CODE_A = 'code-A';
15:globalThis.MEMO_CODE_B = 'code-B';

### 0.9.10.post2 — the same file (module A's two markers are simply GONE)
 6:import {} from "$/public/memo_a.css"
 7:import {} from "$/public/memo_b.css"
11:const MEMO_DYN_B = (globalThis.MEMO_DYN_B = 'dyn-B');
13:globalThis.MEMO_CODE_B = 'code-B';
```

Export names, same file:

```
0.9.11a1                                          0.9.10.post2
Codewidget_div_17ad8794…  Codewidget_div_ae4e383a…  Codewidget_div_72e19cb8…     <- one, not two
Dynwidget_div_1e682796…   Dynwidget_div_21c62824…   Dynwidget_div_72e19cb8…      <- one, not two
Csswidget_div_c9264a9d…   Csswidget_div_e3636b4a…   Csswidget_div_28d12f98…  Csswidget_div_979ae813…
Wrapwidget_div_58f54114…  Wrapwidget_div_695250d8…  Wrapwidget_div_0afb8245… Wrapwidget_div_f840eb17…
```

Note that on 0.9.10.post2 `Codewidget` and `Dynwidget` not only collapse to one name each, they
carry **the same hash as each other** (`72e19cb8…`) — with neither `add_custom_code` nor
`_get_dynamic_imports` in the digest the two classes are indistinguishable apart from the tag
prefix.

### 3. The same thing in a browser (`drive_memo.py`, 29 checks)

| run | version | mode | result |
|---|---|---|---|
| `logs/dev-a1-report.json` | 0.9.11a1 | dev | 28 pass, 1 fail (ISSUE-3, pre-existing) |
| `logs/prod-a1-report.json` | 0.9.11a1 | prod | 28 pass, 1 fail (ISSUE-3, pre-existing) |
| `logs/dev-0910-report.json` | 0.9.10.post2 | dev | 25 pass, **4 fail** |

The three extra failures on 0.9.10.post2 are the dropped memo body, observed as a user would:

```
custom.add_custom_code.A   {'code_a': None, 'code_b': 'code-B', 'dyn_a': None, 'dyn_b': 'dyn-B'}
custom.dynamic_import.A    (same)
nav.page2_custom_markers   (same, after a client-side route change)
```

`window.MEMO_CODE_A` and `globalThis.MEMO_DYN_A` are `null` on 0.9.10.post2 and correct on
0.9.11a1, in dev and in prod. Everything else — the two same-named `@rx.memo` cards driving their
own module's state, `ComponentState` independence, the CSS side-effect imports (`color:
rgb(1,2,3)` **and** `background-color: rgb(4,5,6)` both applied to `.memo-css-target`), both
app-wrap texts in the DOM, dataclass/IntEnum/`rx.match`/`rx.cond` props, memos inside
`rx.foreach` with state-bound props, a `ComponentState` inside a `@rx.memo`, and client-side
navigation between pages sharing the memos — passes on both versions.

### 4. Cache clearing (`reflex` Performance line)

**Under `reflex run`, 25 source edits** (`logs/hot_edit_rss.csv`): the reflex backend worker is a
**fresh process on every hot reload** (a new pid each iteration, `etime` 00:05), so nothing can
accumulate there. RSS 57 220 kB → 57 324 kB across the 25 reloads; the supervising parent went
55 900 kB → 55 952 kB (+52 kB over the whole run). Flat.

**In one interpreter, 30 `app._compile(dry_run=True)` calls** (`probes/recompile_rss.py`) — the app
page mints a fresh function-local dataclass type on every evaluation, which is exactly what a
type-keyed cache would pin:

| | 0.9.11a1 | 0.9.10.post2 |
|---|---|---|
| RSS after compile 1 | 58 596 kB | 58 184 kB |
| RSS after compile 30 | 77 944 kB | 77 376 kB |
| growth | +19 348 kB (≈662 kB/compile) | +19 192 kB (≈662 kB/compile) |
| the four hash caches after each compile | `{str:0, dc_enc:0, dc_layout:0, encoders:0}` | n/a |

The hash caches are genuinely released — all four are empty after every compile, so the
`finally: clear_hash_caches()` in `App._compile` does its job. The ~662 kB/compile that remains is
**identical on both versions**, so it is pre-existing and unrelated to #6947 (the PR itself notes
`GLOBAL_CACHE.clear()` has an ASGI-only gap; that is a plausible candidate). Recorded as an
anomaly, not a finding.

**`reflex export` twice** (`name_stability.sh`): both exports produce the same 35 memo names apart
from the one unstable name in ISSUE-1.

### 5. Are generated memo module names stable across identical compiles? **No** — see ISSUE-1.

### 6. Hashing speed

Micro-benchmark of the whole `component_hash` over the `/page2` component tree, caches cleared per
rep, render warmed first, min of 15 (`probes/hash_bench.py`):

```
0.9.11a1     min=1.75 ms
0.9.10.post2 min=1.83 ms      -> 1.05x
```

Consistent with the PR's own "whole `component_hash`" column (0.99–1.03x); the 1.2–1.3x claim is
about the encoding step alone, which is ~13% of the total, and this page is small. 0.9.11a1 is also
hashing strictly more material (module name, `add_custom_code`, dynamic imports) and still comes
out ahead. Not a finding.

### 7. The PR's "Not in this PR" passthrough-memo import gap — **not reachable end to end**

`ptapp/` builds exactly the shape the PR describes: two `Holder` roots with identical props and
descendants (`SpanA`/`SpanB`) that render byte-identically to `rx.el.span` and differ only in a
tagless CSS `ImportVar`. The two roots **do** share one memo tag
(`Holder_div_dcdfe1a6ac3fe1f08618cc0c90b27133_3c4dcb0a`, one export for both call sites), but the
emitted body's import block is **identical and carries no descendant imports at all**, and both
`pt_a.css` and `pt_b.css` land in the page module:

```
.web/app_components/ptapp/ptapp.jsx : (no pt_*.css import)
.web/app/routes/_index.jsx          : import {} from "$/public/pt_a.css"
                                      import {} from "$/public/pt_b.css"
```

Direct probe of the pipeline confirms why: by the time `compile_experimental_component_memo` runs,
`definition.component.children` is already `[Bare]` — the `{children}` hole — so the
`render._get_all_imports()` at `compiler/utils.py:409` never sees the descendants. Both variants
produce tag `Holder_div_6676a43eefce286418b763dedd2146f2` and body imports
`['$/utils/context', '@emotion/react', 'react']`. **The divergence the PR flagged does not appear
in the shipped auto-memoization passthrough path**; worth confirming before spending a change on it.

---

## Issues

### ISSUE-1 — generated memo module names are not reproducible across identical compiles (MEDIUM, pre-existing)

Compiling unchanged source twice produces a **different memo export name and a different memo
body**, so every `reflex export`/deploy churns the compiled output even when nothing changed.

Repro (from the artifacts dir, no server):

```
cp -r memoapp memoapp_probe && rm -rf memoapp_probe/.web
./name_stability.sh $PWD/memoapp_probe $SB/envs/smoke/bin/reflex logs/stability_a1
```

35 memo names are emitted; 34 are identical across three compiles and two exports, one is not:

```
< export const Foreach_comp_495aa3a762e359a54363b43866abf848_21819d56
> export const Foreach_comp_cca7f1f62935f3f15c04969eb057398a_21819d56
```

Root cause, from diffing the two bodies (`logs/foreach_body_1.txt` vs `_2.txt`):

```
- const ref_row_reflex_Var_3940256426033130345_reflex_Var_i_rx_state_ = useRef(null); …
+ const ref_row_reflex_Var_5949624049744022204_reflex_Var_i_rx_state_ = useRef(null); …
```

`memoapp.py` builds `id=f"row-{i}"` inside an `rx.foreach`. Interpolating a `Var` into an f-string
yields a **string** carrying an internal marker that embeds `hash(var)`:

```python
>>> i = rx.Var("i_rx_state_", _var_type=int)
>>> f"row-{i}"
'row-<reflex.Var>-2417037821921509845</reflex.Var>i_rx_state_'
>>> format.format_ref(f"row-{i}")
'ref_row_reflex_Var_2417037821921509845_reflex_Var_i_rx_state_'
```

`Component._get_ref_hook` calls `format.format_ref(self.id)` (`reflex_base/components/component.py:2074`),
so Python's **per-process randomized string hash** ends up inside a generated JS identifier, inside
the memo body, and therefore inside the memo content hash. Pinning it removes the instability
completely — three compiles under `PYTHONHASHSEED=0` give the identical name
`Foreach_comp_f88140affc1e2f92b74111dd952e0fec_21819d56`.

Regression: **no** — identical on 0.9.10.post2 (`logs/stability_0910/`, the `Foreach_comp_*` name
changes on every compile there too). Downstream: no. Impact: non-reproducible builds and a
cache-bust of the changed chunk on every deploy; it also leaks a raw internal marker
(`reflex_Var_<hash>`) into an emitted identifier. Triggered by any dynamic `id=` built by
interpolating a Var — a common pattern inside `rx.foreach`.

### ISSUE-2 — two same-named `rx.ComponentState` subclasses in different modules crash the compile (MEDIUM, pre-existing)

Exactly the gap #6947 closed for memo names ("the defining module, so same-named components from
different modules stay apart") is still open for `ComponentState`: the dynamic substate name is
derived from `cls.__name__` alone.

```
reflex/state.py:2733-2734
    cls._per_component_state_instance_count += 1
    state_cls_name = f"{cls.__name__}_n{cls._per_component_state_instance_count}"
```

Repro (no server, ~5 s):

```
$SB/envs/smoke/bin/python probes/componentstate_collision.py smoke
```

Two modules each define `class Counter(rx.ComponentState)`; the **first** `Counter.create()` in
each module both mint `reflex.istate.dynamic.Counter_n1`:

```
first  ok -> reflex___state____state.reflex___istate___dynamic____counter_n1
second ERR StateValueError The substate class 'reflex___istate___dynamic____counter_n1' has been
            defined multiple times. Shadowing substate classes is not allowed.
```

In a real app this aborts the compile with `Happened while evaluating page 'samename'` and a
message that names neither module nor the `ComponentState` class the user wrote — the name in the
error (`counter_n1`) does not appear anywhere in their source. Hit while building this cluster's
app; `memoapp` works around it with distinctly-named `CounterA`/`CounterB` twins and keeps the
same-named `Counter` pair defined-but-unused in `mod_a.py`/`mod_b.py` so the collision stays
visible in the sources.

Regression: **no** — byte-identical failure on 0.9.10.post2 (`logs/cs_collision_0910.log`).
Downstream: no. A module-qualified dynamic name (or an error naming both defining modules) fixes it.

### ISSUE-3 — `rx._x.client_state(..., global_ref=False)` throws `ReferenceError` once auto-memoization splits its reader from its writer (MEDIUM, pre-existing)

A non-global `ClientStateVar` read in one component and written from another lands in **two
different memo bodies**; the `useState` hook is emitted only in the reader's body, so the writer's
`useCallback` closes over an undefined symbol. The click silently does nothing and the console
shows a hard `ReferenceError`.

Repro: `/foreach` in `memoapp`, button `#cs-btn` (the `#csg-btn` control right beside it uses the
default `global_ref=True` and works):

```python
cs = rx._x.client_state("memo_cs", default="cs0", global_ref=False)
...
cs_card(value=cs.value, tid="cs-out"),                                  # reader
rx.el.button("set-cs", on_click=cs.set_value("cs-clicked"), id="cs-btn")  # writer
```

Generated `.web/app_components/memoapp/memoapp.jsx`:

```
240: const [memo_cs, setMemo_cs] = useState("cs0")          <- inside Memocomponent_cscard_…
252: const on_click_… = useCallback(… setMemo_cs("cs-clicked") …)   <- inside Button_button_…
```

Browser: `PAGE ERROR: setMemo_cs is not defined`; `#cs-out` stays `cs0`. Driver check
`foreach.client_state_local_memo_prop`.

Regression: **no** — identical in dev and prod on 0.9.11a1 **and** in dev on 0.9.10.post2
(`logs/dev-0910-report.json` fails the same check with the same page error, and the 0.9.10 codegen
splits the hook and the setter across the same two memo bodies). Downstream: no. Either
`global_ref=False` should refuse to compile when its readers and writers fall in different
memoization domains, or the hook has to be hoisted to their common ancestor.

---

## Confirmations of findings already on record

- **FINDING-026** (`add_custom_code` JS touching `window` fails the prod build with an opaque
  prerender 500) reproduced exactly. With `add_custom_code` returning
  `window.MEMO_CODE_A = 'code-A';`, `reflex run --env prod` dies at
  `Error: Prerender: Request failed for /: Prerender (html): Received a 500 status code from
  entry.server.tsx while prerendering the / path` (`logs/prod_run_debug.log:239`) — note it names
  `/`, a page that does not even use the offending component, and never names the custom code.
  Changing the single word `window` to `globalThis` makes the identical build succeed
  (`logs/prod_run_debug2.log`). The app sources ship the `globalThis` form.

## Benign / self-inflicted observations

- 26 console errors and 4 `Hydration failed` page errors per dev run, on **both** versions
  (`26 / 5` on 0.9.11a1 and `26 / 5` on 0.9.10.post2). They are this test app's own doing: the two
  `WrapWidget` classes contribute `rx.text("a")` and `rx.text("bbbbb")` as app-wrap components, and
  the app-wrap mechanism nests them, so the root renders `<p>a<p>bbbbb…</p></p>` — invalid HTML that
  React reports as `<p> cannot contain a nested <p>`. Deliberate: it is what makes "both texts in
  the DOM" observable. In prod the same thing shows as four minified React #418 warnings.
- The auto-memoization pass mirrors a generated memo to the **page's** module, not to the
  component's defining module, so all of `custom_a.py`'s and `custom_b.py`'s widget memos compile
  into `.web/app_components/memoapp/memoapp.jsx` with the `_21819d56` suffix (sha1 of
  `memoapp.memoapp`). Correct — the per-module suffix exists to separate memos, and these are
  already separated by their content hash — but worth knowing when grepping the output.
- `MemoizedBadge_04c36749` appears in `reflex export` output and not in `reflex compile` output.
  Expected (the "Built with Reflex" badge is not in dev builds), noted so it is not mistaken for a
  naming instability in `logs/stability_*/`.
- `@rx.memo` functions are named through `memo_paths.mirrored_symbol` (`<Name>_<sha1(module)[:8]>`),
  not through `memo_tag`, so two same-named `@rx.memo` functions in two modules were already
  separated before #6947 (`Card_6a3335c9` vs `Card_d38f1d91` here). The clicks were still checked
  end to end on both versions and route to the right module's state.

---

## VERIFICATION: Generated memo module names are not reproducible across identical compiles: a dynamic `id=` inside rx.foreach leaks Python's randomized hash(Var) into the memo content hash

Independent adversarial verification (second agent, own working dir
`$SB/apps/verify2_memo_hash_0/`, own 12-line app built from the written repro — the claimant's
`memoapp` was NOT used).

**VERDICT: CONFIRMED as a genuine framework defect, but the root cause is sharper and the
stated impact is largely pre-empted by a separate, unconditional churn source.**

| claim | verdict |
|---|---|
| reproduces on 0.9.11a1 | **yes** — 5/5 identical compiles give 5 different memo names |
| mechanism is `hash(Var)` leaking through an f-string `id=` | **yes**, and pinned to an exact line |
| regression 0.9.10.post2 → 0.9.11a1 | **no** — reproduced on 0.9.10.post2 myself |
| "triggered by a dynamic `id=` inside `rx.foreach`" | **broader** — `rx.foreach` is incidental; any `id=f"…{Var}…"` does it |
| "API misuse / demo-app bug" | **no** — `id=f"…{Var}…"` is a supported, framework-tested pattern |
| "builds are not reproducible / every deploy cache-busts that chunk" | **overstated** — see the control below |
| severity medium | **downgraded to low** |

### Minimal repro (12 lines, no server, ~10 s per compile)

`verification/minapp/minapp/minapp.py` — the whole app:

```python
import reflex as rx


class S(rx.State):
    items: list[str] = ["a", "b", "c"]


def index():
    return rx.el.div(
        rx.foreach(
            S.items,
            lambda item, i: rx.el.div(item, id=f"row-{i}"),
        ),
    )


app = rx.App()
app.add_page(index)
```

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
cp -r verification/minapp /tmp/minapp && cd /tmp/minapp     # NOT inside the reflex checkout
../verify_memo_name_stability.sh $PWD $SB/envs/smoke/bin/reflex 5
```

Actual output (`verification/verify_memo_name_stability.sh`):

```
compile 1: export const Foreach_comp_58730a70adad6413ce8c6c40feb3cc0a_07e222f1  ref_row_reflex_Var_489848986948958380_reflex_Var_i_rx_state_
compile 2: export const Foreach_comp_5c1c977e6b54d4a4ef1f3c16779102a8_07e222f1  ref_row_reflex_Var_8408291360780197414_reflex_Var_i_rx_state_
compile 3: export const Foreach_comp_4bb01582f62fdaa91b3172a2cd913cb1_07e222f1  ref_row_reflex_Var_4376593243455648098_reflex_Var_i_rx_state_
compile 4: export const Foreach_comp_bca0a39b501179798fc2a3f779a6565d_07e222f1  ref_row_reflex_Var_8733017936324516820_reflex_Var_i_rx_state_
compile 5: export const Foreach_comp_a423e6c39e39bdb613d1712c7e5fa847_07e222f1  ref_row_reflex_Var_4888020598322629829_reflex_Var_i_rx_state_
```

Three compiles under `PYTHONHASHSEED=0` are all
`Foreach_comp_f73d48a43498a7266007009ccb87fe9a_07e222f1` with ref
`ref_row_reflex_Var_7755853664824147513_reflex_Var_i_rx_state_` — so `PYTHONHASHSEED` is the
only source of the drift, as claimed.

Baseline, same app source, `$SB/envs/base0910/bin/reflex` (reflex 0.9.10.post2 / reflex-base
0.9.10.post2), 3 compiles:
`Foreach_comp_995b15d8…` → `a98b64ac…` → `af154052…`. **Pre-existing, not a regression.**

### Root cause — more precise than the claim

The claim says `Component._get_ref_hook` "passes that string to `format.format_ref(self.id)`".
The real defect is one line earlier: `Component.get_ref` has a guard whose explicit purpose is
to skip exactly this case, and the guard does not fire.

`packages/reflex-base/src/reflex_base/components/component.py:2065-2074` on
`origin/r/pre-2026.09.10-34457666442` (identical in the installed 0.9.11a1 wheel):

```python
def get_ref(self) -> str | None:
    ...
    # do not create a ref if the id is dynamic or unspecified
    if self.id is None or isinstance(self.id, Var):
        return None
    return format.format_ref(self.id)
```

Interpolating a `Var` into an f-string yields a **`str`** carrying the internal
`<reflex.Var>{hash(var)}</reflex.Var>` marker, not a `Var`, so `isinstance(self.id, Var)` is
False and a ref is minted for a dynamic id — the opposite of what the comment says.
`verification/idtype.py` isolates it (run from a neutral cwd with `$SB/envs/smoke/bin/python`):

```
fstring id  : str 'row-<reflex.Var>-2065862635873230238</reflex.Var>i_rx_state_'
  get_ref   : ref_row_reflex_Var_2065862635873230238_reflex_Var_i_rx_state_   <-- BUG
Var id      : Var                get_ref: None                               <-- guard works
concat id   : ConcatVarOperation get_ref: None                               <-- guard works
static id   : str                get_ref: ref_row_static                     <-- correct
```

So only the f-string form defeats the guard; `id=rx.Var(...)` and `id="row-" + S.name` are
handled correctly. `format_ref` (`reflex_base/utils/format.py:651-662`) then squashes the
marker's non-word characters to underscores, and `_get_ref_hook`
(`component.py:1910-1922`) emits it as a `useRef` declaration plus a `refs[…]` registry key.

Generated body from the minimal app:

```jsx
export const Foreach_comp_6db40c554eee56477ac76c549829718f_07e222f1 = memo(({children}) => {
    const reflex___state____state__minapp___minapp___s = useContext(...)
const ref_row_reflex_Var_1475551538691358606_reflex_Var_i_rx_state_ = useRef(null); refs["ref_row_reflex_Var_1475551538691358606_reflex_Var_i_rx_state_"] = ...;
    return(
        Array.prototype.map.call(... ((item_rx_state_,i_rx_state_)=>(jsx("div",{id:("row-"+i_rx_state_),key:i_rx_state_,ref:ref_row_reflex_Var_1475551538691358606_reflex_Var_i_rx_state_},item_rx_state_))))
    )
});
```

Note the `id` prop itself compiles correctly to `("row-"+i_rx_state_)` — the pattern is
supported. The framework's own suite covers it:
`/home/user/reflex/tests/units/components/test_component.py:1303-1306` param `fstring-id`,
`rx.fragment(id=f"foo{TEST_VAR}bar")`. **Not API misuse, not a demo-app bug.**

### Not foreach-specific

`verification/minapp2` has no `rx.foreach` — one `rx.el.div("hello", id=f"row-{S.name}")` —
and drifts identically over 3 compiles:
`Div_div_9b638c77…` → `Div_div_4a189557…` → `Div_div_66d7d288…`. The claim's "inside
`rx.foreach`" framing is incidental; the trigger is the f-string `id=` alone.

### Where the claim overreaches: `reflex export` is ALREADY non-reproducible

The claim's impact is "`reflex export` of unchanged source produces a different memo module
name and body on every run, so every deploy cache-busts that chunk for no reason and builds
are not reproducible". Two exports of `minapp` do differ
(`verification/logs/build1_sums.txt` vs `build2_sums.txt`) — but so does the **control**.

Control: same app with `, id=f"row-{i}"` deleted (`verification/logs/noid_build1.txt` vs
`noid_build2.txt`). The memo name is now stable across both exports
(`Foreach_comp_95a52ca61d516cb58e302f4916b531e6_07e222f1` twice) and the build output **still
differs**: `_index-*.js`, `context-*.js`, `manifest-*.js`, `root-*.js`, `index.html`,
`404.html`, `server/index.js` all change filename and content.

Cause, isolated by diffing the built `context-*.js` chunk between two control exports:

```
1886c1886
< last_reflex_run_datetime=`2026-09-11 05:39:34.846396`
---
> last_reflex_run_datetime=`2026-09-11 05:39:38.482293`
```

`reflex/utils/prerequisites.py:190-195` `set_last_reflex_run_time()` writes a wall-clock
timestamp into `.web/reflex.json` on every run, and `.web/utils/state.js:4` does
`import reflexEnvironment from "$/reflex.json"`, so the timestamp is bundled into the client.
**Every Reflex production build is byte-different from the last one regardless of this bug**,
for every app. The dynamic-id leak adds one more changed chunk on top of churn that is already
unconditional, so "builds are not reproducible" is true but not attributable to this issue.
(The `reflex.json` timestamp is a separate observation, outside this cluster's scope.)

### Other things checked and ruled out

- **Stale-export accumulation**: 4 consecutive compiles *without* clearing `.web/app_components`
  leave the file at exactly 1 export / 1010 bytes each time, and `.web/app/routes/_index.jsx`
  always imports the current name. No unbounded growth, no dangling import.
- **Runtime breakage**: none. `reflex run --frontend-port 6040 --backend-port 10440` +
  headless Chromium: `div[id]` = `["row-0","row-1","row-2"]`, 0 page errors, console carries
  only the known-benign HydrateFallback / vite / React-DevTools lines. The generated
  identifier is valid JS, so the leak is codegen noise, not a crash.
- **Environment quirks**: none in play. No server needed for the core repro; proxy, ports and
  `NO_PROXY` are irrelevant to `reflex compile`. Confirmed the smoke venv is the one running
  (`assert "/envs/smoke/" in reflex.__file__`) and never ran python from the checkout — a bare
  `python -c "import reflex"` with cwd `/home/user/reflex` does pick up the checkout, which is
  why every command above uses a neutral cwd.
- **Flakiness**: the opposite of flaky — it fails on 100% of unseeded compiles (8/8 observed
  across two apps) and passes on 100% of `PYTHONHASHSEED=0` compiles (3/3).

### Residual real consequences (why this is still worth a ticket)

1. `get_ref`'s own stated invariant is violated: a ref is created for a dynamic id.
2. A dead `useRef` and a `refs["ref_row_reflex_Var_<random>_…"]` registry entry are emitted per
   dynamic-id component. The key embeds a per-process random number, so nothing can ever look
   it up.
3. Inside `rx.foreach` the single hoisted ref is attached to **every** row, so it can only ever
   point at the last one — a semantically wrong ref where the guard intended none.
4. A raw internal marker (`reflex_Var_<hash>`) leaks into an emitted JS identifier.
5. Auto-memo module names churn on every compile for any app using the pattern.

Suggested direction (not implemented — verifiers do not fix): make the guard recognise the
f-string form, e.g. resolve `self.id` through `LiteralVar.create`/`Var.create` and skip when the
result is not a literal string, rather than testing `isinstance(self.id, Var)`.

### Severity / regression / downstream

- **confirmed: true** (genuine defect, but not release-blocking)
- **severity: low** (claimant said medium) — no runtime error, no user-visible behaviour change,
  and the headline "non-reproducible builds" impact is already unconditionally true via the
  `reflex.json` timestamp
- **regression: false** — independently reproduced on 0.9.10.post2
- **downstream: false** — nothing outside `reflex`/`reflex-base` involved

### Exact commands run

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
W=$SB/apps/verify2_memo_hash_0

cd $W && $SB/envs/smoke/bin/python mech.py            # x3 unseeded, x3 PYTHONHASHSEED=0
cd $W && $SB/envs/smoke/bin/python idtype.py          # guard behaviour per id form

cd $W/minapp     && for i in 1 2 3 4 5; do rm -rf .web/app_components .web/utils/components; \
    REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex compile >/dev/null 2>&1; \
    grep -o 'export const Foreach[A-Za-z0-9_]*' .web/app_components/minapp/minapp.jsx; done
cd $W/minapp     && (same loop with PYTHONHASHSEED=0)
cd $W/minapp0910 && (same loop with $SB/envs/base0910/bin/reflex)      # baseline
cd $W/minapp2    && (same loop, no foreach)

cd $W/minapp      && rm -rf .web/build && $SB/envs/smoke/bin/reflex export --no-zip --frontend-only   # x2, md5 manifests
cd $W/minapp_noid && (same, id= removed)                                                              # x4, the control

cd $W/minapp && $SB/envs/smoke/bin/reflex run --frontend-port 6040 --backend-port 10440
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/drive.py http://localhost:6040 $W/logs/shot.png
```

Evidence: `verification/minapp/`, `verification/minapp2/`, `verification/mech.py`,
`verification/idtype.py`, `verification/verify_memo_name_stability.sh`,
`verification/logs/{build1,build2,noid_build1,noid_build2}_sums.txt`.
All processes started here were killed (`ps aux | grep 'reflex run'` clean of ports 6040/10440).

---

## VERIFICATION: Two same-named rx.ComponentState subclasses in different modules abort the compile — the dynamic substate name ignores the defining module

Independent adversarial verification (verifier `verify2_memo_hash_1`), 2026-09-11.
Reproduced from the written repro alone, in my own dir
`$SB/apps/verify2_memo_hash_1/`; the claimant's probe was read but re-implemented,
and their app source was NOT copied.

**VERDICT: CONFIRMED — genuine framework defect. Severity MEDIUM. NOT a regression
(byte-identical on 0.9.10.post2, verified by me). Downstream impact: NO (no upgrade
breakage; nothing in reflex/reflex-enterprise ships a `ComponentState` subclass that
could collide with user names). Not a release blocker for 0.9.11.**

### What I checked, and what I could not refute

Attempted refutations, all of which failed:

1. **Probe artefact?** The claimant's probe builds its two modules with
   `types.ModuleType` + `exec`, which is not how a user writes code. I rewrote it with
   two ordinary on-disk packages imported normally
   (`probes/pkg_one/widget.py`, `probes/pkg_two/widget.py`, each with a plain
   `class Counter(rx.ComponentState)`). Same failure — the module machinery is
   irrelevant, only `cls.__name__` matters.
2. **Only a script-level artefact, not a real app?** No. I built a fresh
   `reflex init --template blank` app (`csapp/`) with two user modules
   `csapp/widget_a.py` and `csapp/widget_b.py`, each defining `class Counter(rx.ComponentState)`,
   and one page rendering both. `reflex compile` exits 1.
3. **Environment quirk (proxy / ports / cwd shadowing)?** No — no server, no network, no
   ports involved; every probe asserts `"/envs/<venv>/" in reflex.__file__` and was run from
   a neutral dir. (Aside worth flagging to other agents: running
   `$SB/envs/smoke/bin/python -c "import reflex"` with cwd `/home/user/reflex` does load the
   checkout, `/home/user/reflex/reflex/__init__.py` — the AGENT_BRIEF hazard is real.)
4. **API misuse / documented behavior?** No. `docs/state_structure/component_state.md`
   documents no uniqueness requirement, and `ComponentState.create()` offers no way to
   name the dynamic state. The framework's *own* guard says this is not supposed to
   happen: `reflex/state.py:637` comments
   `# This should not happen, since we have added module prefix to state names in #3214`.
   Plain `rx.State` subclasses honour that module prefix and coexist fine; the
   `ComponentState` dynamic subclass throws it away.
5. **Regression from 0.9.11a1?** No. Verified myself on both the probe and the real app.
6. **Flaky?** No — deterministic for a given create() ordering (but see the ordering
   landmine below, which the original report missed).
7. **Already reported upstream?** `mcp__github__search_issues` over `reflex-dev/reflex`
   finds no existing issue for this collision (nearest neighbours: #3718, #6153 — both
   different ComponentState problems).

### Mechanism (release wheel = release branch, identical text)

`reflex/state.py:1182-1189` — every state's identity is module-qualified:

```python
@classmethod
def get_name(cls) -> str:
    module = cls.__module__.replace(".", "___")
    return format.to_snake_case(f"{module}___{cls.__name__}")
```

`reflex/state.py:2732-2740` (installed wheel `envs/smoke/.../reflex/state.py`, same line
numbers on `origin/r/pre-2026.09.10-34457666442`) — `ComponentState.create()` pins every
dynamic subclass to the *same* module and discards the defining one:

```python
cls._per_component_state_instance_count += 1
state_cls_name = f"{cls.__name__}_n{cls._per_component_state_instance_count}"
component_state = type(
    state_cls_name,
    (cls, State),
    {"__module__": reflex.istate.dynamic.__name__},   # <- module always reflex.istate.dynamic
    mixin=False,
)
```

`_per_component_state_instance_count` is a `ClassVar[int] = 0` (`state.py:2677`), and
`cls.<attr> += 1` binds a *fresh* counter on each subclass, so the first `create()` of
every `ComponentState` named `Counter`, in any module, mints
`reflex.istate.dynamic.Counter_n1` -> `reflex___istate___dynamic____counter_n1`. The
duplicate is then caught by the shadowing guard at `reflex/state.py:636-642`.

So the disambiguator the 0.9.11a1 memo work added for memo names ("the defining module,
so same-named components from different modules stay apart", reflex-base CHANGELOG
Bug Fixes #6947 — wording verified on the release branch) is indeed still missing here.
Confirmed the memo side works: `csapp_memo/` puts a same-named `@rx.memo def card` in both
modules and compiles clean, emitting them into separate
`.web/app_components/csapp/widget_a.jsx` / `widget_b.jsx`.

### Two things the original report did not cover

**(a) It is not really about modules — it is about the bare class name.** Two distinct
`ComponentState` subclasses that share `__name__` collide even when defined in the *same*
module (e.g. two classes named `Knob` created in two different factory functions). See
`probes/cs_variants.py`, case D. The report's "different modules" framing is a special
case of "same `__name__`".

**(b) The failure is order-dependent, so it is a latent landmine, not just a hard stop.**
The name depends only on the *per-class* instance count, so a same-named twin can
silently succeed once the counts stop overlapping (`probes/cs_interleave.py`):

```
mod_a.Slider #1                ok  -> reflex___istate___dynamic____slider_n1
mod_b.Slider #1                ERR StateValueError: ... slider_n1 ... defined multiple times
mod_b.Slider #2                ok  -> reflex___istate___dynamic____slider_n2
```

i.e. an app with two same-named `ComponentState`s can compile today and start failing
when someone adds (or removes) an instance elsewhere on an unrelated page. That makes the
bug harder to diagnose than a consistent failure would be, and is the main reason I keep
severity at MEDIUM rather than LOW.

### Diagnosability of the error (the real user cost)

The compile abort is:

```
reflex_base.utils.exceptions.StateValueError: The substate class
'reflex.istate.dynamic.CounterN1' Has Been Defined Multiple Times. Shadowing substate
classes is not allowed.
Happened while evaluating page 'samename'
```

Three separate problems for the user: it names neither defining module; it names neither
of the two user classes; and the identifier it does print (`CounterN1`, title-cased by the
console formatter from `counter_n1`) appears nowhere in the user's source and is not
greppable. The traceback does at least point at the `.create()` call site.

Mitigating: renaming either class is a complete fix and needs no framework change —
verified, `csapp_renamed/` (`widget_b.Counter` -> `widget_b.CounterB`) compiles clean in
4.0 s. And no published reflex/reflex-enterprise package ships a `ComponentState`
subclass (grepped both site-packages trees), so a user can always rename their own side.
Generic names are still plausible in a multi-module app — reflex's own docs define
`class Table(rx.ComponentState)` (`docs/library/tables-and-data-grids/table.md`), so two
copy-pasted recipes in two modules collide.

Suggested fix (unchanged from the report, and consistent with #3214's intent): fold
`cls.__module__` into `state_cls_name` — e.g.
`f"{cls.__module__.replace('.', '_')}_{cls.__name__}_n{count}"` or a short module digest —
keeping the `setattr(reflex.istate.dynamic, state_cls_name, ...)` pickle path working. At
minimum, raise from `ComponentState.create()` with a message naming both defining modules
and the user's class.

### Exact commands (all run from `$SB/apps/verify2_memo_hash_1/`, never the checkout)

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
export REFLEX_TELEMETRY_ENABLED=false
cd <this dir>/verification/componentstate_name_collision

# 1. real on-disk modules, no exec tricks (~2 s each)
$SB/envs/smoke/bin/python    probes/cs_collision_real.py smoke      # 0.9.11a1   -> second create ERR
$SB/envs/base0910/bin/python probes/cs_collision_real.py base0910   # 0.9.10.post2 -> identical ERR

# 2. variants: same class twice / same name+2 modules / distinct names / same name+same module
$SB/envs/smoke/bin/python probes/cs_variants.py smoke

# 3. the ordering landmine
$SB/envs/smoke/bin/python probes/cs_interleave.py smoke

# 4. contrast: plain rx.State with the same name in two modules coexists
$SB/envs/smoke/bin/python probes/plain_state_contrast.py smoke

# 5. real app, real compile abort (csapp/ is a plain `reflex init --template blank` app
#    where both widget_a.py and widget_b.py define `class Counter(rx.ComponentState)`)
cd csapp && $SB/envs/smoke/bin/reflex compile        # rc=1, StateValueError
cp -r csapp csapp_0910 && rm -rf csapp_0910/.web
cd csapp_0910 && $SB/envs/base0910/bin/reflex compile # rc=1, identical StateValueError
```

### Evidence (mine, under `verification/componentstate_name_collision/`)

| file | what it shows |
|---|---|
| `probes/cs_collision_real.py` + `probes/pkg_one/`, `probes/pkg_two/` | minimal repro with real modules |
| `probes/cs_variants.py`, `probes/cs_interleave.py`, `probes/plain_state_contrast.py` | scope of the collision, ordering landmine, rx.State contrast |
| `csapp/` | full app whose `reflex compile` aborts (`csapp/widget_a.py`, `csapp/widget_b.py`) |
| `logs/cs_real_a1.log`, `logs/cs_real_0910.log` | probe on both versions — identical |
| `logs/csapp_compile_a1.log`, `logs/csapp_compile_0910.log` | real compile abort on both versions |
| `logs/csapp_renamed_compile_a1.log` | rename workaround compiles clean (rc=0) |
| `logs/csapp_memo_compile_a1.log` | same-named `@rx.memo` in two modules compiles clean (the contrast) |
| `logs/cs_variants_a1.log`, `logs/cs_interleave_a1.log`, `logs/plain_state_contrast_a1.log` | the three probes above |

No servers or browsers were started for this verification (the defect aborts before a
server can start); nothing left running.

---

## VERIFICATION: rx._x.client_state(..., global_ref=False) throws ReferenceError once auto-memoization splits its reader from its writer

Independent adversarial verification (second agent, own app, own venvs, own ports 6048-6050 /
10448-10450). **Verdict: CONFIRMED as a real framework defect — but the claim's framing is wrong
on two points, and its scope is wider than reported.**

| Claim | Verdict |
| --- | --- |
| `global_ref=False` + reader/writer in different components -> `ReferenceError: set<Var> is not defined`, click silently does nothing | **CONFIRMED** (compile output + real Chromium, dev, 0.9.11a1) |
| Not a regression vs 0.9.10.post2 | **CONFIRMED** — and it also fails identically on **0.9.10.post2 and 0.8.28.post1**, so it is long-standing, not release-scoped |
| Caused by / adjacent to #6947 auto-memoization | **REFUTED** — reflex 0.8.28.post1 (legacy `StatefulComponent` pass, before the auto-memo rework) splits the same reader/writer into two sibling page-module functions and produces the byte-identical `setCs_b is not defined`. The new memoize plugin only changes *where* the two bodies live (exported memos in `$/app_components/...` instead of local functions in the route file). |
| Only `@rx.memo` call sites are affected | **REFUTED — the real scope is larger.** No `@rx.memo` is needed anywhere. A plain `rx.el.span(cs.value)` next to a plain `rx.el.button(on_click=cs.set_value(...))` fails the same way, and so does the canonical docs shape `rx.el.input(on_change=cs.set_value)` + sibling `rx.el.span(cs.value)`. |
| Suggested remedy "include the var in the common ancestor" | **Does not work.** The `create()` docstring says "The `ClientStateVar` should be included in the highest parent component … including it ensures that the `useState` hook is called in the correct scope." Putting `cs` in the parent div just mints a *third* memo body (a `Bare` wrapper) with its own `useState`; the writer still references an unbound symbol. |
| Severity medium | **Downgraded to low** for this release: pre-existing in every shipped version tested, behind `rx._x` (which prints "experimental features … might be removed at any time") *and* behind a deliberately non-default keyword; `global_ref=True` (the default) works. Genuine bug worth filing, not a 0.9.11 blocker. |

### Minimal repro (mine, from the written repro only — the claimant's app was not run)

`verification/clientstate_global_ref_split/minrepro` — one page per case, five `ClientStateVar`s
with `global_ref=False` plus one control with the default `global_ref=True`:

| Route | Shape | 0.9.11a1 | 0.9.10.post2 | 0.8.28.post1 |
| --- | --- | --- | --- | --- |
| `/a` | `@rx.memo` card reads `csa.value`, sibling button writes (the claimant's shape) | FAIL `setCs_a is not defined` | FAIL (same) | FAIL (same, compile evidence) |
| `/b` | **no memo at all** — `rx.el.span(csb.value)` + sibling `rx.el.button(on_click=csb.set_value(...))` | FAIL `setCs_b is not defined` | FAIL (same) | FAIL (same, browser-verified) |
| `/c` | same as `/a` but with `csc` included in the parent div (the docstring's prescribed usage) | FAIL `setCs_c is not defined` | FAIL (same) | FAIL (same, compile evidence) |
| `/d` | same as `/a` with the default `global_ref=True` | PASS | PASS | — |
| `/e` | reader *and* writer both inside the same `@rx.memo` body | PASS | PASS | — |
| `/f` | one element both reads and writes: `rx.el.input(value=csf.value, on_change=csf.set_value)` | PASS | PASS | — |
| `/g` | canonical docs shape: `rx.el.input(on_change=csg.set_value)` + sibling `rx.el.span(csg.value)` | FAIL `setCs_g is not defined` | FAIL (same) | FAIL (same, browser-verified) |

So the rule is: with `global_ref=False`, reader and writer must land in the *same generated JS
function body*. That is unobservable from Python — `/b` and `/g` are a single page function with
two sibling elements — and it is neither documented nor diagnosed. `reflex compile` exits 0 with
no warning; the only signal is a runtime `ReferenceError` in the browser console and a control
that does nothing.

### Exact commands

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
APP=$SB/apps/verify2_memo_hash_2/minrepro          # == verification/clientstate_global_ref_split/minrepro

# compile-only repro (no browser), 0.9.11a1
cd $APP && REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex compile
grep -n 'useState("a0")\|setCs_a(' .web/app_components/minrepro/minrepro.jsx
#  39: const [cs_a, setCs_a] = useState("a0")     <- inside Memocomponent_card_..._fd6b33c0...
#  51: ... useCallback(... setCs_a("a-clicked") ...)   <- inside Button_button_3eb7a18d...

# browser repro, 0.9.11a1 dev
cd $APP && REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run \
  --frontend-port 6048 --backend-port 10448 > $SB/apps/verify2_memo_hash_2/logs/dev-a1-run.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py http://localhost:6048/a \
  --actions "$(cat verification/clientstate_global_ref_split/actions_a.json)" --report logs/a1-case-a.json
# ... same for /b /c /d /e /f /g with actions_<case>.json

# baseline 0.9.10.post2 (copy of the same sources, port 6049/10449)
cd $SB/apps/verify2_memo_hash_2/minrepro_0910 && REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/base0910/bin/reflex run --frontend-port 6049 --backend-port 10449 &

# baseline 0.8.28.post1 (pre-auto-memoization), port 6050/10450
uv venv $SB/envs/verify2_memo_hash_2 --python 3.11
cd $SB && uv pip install --python $SB/envs/verify2_memo_hash_2/bin/python 'reflex==0.8.*'   # -> 0.8.28.post1
cd $SB/apps/verify2_memo_hash_2/minrepro_08 && REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/verify2_memo_hash_2/bin/reflex run --frontend-port 6050 --backend-port 10450 &
```

### Mechanism (release source, `origin/r/pre-2026.09.10-34457666442`)

1. `reflex/experimental/client_state.py:211` — the **reader** (`value`) is built as
   `Var(_js_expr=js_expr, _var_data=self._var_data)`, so it carries the
   `const [<var>, set<Var>] = useState(<default>)` hook in its `VarData.hooks`.
2. `reflex/experimental/client_state.py:226-230` — the **writer** (`set_value`) for the non-global
   case is `Var(self._setter_name)`, a bare identifier **with no `_var_data`**. The hook therefore
   never travels with the writer. (The `global_ref=True` arm instead emits
   `refs['_client_state_set<Var>']`, a module-level `refs` lookup, which is why the default works.)
3. `reflex/compiler/plugins/memoize.py:204-205` (`_should_memoize`: "Components with event triggers
   are always memoized (to wrap callbacks)") puts the writer in its own memo function body, and
   `memoize.py:157-169` puts a hooks-carrying `Bare` (the reader) in a *different* one. Whichever
   body carries the hook, the other one closes over an unbound identifier.
4. Attaching `self._var_data` to the setter in (2) would **not** fix it: hooks are deduped per
   rendering body, so each body would get its own independent `useState`. `/c` already shows two
   independent `const [cs_c, setCs_c] = useState("c0")` lines in two memo bodies
   (`logs/gen-a1-app_components-minrepro.jsx:87` and `:99`) — two separate React states for one
   `ClientStateVar`, which is silently wrong even for two *readers*. A real fix must hoist the hook
   to the nearest common rendering ancestor, or reject the configuration at compile time with an
   error pointing at `global_ref=True`.

Note that the framework's own unit test `tests/units/compiler/test_memoize_plugin.py:2369`
(`test_client_state_value_inside_snapshot_boundary_is_memoized`, parametrized over `global_ref`)
asserts that the client-state `useState` **must** live inside the memo body and not in the page —
i.e. the reader half of this behavior is currently pinned by a test. Only the reader is covered;
nothing covers a writer in a different body.

### Refutation attempts that failed to explain it away

- Not an environment quirk: reproduces from `reflex compile` output alone with no server, no
  browser, no proxy involved.
- Not the claimant's app: reproduced from the written repro in a fresh 60-line app.
- Not `@rx.memo` misuse: `/b` and `/g` contain no `@rx.memo`.
- Not documented behavior: the only published `ClientStateVar` example in the repo
  (`docs/wrapping-react/overview.md:74-88`) is exactly this shape — var included in the parent
  `rx.box`, read by one child, written by another sibling — and works only because it uses the
  default `global_ref=True`.
- Not flaky: 7/7 cases deterministic across three reflex versions.
- Not downstream-affecting: no `global_ref` usage anywhere in `/home/user/reflex-enterprise`
  (its `client_state` hits are OAuth `client_state`, unrelated), and it is opt-in via `rx._x`.

### Evidence

- App: `verification/clientstate_global_ref_split/minrepro/minrepro/minrepro.py`
- Playwright action files: `verification/clientstate_global_ref_split/actions_[a-g].json`
- Per-case driver reports (console/page-errors/failed requests):
  `verification/clientstate_global_ref_split/logs/a1-case-[a-g].json`,
  `.../logs/0910-case-[a-g].json`, `.../logs/0828-case-{b,g}.json`
- Screenshots after the click/fill: `verification/clientstate_global_ref_split/shots/[a-g]-after.png`
- Generated JS: `.../logs/gen-a1-app_components-minrepro.jsx` (0.9.11a1),
  `.../logs/gen-0910-app_components-minrepro.jsx` (0.9.10.post2, identical modulo content hashes),
  `.../logs/gen-0828-route-{b,g}.jsx` (0.8.28.post1, same split as two sibling page-module functions)

### Recommendation

Keep it off the 0.9.11 blocker list (pre-existing since at least 0.8.28, experimental API, non-default
flag). File it as a standalone bug against `rx._x.client_state`: either hoist the non-global
`useState` to the nearest common rendering ancestor of all its readers and writers, or make the
compiler raise when a non-global `ClientStateVar`'s readers and writers do not share a rendering
body, naming `global_ref=True` as the fix. A doc note on `global_ref=False` ("reader and writer must
be in the same component") would be the cheap interim mitigation.
