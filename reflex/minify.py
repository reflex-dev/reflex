"""State and event name minification driven by ``minify.json``.

The minification entry point is :class:`MinifyNameResolver`, a
:class:`reflex_base.registry.NameResolver` implementation. Install it via
:func:`install_minify_resolver` (called automatically by
:func:`reflex.utils.prerequisites.get_compiled_app` and
:func:`clear_config_cache`).
"""

from __future__ import annotations

import dataclasses
import functools
import json
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from reflex.state import BaseState

# File name for the minify configuration
MINIFY_JSON = "minify.json"

# Current schema version
SCHEMA_VERSION = 1


class MinifyConfig(TypedDict):
    """Schema for ``minify.json`` (version :data:`SCHEMA_VERSION`)."""

    version: int
    states: dict[str, str]  # state_path -> minified_name
    events: dict[str, dict[str, str]]  # state_path -> {handler_name -> minified_name}


def _get_minify_json_path() -> Path:
    """Return the path to ``minify.json`` in the current working directory."""
    return Path.cwd() / MINIFY_JSON


def _load_minify_config_uncached() -> MinifyConfig | None:
    """Load and validate ``minify.json`` from disk.

    Returns:
        The parsed config, or ``None`` if the file is absent.

    Raises:
        ValueError: If the file exists but is malformed.
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
    """Read ``minify.json`` once per process.

    Returns:
        The parsed config, or ``None`` if the file is absent.
    """
    return _load_minify_config_uncached()


def is_minify_enabled() -> bool:
    """Whether either state or event minification is enabled.

    Returns:
        ``True`` if either ``REFLEX_MINIFY_STATES`` or ``REFLEX_MINIFY_EVENTS``
        is on and a config exists.
    """
    return is_state_minify_enabled() or is_event_minify_enabled()


@functools.cache
def _is_mode_enabled(env_var_name: str) -> bool:
    """Whether the given ``REFLEX_MINIFY_*`` env var is on and a config exists.

    Args:
        env_var_name: The env-var attribute name on
            :class:`~reflex.environment.EnvironmentVariables`.

    Returns:
        ``True`` if the env var is ``ENABLED`` and ``minify.json`` exists.
    """
    from reflex.environment import MinifyMode, environment

    env_var = getattr(environment, env_var_name)
    return env_var.get() == MinifyMode.ENABLED and get_minify_config() is not None


def is_state_minify_enabled() -> bool:
    """Whether state-id minification is enabled.

    Returns:
        ``True`` if ``REFLEX_MINIFY_STATES=enabled`` and ``minify.json`` exists.
    """
    return _is_mode_enabled("REFLEX_MINIFY_STATES")


def is_event_minify_enabled() -> bool:
    """Whether event-id minification is enabled.

    Returns:
        ``True`` if ``REFLEX_MINIFY_EVENTS=enabled`` and ``minify.json`` exists.
    """
    return _is_mode_enabled("REFLEX_MINIFY_EVENTS")


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

    Returns the minified name when the matching env-var
    (``REFLEX_MINIFY_STATES`` / ``REFLEX_MINIFY_EVENTS``) is enabled and the
    entry exists in the config; ``None`` otherwise. Per-class lookups are
    memoized for O(1) amortized cost.

    Attributes:
        config: Parsed ``minify.json``, or ``None``.
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
        """Build a resolver from ``minify.json`` (uncached) and env vars.

        Malformed configs degrade gracefully to ``config=None`` with a warning.

        Returns:
            A configured resolver.
        """
        from reflex.environment import MinifyMode, environment
        from reflex.utils import console

        try:
            config = _load_minify_config_uncached()
        except ValueError as e:
            console.warn(
                f"{MINIFY_JSON} could not be loaded: {e}; minification disabled."
            )
            config = None
        return cls(
            config=config,
            states_enabled=environment.REFLEX_MINIFY_STATES.get() == MinifyMode.ENABLED,
            events_enabled=environment.REFLEX_MINIFY_EVENTS.get() == MinifyMode.ENABLED,
        )

    def _is_minify_allowed(self, state_cls: type[BaseState], enabled: bool) -> bool:
        """Whether ``state_cls`` is eligible for minification under the given mode.

        Args:
            state_cls: The state class being resolved.
            enabled: Whether the relevant ``REFLEX_MINIFY_*`` env var is on.

        Returns:
            ``True`` when the env var is on and ``state_cls`` is user-defined.
        """
        return enabled and not _is_framework_state(state_cls)

    def resolve_state_name(self, state_cls: type[BaseState]) -> str | None:  # noqa: D102
        if self.config is None or not self._is_minify_allowed(
            state_cls, self.states_enabled
        ):
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
        if self.config is None or not self._is_minify_allowed(
            state_cls, self.events_enabled
        ):
            return None
        per_state = self._event_cache.get(state_cls)
        if per_state is None:
            per_state = self.config["events"].get(get_state_full_path(state_cls), {})
            self._event_cache[state_cls] = per_state
        return per_state.get(handler_name)


#: Modules whose ``BaseState`` subclasses can never be minified — their
#: :class:`Var` hooks are baked at framework-import time before any user
#: resolver can run. ``reflex.istate.dynamic`` is *not* listed: that's where
#: ``ComponentState.create()`` puts user-owned dynamic classes.
_FRAMEWORK_STATE_MODULES: frozenset[str] = frozenset({
    "reflex.state",
    "reflex.istate.shared",
    "reflex.custom_components.custom_components",
})


def _is_framework_state(state_cls: type[BaseState]) -> bool:
    """Whether ``state_cls`` is one of the framework's own state classes.

    Args:
        state_cls: The state class to check.

    Returns:
        ``True`` if ``state_cls`` belongs to a known framework module.
    """
    module = getattr(state_cls, "__original_module__", None) or state_cls.__module__
    return module in _FRAMEWORK_STATE_MODULES


def install_minify_resolver() -> None:
    """Install a fresh :class:`MinifyNameResolver` into the active context.

    Must run before any state class registers — :func:`VarData.from_state`
    captures the state's full name at Var-creation time, so a later install
    leaves dangling references in the generated frontend.
    """
    from reflex_base.registry import RegistrationContext

    ctx = RegistrationContext.ensure_context()
    ctx.set_name_resolver(MinifyNameResolver.from_disk())


def ensure_minify_resolver_for_active_context() -> None:
    """Install a :class:`MinifyNameResolver` if one isn't already in place.

    Idempotent — safe to wire into hot paths like
    :func:`reflex.utils.prerequisites.get_app`. Re-installs only when on-disk
    state could have changed (config appearing, or non-minify resolver).
    """
    from reflex_base.registry import RegistrationContext

    ctx = RegistrationContext.ensure_context()
    if isinstance(ctx.name_resolver, MinifyNameResolver):
        if ctx.name_resolver.config is not None:
            return
        if not _get_minify_json_path().exists():
            return
    ctx.set_name_resolver(MinifyNameResolver.from_disk())


def clear_config_cache() -> None:
    """Reload ``minify.json`` and propagate the new names through the registry.

    Call after editing ``minify.json`` programmatically or changing
    ``REFLEX_MINIFY_*`` env vars at runtime.
    """
    get_minify_config.cache_clear()
    _is_mode_enabled.cache_clear()
    install_minify_resolver()


# Base-54 encoding for minified names
# Using letters (a-z, A-Z) plus $ and _ which are valid JS identifier chars
_MINIFY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$_"
_MINIFY_BASE = len(_MINIFY_CHARS)  # 54


def int_to_minified_name(id_: int) -> str:
    """Encode a non-negative integer as a base-54 minified name.

    Args:
        id_: The integer to encode.

    Returns:
        e.g. ``0 → "a"``, ``25 → "z"``, ``54 → "ba"``.

    Raises:
        ValueError: If ``id_`` is negative.
    """
    if id_ < 0:
        msg = f"ID must be non-negative, got {id_}"
        raise ValueError(msg)
    if id_ == 0:
        return _MINIFY_CHARS[0]
    result = []
    num = id_
    while num > 0:
        result.append(_MINIFY_CHARS[num % _MINIFY_BASE])
        num //= _MINIFY_BASE
    return "".join(reversed(result))


def minified_name_to_int(name: str) -> int:
    """Decode a base-54 minified name back to its integer id.

    Args:
        name: The minified string.

    Returns:
        The integer id.

    Raises:
        ValueError: If ``name`` contains invalid characters.
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
    """Build the unique ``module.Class.SubClass`` path for a state class.

    Uses ``__original_module__`` when available so dynamically-relocated
    states (e.g. ``ComponentState.create()``) keep their import-site path.

    Args:
        state_cls: The state class.

    Returns:
        e.g. ``"myapp.state.AppState.UserState"``.
    """
    module = getattr(state_cls, "__original_module__", None) or state_cls.__module__
    class_hierarchy: list[str] = []
    current: type[BaseState] | None = state_cls
    while current is not None:
        class_hierarchy.append(current.__name__)
        current = current.get_parent_state()  # type: ignore[union-attr]
    class_hierarchy.reverse()
    return ".".join([module, *class_hierarchy])


def collect_all_states(
    root_state: type[BaseState] | None = None,
) -> list[type[BaseState]]:
    """Collect state classes in deterministic depth-first, sibling-sorted order.

    Without ``root_state``, walks every state registered in the active
    :class:`~reflex_base.registry.RegistrationContext` (one tree per
    parentless root). With ``root_state``, restricts the walk to that subtree.

    Args:
        root_state: Optional subtree root.

    Returns:
        State classes in depth-first, sibling-sorted order.
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

    Walks the state tree (see :func:`collect_all_states`) and assigns ids
    starting from ``"a"`` per sibling group. Output is byte-stable.

    Args:
        root_state: Optional subtree root.

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


def _find_duplicate_ids(items: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """Group ``(label, minified_id)`` pairs by id, keeping only collisions.

    Args:
        items: Pairs of ``(label, minified_id)``.

    Returns:
        Mapping from minified id to the labels sharing it (always ``len >= 2``).
    """
    by_id: dict[str, list[str]] = {}
    for label, mid in items:
        by_id.setdefault(mid, []).append(label)
    return {mid: labels for mid, labels in by_id.items() if len(labels) > 1}


def _assign_next_ids(
    new_keys: Iterable[str],
    existing_ids: set[int],
    reassign_deleted: bool,
) -> dict[str, str]:
    """Assign minified ids to ``new_keys`` while skipping ``existing_ids``.

    Keys are sorted for deterministic output. ``existing_ids`` is read-only —
    a working copy is taken internally.

    Args:
        new_keys: Keys needing new ids.
        existing_ids: Already-used integer ids in the same scope.
        reassign_deleted: When ``True``, scan from 0 (filling gaps);
            otherwise start past the current max.

    Returns:
        Mapping from key to its newly-assigned minified id.
    """
    pool = set(existing_ids)
    next_id = 0 if reassign_deleted else max(pool, default=-1) + 1
    out: dict[str, str] = {}
    for key in sorted(new_keys):
        while next_id in pool:
            next_id += 1
        out[key] = int_to_minified_name(next_id)
        pool.add(next_id)
        next_id += 1
    return out


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

    # Group sibling states by their actual parent class (not by string-split
    # path) since children of the same parent can live in different modules.
    path_to_cls = {get_state_full_path(s): s for s in all_states}
    parent_to_pairs: dict[type[BaseState] | None, list[tuple[str, str]]] = {}
    for state_path, minified_name in config["states"].items():
        state_cls = path_to_cls.get(state_path)
        parent = state_cls.get_parent_state() if state_cls else None
        parent_to_pairs.setdefault(parent, []).append((state_path, minified_name))

    for parent, pairs in parent_to_pairs.items():
        parent_name = parent.__name__ if parent else "root"
        errors.extend(
            f"Duplicate state_id='{mid}' under '{parent_name}': {paths}"
            for mid, paths in _find_duplicate_ids(pairs).items()
        )

    for state_path, state_events in config["events"].items():
        errors.extend(
            f"Duplicate event_id='{mid}' in '{state_path}': {handlers}"
            for mid, handlers in _find_duplicate_ids(state_events.items()).items()
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

    # Assign new state IDs (unique among siblings of the same parent class).
    for parent_cls, children in parent_cls_to_new_children.items():
        existing_ids = parent_cls_to_existing_ids.get(parent_cls, set())
        new_states.update(_assign_next_ids(children, existing_ids, reassign_deleted))

    # Assign new event IDs (unique within each state).
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        state_events = new_events.get(state_path, {})
        new_handlers = [h for h in state_cls.event_handlers if h not in state_events]
        if new_handlers:
            existing_ids = {minified_name_to_int(eid) for eid in state_events.values()}
            state_events.update(
                _assign_next_ids(new_handlers, existing_ids, reassign_deleted)
            )
            new_events[state_path] = state_events

    return MinifyConfig(
        version=SCHEMA_VERSION,
        states=new_states,
        events=new_events,
    )
