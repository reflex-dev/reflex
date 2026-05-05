"""MemoizeStatefulPlugin — auto-memoize stateful components with ``rx._x.memo``.

This plugin replaces the legacy ``StatefulComponent`` wrapping pass. It
participates in the normal single-pass walk via ``enter_component`` and inserts
per-subtree ``{children}``-pass-through wrappers built on the experimental
memo infrastructure. The wrapped subtree remains in the tree for the normal
walker descent, so downstream plugins (e.g. ``DefaultCollectorPlugin``) still
see the original components and collect their imports/hooks as usual.

Each unique subtree shape contributes:

- One generated experimental memo component definition, compiled into the
  shared ``$/utils/components`` module.
- ``useCallback`` hook lines for each non-lifecycle event trigger, emitted into
  the generated memo body so handler hooks stay inside that rendering domain.

No shared ``stateful_components`` file is produced.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from reflex_base.components.component import (
    BaseComponent,
    Component,
    _deterministic_hash,
    _hash_str,
)
from reflex_base.components.memoize_helpers import (
    MemoizationStrategy,
    _is_structural_memoization_child,
    fix_event_triggers_for_memo,
    get_memoization_strategy,
    is_snapshot_boundary,
)
from reflex_base.constants.compiler import MemoizationDisposition
from reflex_base.plugins import ComponentAndChildren, PageContext
from reflex_base.plugins.base import Plugin
from reflex_base.utils import format

from reflex.experimental.memo import create_passthrough_component_memo


def _compute_memo_tag(component: Component) -> str | None:
    """Compute a stable tag name for a memoizable component.

    Returns ``None`` for components that render empty (non-visual components
    are never memoized).

    The class qualname is encoded directly in the tag prefix so that distinct
    classes which render identically never collide on a tag. Tag collision
    would silently share a single cached memo wrapper across classes and drop
    the later class's class-level metadata (e.g. ``_get_app_wrap_components``,
    which carries providers like ``UploadFilesProvider`` that must reach the
    app root). Baking the qualname into the prefix avoids re-concatenating
    the rendered JSX into the hash input on every call.

    Args:
        component: The component to name.

    Returns:
        The stable tag name, or ``None`` if the component renders empty.
    """
    rendered_code = component.render()
    if not rendered_code:
        return None
    code_hash = _hash_str(_deterministic_hash(rendered_code))
    return format.format_state_name(
        f"{type(component).__qualname__}_{component.tag or 'Comp'}_{code_hash}"
    ).capitalize()


def _subtree_has_reactive_data(
    component: Component, _cache: dict[int, bool] | None = None
) -> bool:
    """Whether ``component``'s subtree carries reactive signals worth memoizing.

    No-arg event handlers (``on_click=State.ping``) contribute hooks only via
    ``event_triggers`` / ``_get_events_hooks``, not as a Var, so the per-Var
    scan must be paired with an explicit ``event_triggers`` check.

    ``useRef`` from a static ``id`` prop is intentionally ignored — it lives
    in ``_get_hooks_internal``, not in any Var, so static-id-only elements
    don't surface here and aren't flagged.

    Args:
        component: The component whose subtree to inspect.
        _cache: Internal ``id()``-keyed cache of per-subtree results so
            components reachable via overlapping ``var_data.components`` and
            ``children`` paths are evaluated once. ``False`` is also used as
            a transient placeholder while a subtree is being computed to
            break cycles.

    Returns:
        True if the subtree carries event triggers, explicit hooks, or any
        Var whose merged var_data has ``state`` or ``hooks``.
    """
    if _cache is None:
        _cache = {}
    key = id(component)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    # Placeholder breaks cycles: a subtree that references itself is
    # treated as non-reactive on the recursive arm; the real result for
    # this node is written back below.
    _cache[key] = False
    result = _component_subtree_is_reactive(component, _cache)
    _cache[key] = result
    return result


def _component_subtree_is_reactive(
    component: Component, _cache: dict[int, bool]
) -> bool:
    """Inner walk for :func:`_subtree_has_reactive_data` (uncached node check).

    Internal hooks (``_get_hooks_internal``) cover event-trigger callbacks,
    lifecycle hooks (``on_mount``/``on_unmount``), and Var-derived hooks
    (state context, client state, custom). The static ``id`` ref hook is
    explicitly subtracted so an id-only element does not flag as reactive.

    Args:
        component: The component to inspect.
        _cache: Shared cache passed through recursive calls.

    Returns:
        True if ``component`` itself or any reachable descendant carries
        reactive signals.
    """
    ref_hook = component._get_ref_hook()
    ref_hook_key = str(ref_hook) if ref_hook is not None else None
    for hook_key in component._get_hooks_internal():
        if hook_key != ref_hook_key:
            return True
    if component._get_hooks() is not None or component._get_added_hooks():
        return True
    for var in component._get_vars(include_children=False):
        var_data = var._get_all_var_data()
        if var_data is None:
            continue
        if var_data.state or var_data.hooks:
            return True
        for comp in var_data.components:
            if isinstance(comp, Component) and _subtree_has_reactive_data(comp, _cache):
                return True
    for child in component.children:
        if isinstance(child, Component) and _subtree_has_reactive_data(child, _cache):
            return True
    return False


def _should_memoize(component: Component) -> bool:
    """Decide whether ``component`` is a candidate for auto-memoization.

    Snapshot boundaries (``recursive=False``) suppress their descendants,
    so a stateful subtree must trigger wrapping at the boundary itself —
    otherwise the state read leaks into the page module. Other components
    are evaluated from their own props/triggers; descendants are visited
    independently by the walker.

    Args:
        component: The candidate component.

    Returns:
        True if the component should be wrapped in a memo definition.
    """
    from reflex_components_core.base.bare import Bare
    from reflex_components_core.core.cond import Cond
    from reflex_components_core.core.match import Match

    strategy = get_memoization_strategy(component)

    if component._memoization_mode.disposition == MemoizationDisposition.NEVER:
        return False
    if isinstance(component, Bare):
        # A stateful value will be wrapped in a separate component. Match the
        # per-Var predicate used by ``_subtree_has_reactive_data`` so a Bare
        # whose Var carries only imports (no state/hooks) is not memoized.
        contents_var_data = component.contents._get_all_var_data()
        if contents_var_data is not None:
            if contents_var_data.state or contents_var_data.hooks:
                return True
            for embedded in contents_var_data.components:
                if isinstance(embedded, Component) and _subtree_has_reactive_data(
                    embedded
                ):
                    return True
    # Cond and Match render conditional branch JSX from their own props rather
    # than from a tag; structural memoization children (e.g. ``Foreach``)
    # render via their own structural form. All have no ``tag`` but still
    # must be considered for memoization — the structural-child case in
    # particular owns its whole subtree as a snapshot, so if it does not
    # wrap here, its descendants leak to the page module.
    if (
        component.tag is None
        and not isinstance(component, (Cond, Match))
        and not _is_structural_memoization_child(component)
    ):
        return False
    if component._memoization_mode.disposition == MemoizationDisposition.ALWAYS:
        return True

    # Direct Vars only (component's own props, style, class_name, id, etc.).
    # Match the per-Var predicate used by ``_subtree_has_reactive_data``
    # var_data carrying only imports is not reactive.
    for prop_var in component._get_vars(include_children=False):
        var_data = prop_var._get_all_var_data()
        if var_data is None:
            continue
        if var_data.state or var_data.hooks:
            return True
        for embedded in var_data.components:
            if isinstance(embedded, Component) and _subtree_has_reactive_data(embedded):
                return True

    if strategy is MemoizationStrategy.SNAPSHOT and not is_snapshot_boundary(component):
        return True

    if is_snapshot_boundary(component) and _subtree_has_reactive_data(component):
        return True

    # Components with event triggers are always memoized (to wrap callbacks).
    return bool(component.event_triggers)


@dataclasses.dataclass(frozen=True, slots=True)
class MemoizeStatefulPlugin(Plugin):
    """Auto-memoize stateful components with experimental-memo wrappers.

    Registered in ``default_page_plugins`` before ``DefaultCollectorPlugin``.
    Components either render as passthrough memo wrappers or snapshot memo
    wrappers (see ``get_memoization_strategy``):

    - Snapshot wrappers (``MemoizationLeaf``-style boundaries and structural
      ``Foreach`` wrappers): wrapped in ``enter_component``
      and returned with empty structural children. The walker skips descent, so
      hooks attached to the captured body are compiled into the memo body only.
    - Passthrough wrappers are wrapped in
      ``leave_component`` after descendants have already compiled, so any inner
      memo wrappers flow into this wrapper's children.

    Descendants of a snapshot boundary are never independently memoized; the
    boundary owns the wrapping decision for its whole subtree. This is tracked
    via ``PageContext.memoize_suppressor_stack`` — a stack of component ids
    that pushed suppression, popped in ``leave_component`` when the matching
    component leaves.
    """

    def enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> BaseComponent | ComponentAndChildren | None:
        """Memoize snapshot-boundary subtrees before descent.

        Snapshot boundaries (``MemoizationLeaf``-style, see
        ``is_snapshot_boundary``) stash state-referencing hooks inside
        internally-built structural children. If we waited until
        ``leave_component`` to swap the boundary for its memo wrapper, the
        walker would have already descended and the collector plugin would
        have pulled those hooks into page scope. Returning the wrapper with
        empty structural children here causes the walker to skip the descent
        entirely — the boundary's full snapshot lives only in the memo
        component definition compiled separately.

        Non-boundary components are handled in ``leave_component`` so their
        already-compiled children flow into the wrapper.

        Args:
            comp: The component being visited.
            page_context: The active page context.
            compile_context: The active compile context.
            in_prop_tree: Whether the component is in a prop subtree.

        Returns:
            A ``(wrapper, ())`` replacement for memoized boundaries, otherwise
            ``None``.
        """
        if in_prop_tree:
            return None
        if not isinstance(comp, Component):
            return None
        if page_context.memoize_suppressor_stack:
            return None
        strategy = get_memoization_strategy(comp)
        if strategy is not MemoizationStrategy.SNAPSHOT:
            return None
        snapshot_boundary = is_snapshot_boundary(comp)

        if not _should_memoize(comp):
            # Boundary not worth wrapping — still suppress descendants so
            # they don't memoize independently of the boundary's subtree.
            if snapshot_boundary:
                page_context.memoize_suppressor_stack.append(id(comp))
            return None

        wrapper = self._build_wrapper(
            comp,
            page_context,
            compile_context,
        )
        return None if wrapper is None else (wrapper, ())

    def leave_component(
        self,
        comp: BaseComponent,
        children: tuple[BaseComponent, ...],
        /,
        *,
        page_context: PageContext,
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> BaseComponent | ComponentAndChildren | None:
        """Wrap non-boundary memoizables and pop any suppression this component pushed.

        Args:
            comp: The component being visited.
            children: Its compiled children (unused; the wrapper reads from
                ``comp.children`` which the walker has already updated).
            page_context: The active page context.
            compile_context: The active compile context.
            in_prop_tree: Whether the component is in a prop subtree.

        Returns:
            The memo wrapper for non-boundary memoizables, else ``None``.
        """
        if in_prop_tree:
            return None
        if not isinstance(comp, Component):
            return None

        stack = page_context.memoize_suppressor_stack
        if stack and stack[-1] == id(comp):
            stack.pop()

        if stack:
            return None

        if len(children) != len(comp.children) or any(
            compiled_child is not current_child
            for compiled_child, current_child in zip(
                children, comp.children, strict=True
            )
        ):
            comp = page_context.own(comp)
            comp.children = list(children)

        strategy = get_memoization_strategy(comp)
        if strategy is MemoizationStrategy.SNAPSHOT:
            return None

        if not _should_memoize(comp):
            return None

        return self._build_wrapper(comp, page_context, compile_context)

    @staticmethod
    def _build_wrapper(
        comp: Component,
        page_context: PageContext,
        compile_context: Any,
    ) -> BaseComponent | None:
        """Return the memo wrapper component for ``comp``, or ``None`` if untagged.

        Rewrites ``comp.event_triggers`` on a page-local clone via
        :func:`fix_event_triggers_for_memo` so the memo body renders the
        memoized ``useCallback`` forms, and registers the memo definition on
        ``compile_context`` so the memo module compile pass emits it.

        Args:
            comp: The component being memoized.
            page_context: The active page context.
            compile_context: The active compile context.

        Returns:
            The wrapper instance, or ``None`` if the component's render is
            empty and has no meaningful tag.
        """
        tag = _compute_memo_tag(comp)
        if tag is None:
            return None

        comp = fix_event_triggers_for_memo(comp, page_context)

        compile_context.memoize_wrappers[tag] = None
        # Passthrough memo definitions capture app-specific event/state vars, so
        # they must be rebuilt for each compile instead of shared globally.
        wrapper_factory, definition = create_passthrough_component_memo(tag, comp)
        compile_context.auto_memo_components[tag] = definition

        wrapper = wrapper_factory()
        # The wrapper has no structural children at the page level, but parents
        # walking ``_get_all_refs`` (e.g. ``Form._get_form_refs`` collecting
        # ref_<id> mappings into ``handleSubmit``) need to see refs from the
        # wrapped subtree. Delegate ref collection to the original component
        # so descendants inside the memo body remain reachable for ref lookup.
        object.__setattr__(wrapper, "_get_all_refs", comp._get_all_refs)
        return wrapper


__all__ = ["MemoizeStatefulPlugin"]
