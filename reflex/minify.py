"""Minification configuration for state and event names.

This module provides centralized ID management for minifying state and event
handler names. The configuration is stored in a ``minify.json`` file at the
project root.

The minification entry point is :class:`MinifyNameResolver`, an implementation
of :class:`reflex_base.registry.NameResolver`. To enable minification at
runtime, install the resolver into the active registration context::

    from reflex.minify import MinifyNameResolver
    from reflex_base.registry import RegistrationContext

    RegistrationContext.get().set_name_resolver(MinifyNameResolver.from_disk())

:func:`clear_config_cache` does this automatically — call it whenever
``minify.json`` or the ``REFLEX_MINIFY_*`` environment variables change.
"""

from __future__ import annotations

import dataclasses
import functools
import json
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from reflex.state import BaseState

# File name for the minify configuration
MINIFY_JSON = "minify.json"

# Current schema version
SCHEMA_VERSION = 1


class MinifyConfig(TypedDict):
    """Schema for minify.json file.

    Version 2 format:
    - states: dict mapping state_path -> minified_name (string)
    - events: dict mapping state_path -> {handler_name -> minified_name}
    """

    version: int
    states: dict[str, str]  # state_path -> minified_name
    events: dict[str, dict[str, str]]  # state_path -> {handler_name -> minified_name}


def _get_minify_json_path() -> Path:
    """Get the path to the minify.json file.

    Returns:
        Path to minify.json in the current working directory.
    """
    return Path.cwd() / MINIFY_JSON


def _load_minify_config_uncached() -> MinifyConfig | None:
    """Load minify configuration from minify.json.

    Returns:
        The parsed configuration, or None if file doesn't exist.

    Raises:
        ValueError: If the file exists but has an invalid format.
    """
    path = _get_minify_json_path()
    if not path.exists():
        return None

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in {MINIFY_JSON}: {e}"
        raise ValueError(msg) from e

    # Validate schema version
    version = data.get("version")
    if version != SCHEMA_VERSION:
        msg = (
            f"Unsupported {MINIFY_JSON} version: {version}. Expected {SCHEMA_VERSION}."
        )
        raise ValueError(msg)

    # Validate required keys
    if "states" not in data or not isinstance(data["states"], dict):
        msg = f"Invalid {MINIFY_JSON}: 'states' must be a dictionary."
        raise ValueError(msg)
    if "events" not in data or not isinstance(data["events"], dict):
        msg = f"Invalid {MINIFY_JSON}: 'events' must be a dictionary."
        raise ValueError(msg)

    # Validate states: all values must be strings
    for key, value in data["states"].items():
        if not isinstance(value, str):
            msg = f"Invalid {MINIFY_JSON}: state '{key}' has non-string id: {value}"
            raise ValueError(msg)

    # Validate events: must be dict of dicts with string values
    for state_path, handlers in data["events"].items():
        if not isinstance(handlers, dict):
            msg = f"Invalid {MINIFY_JSON}: events for '{state_path}' must be a dictionary."
            raise ValueError(msg)
        for handler_name, event_id in handlers.items():
            if not isinstance(event_id, str):
                msg = f"Invalid {MINIFY_JSON}: event '{state_path}.{handler_name}' has non-string id: {event_id}"
                raise ValueError(msg)

    return MinifyConfig(
        version=data["version"],
        states=data["states"],
        events=data["events"],
    )


@functools.cache
def get_minify_config() -> MinifyConfig | None:
    """Get the minify configuration, cached.

    This function is cached so the file is only read once per process.

    Returns:
        The parsed configuration, or None if file doesn't exist.
    """
    return _load_minify_config_uncached()


def is_minify_enabled() -> bool:
    """Check if any minification is enabled (state or event).

    Returns:
        True if either state or event minification is enabled.
    """
    return is_state_minify_enabled() or is_event_minify_enabled()


@functools.cache
def is_state_minify_enabled() -> bool:
    """Check if state ID minification is enabled.

    Requires both REFLEX_MINIFY_STATE=enabled and minify.json to exist.

    Returns:
        True if state minification is enabled.
    """
    from reflex.environment import MinifyMode, environment

    return (
        environment.REFLEX_MINIFY_STATES.get() == MinifyMode.ENABLED
        and get_minify_config() is not None
    )


@functools.cache
def is_event_minify_enabled() -> bool:
    """Check if event ID minification is enabled.

    Requires both REFLEX_MINIFY_EVENTS=enabled and minify.json to exist.

    Returns:
        True if event minification is enabled.
    """
    from reflex.environment import MinifyMode, environment

    return (
        environment.REFLEX_MINIFY_EVENTS.get() == MinifyMode.ENABLED
        and get_minify_config() is not None
    )


def get_state_id(state_full_path: str) -> str | None:
    """Get the minified ID for a state.

    Args:
        state_full_path: The full path to the state (e.g., "myapp.state.AppState.UserState").

    Returns:
        The minified state name (e.g., "a", "ba") if configured, None otherwise.
    """
    config = get_minify_config()
    if config is None:
        return None
    return config["states"].get(state_full_path)


def get_event_id(state_full_path: str, handler_name: str) -> str | None:
    """Get the minified ID for an event handler.

    Args:
        state_full_path: The full path to the state.
        handler_name: The name of the event handler.

    Returns:
        The minified event name (e.g., "a", "ba") if configured, None otherwise.
    """
    config = get_minify_config()
    if config is None:
        return None
    state_events = config["events"].get(state_full_path)
    if state_events is None:
        return None
    return state_events.get(handler_name)


def save_minify_config(config: MinifyConfig) -> None:
    """Save minify configuration to minify.json.

    Args:
        config: The configuration to save.
    """
    path = _get_minify_json_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")


@dataclasses.dataclass(slots=True)
class MinifyNameResolver:
    """:class:`~reflex_base.registry.NameResolver` driven by ``minify.json``.

    Returns the minified name from the configuration when the corresponding
    ``REFLEX_MINIFY_STATES`` / ``REFLEX_MINIFY_EVENTS`` env-var is set to
    ``enabled`` *and* the entry exists in the config. All other lookups return
    ``None`` so the registry falls back to the default name.

    The resolver is constructed once (typically via :meth:`from_disk`) and
    held by the active :class:`~reflex_base.registry.RegistrationContext`.
    Per-class lookups are memoized in ``_state_cache`` and ``_event_cache``
    for O(1) amortized cost on the hot path.

    Attributes:
        config: The parsed ``minify.json`` content, or ``None`` when the file
            is absent or malformed.
        states_enabled: Whether ``REFLEX_MINIFY_STATES`` is on.
        events_enabled: Whether ``REFLEX_MINIFY_EVENTS`` is on.
    """

    config: MinifyConfig | None
    states_enabled: bool
    events_enabled: bool
    _state_cache: dict[type[BaseState], str] = dataclasses.field(
        default_factory=dict, repr=False
    )
    _event_cache: dict[type[BaseState], dict[str, str]] = dataclasses.field(
        default_factory=dict, repr=False
    )

    @classmethod
    def from_disk(cls) -> MinifyNameResolver:
        """Build a resolver from the current ``minify.json`` and env vars.

        Reads each input exactly once. Subsequent state/event lookups never
        touch the filesystem.

        Returns:
            A configured resolver. May still return ``None`` from every lookup
            if minification is disabled or the config file is absent.
        """
        from reflex.environment import MinifyMode, environment

        config: MinifyConfig | None
        try:
            config = _load_minify_config_uncached()
        except ValueError:
            # Treat malformed config as "no config" for the resolver — callers
            # that need to surface the error can read it via get_minify_config.
            config = None
        return cls(
            config=config,
            states_enabled=environment.REFLEX_MINIFY_STATES.get() == MinifyMode.ENABLED,
            events_enabled=environment.REFLEX_MINIFY_EVENTS.get() == MinifyMode.ENABLED,
        )

    def resolve_state_name(self, state_cls: type[BaseState]) -> str | None:  # noqa: D102
        if not (self.states_enabled and self.config):
            return None
        cached = self._state_cache.get(state_cls)
        if cached is not None:
            return cached
        resolved = self.config["states"].get(get_state_full_path(state_cls))
        if resolved is not None:
            self._state_cache[state_cls] = resolved
        return resolved

    def resolve_handler_name(  # noqa: D102
        self, state_cls: type[BaseState], handler_name: str
    ) -> str | None:
        if not (self.events_enabled and self.config):
            return None
        per_state = self._event_cache.get(state_cls)
        if per_state is None:
            per_state = self.config["events"].get(get_state_full_path(state_cls), {})
            self._event_cache[state_cls] = per_state
        return per_state.get(handler_name)


def install_minify_resolver() -> None:
    """Install a fresh :class:`MinifyNameResolver` into the active context.

    Use this after the user's app has been imported (so the registration
    context contains the right state classes) to switch the framework over
    to minified names.

    Returns silently if no registration context is currently attached.
    """
    try:
        from reflex_base.registry import RegistrationContext

        ctx = RegistrationContext.get()
    except LookupError:
        return
    ctx.set_name_resolver(MinifyNameResolver.from_disk())


def clear_config_cache() -> None:
    """Reload the minify configuration and propagate it through the registry.

    Clears the module-level lru_caches for :func:`get_minify_config`,
    :func:`is_state_minify_enabled`, :func:`is_event_minify_enabled`, then
    rebuilds the :class:`MinifyNameResolver` from the current
    ``minify.json`` / env vars and installs it via
    :meth:`reflex_base.registry.RegistrationContext.set_name_resolver`. The
    set-resolver call clears per-class name caches and re-keys the registry
    in one atomic step.

    Call this whenever ``minify.json`` is rewritten programmatically, or
    after monkey-patching ``REFLEX_MINIFY_STATES`` / ``REFLEX_MINIFY_EVENTS``
    at runtime.
    """
    get_minify_config.cache_clear()
    is_state_minify_enabled.cache_clear()
    is_event_minify_enabled.cache_clear()
    install_minify_resolver()


# Base-54 encoding for minified names
# Using letters (a-z, A-Z) plus $ and _ which are valid JS identifier chars
_MINIFY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$_"
_MINIFY_BASE = len(_MINIFY_CHARS)  # 54


def int_to_minified_name(id_: int) -> str:
    """Convert integer ID to minified name using base-54 encoding.

    Args:
        id_: The integer ID to convert.

    Returns:
        A minified string representation.

    Raises:
        ValueError: If id_ is negative.
    """
    if id_ < 0:
        msg = f"ID must be non-negative, got {id_}"
        raise ValueError(msg)

    # Special case: 0 maps to 'a'
    if id_ == 0:
        return _MINIFY_CHARS[0]

    result = []
    num = id_
    while num > 0:
        result.append(_MINIFY_CHARS[num % _MINIFY_BASE])
        num //= _MINIFY_BASE

    return "".join(reversed(result))


def minified_name_to_int(name: str) -> int:
    """Convert minified name back to integer ID.

    Args:
        name: The minified string to convert.

    Returns:
        The integer ID.

    Raises:
        ValueError: If name contains invalid characters.
    """
    result = 0
    for char in name:
        idx = _MINIFY_CHARS.find(char)
        if idx == -1:
            msg = f"Invalid character in minified name: '{char}'"
            raise ValueError(msg)
        result = result * _MINIFY_BASE + idx
    return result


def get_state_full_path(state_cls: type[BaseState]) -> str:
    """Get the full path for a state class suitable for minify.json.

    This returns the module path plus class name hierarchy, which uniquely
    identifies a state class.

    Args:
        state_cls: The state class.

    Returns:
        The full path string (e.g., "myapp.state.AppState.UserState").
    """
    # Build the path from module + class hierarchy
    # Use __original_module__ if available (for dynamic states that get moved)
    module = getattr(state_cls, "__original_module__", None) or state_cls.__module__
    parts = [module]

    # Get the class hierarchy from root to this class
    class_hierarchy = []
    current: type[BaseState] | None = state_cls
    while current is not None:
        class_hierarchy.append(current.__name__)
        current = current.get_parent_state()  # type: ignore[union-attr]

    # Reverse to get root-to-leaf order
    class_hierarchy.reverse()

    # Combine module and class hierarchy
    parts.extend(class_hierarchy)
    return ".".join(parts)


def collect_all_states(
    root_state: type[BaseState] | None = None,
) -> list[type[BaseState]]:
    """Collect state classes in deterministic depth-first order.

    Without ``root_state``, walks every state registered in the active
    :class:`~reflex_base.registry.RegistrationContext` (each connected tree
    starting from a parentless root), sorting siblings alphabetically by
    class name. With ``root_state``, the walk is restricted to that subtree.

    The CLI commands use the parameterless form so the result reflects the
    user's currently-loaded app. Tests typically pass an explicit root to
    scope the walk to the classes defined inside the test.

    Args:
        root_state: Optional subtree root. ``None`` means "every registered
            state".

    Returns:
        List of state classes in depth-first, sibling-sorted order.
    """
    if root_state is not None:
        result = [root_state]
        for substate in sorted(root_state.get_substates(), key=lambda s: s.__name__):
            result.extend(collect_all_states(substate))
        return result

    from reflex_base.registry import RegistrationContext

    ctx = RegistrationContext.get()
    roots = sorted(
        (cls for cls in ctx.base_states.values() if cls.get_parent_state() is None),
        key=lambda s: s.__name__,
    )
    out: list[type[BaseState]] = []
    for root in roots:
        out.extend(collect_all_states(root))
    return out


def generate_minify_config(
    root_state: type[BaseState] | None = None,
) -> MinifyConfig:
    """Generate a complete minify configuration.

    Walks the state tree (see :func:`collect_all_states`) and assigns minified
    names starting from ``"a"`` per sibling group. Siblings are sorted by
    class name and handlers by handler name so the output is byte-stable across
    runs (and therefore VCS-friendly).

    Args:
        root_state: Optional subtree root. ``None`` (the default) generates a
            config for every state registered in the active context.

    Returns:
        A complete :class:`MinifyConfig`.
    """
    states: dict[str, str] = {}
    events: dict[str, dict[str, str]] = {}
    sibling_counter: dict[type[BaseState] | None, int] = {}

    for state_cls in collect_all_states(root_state):
        parent = state_cls.get_parent_state()
        sibling_counter.setdefault(parent, 0)
        state_id = sibling_counter[parent]
        sibling_counter[parent] += 1

        state_path = get_state_full_path(state_cls)
        states[state_path] = int_to_minified_name(state_id)

        handler_names = sorted(state_cls.event_handlers.keys())
        if handler_names:
            events[state_path] = {
                handler_name: int_to_minified_name(event_id)
                for event_id, handler_name in enumerate(handler_names)
            }

    return MinifyConfig(
        version=SCHEMA_VERSION,
        states=states,
        events=events,
    )


def validate_minify_config(
    config: MinifyConfig,
    root_state: type[BaseState] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Validate a minify configuration against the current state tree.

    Args:
        config: The configuration to validate.
        root_state: Optional subtree root. ``None`` validates against every
            state in the active context.

    Returns:
        A tuple ``(errors, warnings, missing_entries)``:

        * ``errors`` — critical issues (duplicate IDs, etc.)
        * ``warnings`` — non-critical issues (orphaned entries)
        * ``missing_entries`` — states/events in code but not in the config
    """
    errors: list[str] = []

    all_states = collect_all_states(root_state)

    # Check for duplicate state IDs among siblings.
    # Group by actual parent class (not string-split path) since children of
    # the same parent can be defined in different modules.
    path_to_cls = {get_state_full_path(s): s for s in all_states}
    parent_cls_to_state_ids: dict[type[BaseState] | None, dict[str, list[str]]] = {}
    for state_path, minified_name in config["states"].items():
        state_cls = path_to_cls.get(state_path)
        parent_cls = state_cls.get_parent_state() if state_cls else None
        parent_cls_to_state_ids.setdefault(parent_cls, {}).setdefault(
            minified_name, []
        ).append(state_path)

    for parent_cls, id_to_states in parent_cls_to_state_ids.items():
        for minified_name, state_paths in id_to_states.items():
            if len(state_paths) > 1:
                parent_name = parent_cls.__name__ if parent_cls else "root"
                errors.append(
                    f"Duplicate state_id='{minified_name}' under '{parent_name}': "
                    f"{state_paths}"
                )

    # Check for duplicate event IDs within same state
    for state_path, state_events in config["events"].items():
        id_to_handlers: dict[str, list[str]] = {}
        for handler_name, minified_name in state_events.items():
            if minified_name not in id_to_handlers:
                id_to_handlers[minified_name] = []
            id_to_handlers[minified_name].append(handler_name)

        for minified_name, handler_names in id_to_handlers.items():
            if len(handler_names) > 1:
                errors.append(
                    f"Duplicate event_id='{minified_name}' in '{state_path}': {handler_names}"
                )

    # Check for missing states (in code but not in config)
    code_state_paths = {get_state_full_path(s) for s in all_states}
    missing: list[str] = [
        f"state:{state_path}"
        for state_path in code_state_paths
        if state_path not in config["states"]
    ]

    # Check for missing events (in code but not in config)
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        state_events = config["events"].get(state_path, {})
        missing.extend(
            f"event:{state_path}.{handler_name}"
            for handler_name in state_cls.event_handlers
            if handler_name not in state_events
        )

    # Check for orphaned entries (in config but not in code)
    warnings: list[str] = [
        f"Orphaned state in config: {state_path}"
        for state_path in config["states"]
        if state_path not in code_state_paths
    ]

    code_event_keys: dict[str, set[str]] = {}
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        code_event_keys[state_path] = set(state_cls.event_handlers.keys())

    for state_path, state_events in config["events"].items():
        if state_path not in code_event_keys:
            warnings.append(f"Orphaned events for state: {state_path}")
        else:
            warnings.extend(
                f"Orphaned event in config: {state_path}.{handler_name}"
                for handler_name in state_events
                if handler_name not in code_event_keys[state_path]
            )

    return errors, warnings, missing


def sync_minify_config(
    existing_config: MinifyConfig,
    root_state: type[BaseState] | None = None,
    reassign_deleted: bool = False,
    prune: bool = False,
) -> MinifyConfig:
    """Synchronize minify configuration with the current state tree.

    Args:
        existing_config: The existing configuration to update.
        root_state: Optional subtree root. ``None`` syncs against every state
            in the active context.
        reassign_deleted: If True, reassign IDs that are no longer in use.
        prune: If True, remove entries for states/events that no longer exist.

    Returns:
        The updated configuration.
    """
    all_states = collect_all_states(root_state)
    code_state_paths = {get_state_full_path(s) for s in all_states}

    # Build current event keys by state
    code_events_by_state: dict[str, set[str]] = {}
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        code_events_by_state[state_path] = set(state_cls.event_handlers.keys())

    new_states = dict(existing_config["states"])
    new_events: dict[str, dict[str, str]] = {
        k: dict(v) for k, v in existing_config["events"].items()
    }

    # Prune orphaned entries if requested
    if prune:
        new_states = {k: v for k, v in new_states.items() if k in code_state_paths}
        new_events = {
            state_path: {
                h: eid
                for h, eid in handlers.items()
                if h in code_events_by_state.get(state_path, set())
            }
            for state_path, handlers in new_events.items()
            if state_path in code_state_paths
        }
        # Remove empty event dicts
        new_events = {k: v for k, v in new_events.items() if v}

    # Build a map from actual parent class to existing sibling minified IDs.
    # Using the live state classes avoids the string-split bug where children
    # of the same parent class defined in different modules get different
    # string-based parent paths and are assigned colliding IDs.
    parent_cls_to_existing_ids: dict[type[BaseState] | None, set[int]] = {}
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        if state_path in new_states:
            parent = state_cls.get_parent_state()
            parent_cls_to_existing_ids.setdefault(parent, set()).add(
                minified_name_to_int(new_states[state_path])
            )

    # Find states that need IDs assigned, grouped by actual parent class.
    parent_cls_to_new_children: dict[type[BaseState] | None, list[str]] = {}
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        if state_path not in new_states:
            parent = state_cls.get_parent_state()
            parent_cls_to_new_children.setdefault(parent, []).append(state_path)

    # Assign new state IDs (unique among siblings of the same parent class)
    for parent_cls, children in parent_cls_to_new_children.items():
        existing_ids = parent_cls_to_existing_ids.get(parent_cls, set()).copy()

        # Assign IDs starting from max + 1 (or 0 if reassign_deleted and gaps exist)
        next_id = 0 if reassign_deleted else (max(existing_ids, default=-1) + 1)

        for state_path in sorted(children):
            while next_id in existing_ids:
                next_id += 1
            new_states[state_path] = int_to_minified_name(next_id)
            existing_ids.add(next_id)
            next_id += 1

    # Find events that need IDs assigned
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        state_events = new_events.get(state_path, {})
        new_handlers = [h for h in state_cls.event_handlers if h not in state_events]

        if new_handlers:
            # Get existing IDs for this state's events
            existing_ids = {minified_name_to_int(eid) for eid in state_events.values()}

            next_id = 0 if reassign_deleted else (max(existing_ids, default=-1) + 1)

            for handler_name in sorted(new_handlers):
                while next_id in existing_ids:
                    next_id += 1
                state_events[handler_name] = int_to_minified_name(next_id)
                existing_ids.add(next_id)
                next_id += 1

            new_events[state_path] = state_events

    return MinifyConfig(
        version=SCHEMA_VERSION,
        states=new_states,
        events=new_events,
    )
