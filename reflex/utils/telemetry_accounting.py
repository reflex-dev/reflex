"""Post-compile accounting helpers for the ``compile`` telemetry event."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any, TypedDict

from reflex_base.config import get_config
from reflex_base.telemetry_context import _KNOWN_FEATURES, TelemetryContext
from reflex_base.utils import console
from reflex_components_core.core.upload import Upload

from reflex.istate.shared import SharedState
from reflex.istate.storage import (
    ClientStorageBase,
    Cookie,
    LocalStorage,
    SessionStorage,
)
from reflex.model import ModelRegistry
from reflex.utils import telemetry

_HAS_SQLALCHEMY = find_spec("sqlalchemy") is not None

__all__ = ["record_compile"]

if TYPE_CHECKING:
    from reflex_base.components.component import BaseComponent
    from reflex_base.telemetry_context import CompileTrigger, FeatureName

    from reflex.app import App
    from reflex.state import BaseState


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


class _ComponentWalk(TypedDict):
    """Aggregated outputs from a single pass over the compiled page trees."""

    counts: dict[str, int]
    upload_count: int


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
    component_walk = _walk_components(app._pages.values())
    return {
        "plugins_enabled": [p.__class__.__name__ for p in config.plugins],
        "plugins_disabled": [p.__name__ for p in config.disable_plugins],
        "pages_count": len(app._pages),
        "component_counts": component_walk["counts"],
        "states": [_collect_state_stats(s) for s in user_states],
        "features_used": _collect_features_used(app, user_states, component_walk),
        "duration_ms": ctx.elapsed_ms(),
        "trigger": ctx.trigger,
        "exception": _sanitize_exception(ctx.exception),
    }


def _walk_components(pages: Iterable[BaseComponent]) -> _ComponentWalk:
    """Walk page trees once and aggregate every telemetry signal we need.

    Auto-memoized components live in the tree as dynamic
    ``ExperimentalMemoComponent_<Type>_<tag>_<hash>`` subclasses. Bucketing by
    the raw class name would explode telemetry cardinality (each handler hash
    produces a new key), so wrappers are counted under the user-authored
    component they stand in for, exposed via ``_wrapped_component_type``.

    Args:
        pages: Component-tree roots to walk.

    Returns:
        A dict with ``counts`` (class name to occurrence count) and
        ``upload_count`` (instances of ``Upload`` or its subclasses).
    """
    counts: dict[str, int] = {}
    upload_count = 0
    stack: list[BaseComponent] = list(pages)
    while stack:
        node = stack.pop()
        if isinstance(node, Upload):
            upload_count += 1
        node_cls = type(node)
        wrapped = getattr(node_cls, "_wrapped_component_type", None)
        name = wrapped.__name__ if wrapped is not None else node_cls.__name__
        counts[name] = counts.get(name, 0) + 1
        if node.children:
            stack.extend(node.children)
    return {"counts": counts, "upload_count": upload_count}


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
    app: App,
    user_states: list[type[BaseState]],
    component_walk: _ComponentWalk,
) -> dict[FeatureName, int]:
    """Build the ``features_used`` snapshot for the compile event.

    Every known feature ships with its invocation count, derived from a fresh
    walk of the live app at compile end. State, app, component, and config
    walks are the single source of truth — there are no marker writes to
    merge in.

    Args:
        app: The compiled application.
        user_states: Pre-walked user state classes (shared with state stats).
        component_walk: Pre-computed component-tree aggregates.

    Returns:
        Dict of feature key -> invocation count.
    """
    features: dict[FeatureName, int] = dict.fromkeys(_KNOWN_FEATURES, 0)
    _walk_state_features(features, user_states)
    _walk_app_features(features, app)
    features["upload_count"] = component_walk["upload_count"]
    if _HAS_SQLALCHEMY:
        features["db_model_count"] = len(ModelRegistry.get_models())
    _record_config_attestations(features)
    return features


_STATE_MANAGER_FEATURE: dict[str, FeatureName] = {
    "disk": "state_manager_disk",
    "memory": "state_manager_memory",
    "redis": "state_manager_redis",
}

_STORAGE_FEATURE: dict[type[ClientStorageBase], FeatureName] = {
    Cookie: "cookie_count",
    LocalStorage: "local_storage_count",
    SessionStorage: "session_storage_count",
}


def _walk_state_features(
    features: dict[FeatureName, int], user_states: list[type[BaseState]]
) -> None:
    """Derive per-state feature counts in one pass over user states.

    Args:
        features: The snapshot to populate.
        user_states: Pre-walked user state classes.
    """
    storage_counts: dict[FeatureName, int] = dict.fromkeys(_STORAGE_FEATURE.values(), 0)
    shared = background = 0
    for state_cls in user_states:
        if issubclass(state_cls, SharedState):
            shared += 1
        for handler in state_cls.event_handlers.values():
            if handler.is_background:
                background += 1
        for field in state_cls.get_fields().values():
            key = _storage_feature_for_field(field)
            if key is not None:
                storage_counts[key] += 1
    features.update(storage_counts)
    features["shared_state_count"] = shared
    features["background_event_handlers_count"] = background


def _walk_app_features(features: dict[FeatureName, int], app: App) -> None:
    """Derive per-app feature counts (dynamic routes, lifespan tasks).

    Args:
        features: The snapshot to populate.
        app: The compiled application.
    """
    features["dynamic_routes_count"] = sum(
        1 for route in app._unevaluated_pages if "[" in route
    )
    user_tasks = 0
    for task in app.get_lifespan_tasks():
        module = getattr(task, "__module__", None) or ""
        if module != "reflex" and not module.startswith("reflex."):
            user_tasks += 1
    features["lifespan_tasks_count"] = user_tasks


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


def _storage_feature_for_field(field: Any) -> FeatureName | None:
    """Return the feature key for a client-storage state field, or None.

    Mirrors ``BaseState._is_client_storage``: detected by an instance default
    or by a ``ClientStorageBase`` subclass annotation. Walks the MRO so user
    subclasses of ``Cookie`` / ``LocalStorage`` / ``SessionStorage`` are
    bucketed under their parent.

    Args:
        field: A pydantic ``ModelField`` from ``state_cls.get_fields()``.

    Returns:
        The feature key, or ``None`` if the field isn't a client-storage var.
    """
    default = field.default
    if isinstance(default, ClientStorageBase):
        cls: type = type(default)
    elif isinstance(field.type_, type) and issubclass(field.type_, ClientStorageBase):
        cls = field.type_
    else:
        return None
    for ancestor in cls.__mro__:
        feature = _STORAGE_FEATURE.get(ancestor)
        if feature is not None:
            return feature
    return None
