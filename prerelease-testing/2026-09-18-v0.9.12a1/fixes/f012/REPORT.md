<!-- Assembled by the orchestrator: the harness does not let subagents write report files, so the fix agent's
report (from its final response) is followed by the independent reviewer's section. Structured results and
evidence: fixes/f012/evidence/, workflow wf_e6187de4-84e. -->

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

## REVIEW

Independent adversarial review, 2026-09-19. **Verdict: approve — merge as-is.**

### What the change is

One line of product code (`reflex/app.py:1653`), plus a four-line inline comment:

```python
self.app_wraps[0, "StickyBadge"] = lambda _: Fragment.create(memoized_badge())
```

Plus `tests/units/test_app.py::test_sticky_badge_wrap_keeps_lower_priority_wrap_renderable`
and `news/+sticky-badge-app-wrap-children.bugfix.md`. Nothing else is touched.

### Root cause independently confirmed

`_app_root` (`reflex/app.py:1574-1590`) sorts the wrap registry by priority
descending and appends each next wrap as a **child** of the previous one, so the
chain is strictly linear. `(0, "AppWrap")` is seeded first in
`_resolve_app_wrap_components` (`reflex/compiler/compiler.py:1088`) and
`(0, "StickyBadge")` is registered later, so with a stable sort the badge lands
directly under `AppWrap` and `rx.data_editor`'s `(-1, "DataEditorPortal")`
(`packages/reflex-components-dataeditor/.../dataeditor.py:582-601`) lands under
the badge. `StickyBadge.create` takes no `*children`, so the compiled memo drops
them. Confirmed from the two real `root.jsx` files built in this review:

unfixed (`vapp_unfixed/.web/app/root.jsx:48`):

```
jsx(Fragment,{},children,jsx(MemoizedBadge_04c36749,{},jsx("div",{...,id:"portal"},)))
```

fixed (`vapp/.web/app/root.jsx:48`):

```
jsx(Fragment,{},children,jsx(Fragment,{},jsx(MemoizedBadge_04c36749,{},),jsx("div",{...,id:"portal"},)))
```

### Regression test: seen to fail, then pass

Run by the reviewer in the worktree, restoring `reflex/app.py` from `HEAD~1`
(the source only — the test file stayed at `HEAD`), then restoring via
`git checkout --`:

- pre-fix source: `FAILED ... assert 'jsx(MemoizedBadge_04c36749,{},)' in chain` (1 failed)
- fixed source: `1 passed`
- `git status --porcelain` empty before and after; branch still
  `fix/finding-012-badge-portal` at `94554d771`.

The two assertions together (`'id:"portal"' in chain` and the badge memo being
childless) are exactly the invariant — it is a structural assertion, which is
right, because the portal is present in `root.jsx` either way.

### End-to-end A/B, re-run by the reviewer

Same tree, same app (a copy of `components_bumps/verification/vapp`, default
`show_built_with_reflex`), same probe (`editor_probe.py`), prod builds on ports
3970 (fixed) and 3971 (pre-fix source), both from `/home/user/wt/f012/.venv`:

| | pre-fix (3971) | fixed (3970) |
|---|---|---|
| `portal_exists` | `false` | `true` |
| `badge_present` | `true` | `true` |
| `overlay_imgs` | `[]` | 4 images |
| `carousel_root` | `null` | `.carousel-root` present |
| "portal not found" | 2x | none |

The fixed-side JSON is byte-identical to the fix agent's
`evidence/logs/fixed_prod_editor.json`. The two console errors that remain on
both sides (a 404, and a `no dispatch function for substate` warning) are present
in the pre-fix run too and in the campaign's own baselines — unrelated.

A second probe on the fixed build confirms no collateral damage to the badge:
on `/`, `/ids` and `/editor` the anchor renders with text "Built with Reflex",
`position: fixed`, `z-index: 9998`, bottom-right at 1121x846 in a 1280x900
viewport, and `#portal` is the same empty `div#portal.css-7zxn5u` the
`show_built_with_reflex=False` control produced in the campaign.

### Checks re-run by the reviewer (worktree root)

- `uv run ruff check .` — All checks passed
- `uv run ruff format --check .` — 1626 files already formatted
- `uv run pyright reflex tests` (full) — 0 errors, 0 warnings
- `uv run pytest tests/units --ignore=tests/units/reflex_cli` — 9123 passed, 20 skipped
- `tests/units/reflex_cli` failures spot-checked and reproduced as environmental:
  `Reflex version 0.0.0.post50.dev0+4cba00435 is not compatible with
  reflex-hosting-cli` — the tagless-worktree version gate, not this change.

### Regression hunting

- The `Fragment.create(memo(...))` shape is already the house idiom for leaf app
  wraps: `(44, "ToasterProvider")` at `reflex/compiler/compiler.py:1104`,
  `default_overlay_component()` at `reflex/app.py:259`,
  `_component_from_import_path` (the `extra_overlay_function` wrap) at
  `reflex/app.py:212`. This fix makes the badge consistent with them.
- Every other framework wrap renders children (`StrictMode` 200,
  `ErrorBoundary` 55, `ToasterProvider` 44, `Overlay` 5, `ExtraOverlay` 4,
  `AppWrap` 0, the event-driven `StateProvider`/`EventLoopProvider`/
  `UploadFilesProvider`), so the badge was the only leaf and
  `(-1, "DataEditorPortal")` the only wrap below it. After the fix no framework
  combination is broken.
- reflex-enterprise 0.9.5 registers only `(30, "DnDProvider")` and
  `(44, "MantineProvider")`, both above the badge and both children-rendering —
  nothing that was previously swallowed starts rendering unexpectedly.
- No public API, no component signature, no prop changed, so no `make_pyi.py`
  run and no `pyi_hashes.json` churn is needed — correct.
- Dev mode is untouched (`_setup_sticky_badge` is only called from
  `reflex/compiler/compiler.py:1357` under `is_prod_mode()`), and the change is
  purely compile-time, so it is orthogonal to redis vs memory state managers.
- The extra `Fragment` adds no DOM node and no JS module (it compiles inline),
  so there is no cost beyond one more component object per compile.
- Nothing else in the tree reads `app_wraps[0, "StickyBadge"]`.

### On the shape of the fix

The brief's preferred shape was to give `StickyBadge.create` a `*children`
parameter. The agent's rejection of that is right and worth recording: the badge
is an `<a href="https://reflex.dev" target="_blank">`, so children rendered
inside it would be inside the anchor, and a click anywhere in a data-editor
overlay would navigate away. Re-prioritising the portal only moves the collision
and would need a component-package release. Wrapping in a `Fragment` is the
smallest change that fixes the defect, is cherry-pickable on its own, and needs
no stub regeneration.

### Blocking issues

None.

### Nits (non-blocking, for the maintainer)

1. The contract the fix relies on — "an app wrap that cannot render children must
   wrap itself in a `Fragment`" — is now tribal knowledge at three call sites. One
   sentence in the `app_wraps` docstring (`reflex/app.py:406`) would be cheap
   insurance. The agent raised the same point.
2. The regression test registers the portal through `app.extra_app_wraps` rather
   than through a component's `_get_app_wrap_components`, which is the path
   `rx.data_editor` actually uses. Both merge into the same registry before
   `_app_root` sorts, so the coverage of the nesting logic is equivalent, but a
   component-provided wrap would be closer to the real failure.
3. The general defect remains: a childless wrap registered *above* another wrap
   still silently drops it. Out of scope for a release blocker (no such
   combination ships), but worth a follow-up issue — `_app_root` could warn.
4. The news fragment is five lines where two would do; the last clause reads a
   little like a changelog narrative. Harmless.
