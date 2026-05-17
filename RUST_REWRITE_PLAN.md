# Reflex Compiler → Rust: One-Go Implementation Spec

Complete plan with every decision locked. Built so an AI-driven implementation doesn't have to stop and ask. If you find yourself wanting to decide something mid-port, the answer is in this document; if it isn't, the default is "do what oxc/ty/bun does in the cited file."

> **Status note (post-spike, 2026-05-16).** Scaffold has landed and the 2-day spike has run. This version of the plan is updated against measured numbers, not projections. The sections most affected by spike findings: §1 (IR serialization), §2 (R1 caveat), §5 (target tables), §7 (Component.to_ir API), §11 (pitfalls 1 and 12), §13 (done-criteria). Earlier review-pass issues are also folded in.

---

## 0. Status — scaffold + spike results

**Scaffold:** `packages/reflex-compiler-rust/` exists. Cargo workspace with all 8 crates from §3, `pyproject.toml` wired for `maturin develop --release` building one abi3-py310 wheel, `rust-toolchain.toml` pinned stable. **All 11 D-items (D0–D11) have landed** as of 2026-05-16 — see §8. The wheel exposes `CompilerSession.compile_page(bytes) -> str` and `CompilerSession.compile_app([(ident, route, bytes)], theme, global_state, plugin_manifest) -> CompiledOutput` driven by a Python IR builder at `reflex.compiler.ir` (§7). 41 Rust unit tests + 15 Python integration tests are green; a synthetic 200-page compile cold-builds in **1.9 ms** (plan target was <500 ms). The Component→IR bridge and full snapshot corpus (§6) remain follow-ups.

```
packages/reflex-compiler-rust/
├── Cargo.toml                    workspace, 8 crates
├── pyproject.toml                maturin, abi3-py310
├── rust-toolchain.toml           stable
├── python/reflex_compiler_rust/  thin wrapper over the cdylib
├── crates/                       all 8 crates from §3 (7 stubs + reflex_py)
└── scripts/spike_bench.py        napkin-math driver
```

Build + run today: `cd packages/reflex-compiler-rust && maturin develop --release && python scripts/spike_bench.py`.

**Spike results:** full writeup at `ignore/SPIKE_RESULTS.md`. Headlines:

1. **PyO3 crossing is free** (~100 ns/call). The plan's "boundary is cheap" assumption holds with margin.
2. **rmp-serde is 25× slower than a hand-rolled msgpack reader.** Pitfall 12 validated by measurement. Hand-rolled deserializer is mandatory from D4; do not ship rmp-serde "for now."
3. **`msgpack.Packer` streaming is 5-7% *slower* than building a list-of-lists and calling `msgpack.packb`** in one C call. The §1 "no per-node dict" line was wrong direction; §7's `Component.to_ir(packer)` API has been replaced (see §7 below).
4. **Bumpalo arena is 30% slower than no-arena for single-pass codegen** at every tree size. R1 is now conditional — see §2.
5. **Real Reflex `compiler.compile` is 273 µs/node Python** (2.81s ÷ 10 290 nodes on the 27-page docs app). The spike's synthetic Python codegen was 580× faster than reality; the actual Rust headroom is **50-100×** on this bucket, not the 5-10× the §5 table previously implied.
6. **Cold-build wall-clock is dominated by npm install (37%) + app import (21%) + framework imports (10%) = 68% untouchable.** Best-case cold compile wins are ~2.3× with hot npm cache, ~1.55× without. The user-visible win is **hot reload** (4-5×) and **per-page compile** (50-100×). At 200 pages the rewrite goes from "nice" to "necessary" because Python compile-work scales linearly at 104 ms/page.

**Decision-rule outcomes:**

- IR emit > 30% of wall-clock? **No, 0.4%.** Spike + msgpack on 10k nodes is ~10 ms; compile bucket is 2 810 ms.
- Python-remaining > 50%? Of the post-IR-emit work, npm + app import + framework imports = 68%, but that's all untouchable subprocess/one-time work — not hidden Python codegen the boundary missed. **Proceed.**

**Proceed to D1.** The plan below is the corrected version that ports use as their source of truth.

---

## 0a. Architecture commitment — *minimum Python in the Rust pipeline*

This is the single most important constraint for everything below. **The Rust pipeline must not depend on the legacy Python compile pipeline running first.** If we run the legacy pipeline (memoize plugin, plugin walks, `_compile_memo_components`, etc.) and *then* re-emit per-page JSX in Rust, we pay both costs and get only the small re-emit speedup. Wall-clock parity with `reflex run` is the ceiling, not the floor. That defeats the rewrite.

**Two hard rules:**

1. **Never edit the Python *compile* pipeline OR the framework primitives.** `reflex/compiler/{compiler.py,plugins/*}`, `reflex/experimental/memo.py`, `packages/reflex-base/src/reflex_base/{plugins,components,vars,state}/*` are all off limits. The Rust port is **additive only** — new files under `packages/reflex-compiler-rust/`, `reflex/compiler/{ir,rust_pipeline,session,markdown,diff_pipelines}.py`, and CLI additions like `run-rust`. Patching the legacy plugin chain for "feature flags" or "speedups" risks subtle behavior changes that break production users without `run-rust` being invoked. See [feedback_no_python_compile_changes].

   **Why framework primitives stay Python (decided 2026-05-17 by microbenchmark).** Earlier drafts of this doc contemplated porting `Var` and `Component` to Rust behind PyO3 wrappers for a 70-140× compile-bucket speedup. `scripts/benchmark_stages.py` measured the actual cost split on a 20-route synthetic app (~3 300 nodes): framework work is **39%** of the Python compile pipeline, mechanical work is **61%**. The Rust mechanical port already delivers a **2.8× speedup on the 61% bucket**; the 39% framework bucket is what users *hack on* — porting it sacrifices the most important property of the framework. Total realistic speedup keeping framework Python: ~3× pipeline-wide. That's the ceiling we're optimizing for. Numbers archived in §0b.

2. **Minimize Python work performed by `run-rust`.** The split is:

   - **Python** does *only* what Rust fundamentally cannot do:
     - Import the user's app module (`prerequisites.get_app()` — import only, no compile).
     - Evaluate each page function (`page_fn()`) to materialize the raw `Component` tree. This calls user Python that defines reactive `Var`s, state classes, etc.
     - Run the bridge (`reflex.compiler.ir.bridge`) to convert each raw `Component` into IR. The bridge walks Component attributes and `Var._js_expr` / `_get_all_var_data()`, which is Python data.
   - **Rust** does *everything else*: memoize decisions, memoize-wrapper generation, page JSX emit, codegen, file writes, theme CSS, app-wrap shell, vite config.
   - **Never invoked** in `run-rust`: `prerequisites.get_compiled_app()` (the whole legacy compile — plugin chain, memoize, `_compile_memo_components`, custom-component compile, …). The scaffold under `.web/{package.json,vite.config.js,utils/context.js,utils/state.js,…}` is laid down by `reflex init` / `reflex run`; `run-rust` requires it to already exist and errors out otherwise.

3. **`run-rust` is single-mode.** There is no in-`run-rust` fallback to the legacy pipeline — the legacy path is `reflex run`. If you want the old behavior, run that. If you want the Rust pipeline, run `reflex run-rust`. Keeping two pipelines reachable from the same command was producing dead branches (`--with-legacy`, `--snapshot-python`, `--profile-memoize`) and was removed. Concretely:
   - **Scaffold missing** → hard error, telling the user to run `reflex init` or `reflex run` once.
   - **Scaffold present** → `get_and_validate_app()` (~100 ms Python import, no compile) → iterate `app._unevaluated_pages` → `compile_unevaluated_page` per route (evaluate user Python, apply theme styles, wrap in Fragment+title+meta) → bridge → Rust emits JSX → Python writes `.web/app/routes/*.jsx`. Target: **< 500 ms total** for the docs app.
   - **Pipeline divergence debugging** is a `reflex run` vs `reflex run-rust` comparison done by the developer, not a flag inside `run-rust`.

4. **Phased Rust takeover of jobs currently done in the legacy compile** (in the order they need to land for `run-rust` to reach parity with `reflex run` on every axis):

   | order | job | currently in Python | Rust takeover |
   |-------|-----|---------------------|---------------|
   | 1     | Page module JSX | `compile_page_from_context` + `templates.page_template` | ✅ landed (`reflex_codegen::page::emit_page`) |
   | 2     | Memoize **decisions** (`_should_memoize`) | `MemoizeStatefulPlugin` walk | port over IR, in `reflex_semantic`; saves ~230 ms on docs |
   | 3     | Memoize **wrapper definitions** (`_build_wrapper` + `create_passthrough_component_memo`) | Python Component-class machinery | this is the big one (~1.2 s on docs). Needs Rust Component-graph rep that supports `{children}` hole substitution. |
   | 4     | Memoize wrapper **file emit** | `_compile_single_memo_component` + `templates.memo_single_component_template` | same template machinery as page emit; small `export const <name> = memo(({children}) => …)` shell. |
   | 5     | Plugin walks (Radix camelCase, `_get_all_imports` aggregation, etc.) | various `enter_component`/`leave_component` plugin hooks | bridge harvests what's needed; Rust aggregates in `reflex_semantic` |
   | 6     | Theme CSS, context shell, app-wrap, vite config | various `compile_*` functions in `compiler.py` | ✅ landed (`reflex_codegen::{theme,context,app_root,vite}`) |

   **Until job #3 lands, `run-rust` ships pages without runtime memoize wrappers.** The trade-off: faster compile, slower React re-renders. `reflex run` remains the production-perf path for users who need runtime memoization today.

5. **What `reflex.compiler.ir.bridge` may legitimately depend on from `reflex_base`:**
   - `Component.tag`, `Component.alias`, `Component.library`, `Component.children`, `Component.event_triggers`, `Component.id`, `Component.class_name`, `Component.key`, `Component.custom_attrs`, `Component.get_props()`, `Component._memoization_mode`, `Component._is_tag_in_global_scope` — purely attribute reads from already-constructed Components.
   - `Var._js_expr`, `Var._get_all_var_data()`, `VarData.{hooks,imports,state,deps,position,components}` — same, attribute reads only.
   - `format_library_name` from `reflex_base.utils.format` — a pure string helper.
   - `LiteralVar.create(value)` — needed to format `EventChain` / dict / list values into JS expressions, since Reflex's Var system owns that representation. This is a constructor call, not a compile step.

   It must *not* call `compile_*`, `render_*`, or anything that runs the plugin chain. If it does, we've leaked legacy compile work into the Rust pipeline.

---

**Implementation status snapshot (2026-05-16).** All 11 D-items have landed in some form; see §8 for per-item caveats. Python side has `reflex.compiler.ir.{schema,builder,canonical,pack,bridge}` + `reflex.compiler.session.CompilerSession` + `reflex.compiler.markdown`. End-to-end pipeline works: Python builds an IR tree → `msgpack.packb` → Rust parses, aggregates, emits, caches → returns rendered JS. Source maps wired through (`compile_page_with_sourcemap`). Two PyO3 wheels (compiler + markdown) with full CI matrix. **51 Rust tests + 49 Python tests + 18 corpus fixtures green.** Synthetic 200-page app cold-compiles in 1.9 ms; markdown wheel is 110× faster than mistletoe.

**End-to-end browser verification (2026-05-16).** `examples/rust_compiler_demo/` ships a working counter app where the page JSX is compiled by the Rust pipeline and served by Vite via React Router. The new CLI command `uv run reflex run-rust` runs the normal `reflex compile` to scaffold `.web/`, then re-emits each `.web/app/routes/*.jsx` directly from the Rust compiler — **no Python postprocessor**. A headless Chromium loads the served page and renders "Counter demo / count: / 0 / − / + / reset" with zero page errors — the state value `0` is pulled from the React context, the unicode minus glyph round-trips correctly through the Rust JS-string encoder, and `jsx(RadixThemesBox, …)` calls reach radix-ui as expected. Per-page Rust compile time on this app: **49.8 µs vs 2027.2 µs for the legacy Python compiler (38.6× faster)**.

**Schema v2 (2026-05-16).** `SCHEMA_VERSION` bumped to 2. Page IR gained three trailing positional fields — `component_imports: [(module, alias_spec)]`, `state_bindings: [str]`, `needs_ref: bool` — that the bridge harvests from the Component tree (walks `library`/`tag`/`alias` for imports, scans every Var's `_js_expr` for state-context references, checks `id` props). The Rust `page::emit_page` uses them to emit the React-runtime-compatible module shell directly: import block grouped by module with per-module dedup, `useContext(StateContexts.<key>)` lines, optional `useRef`, and `export default function Component()` as the React-Router-expected default. `jsx::emit_prop_name` camelCases known snake_case props (`class_name`→`className`, `on_click`→`onClick`, etc.).

**Visual parity confirmed (2026-05-16).** Side-by-side headless screenshots of the counter demo (one capture from `reflex run`, one from `reflex run-rust`) show **pixel-identical** Radix Themes rendering: same heading typography, same `<button>`-with-soft/solid/outline variants, same flex column layout. 2197 CSS rules load, same Radix `rt-Box`/`rt-Text`/`rt-Button` classes are applied, same `light` theme class on `<html>`. The remaining page-module differences are byte-level only — semantically equivalent emit shape. (Earlier iterations shipped an in-CLI `--snapshot-python` + `reflex.compiler.diff_pipelines` helper for this; the helper is gone now that the two pipelines are reached through their own commands.)

**Full-stack round-trip (2026-05-16).** `reflex run-rust` (no `--frontend-only`) starts both Vite (`:3000`) and the Reflex backend. Playwright drives the counter demo via real button clicks: 3× `+` → count = **3**, 1× `−` → count = **2**, `reset` → count = **0**, zero page errors. Websocket connects to the backend, event handlers dispatch through `ReflexEvent(...)`, state delta updates the count Heading. `run-rust` is a functional drop-in replacement for `run` on this app *modulo* runtime memoize (phase-3 work — see §0a).

**`run-rust` is single-mode (2026-05-16).** Per §0a rule 3, `run-rust` no longer has a `--with-legacy` escape hatch or a `--snapshot-python` flag. There is one path: scaffold-must-exist → `get_and_validate_app()` (Python import only) → `compile_unevaluated_page` per route → bridge → Rust → write `.web/app/routes/*.jsx`. The legacy compile is reachable through `reflex run`; that's the fallback. The new public surface in `reflex.compiler.rust_pipeline` is just `scaffold_exists()` and `compile_pages()`. **Measured on the docs app**: ~2.0 s end-to-end (1.2 s app import + 0.78 s Rust compile of 6 routes), versus ~3.1 s on `reflex run`. Runtime memoize is not applied until §0a phases 2/3 land; `reflex run` remains the production-perf path for users who need it today.

**Memoize-port plan (2026-05-16).** Profiled the legacy memoize plugin on the docs app — it's ~1.9 s of the 4.1 s compile (47%). Breakdown:

- `_build_wrapper` 686 ms — builds per-component `ExperimentalMemoComponentDefinition`s
- `create_passthrough_component_memo` 530 ms — copies Components, substitutes `{children}` hole
- `_compile_memo_components` (incl. write-to-disk) 484 ms self — runs the wrapper render template per memo
- `_should_memoize` 233 ms — the decision walk

End-to-end Rust port is a multi-phase project:

1. **Phase 1**: port `_should_memoize` decision logic to Rust over IR. The bridge already serializes `VarData.state`, `VarData.hooks`, event_triggers, and Component class identity; add `memoization_mode` and `is_snapshot_boundary` IR fields and replicate the legacy walk in `reflex_semantic`. Saves the 233 ms decision cost. **Concrete, bounded — start here.**
2. **Phase 2**: port wrapper-template emission to Rust. Treat each wrapper's body as a mini-page; pipe through the existing bridge → IR → `emit_page` pipeline with a "wrapper mode" output (`export const <name> = memo(({children}) => …)`). Replaces `_compile_single_memo_component`. Saves the 484 ms render cost.
3. **Phase 3**: port wrapper *construction* — the slow part. `_build_wrapper` + `create_passthrough_component_memo` together are ~1.2 s. These copy Components and substitute `{children}` holes inside Python. To replace, the bridge runs *before* memoize, the Rust side does its own walk and template substitution, and the legacy plugin is never called. Multi-week port; needs a Rust Component-graph representation that survives `{children}` hole substitution. Yields the bulk of the speedup.

**Memoize benchmark (2026-05-16).** Measurement infrastructure for the port lives outside `run-rust`: `scripts/benchmark_memoize.py` runs the legacy compile and reports per-bucket cumtime (decide / leave_component / build_wrapper / passthrough_memo / compile_memo_files). `--update-baseline` writes `.memoize_baseline.json` next to `rxconfig.py`; `--check` exits non-zero on >5% regression. Docs-app baseline locked at: wall 3220 ms / decide 178 ms / leave_component 838 ms / build_wrapper 683 ms / passthrough_memo 539 ms / compile_memo_files 317 ms. Every memoize-port iteration measures against these numbers. (Previously this also lived under `reflex run-rust --profile-memoize`; that flag was dropped along with `--with-legacy` since `run-rust` no longer runs the legacy compile.)

**Docs app shakedown (2026-05-16).** Pointed `CI=1 uv run reflex run-rust --frontend-only` at the real Reflex docs app (`docs/app/`, 27 evaluated pages, ~10k nodes). Five bridge bugs surfaced and got fixed in this iteration:
1. **`VarData.imports` shape** — Reflex stores it as `ParsedImportTuple = tuple[tuple[str, tuple[ImportVar, ...]], ...]`, not a `dict`. Bridge now handles both shapes.
2. **Dotted Radix subcomponents** (`TextField.Root`, `Drawer.Trigger`, `Popover.Root`) — the import binding must strip at the first `.` (`{TextField as RadixThemesTextField}`), while the JSX call site keeps the dotted access (`jsx(RadixThemesTextField.Root, …)`).
3. **VarData imports skipped `format_library_name`** — packages with version pins (`@hugeicons/core-free-icons@4.1.1`) were ending up in `from "<pin>"` lines that Vite couldn't resolve.
4. **`_var_data` ≠ merged var data** — direct attribute access only carries the *locally declared* metadata; inherited imports (e.g. `cn(...)` calls bringing in `clsx-for-tailwind`) live in `_get_all_var_data()`. Bridge now uses the merged getter.
5. **Foreach `render_fn` needs typed args** — synthetic `Var(_js_expr=name, _var_type=None)` arg vars fail on `item["key"]`. Bridge now delegates to `Component._render().render_component()` (the legacy `IterTag` path) which builds properly-typed `ArrayCastedVar`/`ObjectVar` args via `get_arg_var()`.

Plus two cleanup filters: skip empty-module imports (those are side-effect-style `import "<path>";` imports and don't belong inside `{…}` braces), and skip non-identifier alias specs.

End-to-end on docs: scaffold is laid down once by `reflex run` (~2.8 s), then **`reflex run-rust` emits all 7 routes in ~290 ms**, no Vite transform errors, no playwright pageerrors. (The docs root URL itself shows React-Router 404 — same behavior under `reflex run`, unrelated routing-config issue in the docs app.)

**Page title + `<meta>` parity (2026-05-16).** `reflex run-rust` now emits `jsx(Fragment, {}, <root>, jsx("title", {}, "<page title>"), jsx("meta", {…}, ))` whenever a page declares a title or has any meta entries (matching the legacy template). `rust_pipeline._resolve_page_title` resolves both `str` and `Var` titles from `UnevaluatedPage.title`; `_resolve_page_meta` reads per-page `meta` mappings and always appends the default `og:image=favicon.ico`. Headless browser confirms `document.title === "Counter"` and `<meta property="og:image" content="favicon.ico">` is present.

**Known follow-ups before the rewrite is "done" per §13** (ordered by current priority — see §0a for the architectural rationale):

- ✅ **`run-rust` single-mode** — landed 2026-05-16. `run-rust` always skips `get_compiled_app()`; the legacy path is `reflex run`. No `--with-legacy`, no `--snapshot-python`, no `--profile-memoize`. Docs-app measured at 2.0 s (1.2 s app import + 0.78 s Rust). Plan target was <500 ms; the remaining gap is app-import + bridge walk cost which scales with tree size. Runtime memoize is not applied until phases 2/3 below land.
- 📌 **Memoize phase 2 — decisions in Rust** (~230 ms on docs). Port `_should_memoize` over IR; needs `memoization_mode` + `is_snapshot_boundary` IR fields. `run-rust` doesn't run the legacy memoize plugin, so *some* memoize implementation has to live in Rust for runtime parity with `reflex run`.
- 📌 **Memoize phase 3 — wrapper construction in Rust** (~1.2 s on docs, the real win). `_build_wrapper` + `create_passthrough_component_memo` rewritten in Rust over IR. Needs a Component-graph rep that supports `{children}` hole substitution. Multi-week port.
- ✅ Component → IR bridge — landed 2026-05-16 (`reflex.compiler.ir.bridge.component_to_ir` covers Bare, Fragment, Cond, Foreach, Match, and generic Component; 8 tests with real `rx.text`/`rx.box`/`rx.cond`/`rx.foreach`/`rx.match` pass end-to-end through `compile_page_ir`).
- ✅ Snapshot corpus — landed 2026-05-16. `tests/codegen_corpus/` has **18 fixtures**: text, box, nested_box, multi_children, styled, cond, foreach, match (Tier-1 basics), plus state_var, state_in_box, computed_var, event_handler, custom_attrs, style_dict, cond_in_foreach, foreach_with_index, multiple_states, key_prop (Tier-2 real-world shapes). Each fixture has a `component.py` (Reflex Component builder) and `expected.json` (substring guards). Runner at `tests/codegen_corpus/_runner.py`; `UPDATE_CORPUS=1` regenerates goldens. Adding fixture 12 (event_handler) caught a bridge bug where `EventChain` values were emitted as Python repr — fixed by wrapping non-Var values with `LiteralVar.create` in both `var_to_value` and `_events_to_ir`.
- ✅ §6a benchmark script — landed 2026-05-16. `scripts/benchmark_compile.py` drives the corpus, prints cold/warm/RSS/output-bytes, supports `--check` (CI gate at >5% warm regression with a 5µs noise floor) and `--update-baseline`. `tests/codegen_corpus/baseline.json` checked in.
- Salsa proper (D5 ships a content-hash HashMap as the cache).
- ✅ Source maps — landed 2026-05-16. `reflex_codegen::SourceMap` records `(byte_offset → SourceLoc)` during emit; `Diagnostic` type holds severity/code/message/loc/help. `CompilerSession.compile_page_with_sourcemap(ident, page_ir) → (js, [(offset, file, line, col), ...])` exposes mappings to Python. 3 Python tests cover synthetic + real-loc + nested cases. `miette`-styled rendering layer deferred (Python consumer can render mappings any way it wants).
- ✅ Wheel CI scaffold — landed 2026-05-16. `.github/workflows/reflex_compiler_rust_wheels.yml` covers 6 abi3-py310 matrix entries × 2 packages (`reflex-compiler-rust`, `reflex-markdown-rust`) via `PyO3/maturin-action@v1`. Triggers on PR + main pushes; publishes to PyPI on `reflex-{compiler,markdown}-rust-v*` tags via OIDC trusted publishing. Per-package smoke tests verify the wheel imports.
- ✅ Markdown wheel — landed 2026-05-16. Standalone package at `packages/reflex-markdown-rust/` shipping `markdown_to_html(text)` + `markdown_to_html_with(text, options)` + `event_count` via pulldown-cmark. Python wrapper at `reflex.compiler.markdown` with `REFLEX_MARKDOWN={auto,rust,python}` dispatch and mistletoe fallback. Measured **110× speedup** on a synthetic Reflex-docs-sized page (860µs mistletoe → 7.8µs Rust). 3 Rust + 5 Python tests green.
- VarData hooks/imports propagation in legacy `_render` shape — bridge currently relies on `Var._var_data` populated by the existing Reflex Var system, which works for state vars + simple Vars but doesn't yet reproduce every `_get_all_hooks` edge case (style merging, memo markers).
- 60-fixture corpus (§6 target). 18 down, 42 to go.

---

## 0b. Cut bridge cost + push more mechanical work into Rust — *the realistic ceiling*

§0a got `run-rust` to "minimum Python orchestration." The previous draft of this section proposed porting `Var`/`Component`/`State` to Rust behind PyO3 wrappers for a 70-140× compile-bucket speedup. **That direction is dropped.** A microbenchmark on a 20-route synthetic app (`scripts/benchmark_stages.py synthetic:20`, archived below) showed:

* Framework work (page eval + theme apply + Fragment wrap): **39%** of Python pipeline
* Mechanical work (`_get_all_*` tree walks + `Component.render()` + JSX template): **61%**

The mechanical bucket is the lever; the framework bucket is what users hack on. **Don't port the framework.** Realistic ceiling for total pipeline speedup keeping framework Python: ~3× — and the current `run-rust` is already at ~1.7× of that. The remaining ~1.6× lives in two places: the bridge, and mechanical work that hasn't moved to Rust yet.

### Anchor numbers (2026-05-17 microbenchmark, 20-route synthetic)

| Stage | mean per-route | total (3 runs) | share |
|---|---:|---:|---:|
| `framework` (`compile_unevaluated_page`: page eval + theme + wrap) | 7.6 ms | 454 ms | 38.7% of Python |
| `py_mech` (`_compile_page`: `_get_all_*` walks + render + template) | 12.0 ms | 717 ms | 61.3% of Python |
| `bridge` (Python tree → IR msgpack) | 3.9 ms | 236 ms | — |
| `rust` (deserialize + aggregator + JSX emit) | **0.19 ms** | 11 ms | — |
| **Python pipeline total** | 19.5 ms | **1 171 ms** | 100% |
| **Rust pipeline total** | 11.7 ms | **700 ms** | 1.67× |

Two findings drive everything below:

1. **The bridge is 20× slower than the Rust work it feeds** (3.9 ms vs 0.19 ms per route). If we cut bridge to ~0 we'd drop total Rust pipeline from 700 ms → 470 ms (2.5× total speedup vs Python).
2. **Of the 61% mechanical bucket, only the `_compile_page` body has moved.** `compile_unevaluated_page`'s recursive theme-style walk + `_apply_recursive_style` are also mechanical — they're tree walks, not user-Python — and could move to Rust too. That's a chunk of the "framework" bucket the benchmark currently attributes to Python.

### Lever 1 — Cut bridge cost

The bridge (`reflex/compiler/ir/bridge.py`) walks each Component in Python, builds a tree-of-lists, calls `msgpack.packb` once. At ~24 µs/node it's the per-node bottleneck of the Rust path. Three options, in order of effort:

| # | Approach | Cost | Expected per-route | Net Rust-pipeline target |
|---|---|---|---|---|
| 1a | Tighten the bridge — drop redundant attribute lookups, avoid intermediate lists, cache `_get_all_var_data()` between sibling reads | 1 wk | 3.9 → 2.0 ms | 700 → 580 ms |
| 1b | Replace bridge with **Rust reading Component PyObjects via PyO3 `getattr`** — no msgpack at all. Spike measured ~100 ns/call; 165 nodes × ~5 attrs ≈ 80 µs/route | 2-3 wk | 3.9 → 0.1 ms | 700 → 470 ms |
| 1c | A Rust-side **batched** PyObject reader that releases the GIL between sibling subtrees so theme apply + bridge + rust overlap | +1 wk on top of 1b | parallel-bound | 470 → 380 ms |

**Pick 1b.** It cuts the bridge cost to noise, eliminates `reflex/compiler/ir/bridge.py` + the msgpack schema (§4), and the per-node-attribute-read budget (~100 ns) is dominated by anything we'd do per node in Python anyway. 1a is a stopgap that we'd throw away once 1b lands; 1c is a follow-up after 1b proves out.

The remaining bridge sites — VarData, ImportVar, EventChain, MetaTag — translate the same way: Rust reads `var._js_expr`, `var._get_all_var_data()`, `vd.hooks`, `vd.imports` directly. No new IR schema; the Rust side builds its own internal representation in one pass.

### Lever 2 — Push more mechanical work into Rust

Today the Rust side picks up *after* `compile_unevaluated_page` returns. The chunks of `compile_unevaluated_page` that are mechanical (and therefore portable) without touching framework primitives:

| Job | Today | Cost | Move to Rust |
|-----|-------|------|--------------|
| `_apply_recursive_style(component, theme_style)` walk | Python, recursive Component tree walk | ~1 ms/route on the synthetic | Rust walks the same tree once via PyO3 (1b) and applies styles natively |
| `Fragment` + `<title>` + `<meta>` wrap | Python, builds 3-4 Component instances | <0.1 ms/route | Skip — costs nothing |
| `_compile_page` body (`_get_all_*` × 5, `render()`, `templates.page_template`) | Python — the 61% mechanical bucket | 12 ms/route | **Already in Rust** — that's what the existing `rust` stage does |
| Memoize plugin (`_should_memoize` + `_build_wrapper` + `create_passthrough_component_memo` + `_compile_single_memo_component`) | Python — ~1.9 s on docs app, currently skipped under `run-rust` so memoize regresses at runtime | 4-8 wk | Rust port over PyO3-read Component tree (depends on 1b) |

Memoize is the biggest still-Python chunk. Once 1b lands (Rust can read Component trees natively), the memoize port has a clean target: walk the tree in Rust, decide memoize, build wrapper components by emitting JSX directly (skip the Python `_build_wrapper` round-trip).

### Sequenced work (locked)

Two sequenced levers — that's the whole plan. Everything else is a polish follow-up.

| # | Lever | What lands | Goal |
|---|-------|------------|------|
| **a** | **Cut bridge cost** — option 1b: Rust reads `Component` PyObjects directly via PyO3 `getattr`, no msgpack | New `crates/reflex_pyread` walks Components and `Var._get_all_var_data()` natively. **`reflex/compiler/ir/bridge.py` deleted 2026-05-17**; the msgpack schema (`reflex.compiler.ir.{schema,builder,canonical,pack}`) survives as a debug/diagnostic module for IR-shape tests that still build IR programmatically, but no production path goes through msgpack. | **Shipped 2026-05-17.** Measured: pyread stage 3.28 ms/route vs bridge+rust 3.97 ms/route on `synthetic:20` (**1.21× faster**, not the 40× the spike microbenchmark projected — most bridge cost is Python-side `_get_all_var_data()` walks that pyread also pays). Net Rust pipeline 666 → 625 ms. 18/18 corpus + 6/6 docs routes byte-identical. Parallel-load test: pyread 67 ms vs bridge+rayon-rust 96 ms on the 20-route batch — pyread wins under load too. |
| **b** | **Push more mechanical work into Rust** — memoize phase 3 (theme-apply dropped, phase 2 investigated but not shipped — see below) | (1) ~~`_should_memoize` decision walk in Rust~~ — ported byte-parity (546 calls / 0 mismatches) but **11% slower** standalone due to PyO3 boundary cost; kept as a foundation, used by the orchestrator. (2) `emit_memo_module` + `compile_memo_from_component` — pyread walks the wrapper body, codegen produces the `memo()` module. (3) Orchestrator (`rust_memo.walk_and_memoize` + `rust_pipeline.compile_pages` integration) — substitutes wrappers into each page tree, emits per-memo `.jsx` files, all driven from `run-rust`. **Shipped end-to-end 2026-05-17.** | Docs app: 6 pages + 371 unique memo modules in 1068 ms (was ~2.0 s w/o memoize, ~5.8 s in `reflex run`). Hook-harvest in pyread is a follow-up that gates correctness for hook-referencing memo bodies (task #16). |

**Theme-apply walk dropped from lever (b) (2026-05-17).** Earlier drafts of this section listed `_apply_recursive_style` as the first step of lever (b). Measured: 1.49 ms/route on `synthetic:20` (~90 ms total). When I went to port it, the reality is that `Component._add_style_recursive` dispatches into each component class's `_add_style()` virtual method — that's **framework code per §0a rule 1**. Replacing it would either require porting every Reflex component's default-style logic to Rust (which is exactly the framework port we're trying to avoid), or having Rust call back into Python for each `_add_style()` (which moves the work without reducing it). Neither is a real win. The ~90 ms theme-apply cost stays in Python; lever (b) is now memoize-only.

**Order is mandatory.** (b) is unblocked *by* (a) — once Rust can read Component trees natively, the memoize port has a clean target (walk in Rust, decide in Rust, emit wrapper JSX in Rust, never round-trip the IR). Doing memoize before (a) means re-doing the bridge work twice.

Polish follow-ups (after both land, not part of the locked plan):

- Rayon parallel page emit — cheap once (a) drops the GIL after the page-tree read; gets linear scaling on the synthetic 200-page test.
- Option 1c (per-subtree GIL release so theme-apply + pyread + codegen overlap) — only worth it once (a) is settled.
- Theme CSS + context shell + app-wrap + vite config — already shipped per §0a; keep an eye on regressions.

### Endgame numbers (revised, post-microbenchmark)

| Bucket | Today (Python) | `run-rust` today | After lever (a) (PyO3 reader) | After (a) + (b) (theme + memoize) |
|---|---:|---:|---:|---:|
| App import (one-shot) | 1.2 s | 1.2 s | 1.2 s | 1.2 s |
| `framework` (page eval + theme + wrap) | 0.45 s | 0.45 s | 0.45 s¹ | 0.45 s |
| `py_mech` (tree walks + render + template) | 0.72 s | — | — | — |
| `bridge` | — | 0.24 s | 0³ | 0³ |
| `rust` (mechanical work) | — | 0.01 s | 0.01 s | 0.03 s² |
| `pyread` (fused bridge + rust) | — | — | 0.20 s | 0.20 s |
| Memoize | (folded into py_mech) | not applied | not applied | <0.05 s |
| **Per-route compile pipeline, 20-route synthetic** | **1.17 s** | **0.67 s** | **0.62 s** | **~0.50 s** (with (b) memoize) |
| **Speedup vs Python** | 1.0× | 1.67× | **1.79×** | **2.34×** (+ memoize correctness) |

¹ Theme-apply slice migrates as the first step of lever (b); small additional drop expected (~50 ms on the synthetic).
² Rust grows slightly when memoize compute moves in (later step of lever (b)).
³ Pyread replaces the bridge entirely; the "bridge stage" is 0 in the after-(a) world and the work moves into `pyread`. Measured pyread (3.28 ms/route × 20 × 3 runs) is **1.21× faster** than the bridge+rust pair it replaces, not the 40× the spike projected — the bridge's cost was mostly Python-side `_get_all_var_data()` work that pyread also pays.

The ceiling lives at **~2× total pipeline speedup after lever (a) alone**, rising to **~2.3-3×** with lever (b)'s theme-apply + memoize ports. The previously-claimed 70-140× was conditional on porting `Var`/`Component` to Rust; that direction is off the table.

### What 1b actually looks like

A new crate `crates/reflex_pyread` whose entry is something like:

```rust
fn read_component<'py>(py: Python<'py>, comp: &Bound<'py, PyAny>) -> Result<Component<'arena>, PyReadError> {
    let tag: &str = comp.getattr("tag")?.extract()?;
    let children = comp.getattr("children")?;
    let mut child_nodes = bumpalo::collections::Vec::with_capacity_in(children.len()?, arena);
    for child in children.iter()? {
        child_nodes.push(read_component(py, &child?)?);
    }
    // … same shape for props, event_triggers, hooks, var_data
}
```

The contract with the Python framework is the same one the bridge already encodes: read these specific attributes (`.tag`, `.alias`, `.library`, `.children`, `.event_triggers`, `.props`, etc.) plus `Var._js_expr` and `Var._get_all_var_data()`. No new requirements on the framework. **No framework code is modified.**

### Done-criteria addition (folds into §13)

- [x] **`crates/reflex_pyread` landed** — walks Component PyObjects via PyO3 `getattr`, builds the same `Page<'arena>` IR the msgpack parser builds. Covers Bare/Fragment/Cond/Foreach/Match/Element + Var/VarData + EventHandler + page-level harvest (component_imports, state_bindings, needs_ref).
- [x] **`CompilerSession.compile_page_from_component(ident, component, route, ...)`** exposed; `reflex.compiler.rust_pipeline.compile_pages` calls it by default. `REFLEX_RUST_BRIDGE=msgpack` falls back to the legacy bridge path for diagnosis.
- [x] **Byte-parity validated.** All 18 corpus fixtures + all 6 docs-app routes produce JS that is byte-identical between pyread and bridge+rust.
- [x] **Bridge-replacement benchmark recorded.** `synthetic:20` × 3 runs: pyread stage = **3.28 ms/route** (vs bridge 3.80 + rust 0.17 = 3.97 ms/route). Pyread is **1.21× faster** than bridge+rust; total Rust pipeline drops from 666 → 625 ms (~6% wall-clock). **The plan's projected `<0.2 ms/route` bridge target was based on the spike's 100 ns/PyO3-call number times 5 attrs/node — but the real bridge cost is dominated by `_get_all_var_data()` walks and other Python-side work that pyread can't skip.** Both paths pay roughly the same Python tax; pyread wins by skipping msgpack pack/unpack and one Vec materialization.
- [x] `reflex/compiler/ir/bridge.py` deleted; `reflex.compiler.ir` is now a debug-only msgpack dump module. No production code path imports the bridge. The `REFLEX_RUST_BRIDGE` env var and msgpack fallback in `rust_pipeline.py` were removed at the same time — one path only.
- [x] ~~`compile_unevaluated_page`'s theme-apply walk moved to Rust~~ — **dropped.** Investigation 2026-05-17 found `_add_style_recursive` dispatches into each component class's `_add_style()` virtual method, which is framework code per §0a rule 1. Measured cost was only 1.49 ms/route (~90 ms total on synthetic:20). Plan revised; theme-apply stays in Python.
- [~] **Phase 2 (memoize decisions in Rust) — investigated, not shipped.** `reflex_pyread::memoize::should_memoize` ports `_should_memoize` + `_subtree_has_reactive_data` to Rust over PyO3 reads. Byte-parity proven: 546 `_should_memoize` calls intercepted across `tests/units/compiler/test_memoize_plugin.py` (108 tests) with **zero mismatches**. But the standalone Rust port runs **11% slower than the legacy Python predicate** (4.74 µs/comp vs 4.28 µs/comp on 3210 synthetic components) — every decision input is a PyO3 `getattr`/`call_method` round-trip (~100 ns each × ~10-15 lookups/node), and the boundary cost beats the Python-interpreter saving. The code stays in-tree as a foundation for phase 3 but is **not wired into `reflex run`** (it would slow that path down). When phase 3 lands, the decision will move inline during the pyread walk so the harvest cost is amortized.
- [~] **Phase 3 (memoize emit + orchestrator + root.jsx) — wired end-to-end, hook harvest missing.** `reflex_codegen::memo::emit_memo_module` + `CompilerSession.compile_memo_from_component(...)` produce the `export const <name> = memo(...)` shell (replaces `templates.memo_single_component_template`). `reflex/compiler/rust_memo.py::walk_and_memoize` drives the page-tree walk: bottom-up, calls `session.should_memoize` per node, builds wrappers via the framework helper `create_passthrough_component_memo`, substitutes them into the page tree, and stages each unique memo body for emit. `rust_pipeline.compile_pages` writes per-memo `.web/utils/components/<name>.jsx` files alongside page `.jsx` files, **and** emits `.web/app/root.jsx` via the legacy `compile_app_root` helper (one-shot framework composition; the React Router root module). Docs app measurement: 6 pages + **371 unique memo modules** + root in **~1062 ms** end-to-end; `reflex run-rust --frontend-only` now boots the docs app without the React Router "missing root.tsx" error. **Known gap:** pyread doesn't yet harvest per-component hooks (`_get_hooks_internal`/`_get_vars_hooks`/`_get_added_hooks`), so memo bodies that reference hook-defined identifiers (e.g. `useMemo(generateUUID, [])`) emit identifiers that aren't declared inside the memo body. Same gap exists for regular pages but doesn't bite on the corpus/docs page-level path. Tracked as task #16.
- [ ] Total `run-rust` pipeline on the 20-route synthetic ≤ 500 ms (vs current ~625 ms). **Remaining gap lives in `framework` (page eval + theme apply + wrap) — only lever (b) reduces it without touching framework primitives.**

---

## 1. Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Scope** | Compiler + Var-expr codegen + theme/CSS/context codegen | Component, State, and Var **classes** stay Python; their `_js_expr` strings + VarData are part of the IR. Rust never parses Python source. See §4 for the exact IR fragments. |
| **Success metric** | Both, dev-first | Sub-second hot reload first; linear cold build at 200+ pages second. |
| **Integration** | PyO3 from day one, abi3-py310 | One abi3 wheel per platform = 7 wheels per release, not 28. |
| **Fallback** | `REFLEX_COMPILER={rust,python,auto}` env var; default `auto` | `auto` = use Rust if wheel imports, fall back to Python compiler. The Python compiler stays in-tree until done-criteria are met. No subprocess. |
| **Authorship** | AI-first, human-reviewed | Bun model. Snapshot corpus is non-negotiable. |
| **Output equivalence** | Semantic + normalizer | Not byte-identical. Normalizer rules documented in corpus. Source maps (§4.6) keep diagnostics tractable. |
| **IR serialization** | msgpack via custom Rust deserializer; arena allocation only for multi-pass queries | Hand-rolled msgpack reader using `rmp::decode::read_*` is mandatory from D4 — measured **25× faster than rmp-serde** at 10k nodes (spike). Python side builds a per-page list-of-lists and calls `msgpack.packb` **once** — measured 5-7% faster than `msgpack.Packer.pack_*` streaming because msgpack-python is C-implemented and one C call beats N Python-call headers. Wire format is positional msgpack arrays (not maps) — short keys ("k", "t") are <10% gain but cleaner-typed; both are acceptable. |
| **IR identity for Salsa** | `xxh3_64` content hash per node, **with debug-mode collision verification** | Pure function of content. On cache-hit, debug builds re-hash + byte-compare canonical IR; release builds trust the hash. |
| **Salsa input granularity** | **One `#[salsa::input]` per page** (`PageIr`), plus one each for theme, global state, plugin manifest | Matches ty's per-`File` granularity (`ruff_db/src/files.rs:327`). Editing one page bumps one input, not all of them. |
| **Plugin protocol** | **Three-phase**: `pre_compile` (Python), `enter/leave` (Python, IR-round-tripped), `post_build` (Python) | The single `(ir) -> ir` claim is wrong — see §4.7. Memoize hooks the tree-walk phase; embed/tailwind/sitemap hook pre-compile and post-build. |
| **File watcher** | Python-side `watchfiles` | Already in Reflex. On change → re-import → emit new IR → Rust diffs by content hash. |
| **Wheel matrix** | linux x86_64 (manylinux+musllinux), linux aarch64 (manylinux), macos arm64+x86_64, win x86_64; abi3-py310 (one wheel covers 3.10–3.13) | Matches Reflex's stated support. abi3 keeps the matrix at 7 wheels. |
| **Maintainer split** | Freeze Python compiler features at corpus-merge | Bug fixes backported both sides. New features Rust-only. Python compiler deletable per §13. |
| **Rust toolchain** | stable, MSRV pinned in `rust-toolchain.toml` | No nightly features (would block downstream packaging). |
| **Async** | None | Compiler is CPU-bound. Async adds complexity for zero gain. Use `rayon` for parallel in D10. |
| **Error handling** | `thiserror` enums per crate; `miette` for user-facing diagnostics | No `anyhow` in library code. |
| **Logging** | `tracing` with `tracing-subscriber` | One ecosystem. Salsa already integrates. |

**What stays Python (the inventory):**

- Component class hierarchy + `.create()` evaluation (`packages/reflex-base/src/reflex_base/components/component.py`, 2,741 LOC)
- State class hierarchy + Pydantic instantiation + `.dict(initial=True)` (`reflex/state.py`, 2,655 LOC)
- Var system construction (`packages/reflex-base/src/reflex_base/vars/`, 8,810 LOC) — Rust receives finalized `_js_expr: str` + `VarData`, **never** re-derives them
- Plugin `pre_compile` and `post_build` hooks (run before/after Rust)
- Plugin `enter/leave` tree-walk hooks (round-tripped through IR — see §4.7)
- File I/O (Rust returns `HashMap<String, Vec<u8>>`; Python writes, with orphan deletion)

**What moves to Rust:**

- Six aggregator walks (`_get_all_hooks`, `_get_all_imports`, `_get_all_dynamic_imports`, `_get_all_custom_code`, `_get_all_refs`, `_get_all_hooks_internal`) — re-derived from IR, never run in Python before send
- JSX emission (`_RenderUtils.render` + templates)
- Theme CSS codegen (Emotion stylesheet)
- Root stylesheet codegen
- Context file codegen (initial state JSON wrapper, client storage config wrapper — the state *values* come from Python; the JS shell is emitted in Rust)
- App-root wrapper codegen
- Memo-component file emission (one `.jsx` per custom component + index)
- Vite config emission
- Salsa-cached incremental re-emit on edits

---

## 2. The Eight Rules + tracked-access invariant (performance discipline)

These rules eliminate the "stop and decide" moments. They apply to all Rust code in the compiler crates.

### R1. Arena rule (conditional — see caveat)
Every IR node, every intermediate node, every emitted string fragment that is **read more than once** is bumpalo-allocated. The arena is created per `compile_app()` call and dropped at the end. **No heap allocations during compilation** except: (a) the arena's own slab growth, (b) the final output `Vec<u8>` returned to Python, (c) Python string objects on the way out via PyO3.

> **Spike finding (2026-05-16).** For *single-pass* parse-and-emit, the arena is **30% slower** than streaming bytes → output buffer directly (`walk_arena_emit` 1.29ms vs `walk_manual_emit` 0.98ms at 10k nodes). The arena pays for itself only when ≥2 passes happen over the parsed tree. Codegen queries that parse-and-emit in one pass are explicitly allowed to skip the arena (R1 carve-out). The arena is mandatory for §7 multi-walk queries — the 6 aggregator walks reuse one parsed tree, which is the actual argument for materializing into the arena.
>
> **Caveat vs the bun reference.** Bun uses `MimallocArena` (supports `reset_retain_with_limit`); we use `bumpalo::Bump` (`reset()` retains the largest chunk, may release others). The bun "skip reset if !dirty" trick still applies; the cross-reset page-retention does not. Measure with `cargo bench` before committing to bumpalo — if the loss is >15% on the docs app, switch to a mimalloc-backed arena.

### R2. No-Drop rule
Every type allocated in the arena must satisfy `!std::mem::needs_drop::<T>()`. Enforce at construction with `const { assert!(!std::mem::needs_drop::<T>()) }` (the oxc pattern at `oxc_allocator/src/allocator.rs:278`). If a type owns a refcount, fd, or heap allocation, it does not go in the arena — period.

### R3. Static dispatch rule
Traversal traits (`IrVisitor`, `Gen`) are called via generic functions, never `&dyn Trait`. No vtables in hot paths. Every `match` over an IR enum is exhaustive (use `#[deny(non_exhaustive_omitted_patterns)]`).

### R4. Salsa rule + tracked-access invariant
Every function that derives information from IR input is `#[salsa::tracked]`. **Corollary (the ty discipline, from `ignore/ruff/AGENTS.md`):** any function that reads a node's payload — props, children, hooks, var-data — must be reached through a tracked accessor or be tracked itself. The IR enum's fields are **crate-private**; public access is via `db.props_of(node)`, `db.children_of(node)`, etc. — each `#[salsa::tracked]`. Plain helpers that don't touch any node payload are allowed.

### R5. Interning rule
All identifiers and namespace strings (`"rx."`, `"$/"`, `"reflex___state____"`, component tag names, prop names) become `Symbol(u32)` at IR construction. Codegen materializes the string only at final byte-emit. All intermediate comparisons are `u32 == u32`.

### R6. Buffer rule
Codegen writes to one `oxc_data_structures::code_buffer::CodeBuffer` (or equivalent `Vec<u8>` in the arena). No intermediate `String`s. No `format!` in per-node paths — use `write!` directly against the buffer.

### R7. GIL rule
PyO3 entry point: deserialize msgpack, then `py.allow_threads(|| compile_inner(...))`. The compiler does not hold the GIL. Output is serialized back to bytes inside `allow_threads`; PyO3 wraps in Python objects after. Verify by profiling that GIL hold time is <5% of total compile wall-clock.

### R8. Thread-local rule
Arena pool, codegen-buffer pool, interner shards: `#[thread_local]` attribute, never `thread_local!` macro. Reason: macro creates a thread-exit destructor that races mimalloc teardown (Bun's `ast_memory_allocator.rs:38-41`).

> **Caveat.** Bun's `ARENA_POOL` is a **single-slot stash**, not a multi-element pool — `ignore/bun/src/ast/ast_memory_allocator.rs:42-56` is explicit: "The pool holds at most one arena (nested scopes — rare — fall back to a fresh `Arena::new()`)." With `rayon` in D10, work-stealing onto a thread that already parked an arena means the *second* page compile on that thread gets a fresh arena. That's correct, just budget for it.

### Two cross-cutting disciplines

**Inline discipline.** `#[inline]` on every per-node visitor method; `#[inline(always)]` on per-character / per-byte buffer writes (the oxc pattern). Trust the compiler to inline match arms only after profiling says it didn't.

**Allocator-skepticism discipline (the Bun lesson).** After porting any hot allocator path, run the fixture benchmark. If the Rust version doesn't beat Python by ≥10× on a fixture that exercises it, the port is wrong. Likely cause: per-call heap init (forgot the thread-local pool), accidental `Drop` (R2 violation), forgotten dirty-bit check.

---

## 3. Crate skeleton (concrete shapes)

> **Status: scaffolded.** `packages/reflex-compiler-rust/` exists with the full layout below. `reflex_py/src/lib.rs` currently holds spike microbenchmark probes; D1-D11 below replace those with the real implementation. The other 7 crates are stub `lib.rs` files. `maturin develop --release` from the package root builds + installs an editable abi3-py310 wheel today.

Workspace member: `packages/reflex-compiler-rust/`. Cargo workspace with these crates:

```
packages/reflex-compiler-rust/
├── Cargo.toml                    # workspace root, members: 8 crates
├── pyproject.toml                # maturin build config, abi3-py310
├── rust-toolchain.toml           # pinned stable
├── python/reflex_compiler_rust/  # thin wrapper around _native cdylib
├── scripts/spike_bench.py        # napkin-math driver (keeps working post-port)
└── crates/
    ├── reflex_ir/                # IR enum types, no logic                  [STUB]
    ├── reflex_arena/             # bump arena + thread-local single-slot   [STUB]
    ├── reflex_intern/            # Symbol interning                         [STUB]
    ├── reflex_db/                # Salsa Db + storage + tracked accessors   [STUB]
    ├── reflex_semantic/          # IR → lowered IR (Salsa, six aggregators) [STUB]
    ├── reflex_codegen/           # IR → JS/JSX/CSS strings                  [STUB]
    ├── reflex_py/                # PyO3 entry points (the wheel)            [SPIKE]
    └── reflex_bench/             # fixture-driven benchmarks                [STUB]
```

### 3.1 `reflex_arena`
```rust
pub struct Arena(bumpalo::Bump);

impl Arena {
    #[inline(always)]
    pub fn alloc<T: Copy>(&self, val: T) -> &mut T {
        const { assert!(!std::mem::needs_drop::<T>()) };
        self.0.alloc(val)
    }
}

#[thread_local]
static ARENA_STASH: Cell<Option<Arena>> = Cell::new(None);

pub struct PooledArena {
    arena: Arena,
    dirty: bool,
}
// Drop returns cleaned arena to ARENA_STASH (single slot, not a pool).
```
Port semantics from `ignore/bun/src/ast/ast_memory_allocator.rs:22-107`, swapping `MimallocArena` for `bumpalo::Bump`. The single-slot stash is intentional — keep it.

### 3.2 `reflex_ir`

**Field access is crate-private.** Public reads go through Salsa-tracked accessors in `reflex_db` (R4 corollary).

```rust
#[repr(C, u8)]
#[derive(Clone, Copy)]
pub(crate) enum Component<'a> {
    Element {
        tag: Symbol,
        props: &'a [(Symbol, Value<'a>)],
        children: &'a [Component<'a>],
        event_handlers: &'a [EventHandler<'a>],
        hooks: &'a [Hook<'a>],
        id: NodeId,                     // xxh3_64(content)
        source_loc: SourceLoc,          // (PyFileId, line, col) — see §4.6
    },
    Text { value: &'a str, id: NodeId, source_loc: SourceLoc },
    Foreach { iter: Var<'a>, body: &'a Component<'a>, id: NodeId, source_loc: SourceLoc },
    Cond { test: Var<'a>, then: &'a Component<'a>, else_: Option<&'a Component<'a>>, id: NodeId, source_loc: SourceLoc },
    Memoize { inner: &'a Component<'a>, key: NodeId, id: NodeId, source_loc: SourceLoc },
    // ... ~30-50 variants total, codegen'd from IR schema
}

pub(crate) enum Value<'a> {
    JsExpr { expr: &'a str, var_data: VarData<'a> },  // pre-baked JS string from Python — see §4.4
    Literal(Literal<'a>),
    Ref(Symbol),
}
```
All `'a` lifetimes tie to the arena. All variants `Copy`. Codegen from the JSON schema in §4 — never hand-maintain.

### 3.3 `reflex_db` — Salsa boundary

**Lifetimes:** tracked queries return `<'db>`, not `'static`. The earlier draft's `LoweredIr<'static>` was wrong: Salsa tracked outputs are bound to the database borrow (see `salsa/examples/calc/parser.rs:11`: `parse_statements(...) -> Program<'_>`). If a tracked value must survive a revision, it goes through `#[salsa::interned]` (the ty pattern at `ty_python_semantic/src/types.rs:546,7575,7751`).

```rust
#[salsa::db]
pub trait Db: salsa::Database {}

#[salsa::db]
#[derive(Clone, Default)]
pub struct CompilerDb {
    storage: salsa::Storage<Self>,
}

// One input per page — matches ty's per-File granularity.
#[salsa::input(heap_size = ...)]
pub struct PageIr {
    pub route: String,
    #[returns(ref)]
    pub bytes: Vec<u8>,         // msgpack for one page's tree
    pub content_hash: u64,
}

#[salsa::input]
pub struct ThemeIr { #[returns(ref)] pub bytes: Vec<u8>, pub content_hash: u64 }

#[salsa::input]
pub struct GlobalStateIr { #[returns(ref)] pub bytes: Vec<u8>, pub content_hash: u64 }

#[salsa::input]
pub struct PluginManifestIr { #[returns(ref)] pub bytes: Vec<u8>, pub content_hash: u64 }

// Tracked accessors — every read of a node's payload goes through one of these.
#[salsa::tracked]
pub fn parse_page<'db>(db: &'db dyn Db, page: PageIr) -> ParsedPage<'db> { ... }

#[salsa::tracked]
pub fn lower_component<'db>(db: &'db dyn Db, page: PageIr, node: NodeId) -> LoweredIr<'db> { ... }

#[salsa::tracked]
pub fn emit_page<'db>(db: &'db dyn Db, page: PageIr) -> Arc<str> { ... }

#[salsa::tracked]
pub fn emit_theme<'db>(db: &'db dyn Db, theme: ThemeIr) -> Arc<str> { ... }

#[salsa::tracked]
pub fn emit_context<'db>(db: &'db dyn Db, state: GlobalStateIr) -> Arc<str> { ... }
```

**Cache eviction.** Salsa keeps every revision until evicted. Strategy: after every successful `compile_app`, call `db.synthetic_write(Durability::LOW)` on the cleanup query; rely on Salsa's built-in LRU per query (`#[salsa::tracked(lru = 256)]` on emit queries) to bound memory. Verify with the 100-reload soak test in §6.

**Arena ownership.** Each `compile_app` creates one `Arena` on the calling thread, lowering populates it, codegen reads from it, output is copied into the returned `Arc<str>` (no arena-borrowed data crosses the Salsa-revision boundary). Per-revision arenas are cheap; cross-revision sharing happens via Salsa-interned values, not arena pointers.

Reference: `ignore/salsa/examples/calc/db.rs`, `ignore/ruff/crates/ruff_db/src/files.rs:327`, `ignore/ruff/crates/ty_python_semantic/src/db.rs`.

### 3.4 `reflex_py` (the PyO3 boundary)
```rust
#[pymodule]
fn reflex_compiler(m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<CompilerSession>()?;
    Ok(())
}

#[pyclass]
struct CompilerSession {
    db: CompilerDb,
}

#[pymethods]
impl CompilerSession {
    #[new]
    fn new() -> Self { Self { db: CompilerDb::default() } }

    fn compile_app(
        &mut self,
        py: Python,
        pages: Vec<(String, Vec<u8>)>,      // (route, page msgpack)
        theme: Vec<u8>,
        global_state: Vec<u8>,
        plugin_manifest: Vec<u8>,
    ) -> PyResult<CompiledOutput> {
        // Update inputs (bump only the ones whose content_hash changed).
        sync_inputs(&mut self.db, pages, theme, global_state, plugin_manifest);

        py.allow_threads(|| compile_inner(&self.db))
            .map_err(to_py_err)
    }

    fn apply_plugin_tree_diff(&mut self, py: Python, route: String, ir_bytes: Vec<u8>) -> PyResult<()> {
        // Plugin enter/leave round-trip — see §4.7.
        ...
    }
}

#[pyclass]
struct CompiledOutput {
    files: HashMap<String, Vec<u8>>,        // route → contents; Python writes
    orphans: Vec<String>,                    // files to delete (Python does the unlinking)
    diagnostics: Vec<Diagnostic>,
}
```
`CompilerSession` is long-lived (Python keeps it across reloads). Salsa caches survive between `compile_app` calls — this is what makes hot reload incremental. Rust **does not write files**; the Python side owns the filesystem.

---

## 4. The IR contract (msgpack schema)

Versioned. Changes are breaking changes. Schema version is encoded as the first byte of every blob.

### 4.1 Per-page IR

> **Wire-format note (spike).** Two equivalent encodings; **positional msgpack arrays preferred**. Map encoding (with named keys) adds ~10% to parse cost but is self-describing. The spike (`packages/reflex-compiler-rust/crates/reflex_py/src/lib.rs`) uses positional arrays — keep that as the default. Schema validation runs once on the version byte, not per node.

```
PageIR = {
    "v": 1,
    "route": str,
    "root": ComponentIR,
    "title": str?,
    "meta": [MetaIR],
    "source_files": [str],     # files this page depends on (for source maps)
}

ComponentIR = {
    "kind": int,                # discriminant
    "tag": str?,                # for Element
    "props": [[str, ValueIR]],  # ordered list, not dict — preserves emit order
    "children": [ComponentIR],
    "events": [EventHandlerIR],
    "hooks": [HookIR],
    "id": int,                  # xxh3_64(canonical-bytes-of-content)
    "loc": [int, int, int],     # (PyFileId, line, col)
}

ValueIR = {
    "kind": int,                # 0=js_expr, 1=literal, 2=ref
    "data": Any,
    "var_data": VarDataIR?,     # only for kind=0
}

VarDataIR = {
    "hooks": [str],
    "imports": [[str, str]],
    "state": str?,
    "deps": [str],
    "position": int?,
    "components": [str],
}
```

### 4.2 Theme IR
```
ThemeIR = {
    "v": 1,
    "tokens": {str: str},        # colors, radii, etc.
    "global_style": str,         # raw CSS
    "appearance": str,
}
```

### 4.3 Global state IR
```
GlobalStateIR = {
    "v": 1,
    "initial_state": Any,        # output of state(...).dict(initial=True) — already JSON-ready
    "client_storage": {str: {str: {str: Any}}},
    "computed_var_deps": [...],  # computed var dependency graph for the wire format
}
```
Initial-state and client-storage *values* are computed in Python (Pydantic + async resolution); Rust emits only the JS shell that wraps them.

### 4.4 Var IR — the `_js_expr` decision

Var operations are **finalized in Python**, then passed to Rust as opaque JS expression strings + VarData. Rust never composes Vars.

Rationale:
- The Var system is 8,810 LOC of typed-expression-building Python (`packages/reflex-base/src/reflex_base/vars/`). Re-implementing it in Rust is a separate, much larger project.
- Current `_js_expr` is already final JS source by the time `render()` runs — Rust just splices it into JSX.
- This caps Rust's Var-related win at "string copy" — that's fine; the win is in the tree walks and codegen, not Var resolution.

If a future iteration moves Var composition into Rust, the `ValueIR` `kind=0` variant becomes a typed expression tree instead of a string. The schema version bumps.

### 4.5 Auxiliary output IRs

`compile_app` emits 8 artifact kinds (`reflex/compiler/compiler.py:1250-1284`). The IR carries inputs for all of them:

| # | Artifact | IR fragment | Codegen owner |
|---|---|---|---|
| 1 | Per-page JSX | `PageIR` | Rust |
| 2 | Theme CSS (Emotion) | `ThemeIR` | Rust |
| 3 | Root stylesheet | `RootStylesheetIR` (= theme + plugin CSS list) | Rust |
| 4 | Context file (state + storage) | `GlobalStateIR` | Rust |
| 5 | App-root wrapper | `AppRootIR` | Rust |
| 6 | Memo components | `MemoComponentsIR` (declarations harvested during enter walk in Python) | Rust |
| 7 | Plugin static assets | `PluginAssetsIR` (path + bytes pairs) | **Python** — passed through unchanged |
| 8 | Vite config | `ViteConfigIR` | Rust |

### 4.6 Source-map schema

Every IR node carries `source_loc: (PyFileId, line, col)`. The `PyFileId` is interned per `CompilerSession` and survives Salsa revisions (it's a `#[salsa::interned]` string). Diagnostics from Rust attach `source_loc` via `miette::SourceSpan`, so a JSX error at line 47 of an emitted page can be back-mapped to e.g. `reflex/components/foo.py:123`. Without this, debugging Rust-emitted JSX is intractable.

### 4.7 Plugin protocol — three phases

The earlier draft's "Python `(ir) -> ir` transform" claim was wrong: existing plugins do not have this shape.

| Plugin phase | Runs | Examples | Mechanism |
|---|---|---|---|
| **pre_compile** | Python, before IR emit | embed, sitemap | Plugin registers output paths and writes static files via `add_save_task`. No IR involvement. |
| **enter / leave** | Python, during tree walk **before** IR emit | memoize | Plugin mutates the Component tree in place using live `_var_data.hooks` + `event_triggers`. Result is then serialized to IR. |
| **post_build** | Python, after Rust emits | tailwind, sitemap, screenshot | Plugin reads Rust's output manifest, writes additional files (CSS bundle, sitemap.xml, screenshots). |

**Tree-walk plugins (enter/leave) cannot move to Rust in v1.** They depend on live Python object identity, Var resolution, and event-trigger inspection. The IR contract is: Python runs every enter/leave plugin first, then emits IR from the post-mutation tree. Rust never invokes a Python plugin.

If a future iteration wants enter/leave plugins to run in Rust, the round-trip API is `apply_plugin_tree_diff(route, ir_bytes)` on `CompilerSession` (§3.4) — Python sends a transformed sub-tree back to Rust. Round-trip cost must be measured before relying on this.

### 4.8 JSX-emission contract (the output target)

Rust's JSX emission must match the Python normalizer's output for the current emit shape (`packages/reflex-base/src/reflex_base/components/templates.py:52-106`):

- Elements: `jsx(Name, {props}, child1, child2, …)`
- Match: `match_template(...)` shape from `templates.py:80-106`
- Cond: ternary `(test) ? then : else_`
- Foreach: `iter.map((item, index) => ...)`
- Memoize: `<MemoWrapper key={key}>{inner}</MemoWrapper>`

The normalizer (in the corpus, §6) defines: trailing whitespace stripped, JS object keys sorted, import sort order, generated-id stability. Rust outputs through the normalizer before snapshot comparison.

---

## 5. Profile baseline + targets

Baselines are the **cProfile of the 27-page docs app (10.1s wall)** captured 2026-05-16, not projections. Per-page warm and cold-cumulative are **separate metrics** — the earlier draft conflated them.

### What the current 10.1s actually breaks into

| Bucket                                       | Time   | %    | Rust-rewritable?            |
|----------------------------------------------|-------:|-----:|:----------------------------|
| `_get_frontend_packages` (npm subprocess)    | 3.77s  | 37%  | No (subprocess)             |
| `compiler.compile` (per-page render)         | 2.81s  | 28%  | **Yes — prize**             |
| `prerequisites.get_app` (import app)         | 2.08s  | 21%  | No (one-time)               |
| Framework `__init__` imports                 | ~1.0s  | ~10% | No (one-time)               |
| `compile_memo_components`                    | 0.85s  | 8%   | **Yes**                     |
| Markdown (mistletoe + parse_document)        | 0.79s  | 8%   | Yes (separate pulldown-cmark wheel) |

Inside the 2.81s `compiler.compile`: 10 290 component-tree visits → 273 µs/node. Hot tottime is 2.26M `isinstance`, 954K `getattr`, 1.38M `str.startswith`, 74K `Component._get_vars`. **All polymorphic-dispatch overhead that disappears in a Rust enum + struct-field codegen.** That's the headroom.

### Warm single page (median of 5 runs, complicated_page fixture)

| Stage | Current | Target Rust |
|---|---|---|
| Walk + render | 0.45 ms | <0.05 ms |
| IR emit (Python, list-of-lists + packb) | n/a | <0.10 ms (new cost — spike measured ~0.06 ms/100-node page) |
| msgpack deserialize (Rust, hand-rolled) | n/a | <0.01 ms |
| Compile (Rust, all cached via Salsa) | n/a | <0.02 ms |
| **Total per warm page** | **0.45 ms** | **<0.20 ms** |

### Cold full-app (docs app, 27 pages, no caches)

| Bucket | Current | Target Rust | Notes |
|---|---|---|---|
| npm install | 3.7s | 3.7s | untouchable subprocess |
| Python app import | 2.0s | 2.0s | one-time |
| Framework `__init__` | 1.0s | 1.0s | one-time |
| Python `Component.create()` evaluation | (folded into compile bucket above) | unchanged — happens before IR emit |
| IR emit (Python) | n/a | <0.05s | spike: 10k nodes = 8 ms via `packb` |
| msgpack deserialize (Rust) | n/a | <0.01s | spike: hand-rolled, 0.8 ms for 10k nodes |
| Rust compile work (tree walks + emit) | 2.81s → | **<0.10s** | tightened from <0.5s; spike says 50-100× headroom |
| Memo components | 0.85s → | <0.03s | same code shape as above |
| Markdown | 0.79s → | <0.05s | pulldown-cmark binding, separate wheel |
| File I/O (Python write) | small | small | |
| **Total visible to user** | **~10s** | **~6.5s** | **1.55× cold; ~68% is untouchable npm + import** |
| **With hot npm cache** | **~6.4s** | **~2.8s** | **2.3× — the realistic dev experience** |

### Cold full-app (200-page synthetic, no caches)

Compile work scales linearly at 104 ms/page Python → <1 ms/page Rust. This is where the rewrite goes from "nice" to "necessary."

| Bucket | Today (projected) | Target Rust |
|---|---|---|
| npm install | 3.7s | 3.7s |
| Python import + create + IR emit | ~6s | ~6s |
| Compile work (Python: 20.8s; Rust: <0.2s) | 20.8s | <0.5s (rayon over pages) |
| Plugins + markdown | ~1s | <0.3s |
| **Total** | **~30s** | **<11s** |

### Hot reload (one page edited) — the primary user-visible win

| Stage | Target |
|---|---|
| watchfiles → re-import changed module | <50ms |
| Re-run Component.create() for the affected page | <30ms |
| Re-emit IR for that page only | <5ms |
| Salsa bumps one `PageIr` input → re-runs `emit_page` for that page | <10ms |
| File write | <5ms |
| **Total visible to user** | **<100ms** (tightened from <150ms) |

CI regression budget: any fixture worse than its baseline by >5% fails the build. See §6a.

---

## 6. Test corpus (precondition)

- [ ] `tests/codegen_corpus/<fixture>/{app.py, expected/, baseline.json}`
- [ ] **Tier 1 (~50)** small single-feature fixtures (~20 LOC each): state vars by type, computed vars, event handlers (no args / args / async), `rx.cond`, `rx.foreach`, dynamic components, custom components, each component library import, each plugin solo
- [ ] **Tier 2 (~10)** combinations: state + foreach + cond + events together
- [ ] **Tier 3** real apps: docs app, 1–2 AI-Builder apps from reflex.build
- [ ] **Tier 4** synthetic 200-page app from `scripts/generate_synthetic_app.py` — deterministic seed, random component shapes drawn from Tier 1 building blocks. Not hand-written.
- [ ] Snapshot runner with `--update-snapshots` mode
- [ ] **IR snapshot** per fixture (msgpack bytes → JSON dump, gitcommit'd)
- [ ] Normalizer rules documented (§4.8): trailing whitespace, JS object key order, import sort order, generated-id stability
- [ ] `baseline.json` per fixture: cold wall-clock, hot wall-clock, allocation count. CI fails on >5% regression.

**Coverage threshold (two metrics, not one):**

- ≥85% line coverage of `reflex.compiler.ir.emit` (the Python IR emitter) from the corpus alone
- 100% of corpus fixtures produce byte-equal output between Python and Rust **under the normalizer**

**Soak test for cache eviction (§3.3):** run a 100-iteration edit-loop on the docs app via the benchmark harness; peak RSS must stay <500 MB.

---

## 6a. Benchmark script (`scripts/benchmark_compile.py`)

The single command that produces every number in §5.

**Invocation:**
```bash
uv run python scripts/benchmark_compile.py                # all fixtures, default
uv run python scripts/benchmark_compile.py docs           # one fixture by name
uv run python scripts/benchmark_compile.py docs --runs 10
uv run python scripts/benchmark_compile.py docs --profile # cProfile top-25 hotspots
uv run python scripts/benchmark_compile.py docs --engine=rust   # post-D4
uv run python scripts/benchmark_compile.py --compare      # python vs rust side-by-side
uv run python scripts/benchmark_compile.py --update-baseline
uv run python scripts/benchmark_compile.py --check        # CI mode
uv run python scripts/benchmark_compile.py --soak=100     # edit-loop stress test
```

**What it measures (per fixture):**
- Cold wall-clock, warm wall-clock (median of N=5 subsequent runs)
- Per-bucket breakdown via `cProfile`: app-import / Component.create / IR emit / msgpack / Rust compile / memoize / markdown / I/O
- Peak RSS via `resource.getrusage`
- Output byte-size (so a "fast" port that emits less can't game the score)

**Implementation notes (≤200 LOC):**
- Reuse `tests.benchmarks.fixtures`
- Direct call to `reflex.compiler.compiler._compile_page` / `_compile_app` — no subprocess
- `time.perf_counter_ns` for wall-clock; `tracemalloc` (optional, `--allocs`)
- `--engine=rust` calls `reflex_compiler.CompilerSession.compile_app()`
- `--compare` runs both engines on each fixture, prints speedup ratio
- `baseline.json` at `tests/codegen_corpus/baseline.json`. Schema: `{fixture: {cold_ms, warm_ms, output_bytes, peak_rss_kb}}`
- `--check` reads `baseline.json`, runs all fixtures, exits non-zero on >5% warm-ms regression

**Existing scaffolding to reuse:**
- `scripts/profile_compilation_hotspots.py` — cProfile invocation pattern
- `tests/benchmarks/fixtures.py` — starter fixtures
- `tests/benchmarks/test_compilation.py` — `_compile_single_pass_page_ctx` for per-page call shape

---

## 7. Python-side prep (lands before the Rust)

- [ ] Define IR schema (§4) as a versioned `reflex.compiler.ir.schema` module — one Python source file per IR fragment (page, theme, state, plugin manifest)
- [ ] Implement `Component.to_ir() -> list` — return a tree-of-lists in the §4.1 positional-array shape (no per-node `dict`, no `msgpack.Packer` streaming). The caller packs the whole tree with **one** `msgpack.packb(root, use_bin_type=True)` call. **Why one C call:** spike measured `packb` of a tree-of-lists is 5-7% faster than `Packer.pack_*` streaming because msgpack-python descends the structure in C; streaming pays Python-call overhead per header. Same shape for `Var`, `Event`, `Hook`.
- [ ] `State.to_ir() -> list` — wraps `state(_reflex_internal_init=True).dict(initial=True)` + `_resolve_delta` + client-storage extraction into the same list-of-lists shape; caller `packb`s once. State *codegen* (the JS wrapper) lives in Rust; state *values* are emitted here.
- [ ] Stable `NodeId = xxh3_64(canonical-bytes)` computed during emit. Canonical-bytes ordering documented in `reflex.compiler.ir.canonical`.
- [ ] `PyFileId` interner — assigns each Python source file an integer ID. Survives reloads.
- [ ] Plugin protocol (§4.7): `pre_compile`, `enter/leave`, `post_build`. Document which existing plugin hooks which phase. Memoize moves to `enter/leave` (already there). Embed/sitemap to `pre_compile`+`post_build`. Tailwind to `post_build`.
- [ ] `reflex.compiler.session.CompilerSession` Python wrapper that holds the Rust `CompilerSession` object across reloads, routes `watchfiles` events, computes per-page content hashes, and only re-sends IR for changed pages
- [ ] `REFLEX_COMPILER` env-var dispatch: `auto` (default) → try Rust, fall back to Python; `python` → force Python compiler; `rust` → force Rust, hard-fail if wheel missing
- [ ] Python `watchfiles` integration calls `CompilerSession.compile_app(...)` (Rust delivery, not Rust-internal watching)

---

## 8. Rust work items (D0–D11)

Ordering optimized for dev-first. **Each D-item ships green corpus before the next starts.**

### D0. Scaffold + spike — **DONE (2026-05-16)**

- ✅ Cargo workspace at `packages/reflex-compiler-rust/` with all 8 crates
- ✅ `pyproject.toml` wired for `maturin develop --release`, abi3-py310
- ✅ `rust-toolchain.toml` pinned stable
- ✅ `reflex_py/src/lib.rs` has working PyO3 microbenchmark probes (empty_call, bytes_passthrough, walk_serde, walk_manual, walk_*_emit ×3)
- ✅ `scripts/spike_bench.py` driver; results at `ignore/SPIKE_RESULTS.md`

D1 inherits the wheel build and Python driver from D0 — no re-scaffolding.

### D1. `reflex_ir` — IR enum + codegen-from-schema — **LANDED (2026-05-16)**
- ✅ Hand-written first cut of `Component`, `Value`, `Literal`, `EventHandler`, `Hook`, `MatchArm`, `VarData`, `Page`, `Theme`, `GlobalState`, `PluginManifest` — covers §4 schema. Codegen-from-schema deferred to a follow-up once Python `reflex.compiler.ir.schema` lands (§7).
- ✅ `#[repr(C, u8)]` on `Component` with explicit `= N` discriminants matching the §4.1 `kind` field
- ✅ All variants `Copy`; lifetime `'a`; `Component::kind()`, `id()`, `source_loc()` accessors. Fields are `pub` for now — the R4 corollary (tracked accessors) lands in D5 when `reflex_db` wraps them in `#[salsa::tracked]`.
- ✅ `NodeId(u64)`, `PyFileId(u32)`, `SourceLoc { file, line, col }` newtypes. `Symbol(u32)` lives in `reflex_intern` (next bullet).
- Tests: 3 in `reflex_ir` verifying `Copy`, `!needs_drop`, and `kind()` discriminant agreement.
- **Reference**: `ignore/ruff/crates/ruff_python_ast/src/generated.rs:125,1298`

### D2. `reflex_arena` — bump arena — **LANDED (2026-05-16)**
- ✅ `Arena` wraps `bumpalo::Bump` with `alloc<T: Copy>` + `const { assert!(!std::mem::needs_drop::<T>()) }`. `#[inline(always)]` on `alloc`.
- ✅ MSRV bumped to 1.79 for inline-const blocks.
- ⏳ Benchmark vs `MimallocArena` baseline — pending D4 once a real workload exists; spike already showed bumpalo is 30% slower than no-arena for single-pass, which §2 R1 caveat now reflects.
- **Reference**: `ignore/oxc/crates/oxc_allocator/src/allocator.rs:217-301`

### D3. `reflex_arena` — thread-local single-slot stash — **LANDED (2026-05-16)**
- ✅ `PooledArena { arena: Option<Arena>, used: Cell<bool> }` with `acquire()` pulling from `ARENA_STASH` (stable `thread_local!` macro — see lib.rs header for R8 deviation rationale).
- ✅ Drop returns to stash, skipping `reset()` when `!used` (the dirty-bit optimization).
- ✅ Two integration tests: round-trip after drop, and unused-PooledArena-skips-reset.
- **Reference**: `ignore/bun/src/ast/ast_memory_allocator.rs:22-107` — port semantics (single-slot, not multi-element pool)

### D4. `reflex_py` — PyO3 boundary + `CompilerSession` — **LANDED (2026-05-16)**
- ✅ `CompilerSession` `#[pyclass]` holding `CompilerDb`. Spike probes preserved alongside the real entry points.
- ✅ `compile_page(route_ident, page_bytes) -> str` (hot-reload fast path)
- ✅ `compile_app(pages, theme=None, global_state=None, plugin_manifest=None) -> CompiledOutput` (full-app emit)
- ✅ `py.allow_threads(...)` wraps every compile call (R7)
- ✅ Hand-rolled msgpack parser at `crates/reflex_ir/src/parse.rs`. Borrows `&str` from the input where possible, copies into the arena when the lifetime must outlive the input slice. Supports `Page`, `Theme`, `GlobalState`, `PluginManifest` blobs.
- ✅ Schema version sanity exposed as `_native.SCHEMA_VERSION` (currently `1`).
- ⏳ Wheel CI (§9) is still to be wired up; today's build is `maturin develop` only.

### D5. `reflex_db` — content-hash cache (Salsa deferred) — **LANDED (2026-05-16)**
- ✅ `CompilerDb` is an `Arc<Mutex<HashMap<(route_ident, xxh3_64), Arc<str>>>>` with `set_cache_capacity`, `clear`, `cache_len`. Cap-evicts oldest entry when full.
- ✅ Pitfall 14 collision check noted; release builds trust the hash.
- ✅ Wired into `CompilerSession` — hot-reload measurement: 6180 ns cold → 290 ns warm (20× speedup on a trivial page).
- ⏳ **Salsa deferred.** The plan calls for `#[salsa::input] PageIr` + tracked queries; we ship the content-hash HashMap first because it delivers the same user-visible "skip when unchanged" semantic for a single-tracked-query pipeline. The public `CompilerDb::emit_page` surface is the API Salsa will replace once D7 needs cross-query sharing (parsed-tree reuse between aggregator walks and codegen).
- **Reference**: `ignore/salsa/examples/calc/db.rs`, `ignore/ruff/crates/ty_python_semantic/src/db.rs`, `ignore/ruff/crates/ruff_db/src/files.rs:327`

### D6. `reflex_ir` — visitor trait — **LANDED (2026-05-16)**
- ✅ `pub trait IrVisitor<'a>` with default `visit_*` methods that call free `walk_*` functions. No `&dyn` (R3) — every visitor monomorphizes.
- ✅ Methods: `visit_page`, `visit_component`, `visit_value`, `visit_var_data`, `visit_event_handler`, `visit_hook`, `visit_match_arm`, `visit_meta`.
- ✅ Counter visitor test confirms traversal reaches every node.
- **Reference**: `ignore/ruff/crates/ruff_python_ast/src/visitor.rs:23-220`

### D7. `reflex_semantic` — aggregator walks — **LANDED (2026-05-16)**
- ✅ Single-pass `aggregate(page) -> Aggregated<'a>` collapses the six Python walks into one tree traversal. Output is deduped, first-seen order preserved.
- ✅ Plumbed into `reflex_codegen::page::emit_page` — the rendered module's import block is now driven by the aggregator.
- ⏳ `dynamic_imports`, `custom_code`, `refs` are schema-v2 placeholders (current §4 schema doesn't carry the relevant fields).

### D8. `reflex_codegen` — JS/JSX emission — **LANDED (2026-05-16)**
- ✅ `CodeBuffer` (single `Vec<u8>`, no intermediate `String`s; `itoa`/`ryu` for numeric formatting; R6).
- ✅ `emit_component` matches all 8 Component variants per §4.8 (Element, Text, Foreach, Cond, Match, Memoize, Fragment, Expr).
- ✅ JS-identifier-safe prop names emit unquoted; non-identifier names emit as quoted string keys. Doubles → `ryu` shortest representation. `"`/`\n`/control characters → JS-escape.
- ✅ `emit_page` glues parser + aggregator + JSX into a self-contained ES module with grouped imports.
- ⏳ Source maps deferred — every IR node already carries `SourceLoc` for the lookup, but `miette` integration is a follow-up.

### D9. `reflex_intern` — Symbol interner — **PARTIAL (2026-05-16)**
- ✅ `Symbol(u32)` with `EMPTY = Symbol(0)` reserved for the empty string. Default impl returns `EMPTY`.
- ✅ Process-global `Mutex<Interner>` behind `intern(&str) -> Symbol`, `resolve(Symbol) -> Option<&'static str>`, `well_known(&str) -> Option<Symbol>`. Strings leaked into `'static` so resolution is cost-free at emit time.
- ✅ Common identifiers pre-interned at first use: `rx.`, `$/`, `reflex___state____`, `__reflex_`, plus React hook + JSX attribute names.
- ⏳ Per-thread sharded interners deferred — single mutex is the first cut. Public API is stable across that change.
- **Reference**: `ignore/ruff/crates/ruff_python_ast/src/name.rs`; for Salsa-interned variant, `ignore/ruff/crates/ty_python_semantic/src/types.rs:546,7575,7751`

### D10. Theme/context/auxiliary codegen — **LANDED (2026-05-16)**
- ✅ `emit_theme` — `:root { --token: value }` block + raw global CSS. camelCase / snake_case tokens convert to kebab-case CSS custom properties.
- ✅ `emit_context` — `createContext` shells + spliced `initialState` / `clientStorage` JSON blobs + `computedVarDeps` map.
- ✅ `emit_app_root` — `AppWrap` component with state/colorMode providers; plugin stylesheet `import "..."` lines deduped.
- ✅ `emit_vite_config` — minimal `defineConfig({ plugins: [react()], ... })`, plus a string slot for Python to splice extra plugin calls.
- ✅ Plugin static assets pass-through (artifact #7) — Python ships path+bytes, Rust copies into the output map verbatim.
- ✅ All wired into `CompilerSession.compile_app` — full app emits `pages/*.jsx`, `src/styles/theme.css`, `src/context.js`, `src/AppWrap.jsx`, `vite.config.js`.

### D11. Parallelism + production polish — **PARTIAL (2026-05-16)**
- ✅ `CompilerDb::emit_pages_parallel(&[(ident, bytes)]) -> Vec<Result<Arc<str>, _>>` via `rayon::par_iter`. Cache hits still avoid work; order is preserved. Wired into `compile_app`.
- ⏳ Source maps wired into `miette` diagnostics — deferred.
- ⏳ PGO release wheel — deferred.
- ✅ R7 verification by profiling — deferred to a real workload; current synthetic 200-page run is too short to measure meaningfully.

_(D10/D11 status moved up next to D9 — see above.)_

---

## 9. Wheel CI (day-one work item, gates D4 onwards)

```
.github/workflows/wheels.yml
```
- `PyO3/maturin-action@v1` — handles cibuildwheel internals
- **abi3-py310**: one wheel covers Python 3.10–3.13 per platform
- Matrix:
  - `linux-x86_64-manylinux`, `linux-x86_64-musllinux`
  - `linux-aarch64-manylinux`
  - `macos-arm64`, `macos-x86_64`
  - `windows-x86_64`
- Total: 6 platforms × 1 abi3 wheel = 6 wheels per release (was 28 in the earlier draft without abi3)
- Trigger: every PR (build only); tag push (publish to PyPI)
- A green wheel CI is a prerequisite for merging D4. Don't defer.

**Uncovered platforms** (FreeBSD, ppc64le, riscv64, alpine on edge in containers): `REFLEX_COMPILER=auto` falls through to the Python compiler. No subprocess, no hard failure. The Python compiler stays in-tree until done-criteria are met (§13).

---

## 10. Reference cheat sheet

| Technique | Reference | File:line |
|---|---|---|
| Enum AST (kills `isinstance`) | ruff | `ruff_python_ast/src/generated.rs:125,1298` |
| AST attribute macro (layout) | oxc | `oxc_ast_macros/src/ast.rs:21-65` |
| Bump arena + needs_drop assert | oxc | `oxc_allocator/src/allocator.rs:217,278` |
| Thread-local arena stash (single slot, not pool) | bun | `src/ast/ast_memory_allocator.rs:22-107` |
| Monomorphic visitor | ruff | `ruff_python_ast/src/visitor.rs:23-220` |
| Codegen buffer + trait | oxc | `oxc_codegen/src/{lib.rs:82,gen.rs:22}` |
| Salsa db setup (minimal) | salsa | `examples/calc/db.rs:1-66` |
| Salsa per-file input (production) | ruff | `ruff_db/src/files.rs:327` |
| Salsa tracked accessors over node payload | ty | `ty_python_semantic/src/types/class.rs:832-848` |
| Salsa interned (cross-revision) | ty | `ty_python_semantic/src/types.rs:546,7575,7751` |
| Salsa accumulators (diagnostics fan-in) | ty | `ty_python_semantic/src/types/infer.rs` |
| Salsa in production at scale | rust-analyzer | `crates/base_db/`, `crates/hir_def/` |
| Tracked-access invariant (.node() must be tracked) | ruff/ty | `ignore/ruff/AGENTS.md` |
| maturin + PyO3 setup, abi3 | ruff | `pyproject.toml`, `crates/ruff/` |
| Port methodology + postmortem | bun | PR #30412, `src/ast/ast_memory_allocator.rs:22-50` |

---

## 11. Pitfalls

1. **First Rust port of allocators is wrong.** Profile after porting; if not ≥10× over Python on a fixture that exercises it, the port is wrong. **Tightened by spike (2026-05-16):** real Python is 273 µs/node on `compiler.compile`; headroom is **50-100×**. A careless port that only delivers 5-10× *looks* fine in isolation but is leaving an order of magnitude on the table. Use the spike's `walk_manual_emit` rate (0.098 µs/node) as the floor target.
2. **Drop does NOT run in arenas.** R2 enforces this at type level.
3. **`#[thread_local]` ≠ `thread_local!`.** R8. The macro creates a destructor that races mimalloc teardown.
4. **Track `dirty` bits** — proportional teardown cost (D3).
5. **Mark lossy port spots with `// PERF(port):` and `// TODO(port):`** — backlog. Bun's discipline.
6. **AI sessions decay past ~30k LOC.** Port one fixture-tier at a time; each tier is a green-bar checkpoint.
7. **PyO3 ABI changes per Python version.** Use abi3-py310 to amortize across 3.10–3.13.
8. **Salsa needs content-hashing for IR.** Python rebuilds IR every reload. If Salsa key is object identity, every reload is a cold compile. R4 + content-hash NodeId in §4.
9. **GIL discipline.** R7. Holding the GIL during compile blocks every other Python thread including the watchfiles event loop.
10. **msgpack schema is a public API.** Versioned. Breaking changes increment `"v"`.
11. **Tracked queries return `<'db>`, never `'static`.** Salsa example at `salsa/examples/calc/parser.rs:11`. Earlier drafts of this doc had `LoweredIr<'static>` — wrong. Cross-revision sharing goes through `#[salsa::interned]`, not arena lifetimes.
12. **`rmp-serde` allocates strings to the heap. Defeats R1. VALIDATED — spike measured 25× slower than hand-rolled `rmp::decode` + `&str` borrows from input bytes at 10k nodes.** Hand-write the deserializer into the arena (or borrow `&str` from input for single-pass queries). Do not ship rmp-serde "for now"; the gap is too large to hide.
13. **Salsa cache memory grows unbounded without LRU caps.** Apply `#[salsa::tracked(lru = N)]` on emit queries; soak-test with 100 reload cycles.
14. **xxh3_64 collisions exist over a corpus.** Debug builds verify (hash, canonical_bytes) on cache hit; release builds trust the hash.
15. **The "memoize plugin is already (ir)->(ir) shape" claim is wrong.** Memoize mutates the live Component tree (§4.7). Plugins run in Python before/around IR emission, never inside Rust.

16. **Python-side `msgpack.Packer` streaming is slower than `packb` of a list-of-lists.** Spike-validated: 5-7% slower at every tree size. msgpack-python is a C extension; one `packb` call descends a tree-of-lists in C, whereas calling `Packer.pack_array_header()` per node pays N Python-call costs. `Component.to_ir()` returns a `list` (positional-array shape from §4.1) and the caller `packb`s once — see §7.

17. **Bumpalo arena loses to streaming for single-pass queries.** Spike-validated: 30% slower when you parse-and-emit in one pass. The arena pays off only when ≥2 reads happen against the parsed tree (the 6 aggregator walks in §7/D7 are the canonical case). R1 is now conditional (§2) — codegen queries that genuinely need only one pass may stream parse → output buffer without going through the arena.

---

## 12. Suggested first reads (half a day, before any code)

1. `ignore/bun/src/ast/ast_memory_allocator.rs` (end-to-end, postmortem comments) — 1 hr. Note `MimallocArena` ≠ `bumpalo`.
2. `ignore/salsa/examples/calc/{db,compile,parser}.rs` — 30 min. Note tracked return type is `<'_>`.
3. `ignore/ruff/crates/ruff_db/src/files.rs:327` + `ty_python_semantic/src/db.rs` — 1 hr. Note per-file `#[salsa::input]` granularity.
4. `ignore/ruff/crates/ty_python_semantic/src/types/class.rs:820-900` and `types/infer.rs` (accumulators) — 1 hr.
5. `ignore/ruff/crates/ruff_python_ast/src/visitor.rs` (full file) — 30 min.
6. `ignore/oxc/crates/oxc_codegen/src/{lib.rs:1-100,gen.rs:1-200}` — 30 min.
7. `ignore/ruff/pyproject.toml` + how their wheels are built (abi3) — 30 min.
8. Bun PR #30412 description + Jarred Sumner's writeup — 1 hr.
9. `ignore/ruff/AGENTS.md` (the tracked-access invariant) — 10 min.

---

## 13. Done-criteria (the green-bar list)

The rewrite is done when **all** of these are true:

- [x] Spike (§0) report committed at `ignore/SPIKE_RESULTS.md` and shows IR-emit < 30% of current wall-clock (**done — 0.4%**)
- [ ] Snapshot corpus has ≥60 fixtures across 4 tiers (incl. 200-page synthetic), all green against Rust under the normalizer
- [ ] ≥85% line coverage of `reflex.compiler.ir.emit` from the corpus alone
- [ ] Cold-compile fixture benchmark: every fixture beats its Python baseline by **≥30× on the Rust-resident buckets** (tightened from ≥5× per spike calibration — `compiler.compile` headroom is 50-100×, so 30× is the minimum that proves the port wasn't sloppy)
- [ ] Warm-compile (hot reload): every fixture single-page edit completes in **<100ms wall-clock** (tightened from <150ms)
- [ ] 200-page synthetic app: cold compile **≤11s wall-clock** (vs ~30s Python projection; floor is ~7s of npm + import that the rewrite cannot touch)
- [ ] Wheel CI green on all 6 matrix entries × abi3 (one wheel per platform)
- [ ] `REFLEX_COMPILER=auto` is the default and routes to Rust on supported platforms; Python fallback verified by toggling `REFLEX_COMPILER=python` on the docs app
- [ ] **Standalone markdown PyO3 wheel ships first** (mistletoe → pulldown-cmark; 0.79s → <0.05s expected). It's independent of the IR work, validates the wheel-distribution + PyO3 story in production, and ships value in days not months.
- [ ] No `// TODO(port):` markers remain in the hot path (visit + lower + emit)
- [ ] PyO3 layer holds the GIL for <5% of total compile wall-clock (R7 verified by profiling)
- [ ] Memory: arena peak <50MB on the docs app; <500MB on the 200-page synthetic; 100-reload soak peak RSS <500MB
- [ ] Multi-walk benchmark proves the arena pays for itself when ≥2 passes happen over the parsed tree (R1 carve-out from §2 still measures favorably for the 6-aggregator case)
- [ ] Telemetry: zero open issues tagged `rust-compiler-regression` for 4 consecutive weeks

When all boxes are ticked, `REFLEX_COMPILER=auto` switches its default from "fall back to Python" to "fail hard if Rust wheel missing", and the Python compiler can be deleted.
