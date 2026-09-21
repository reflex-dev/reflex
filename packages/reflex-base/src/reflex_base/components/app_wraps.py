"""Collection of the app-wrap components a component subtree requires.

App wraps are requested in two ways: a component class declares them with
:meth:`Component._get_app_wrap_components`, or a Var carries them on its
``VarData.app_wraps`` (the ``UploadFilesProvider`` behind ``rx.upload`` is the
canonical example). The compiler collects both while walking a page, so these
helpers exist for the places the page walk doesn't reach -- sealed memo bodies,
snapshot-boundary subtrees, and the app-wrap chain itself.
"""

from __future__ import annotations

from reflex_base.components.component import BaseComponent, Component
from reflex_base.components.state_context import get_events_hooks_var_data
from reflex_base.constants.compiler import Hooks
from reflex_base.vars import VarData
from reflex_base.vars.base import insert_app_wraps


def collect_var_app_wraps_in_subtree(
    page_app_wrap_components: dict[tuple[int, str], Component],
    root: Component,
) -> None:
    """Walk ``root`` and its descendants, surfacing Var-declared app_wraps.

    Each visited component contributes via :func:`collect_var_app_wraps_for_component`.
    Used wherever the page walker doesn't reach — e.g. snapshot-boundary
    descendants sealed by ``MemoizeStatefulPlugin``, or the app-wrap chain
    components assembled by ``App._app_root`` (their own subtrees, e.g.
    ``ErrorBoundary``'s fallback render, are not pages).

    Args:
        page_app_wrap_components: Registry that receives the collected wraps.
        root: The subtree root to walk.
    """
    visited: set[int] = set()
    stack: list[Component] = [root]
    while stack:
        node = stack.pop()
        node_id = id(node)
        if node_id in visited:
            continue
        visited.add(node_id)
        page_app_wrap_components.update(
            collect_var_app_wraps_for_component(page_app_wrap_components, node)
        )
        stack.extend(child for child in node.children if isinstance(child, Component))
        stack.extend(
            component
            for component in node._get_components_in_props()
            if isinstance(component, Component)
        )


def collect_subtree_app_wraps(root: Component) -> dict[tuple[int, str], Component]:
    """Collect every app wrap ``root``'s subtree requires.

    Covers both categories at once: the class-declared wraps that
    :meth:`Component._get_all_app_wrap_components` gathers from the structural
    children, and the Var-declared ones (including the event providers implied
    by event triggers) that :func:`collect_var_app_wraps_in_subtree` gathers
    from structural children and prop subtrees alike. That split mirrors what
    the page collector does for components it walks itself.

    Args:
        root: The subtree root whose requirements to collect.

    Returns:
        Mapping of ``(priority, name)`` -> wrapper component.
    """
    app_wraps = root._get_all_app_wrap_components()
    collect_var_app_wraps_in_subtree(app_wraps, root)
    return app_wraps


def _ingest_component_var_app_wraps(
    wraps_by_key: dict[tuple[int, str], Component],
    existing: dict[tuple[int, str], Component],
    component: Component,
    hooks_internal: dict[str, VarData | None],
    added_hooks: dict[str, VarData | None],
) -> None:
    """Ingest app_wraps from a component's Vars, pre-fetched hooks, and events.

    Scans the component's Vars (props/style/event-trigger args), the VarData on
    its framework-managed internal hooks and ``add_hooks`` output (e.g.
    ``Hooks.EVENTS``), and the state/event-loop providers it requires via
    :meth:`Component._get_event_app_wraps`.

    ``hooks_internal`` and ``added_hooks`` are supplied by the caller rather than
    re-fetched here so the page collector — which already pulls them to populate
    ``page_hooks`` — doesn't pay for a second ``_get_hooks_internal`` /
    ``_get_added_hooks`` (and the latter is uncached). New entries are written
    into ``wraps_by_key``; entries already in ``existing`` are skipped.

    Args:
        wraps_by_key: Registry that receives the newly seen wraps.
        existing: Already-committed wraps to dedupe against without writing.
        component: The component to scan.
        hooks_internal: The component's framework-managed internal hooks.
        added_hooks: The component's ``add_hooks`` output.
    """
    for var in component._get_vars():
        var_data = var._get_all_var_data()
        if var_data is None:
            continue
        _ingest_var_data_app_wraps(wraps_by_key, existing, var_data)
    for hook_var_data in hooks_internal.values():
        if hook_var_data is None:
            continue
        _ingest_var_data_app_wraps(wraps_by_key, existing, hook_var_data)
    for hook, hook_var_data in added_hooks.items():
        if hook_var_data is None and hook == Hooks.EVENTS:
            hook_var_data = get_events_hooks_var_data()
        if hook_var_data is None:
            continue
        _ingest_var_data_app_wraps(wraps_by_key, existing, hook_var_data)
    insert_app_wraps(
        wraps_by_key,
        (
            (priority, wrapper)
            for (priority, _tag), wrapper in component._get_event_app_wraps().items()
        ),
        existing=existing,
    )


def collect_var_app_wraps_for_component(
    page_app_wrap_components: dict[tuple[int, str], Component],
    component: Component,
) -> dict[tuple[int, str], Component]:
    """Return Var-declared app_wraps newly contributed by ``component``.

    Convenience wrapper over :func:`_ingest_component_var_app_wraps` for callers
    (snapshot-boundary and app-root walks) that don't already have the
    component's hooks in hand. The page collector fetches the hooks once and
    calls the underlying helper directly instead.

    Entries already in ``page_app_wrap_components`` are skipped, leaving the
    caller to decide how to merge the result and whether to recurse into
    each wrapper's own subtree.

    Args:
        page_app_wrap_components: Already-committed wraps to dedupe against.
        component: The component to scan.

    Returns:
        Mapping of ``(priority, name)`` -> wrapper for new entries only.
    """
    wraps_by_key: dict[tuple[int, str], Component] = {}
    _ingest_component_var_app_wraps(
        wraps_by_key,
        page_app_wrap_components,
        component,
        component._get_hooks_internal(),
        component._get_added_hooks(),
    )
    return wraps_by_key


def _ingest_var_data_app_wraps(
    wraps_by_key: dict[tuple[int, str], Component],
    existing: dict[tuple[int, str], Component],
    var_data: VarData,
) -> None:
    """Insert app_wraps carried or implied by ``var_data``.

    Args:
        wraps_by_key: Registry that receives the newly seen wraps.
        existing: Already-committed wraps to dedupe against without writing.
        var_data: The var data to read declarations from.
    """
    if var_data.app_wraps:
        _ingest_app_wraps(wraps_by_key, existing, var_data.app_wraps)
    if Hooks.EVENTS in var_data.hooks:
        _ingest_app_wraps(
            wraps_by_key,
            existing,
            get_events_hooks_var_data().app_wraps,
        )


def _ingest_app_wraps(
    wraps_by_key: dict[tuple[int, str], Component],
    existing: dict[tuple[int, str], Component],
    app_wraps: tuple[tuple[int, BaseComponent], ...],
) -> None:
    """Insert app_wraps not already present in ``existing`` or ``wraps_by_key``.

    Args:
        wraps_by_key: Registry that receives the newly seen wraps.
        existing: Already-committed wraps to dedupe against without writing.
        app_wraps: The ``(priority, wrapper)`` requests to merge in.
    """
    insert_app_wraps(
        wraps_by_key,
        (
            (priority, wrapper)
            for priority, wrapper in app_wraps
            if isinstance(wrapper, Component)
        ),
        existing=existing,
    )
