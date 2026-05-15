"""Post-compile accounting helpers for the ``compile`` telemetry event."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, TypedDict

from reflex_base.config import get_config
from reflex_base.utils import console

from reflex.utils import telemetry
from reflex.utils.telemetry_context import (
    _KNOWN_FEATURES,
    TelemetryContext,
    _recorded_features,
    increment_feature,
)

__all__ = ["increment_feature", "record_compile"]

if TYPE_CHECKING:
    from reflex_base.components.component import BaseComponent

    from reflex.app import App
    from reflex.state import BaseState
    from reflex.utils.telemetry_context import CompileTrigger, FeatureName


class _StateStats(TypedDict):
    """Per-state structural statistics."""

    event_handlers_count: int
    vars_count: int
    backend_vars_count: int
    computed_vars_count: int
    depth_from_root: int


class _ExceptionInfo(TypedDict):
    """Sanitized exception descriptor (class name only, no message)."""

    type: str


class _CompileEventProperties(TypedDict):
    """Properties payload of the ``compile`` telemetry event."""

    plugins_enabled: list[str]
    plugins_disabled: list[str]
    pages_count: int
    component_counts: dict[str, int]
    states: list[_StateStats]
    features_used: dict[FeatureName, int]
    duration_ms: int
    trigger: CompileTrigger | None
    exception: _ExceptionInfo | None


def record_compile(app: App, ctx: TelemetryContext) -> None:
    """Build the compile-event payload and send it to PostHog.

    Any exception from payload assembly or sending is swallowed and logged
    so telemetry can never break a real compile.

    Args:
        app: The compiled application.
        ctx: The active telemetry context.
    """
    try:
        payload = _collect_compile_event_payload(app, ctx)
        telemetry.send("compile", properties=dict(payload))
    except Exception as exc:
        console.debug(f"compile telemetry event failed: {exc!r}")


def _collect_compile_event_payload(
    app: App, ctx: TelemetryContext
) -> _CompileEventProperties:
    """Build the properties dict sent with the ``compile`` PostHog event.

    Args:
        app: The compiled application.
        ctx: The active telemetry context.

    Returns:
        The properties dict to send to PostHog.
    """
    config = get_config()
    user_states = list(_walk_states(app._state))
    return {
        "plugins_enabled": [p.__class__.__name__ for p in config.plugins],
        "plugins_disabled": [p.__name__ for p in config.disable_plugins],
        "pages_count": len(app._pages),
        "component_counts": _count_components(app._pages.values()),
        "states": [_collect_state_stats(s) for s in user_states],
        "features_used": _collect_features_used(ctx, user_states),
        "duration_ms": ctx.elapsed_ms(),
        "trigger": ctx.trigger,
        "exception": _sanitize_exception(ctx.exception),
    }


def _count_components(pages: Iterable[BaseComponent]) -> dict[str, int]:
    """Count component types across one or more component trees.

    Auto-memoized components live in the tree as dynamic
    ``ExperimentalMemoComponent_<Type>_<tag>_<hash>`` subclasses. Bucketing by
    the raw class name would explode telemetry cardinality (each handler hash
    produces a new key), so wrappers are counted under the user-authored
    component they stand in for, exposed via ``_wrapped_component_type``.

    Args:
        pages: Component-tree roots to walk.

    Returns:
        Mapping of component class name to occurrence count.
    """
    counts: dict[str, int] = {}
    stack: list[BaseComponent] = list(pages)
    while stack:
        node = stack.pop()
        node_cls = type(node)
        wrapped = getattr(node_cls, "_wrapped_component_type", None)
        name = wrapped.__name__ if wrapped is not None else node_cls.__name__
        counts[name] = counts.get(name, 0) + 1
        if node.children:
            stack.extend(node.children)
    return counts


def _walk_states(root: type[BaseState] | None) -> Iterator[type[BaseState]]:
    """Yield user-authored state classes reachable from ``root``.

    Framework-internal states (those whose module lives under ``reflex.``) are
    skipped, but their user-defined subclasses are still yielded — ``SharedState``
    user classes hang off ``SharedStateBaseInternal``, so we descend through the
    internal node rather than pruning the subtree.

    Args:
        root: The root state class, or ``None`` when the app has no state.

    Yields:
        Every user-authored state class reachable through ``get_substates()``.
    """
    if root is None:
        return
    if root.is_user_defined():
        yield root
    for sub in root.get_substates():
        yield from _walk_states(sub)


def _collect_state_stats(state_cls: type[BaseState]) -> _StateStats:
    """Collect structural statistics for a single state class.

    Args:
        state_cls: The state class to inspect.

    Returns:
        A dict with field counts and depth-from-root.
    """
    depth = 0
    parent = state_cls.get_parent_state()
    while parent is not None:
        depth += 1
        parent = parent.get_parent_state()
    return {
        "event_handlers_count": len(state_cls.event_handlers),
        "vars_count": len(state_cls.vars),
        "backend_vars_count": len(state_cls.backend_vars),
        "computed_vars_count": len(state_cls.computed_vars),
        "depth_from_root": depth,
    }


def _sanitize_exception(exc: BaseException | None) -> _ExceptionInfo | None:
    """Return a sanitized dict describing an exception, or ``None``.

    Only the exception class name is included. No message, no traceback,
    no cause/context chain, no file paths.

    Args:
        exc: The exception to sanitize, or ``None``.

    Returns:
        ``None`` when ``exc`` is ``None``, else ``{"type": <class name>}``.
    """
    if exc is None:
        return None
    return {"type": type(exc).__name__}


def _collect_features_used(
    ctx: TelemetryContext, user_states: list[type[BaseState]]
) -> dict[FeatureName, int]:
    """Build the ``features_used`` snapshot for the compile event.

    Every known feature ships with its invocation count (zero by default), so
    consumers don't have to distinguish "feature not used" from "detector broken."

    Args:
        ctx: The active telemetry context.
        user_states: Pre-walked user state classes (shared with state stats).

    Returns:
        Dict of feature key -> invocation count.
    """
    features: dict[FeatureName, int] = dict.fromkeys(_KNOWN_FEATURES, 0)
    features.update(_recorded_features)
    _record_config_attestations(features)
    _record_background_handler_count(features, user_states)
    features.update(ctx.features_used)
    return features


_STATE_MANAGER_FEATURE: dict[str, FeatureName] = {
    "disk": "state_manager_disk",
    "memory": "state_manager_memory",
    "redis": "state_manager_redis",
}


def _record_config_attestations(features: dict[FeatureName, int]) -> None:
    """Write config-derived feature counts (state-manager mode, CORS).

    Args:
        features: The snapshot to populate.
    """
    config = get_config()
    key = _STATE_MANAGER_FEATURE.get(config.state_manager_mode.value)
    if key is not None:
        features[key] = 1
    if tuple(config.cors_allowed_origins) != ("*",):
        features["cors_customized"] = 1


def _record_background_handler_count(
    features: dict[FeatureName, int], user_states: list[type[BaseState]]
) -> None:
    """Count ``@rx.event(background=True)`` handlers across user states.

    Args:
        features: The snapshot to populate.
        user_states: Pre-walked user state classes.
    """
    features["background_event_handlers_count"] = sum(
        1
        for state_cls in user_states
        for handler in state_cls.event_handlers.values()
        if handler.is_background
    )
