"""MemoizeStatefulPlugin — auto-memoize stateful components with ``rx._x.memo``.

This plugin replaces the legacy ``StatefulComponent`` wrapping pass. It
participates in the normal single-pass walk via ``enter_component`` and inserts
per-subtree ``{children}``-pass-through wrappers built on the experimental
memo infrastructure. The wrapped subtree remains in the tree for the normal
walker descent, so downstream plugins (e.g. ``DefaultCollectorPlugin``) still
see the original components and collect their imports/hooks as usual.

Each unique subtree shape contributes:

- One generated experimental memo component definition, compiled into a module
  mirroring its source module under ``$/app_components/`` (or, when it can't be
  mirrored, a per-memo module at ``$/utils/components/<name>``).
- ``useCallback`` hook lines for each non-lifecycle event trigger, emitted into
  the generated memo body so handler hooks stay inside that rendering domain.

No shared ``stateful_components`` file is produced.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from reflex_base.components.app_wraps import (
    collect_var_app_wraps_for_component,
    collect_var_app_wraps_in_subtree,
)
from reflex_base.components.component import BaseComponent, Component, ComponentStyle
from reflex_base.components.memo import create_passthrough_component_memo
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
from reflex_components_core.base.bare import Bare
from reflex_components_core.core.cond import Cond
from reflex_components_core.core.match import Match

_EMPTY_SHARED_SCOPE_COUNTS: dict[str, int] = {}


def _subtree_has_reactive_data(
    component: Component, _cache: dict[int, bool] | None = None
) -> bool:
    """Whether ``component``'s subtree carries reactive signals worth memoizing.

    No-arg event handlers (``on_click=State.ping``) are deliberately not
    treated as reactive on their ``event_triggers`` alone: ``addEvents`` is
    reached through a module-level import (``Imports.EVENTS``) rather than a
    hoisted hook, so the inline callback never drives a re-render and the
    subtree gains nothing from being wrapped. Handlers that reference state
    (e.g. ``State.set_x(State.y)``) still surface through the per-Var scan.

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
        True if the subtree carries explicit or internal hooks, or any Var
        whose merged var_data has ``state`` or ``hooks``.
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


def _subtree_requires_shared_scope(
    component: Component,
    scope_counts: dict[str, int],
    style: ComponentStyle | None = None,
    _visiting: set[int] | None = None,
) -> None:
    """Count each appearance of a local hook scope in a subtree.

    Args:
        component: Subtree root to scan.
        scope_counts: Scope-key to render-occurrence count being populated.
        style: App-level styles whose vars may add hook-scope users.
        _visiting: Component identities on the current recursion path.
    """
    if _visiting is None:
        _visiting = set()
    component_id = id(component)
    if component_id in _visiting:
        return
    _visiting.add(component_id)

    try:
        local_scope_keys = {
            key
            for var in component._get_vars(include_children=False)
            if (var_data := var._get_all_var_data()) is not None
            for key in var_data.shared_scope_keys
        }
        if (
            style is not None
            and (component_style := component._get_component_style(style)) is not None
            and (var_data := component_style._var_data) is not None
        ):
            local_scope_keys.update(var_data.shared_scope_keys)
        for key in local_scope_keys:
            scope_counts[key] = scope_counts.get(key, 0) + 1

        for var in component._get_vars(include_children=False):
            var_data = var._get_all_var_data()
            if var_data is not None:
                for embedded in var_data.components:
                    if isinstance(embedded, Component):
                        _subtree_requires_shared_scope(
                            embedded, scope_counts, style, _visiting
                        )

        for child in component.children:
            if isinstance(child, Component):
                _subtree_requires_shared_scope(child, scope_counts, style, _visiting)
        for prop_component in component._get_components_in_props():
            if isinstance(prop_component, Component):
                _subtree_requires_shared_scope(
                    prop_component, scope_counts, style, _visiting
                )
    finally:
        _visiting.remove(component_id)


def _merge_shared_scope_counts(
    counts: dict[str, int] | None, descendant_counts: dict[str, int]
) -> dict[str, int] | None:
    """Merge a descendant's scope counts without allocating for empty subtrees.

    Returns:
        The merged counts, or ``None`` if both subtrees are empty.
    """
    if not descendant_counts:
        return counts
    if counts is None:
        counts = {}
    for key, count in descendant_counts.items():
        counts[key] = counts.get(key, 0) + count
    return counts


def _collect_subtree_shared_scope_counts(
    component: Component,
    subtree_counts: dict[int, dict[str, int]],
    visiting: set[int],
    style: ComponentStyle | None = None,
) -> dict[str, int] | None:
    """Count each subtree's shared-scope appearances in one post-order traversal.

    Args:
        component: Subtree root to scan.
        subtree_counts: Component identity to scope occurrence counts.
        visiting: Component identities on the current traversal path.
        style: App-level styles whose vars may add hook-scope users.

    Returns:
        Scope occurrence counts in this subtree, or None if a component cycle is found.
    """
    component_id = id(component)
    if component_id in visiting:
        return None
    if component_id in subtree_counts:
        return subtree_counts[component_id]

    visiting.add(component_id)
    counts: dict[str, int] | None = None

    try:
        local_scope_keys: set[str] = set()
        for var in component._get_vars(include_children=False):
            var_data = var._get_all_var_data()
            if var_data is None:
                continue
            local_scope_keys.update(var_data.shared_scope_keys)
            for embedded in var_data.components:
                if not isinstance(embedded, Component):
                    continue
                descendant_counts = _collect_subtree_shared_scope_counts(
                    embedded, subtree_counts, visiting, style
                )
                if descendant_counts is None:
                    return None
                counts = _merge_shared_scope_counts(counts, descendant_counts)
        if (
            style is not None
            and (component_style := component._get_component_style(style)) is not None
            and (var_data := component_style._var_data) is not None
        ):
            local_scope_keys.update(var_data.shared_scope_keys)

        for child in component.children:
            if not isinstance(child, Component):
                continue
            descendant_counts = _collect_subtree_shared_scope_counts(
                child, subtree_counts, visiting, style
            )
            if descendant_counts is None:
                return None
            counts = _merge_shared_scope_counts(counts, descendant_counts)
        for prop_component in component._get_components_in_props():
            if not isinstance(prop_component, Component):
                continue
            descendant_counts = _collect_subtree_shared_scope_counts(
                prop_component, subtree_counts, visiting, style
            )
            if descendant_counts is None:
                return None
            counts = _merge_shared_scope_counts(counts, descendant_counts)
        if local_scope_keys:
            if counts is None:
                counts = {}
            for key in local_scope_keys:
                counts[key] = counts.get(key, 0) + 1
    finally:
        visiting.remove(component_id)

    result = counts if counts is not None else _EMPTY_SHARED_SCOPE_COUNTS
    subtree_counts[component_id] = result
    return result


def _subtree_splits_shared_scope(
    component: Component,
    shared_scope_counts: dict[str, int],
    split_component_ids: set[int] | None = None,
    component_id: int | None = None,
    style: ComponentStyle | None = None,
) -> bool:
    """Whether memoizing this subtree would separate users of a shared hook scope.

    Args:
        component: Subtree candidate for memoization.
        shared_scope_counts: Total component users of each shared scope on the page.
        split_component_ids: Precomputed candidates that split a shared scope.
        component_id: Original component identity when ``component`` is a
            page-owned clone created after the prepass.
        style: App-level styles whose vars may add hook-scope users.

    Returns:
        Whether this subtree contains only part of any shared scope.
    """
    if split_component_ids is not None:
        return (
            component_id if component_id is not None else id(component)
        ) in split_component_ids
    if not shared_scope_counts:
        return False
    scope_counts: dict[str, int] = {}
    _subtree_requires_shared_scope(component, scope_counts, style)
    return any(
        0 < scope_counts.get(key, 0) < count
        for key, count in shared_scope_counts.items()
    )


def _component_uses_shared_scope(
    component: Component, shared_scope_counts: dict[str, int]
) -> bool:
    """Whether a component directly uses a hook scope shared across components.

    Args:
        component: Component being considered for memoization.
        shared_scope_counts: Shared hook scopes present on the page.

    Returns:
        Whether the component directly carries a shared-scope Var.
    """
    if not shared_scope_counts:
        return False
    return any(
        key in shared_scope_counts
        for var in component._get_vars(include_children=False)
        if (var_data := var._get_all_var_data()) is not None
        for key in var_data.shared_scope_keys
    )


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

    Explicitly memoized (``@rx.memo``) components are no exception: React's
    ``memo`` only spares their own subtree, so state bound at the call site
    still needs a wrapper to keep the hooks out of the page module. The
    wrappers this pass generates are themselves memo components and opt out
    via ``MemoizationDisposition.NEVER``.

    Args:
        component: The candidate component.

    Returns:
        True if the component should be wrapped in a memo definition.
    """
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

    style: ComponentStyle | None = None

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
        root = page_context.root_component
        if comp is root or page_context._owned.get(id(root)) is comp:
            subtree_counts: dict[int, dict[str, int]] = {}
            root_counts = _collect_subtree_shared_scope_counts(
                comp, subtree_counts, set(), self.style
            )
            if root_counts is None:
                # Preserve the cycle-safe fallback for unusual component graphs.
                scope_counts: dict[str, int] = {}
                _subtree_requires_shared_scope(comp, scope_counts, self.style)
                page_context.memoize_shared_scope_split_ids = None
            else:
                scope_counts = root_counts
                if any(count > 1 for count in scope_counts.values()):
                    page_context.memoize_shared_scope_split_ids = {
                        component_id
                        for component_id, counts in subtree_counts.items()
                        if any(
                            0 < counts.get(key, 0) < count
                            for key, count in scope_counts.items()
                            if count > 1
                        )
                    }
                else:
                    page_context.memoize_shared_scope_split_ids = set()
            page_context.memoize_shared_scope_counts = {
                key: count for key, count in scope_counts.items() if count > 1
            }
        if page_context.memoize_suppressor_stack:
            return None
        strategy = get_memoization_strategy(comp)
        if strategy is not MemoizationStrategy.SNAPSHOT:
            return None
        snapshot_boundary = is_snapshot_boundary(comp)
        if _subtree_splits_shared_scope(
            comp,
            page_context.memoize_shared_scope_counts,
            page_context.memoize_shared_scope_split_ids,
            page_context._owned_original_ids.get(id(comp)),
            self.style,
        ):
            if snapshot_boundary:
                page_context.memoize_suppressor_stack.append(id(comp))
            return None

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
        if wrapper is not None:
            # Snapshot-boundary descendants are sealed from the page walker, so
            # ``DefaultCollectorPlugin._collect_var_app_wraps`` never sees Vars
            # buried inside the boundary. Surface their app_wraps now (before
            # sealing) so providers declared via ``VarData.app_wraps`` still
            # reach the page-level app_wrap registry.
            collect_var_app_wraps_in_subtree(page_context.app_wrap_components, comp)
            return (wrapper, ())
        return None

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

        if _component_uses_shared_scope(comp, page_context.memoize_shared_scope_counts):
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

        # The collector plugin runs at HookOrder.POST — *after* this plugin
        # rewrites ``comp`` into its wrapper — so the wrapper (which holds no
        # Vars of its own) is what the collector sees for the current node.
        # Surface ``comp``'s own Var-declared app_wraps before returning the
        # wrapper. Descendants have already been visited by the collector, so
        # this only needs to look at the current node — not its subtree.
        page_context.app_wrap_components.update(
            collect_var_app_wraps_for_component(page_context.app_wrap_components, comp)
        )

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
        comp = fix_event_triggers_for_memo(comp, page_context)

        # Passthrough memo definitions capture app-specific event/state vars, so
        # they must be rebuilt for each compile instead of shared globally. The
        # tag is derived from the rendered memo body inside
        # ``create_passthrough_component_memo`` after the ``{children}`` hole
        # is substituted, so passthrough wrappers that differ only in their
        # children collapse to a single definition.
        wrapper_factory, definition = create_passthrough_component_memo(
            comp, source_module=page_context.source_module
        )
        tag = definition.export_name
        compile_context.memoize_wrappers[tag] = None
        # Key by (tag, source_module) so identical-rendering subtrees from
        # different user modules each get their own entry and emit into the
        # right mirrored memo file.
        compile_context.auto_memo_components[tag, definition.source_module] = definition

        wrapper = wrapper_factory()
        # The wrapper has no structural children at the page level, but parents
        # walking ``_get_all_refs`` (e.g. ``Form._get_form_refs`` collecting
        # ref_<id> mappings into ``handleSubmit``) need to see refs from the
        # wrapped subtree. Delegate ref collection to the original component
        # so descendants inside the memo body remain reachable for ref lookup.
        object.__setattr__(wrapper, "_get_all_refs", comp._get_all_refs)
        # Keep each ref's owning control available after replacing the subtree.
        object.__setattr__(wrapper, "_form_control_source", comp)
        return wrapper


__all__ = ["MemoizeStatefulPlugin"]
