"""Minification configuration for state and event names.

This module provides centralized ID management for minifying state and event handler
names. The configuration is stored in a `minify.json` file at the project root.
"""

from __future__ import annotations

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


def clear_config_cache() -> None:
    """Clear the cached configuration.

    This should be called after modifying minify.json programmatically.
    """
    get_minify_config.cache_clear()
    is_state_minify_enabled.cache_clear()
    is_event_minify_enabled.cache_clear()


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
    root_state: type[BaseState],
) -> list[type[BaseState]]:
    """Recursively collect all state classes starting from root.

    Args:
        root_state: The root state class to start from.

    Returns:
        List of all state classes in depth-first order.
    """
    result = [root_state]
    for substate in sorted(root_state.class_subclasses, key=lambda s: s.__name__):
        result.extend(collect_all_states(substate))
    return result


def generate_minify_config(root_state: type[BaseState]) -> MinifyConfig:
    """Generate a complete minify configuration for all states and events.

    Assigns minified names starting from 'a' for each scope (siblings get unique names),
    sorted alphabetically by name for determinism.

    Args:
        root_state: The root state class.

    Returns:
        A complete MinifyConfig.
    """
    states: dict[str, str] = {}
    events: dict[str, dict[str, str]] = {}

    def process_state(
        state_cls: type[BaseState],
        sibling_counter: dict[type[BaseState] | None, int],
    ) -> None:
        """Process a state and its children recursively.

        Args:
            state_cls: The state class to process.
            sibling_counter: Counter for assigning sibling-unique IDs.
        """
        parent = state_cls.get_parent_state()

        # Assign state ID (unique among siblings)
        if parent not in sibling_counter:
            sibling_counter[parent] = 0
        state_id = sibling_counter[parent]
        sibling_counter[parent] += 1

        # Store state minified name
        state_path = get_state_full_path(state_cls)
        states[state_path] = int_to_minified_name(state_id)

        # Assign event IDs for this state's handlers (sorted alphabetically)
        handler_names = sorted(state_cls.event_handlers.keys())
        state_events: dict[str, str] = {}
        for event_id, handler_name in enumerate(handler_names):
            state_events[handler_name] = int_to_minified_name(event_id)
        if state_events:
            events[state_path] = state_events

        # Process children (sorted alphabetically)
        children = sorted(state_cls.class_subclasses, key=lambda s: s.__name__)
        for child in children:
            process_state(child, sibling_counter)

    # Start processing from root
    sibling_counter: dict[type[BaseState] | None, int] = {}
    process_state(root_state, sibling_counter)

    return MinifyConfig(
        version=SCHEMA_VERSION,
        states=states,
        events=events,
    )


def validate_minify_config(
    config: MinifyConfig,
    root_state: type[BaseState],
) -> tuple[list[str], list[str], list[str]]:
    """Validate a minify configuration against the current state tree.

    Args:
        config: The configuration to validate.
        root_state: The root state class.

    Returns:
        A tuple of (errors, warnings, missing_entries):
        - errors: Critical issues (duplicate IDs, etc.)
        - warnings: Non-critical issues (orphaned entries)
        - missing_entries: States/events in code but not in config
    """
    errors: list[str] = []

    all_states = collect_all_states(root_state)

    # Check for duplicate state IDs among siblings
    # Group states by parent path and check for duplicate minified names
    parent_to_state_ids: dict[str | None, dict[str, list[str]]] = {}
    for state_path, minified_name in config["states"].items():
        # Get parent path
        parts = state_path.rsplit(".", 1)
        parent_path = parts[0] if len(parts) > 1 else None

        if parent_path not in parent_to_state_ids:
            parent_to_state_ids[parent_path] = {}
        if minified_name not in parent_to_state_ids[parent_path]:
            parent_to_state_ids[parent_path][minified_name] = []
        parent_to_state_ids[parent_path][minified_name].append(state_path)

    for parent_path, id_to_states in parent_to_state_ids.items():
        for minified_name, state_paths in id_to_states.items():
            if len(state_paths) > 1:
                errors.append(
                    f"Duplicate state_id='{minified_name}' under '{parent_path or 'root'}': "
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
    root_state: type[BaseState],
    reassign_deleted: bool = False,
    prune: bool = False,
) -> MinifyConfig:
    """Synchronize minify configuration with the current state tree.

    Args:
        existing_config: The existing configuration to update.
        root_state: The root state class.
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

    # Find states that need IDs assigned
    # Group by parent for sibling-unique assignment
    parent_to_children: dict[str | None, list[str]] = {}
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        if state_path not in new_states:
            parent = state_cls.get_parent_state()
            parent_path = get_state_full_path(parent) if parent else None
            if parent_path not in parent_to_children:
                parent_to_children[parent_path] = []
            parent_to_children[parent_path].append(state_path)

    # Assign new state IDs
    for parent_path, children in parent_to_children.items():
        # Get existing IDs for this parent's children (convert to ints for finding max)
        existing_ids: set[int] = set()
        for state_path, minified_name in new_states.items():
            parts = state_path.rsplit(".", 1)
            sp_parent = parts[0] if len(parts) > 1 else None
            # Compare parent paths correctly
            if parent_path is None:
                if sp_parent is None or "." not in state_path:
                    existing_ids.add(minified_name_to_int(minified_name))
            elif sp_parent == parent_path:
                existing_ids.add(minified_name_to_int(minified_name))

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
