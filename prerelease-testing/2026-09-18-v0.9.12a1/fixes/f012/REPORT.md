<!-- Written by the orchestrator from the fix agent's final response: the harness does not let subagents write
report files. Structured result and evidence: fixes/f012/evidence/, workflow wf_e6187de4-84e. -->

# f012 — FINDING-012 / reflex-dev/reflex#6143 — FIXED, E2E VERIFIED

Branch `fix/finding-012-badge-portal` in `/home/user/wt/f012`, commit `94554d771` (`fix: keep app wraps below the sticky badge renderable`). Never pushed, no PR.

## Root cause

Three pieces compose:

1. `/home/user/wt/f012/reflex/app.py:1574-1590` — `App._app_root` sorts app wraps by priority **descending** and `functools.reduce`s over them appending each next wrap as a **child** of the previous one. Every wrap is assumed to render `props.children`.
2. `/home/user/wt/f012/reflex/app.py:1649` (pre-fix) — `_setup_sticky_badge` registered the bare memo: `self.app_wraps[0, "StickyBadge"] = lambda _: memoized_badge()`. The compiled memo is `memo(({}) => jsx("a", …))` — `StickyBadge.create` (`packages/reflex-components-core/src/reflex_components_core/core/sticky.py:85-107`) takes no `*children`, so the generated function destructures no `children` prop and never renders one.
3. `/home/user/wt/f012/packages/reflex-components-dataeditor/src/reflex_components_dataeditor/dataeditor.py:596` — the Glide portal is `(-1, "DataEditorPortal")`, the only negative-priority wrap, i.e. always the last link of the chain.

`reflex/compiler/compiler.py:1356-1357` calls `_setup_sticky_badge()` when `is_prod_mode() and config.show_built_with_reflex` (default true), so in any default prod build the portal became a child of the badge memo, was emitted into `root.jsx`, and dropped at render time:

```jsx
// unfixed — byte-identical AppWrap to the campaign's logs/root_prod_withbadge.jsx
jsx(Fragment,{},children,jsx(MemoizedBadge_04c36749,{},jsx("div",{css:…,id:"portal"},)))
```

`getElementById("portal")` is null → `Cannot open Data Grid overlay editor, because portal not found.` → no overlay cell editor opens, including #7081's image carousel (whose 40 CSS rules do load). Dev has no badge; `show_built_with_reflex=False` restores it.

Important subtlety: the portal `<div>` is present in the generated source **either way** — only the nesting differs. A test that merely asserts the element is emitted passes on the broken tree.

## The fix (1 line + comment, `reflex/app.py`)

```python
-        self.app_wraps[0, "StickyBadge"] = lambda _: memoized_badge()
+        # The badge memo renders no children, and `_app_root` nests every
+        # lower-priority wrap inside the previous one, so keep the badge inside
+        # a Fragment: wraps below it (e.g. the `rx.data_editor` portal at
+        # priority -1) then stay siblings of the badge and reach the DOM.
+        self.app_wraps[0, "StickyBadge"] = lambda _: Fragment.create(memoized_badge())
```

```jsx
// fixed
jsx(Fragment,{},children,jsx(Fragment,{},jsx(MemoizedBadge_04c36749,{},),jsx("div",{css:…,id:"portal"},)))
```

**Why this shape.** A leaf app wrap must be its own `Fragment` so the reduce has somewhere to put the rest of the chain — already the idiom at `reflex/app.py:259` (`default_overlay_component` → `Fragment.create(memo(...)())`) and `reflex/compiler/compiler.py:1104` (`ToasterProvider` → `Fragment.create(memoized_toast_provider())`). The badge was the one framework wrap that broke it. This generalises: any lower-priority wrap (a user's `extra_app_wraps`, another library's portal) now survives the badge.

**Rejected alternatives.**
1. *Give `StickyBadge.create` `*children`* (the brief's first suggestion): `StickyBadge` is an `<a href="https://reflex.dev" target="_blank">` with `z-index: 9998`. Forwarded children land **inside the anchor**, so the portal — and every overlay React-portals into it — would sit inside a link, and clicks inside an open overlay editor would bubble and navigate the user to reflex.dev. It also changes a public component signature (new API + `.pyi` regen) to express what the wrap layer already handles. To be correct it would have to render `Fragment(badge, children)` anyway — which is what this fix does one level up, without touching the component API.
2. *Non-negative priority for the portal*: only moves the collision (the portal is a leaf too, so whatever lands below it gets swallowed); above the badge it would nest the badge inside `<div id="portal">` where Glide mounts overlays; and it fixes one component instead of the mechanism, needing a `reflex-components-dataeditor` release rather than a `reflex` one.
3. *Make `_app_root` special-case leaf wraps*: the framework cannot distinguish a provider ("nest my children") from a leaf ("be a sibling") — only the author knows, and nesting is the contract of the priority chain. Any heuristic would be a runtime patch over a type-level problem and would reshape the tree for existing third-party wraps.

No deprecation path needed: private method, no public API change, adds a `<Fragment>` (zero DOM nodes).

## Regression test

`tests/units/test_app.py::test_sticky_badge_wrap_keeps_lower_priority_wrap_renderable`, next to the other app-root chain tests, reusing that file's `compile_app_root_from_page_wraps` and `_find_mirrored_memo_symbol`. It registers the badge wrap plus a `-1` wrap standing in for the portal, compiles the app root, and asserts the portal is emitted **and** that the badge memo is childless in the chain.

Before (with `reflex/app.py` reverted to `HEAD~1`) — `evidence/logs/regression_test_before.txt`:
```
>       assert f"jsx({badge_symbol},{{}},)" in chain
E       assert 'jsx(MemoizedBadge_04c36749,{},)' in 'function AppWrap({children}) {…'
FAILED tests/units/test_app.py::test_sticky_badge_wrap_keeps_lower_priority_wrap_renderable
```
After — `evidence/logs/regression_test_after.txt`: `1 passed, 182 deselected`.

## End-to-end (campaign's own repro, A/B on the same tree)

`components_bumps/verification/vapp` copied unmodified to scratch; `editor_probe.py` / `vdrive.py` run from the campaign driver venv; prod server from **this worktree's** venv on port 3960 with the badge at its default. The same app dir was built twice — once with the fix, once with `app.py` reverted — so the one line is the only variable.

| | unfixed (`evidence/logs/unfixed_prod_editor.json`) | fixed (`evidence/logs/fixed_prod_editor.json`) |
|---|---|---|
| `portal_exists` | `false` | `true` (`<div id="portal" class="css-7zxn5u">`, parent `DIV`) |
| `badge_present` | `true` | `true` |
| `carousel_css_rules` | 40 | 40 |
| `overlay_imgs` after dbl-click | `[]` | `["/green.png","/red.png","/green.png","/red.png"]` |
| `carousel_root` | `null` | `<div class="carousel-root">…control-dots…` |
| console | `Cannot open Data Grid overlay editor, because portal not found…` ×2 | no such error |

`evidence/shots/fixed-prod-editor-overlay.png` shows the carousel open on the cell ("1 of 2", arrows, dots) **and** the "Built with Reflex" badge still rendered bottom-right; `unfixed-prod-editor.png` shows no overlay. Compiled roots: `evidence/logs/root_unfixed_snippet.jsx` / `root_fixed_snippet.jsx`. The fixed result matches the campaign's `show_built_with_reflex=False` control (`prod_nobadge_results.json`) while keeping the badge — the intended end state.

The published-0.9.12a1 baseline (`envs/shared`, port 3961) was built and started, but its backend worker exits on load here with `AttributeError: module 'vapp' has no attribute 'app'` (`evidence/logs/pub_prod.log`) — an app-module resolution difference between 0.9.12a1 and `main`, unrelated to this finding, that kills the server before a probe can run. The unfixed-tree run above is the like-for-like A/B; for the published package the campaign's capture stands (`prod_results.json`: `portal_exists=false` + the two quoted Glide errors).

## Checks

- `uv run ruff check .` → All checks passed; `uv run ruff format --check .` → 1626 files already formatted
- `uv run pyright reflex tests` (full) → 0 errors, 0 warnings
- `uv run pytest tests/units/test_app.py tests/units/components/test_memo.py tests/units/reflex_components_core/core/test_sticky.py` → 306 passed
- `uv run pytest tests/units/compiler tests/units/components` → 4480 passed
- `uv run pytest tests/units` → 9484 passed, 20 skipped, **207 failed, all in `tests/units/reflex_cli/`** — pre-existing and environmental: every one is the hosting CLI's version gate rejecting the tagless worktree version (`Error: Reflex version 0.0.0.post50.dev0+4cba00435 is not compatible with reflex-hosting-cli…`), the quirk `FIX_BRIEF` warns about. No `reflex_cli` test touches `_setup_sticky_badge`.
- No `.pyi` regen: no component `create` signature or props changed, `pyi_hashes.json` untouched.
- News fragment: `news/+sticky-badge-app-wrap-children.bugfix.md` (root only — nothing under `packages/` was touched).

## Risks

One extra `<Fragment>` in the prod app root (no DOM node). DOM order changes so the badge renders *before* the lower-priority wrap instead of containing it — previously that wrap rendered nowhere, so nothing can regress. `show_built_with_reflex=False` keeps working. `StickyBadge` itself and its tests are untouched.

## Open questions for maintainers

1. Should `_app_root` warn when nesting into a wrap that cannot render children? A user registering a childless `extra_app_wraps` entry above another wrap hits the same silent drop; left out as out of scope for a blocker.
2. The rule "a leaf app wrap must wrap itself in `Fragment`" is tribal knowledge across two call sites — it belongs in the `app_wraps` docstring at `reflex/app.py:406`.
3. Pre-existing: `reflex-components-dataeditor` uses the fixed global id `portal` and Glide wants it as the last child of `<body>`, while it renders deep inside the app root. Works, but two data-editor-bearing libraries on one page would collide.
4. Unrelated but worth a look: published 0.9.12a1 fails to start this app with `module 'vapp' has no attribute 'app'` while `main` starts it fine.
