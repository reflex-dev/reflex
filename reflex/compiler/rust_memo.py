"""Memoize orchestrator for the Rust pipeline. See plan §0b lever (b3).

Drives the auto-memoization pass for ``reflex run-rust``:

1. Walks each page's Component tree bottom-up.
2. For each Component, asks the Rust-side decision predicate
   (:meth:`CompilerSession.should_memoize`) whether it should be wrapped.
3. For candidates, calls the framework helper
   :func:`reflex.experimental.memo.create_passthrough_component_memo` to
   produce the wrapper Component + definition. The wrapper takes the
   original's children (passthrough) or none (snapshot).
4. The wrapper replaces the original in the parent's children list.
5. Each unique memo body (keyed by ``export_name``) gets emitted via
   :meth:`CompilerSession.compile_memo_from_component` and written to
   ``.web/utils/components/<name>.jsx``.
6. The transformed page tree then flows through the normal
   :func:`compile_page_from_component` path, so the page module imports
   ``<name>`` from ``$/utils/components/<name>`` and renders the wrapper
   at the call site with the original children passed as JSX children.

What this **does not yet match** vs the legacy
:class:`MemoizeStatefulPlugin`:

* No ``memoize_suppressor_stack`` — snapshot boundaries don't suppress
  descendant memoization. Empirically this affects nested ``Foreach`` +
  ``MemoizationLeaf`` subtrees; the docs app exercises a small number of
  these. Edge case to revisit if regressions surface.
* No ``fix_event_triggers_for_memo`` rewrite — event triggers are not
  re-baked into the memo body. Functional impact: event handlers still
  fire correctly; identity stability across renders is slightly worse.
* Snapshot vs passthrough split is whatever
  ``create_passthrough_component_memo`` produces; no explicit branch on
  ``get_memoization_strategy``.

Trade-off: the MVP orchestrator covers ~90% of real apps and skips the
~870 ms ``_compile_memo_components`` template-render cost by using the
Rust emit. Edge cases land iteratively.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from reflex.compiler.session import CompilerSession


def walk_and_memoize(
    component: Any,
    session: CompilerSession,
    memo_bodies: dict[str, Any],
) -> Any:
    """Walk ``component`` bottom-up, substituting memo wrappers in-place.

    Args:
        component: A Reflex ``Component`` (or anything else, in which case
            it's returned unchanged — non-Component children carry no
            reactive signal so they don't memoize).
        session: The :class:`CompilerSession` whose ``should_memoize``
            drives per-node decisions.
        memo_bodies: Mutated. After the walk, every unique memo wrapper
            seen is registered here as ``{export_name: body_component}``,
            where ``body_component`` has the ``{children}`` hole
            substituted in (passthrough wrappers) or carries the full
            captured subtree (snapshot bodies).

    Returns:
        The (possibly wrapper-substituted) Component to splice into the
        parent's children list.
    """
    from reflex_base.components.component import Component

    if not isinstance(component, Component):
        return component

    # Recurse children first; wrappers may already replace deeper nodes.
    new_children = [walk_and_memoize(c, session, memo_bodies) for c in component.children]
    if new_children != component.children:
        component.children = new_children

    if not session.should_memoize(component):
        return component

    return _wrap_with_memo(component, memo_bodies)


def _wrap_with_memo(component: Any, memo_bodies: dict[str, Any]) -> Any:
    """Build the memo wrapper for ``component`` and register its body."""
    from reflex.experimental.memo import create_passthrough_component_memo

    factory, definition = create_passthrough_component_memo(component)
    export_name = definition.export_name

    if export_name not in memo_bodies:
        body = copy.copy(definition.component)
        if definition.passthrough_hole_child is not None:
            body.children = [definition.passthrough_hole_child]
        memo_bodies[export_name] = (body, definition)

    wrapper = factory()
    # Passthrough wrappers carry the original's children at the page-level
    # call site; the memo body itself renders them through the
    # ``{children}`` hole. Snapshot wrappers leave the children empty
    # (the full body lives in the memo module).
    if definition.passthrough_hole_child is not None:
        wrapper.children = list(component.children)
    return wrapper


def emit_memo_modules(
    memo_bodies: dict[str, Any],
    session: CompilerSession,
    components_dir: Path,
) -> dict[str, Path]:
    """Emit each unique memo body to ``components_dir/<name>.jsx``.

    Args:
        memo_bodies: ``{export_name: (body_component, definition)}`` map
            built by :func:`walk_and_memoize`.
        session: The compile session whose
            :meth:`compile_memo_from_component` does the emit.
        components_dir: Filesystem directory under ``.web/`` where each
            memo file lands. Created if missing.

    Returns:
        ``{export_name: written_path}`` for every emitted memo file.
    """
    components_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, (body, definition) in memo_bodies.items():
        signature = _signature_for(definition)
        pre_hooks = _harvest_pre_hooks(body)
        js = session.compile_memo_from_component(
            name, signature, body, pre_hooks=pre_hooks
        )
        out_path = components_dir / f"{name}.jsx"
        out_path.write_text(js)
        written[name] = out_path
    return written


def _harvest_pre_hooks(body: Any) -> str:
    """Collect the memo body's non-trivial hooks as a rendered JS block.

    The Rust ``emit_memo_module`` always emits
    ``useContext(StateContexts.*)`` for each ``state_binding`` and
    ``useContext(EventLoopContext)`` unconditionally. Anything else the
    body needs (color-mode destructure, custom hook helpers from
    ``_get_hooks_internal``, …) has to come from the framework's hook
    harvest — port of `RUST_REWRITE_PLAN.md` task #16. Until the harvest
    moves into ``reflex_pyread`` we lean on the legacy
    :meth:`Component._get_all_hooks` and :func:`_render_hooks` here and
    pass the rendered string through PyO3 for Rust to splice.

    Args:
        body: The memo body Component.

    Returns:
        The rendered hook block, with the Rust-emitted hooks filtered out
        so nothing gets declared twice. Empty string if there's nothing
        left after filtering.
    """
    from reflex_base.compiler.templates import _render_hooks

    all_hooks = body._get_all_hooks()
    filtered = {
        hook: data
        for hook, data in all_hooks.items()
        if "useContext(StateContexts." not in hook
        and "useContext(EventLoopContext)" not in hook
    }
    if not filtered:
        return ""
    return _render_hooks(filtered).strip()


def _signature_for(definition: Any) -> str:
    """Return the JS parameter list spliced after ``memo(`` for ``definition``.

    Passthrough wrappers receive a destructured ``{ children }`` argument;
    snapshot bodies don't see children (their full subtree lives in the
    memo module).
    """
    if definition.passthrough_hole_child is not None:
        return "({ children })"
    return "()"


def collect_memo_modules_for_pages(
    pages: Iterable[tuple[str, Any]],
    session: CompilerSession,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the memoize orchestrator over many pages.

    Args:
        pages: ``(route, root_component)`` pairs.
        session: The compile session driving decisions + emit.

    Returns:
        ``(transformed_pages, memo_bodies)``: ``transformed_pages`` maps
        each route to its wrapper-substituted root Component;
        ``memo_bodies`` is the merged ``{export_name: (body, defn)}``.
    """
    transformed: dict[str, Any] = {}
    memo_bodies: dict[str, Any] = {}
    for route, root in pages:
        transformed[route] = walk_and_memoize(root, session, memo_bodies)
    return transformed, memo_bodies
