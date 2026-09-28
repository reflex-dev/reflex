"""State, event and var name minification driven by ``minify.json``.

The minification entry point is :class:`MinifyNameResolver`, a
:class:`reflex_base.registry.NameResolver` implementation. Install it via
:func:`install_minify_resolver`; :func:`ensure_minify_resolver_for_active_context`
runs it from :mod:`reflex.state` at import time and from
:func:`reflex.utils.prerequisites.get_app`.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import logging
import re
from collections.abc import Callable, Collection, Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, TypedDict

from reflex_base.constants.state import FIELD_MARKER

if TYPE_CHECKING:
    from reflex.state import BaseState

logger = logging.getLogger(__name__)

# File name for the minify configuration
MINIFY_JSON = "minify.json"

# Current schema version
SCHEMA_VERSION = 1

# Names listed in the stale-config warning before it summarizes the rest.
_STALE_WARNING_LIMIT = 5

# A var id is a key of its state's object in the frontend, so it must not read
# an inherited Object.prototype member while the var is absent.
_RESERVED_VAR_IDS = frozenset({
    "__defineGetter__",
    "__defineSetter__",
    "__lookupGetter__",
    "__lookupSetter__",
    "__proto__",
    "constructor",
    "hasOwnProperty",
    "isPrototypeOf",
    "propertyIsEnumerable",
    "toLocaleString",
    "toString",
    "valueOf",
})


class StateEntry(TypedDict):
    """A single state entry in ``minify.json``.

    ``parent`` preserves the sibling scope of an entry even after the class is
    renamed or deleted, keeping orphaned ids reserved in their sibling group.
    """

    id: str  # minified name, e.g. "a"
    parent: str | None  # parent state_path, None for root states


class MinifyConfig(TypedDict):
    """Schema for ``minify.json`` (version :data:`SCHEMA_VERSION`)."""

    version: int
    states: dict[str, StateEntry]  # state_path -> {id, parent}
    events: dict[str, dict[str, str]]  # state_path -> {handler_name -> minified_name}
    vars: dict[str, dict[str, str]]  # state_path -> {var_name -> minified_name}


@dataclasses.dataclass(frozen=True, slots=True)
class _MemberKind:
    """A kind of state member that ``minify.json`` numbers within each state."""

    # The config section holding the ids, keyed by state path.
    key: Literal["events", "vars"]
    # How a member of this kind is named in labels, e.g. ``event:<path>.<name>``.
    label: str
    # The members of this kind a state class has.
    names: Callable[[type[BaseState]], Iterable[str]]


_EVENTS = _MemberKind(
    key="events", label="event", names=lambda state_cls: state_cls.event_handlers
)
# Only vars sent to the frontend have a wire name to shorten.
_VARS = _MemberKind(
    key="vars", label="var", names=lambda state_cls: state_cls._frontend_var_names
)
_MEMBER_KINDS = (_EVENTS, _VARS)


def _get_minify_json_path() -> Path:
    """Return the ``minify.json`` of the app being run.

    ``REFLEX_MINIFY_CONFIG`` names it explicitly, relative to the working
    directory; otherwise it is the one in the working directory, which is the
    app's own.

    Returns:
        The absolute path, whether or not the file exists.
    """
    from reflex.environment import environment

    return (environment.REFLEX_MINIFY_CONFIG.get() or Path(MINIFY_JSON)).absolute()


def _read_minify_json(path: Path) -> bytes | None:
    """Read a ``minify.json``.

    Args:
        path: The file.

    Returns:
        Its content, or ``None`` if it does not exist.
    """
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


class _ConfigSource(NamedTuple):
    """What a :class:`MinifyNameResolver` is built from, read in one go."""

    # The ``minify.json`` of the app being run.
    path: Path
    # Its content, ``None`` if it does not exist.
    content: bytes | None
    # Whether ``REFLEX_MINIFY_STATES``, ``_EVENTS`` and ``_VARS`` are on.
    modes: tuple[bool, bool, bool]

    @classmethod
    def read(cls) -> _ConfigSource:
        """Read the file and the modes as they are now.

        Returns:
            The source.
        """
        from reflex.environment import environment

        path = _get_minify_json_path()
        return cls(
            path,
            _read_minify_json(path),
            (
                environment.REFLEX_MINIFY_STATES.get(),
                environment.REFLEX_MINIFY_EVENTS.get(),
                environment.REFLEX_MINIFY_VARS.get(),
            ),
        )


def _validate_minified_id(label: str, value: str) -> None:
    """Reject ids that can't be emitted as a JS identifier segment.

    Args:
        label: Human-readable location for the error message.
        value: The candidate minified id.

    Raises:
        ValueError: If the id is empty or uses characters outside the alphabet.
    """
    if not value or not _MINIFY_CHARS_SET.issuperset(value):
        msg = f"Invalid {MINIFY_JSON}: {label} has invalid id: {value!r}"
        raise ValueError(msg)


def _validate_var_id(label: str, value: str) -> None:
    """Reject var ids that the frontend could confuse with another key.

    Args:
        label: Human-readable location for the error message.
        value: The candidate minified id.

    Raises:
        ValueError: If the id is reserved or looks like an unminified var key.
    """
    if value in _RESERVED_VAR_IDS or value.endswith(FIELD_MARKER):
        msg = f"Invalid {MINIFY_JSON}: {label} has reserved id: {value!r}"
        raise ValueError(msg)


def _validate_member_ids(
    kind: _MemberKind, members: Any, *, for_repair: bool = False
) -> None:
    """Validate one ``{state_path: {name: id}}`` section of ``minify.json``.

    Args:
        kind: The kind of member the section numbers.
        members: The loaded section.
        for_repair: Accept an id two members of a state share, which
            ``reflex minify sync`` reassigns.

    Raises:
        ValueError: If the section is malformed.
    """
    if not isinstance(members, dict):
        msg = f"Invalid {MINIFY_JSON}: '{kind.key}' must be a dictionary."
        raise ValueError(msg)
    for state_path, ids in members.items():
        if not isinstance(ids, dict):
            msg = f"Invalid {MINIFY_JSON}: {kind.key} for '{state_path}' must be a dictionary."
            raise ValueError(msg)
        for name, member_id in ids.items():
            label = f"{kind.label} '{state_path}.{name}'"
            if not isinstance(member_id, str):
                msg = f"Invalid {MINIFY_JSON}: {label} has non-string id: {member_id}"
                raise ValueError(msg)
            _validate_minified_id(label, member_id)
            if kind is _VARS:
                _validate_var_id(label, member_id)
        if not for_repair and (duplicates := _find_duplicate_ids(ids.items())):
            msg = f"Invalid {MINIFY_JSON}: {_duplicate_member_ids_message(kind, state_path, duplicates)}"
            raise ValueError(msg)


def _is_state_id(value: str) -> bool:
    """Whether a minified id keeps its state's path unambiguous once formatted.

    The compiled frontend joins path segments with ``__``, so ``a`` + ``_b``
    and ``a_`` + ``b`` would both read ``a___b``. An id with no underscore at
    either end and none doubled can only ever split one way.

    Args:
        value: The candidate state id.

    Returns:
        Whether the id may name a state.
    """
    return not (value.startswith("_") or value.endswith("_") or "__" in value)


def _ambiguous_state_id_message(state_path: str, state_id: str) -> str:
    """Explain why a state id is rejected and how to replace it.

    Args:
        state_path: The state's config path.
        state_id: Its id, which :func:`_is_state_id` rejects.

    Returns:
        The message.
    """
    return (
        f"state '{state_path}' has id {state_id!r}; a state id may not start or "
        "end with '_' or contain '__', which would make two state paths read the "
        "same once dots become '__'. Run 'reflex minify sync' to reassign it."
    )


def _duplicate_member_ids_message(
    kind: _MemberKind, state_path: str, duplicates: dict[str, list[str]]
) -> str:
    """Explain which members of a state share an id and how to fix it.

    Args:
        kind: The kind of member.
        state_path: The state's config path.
        duplicates: The shared ids and the members holding each.

    Returns:
        The message.
    """
    shared = "; ".join(
        f"{mid!r} by {', '.join(sorted(names))}" for mid, names in duplicates.items()
    )
    return (
        f"{kind.label}s of '{state_path}' share ids ({shared}), which the frontend "
        "and backend cannot tell apart. Run 'reflex minify sync' to reassign them."
    )


def _load_minify_config_uncached(*, for_repair: bool = False) -> MinifyConfig | None:
    """Load and validate ``minify.json`` from disk.

    Args:
        for_repair: See :func:`_parse_minify_config`.

    Returns:
        The parsed config, or ``None`` if the file is absent.
    """
    return _parse_minify_config(
        _read_minify_json(_get_minify_json_path()), for_repair=for_repair
    )


def _parse_minify_config(
    content: bytes | None, *, for_repair: bool = False
) -> MinifyConfig | None:
    """Parse and validate the content of a ``minify.json``.

    Args:
        content: The content, ``None`` if the file is absent.
        for_repair: Accept the problems ``reflex minify sync`` repairs -- state
            ids :func:`_is_state_id` rejects and an id two handlers of a state
            share -- so the ``reflex minify`` commands can report and fix them.

    Returns:
        The parsed config, or ``None`` if the file is absent.

    Raises:
        ValueError: If the content is malformed.
    """
    if content is None:
        return None

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in {MINIFY_JSON}: {e}"
        raise ValueError(msg) from e

    if not isinstance(data, dict):
        msg = (
            f"Invalid {MINIFY_JSON}: must be a JSON object, got {type(data).__name__}."
        )
        raise ValueError(msg)

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
    if "events" not in data:
        msg = f"Invalid {MINIFY_JSON}: 'events' must be a dictionary."
        raise ValueError(msg)

    # Validate states: all values must be {id: str, parent: str | None} entries
    for key, value in data["states"].items():
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("id"), str)
            or "parent" not in value
        ):
            msg = f"Invalid {MINIFY_JSON}: state '{key}' must be an object with a string 'id' and a 'parent': {value}"
            raise ValueError(msg)
        _validate_minified_id(f"state '{key}'", value["id"])
        if not for_repair and not _is_state_id(value["id"]):
            msg = f"Invalid {MINIFY_JSON}: {_ambiguous_state_id_message(key, value['id'])}"
            raise ValueError(msg)
        parent = value.get("parent")
        if parent is not None and not isinstance(parent, str):
            msg = (
                f"Invalid {MINIFY_JSON}: state '{key}' has non-string parent: {parent}"
            )
            raise ValueError(msg)

    # Files written before vars were minified have no 'vars' section.
    data.setdefault(_VARS.key, {})
    for kind in _MEMBER_KINDS:
        _validate_member_ids(kind, data[kind.key], for_repair=for_repair)

    return MinifyConfig(
        version=data["version"],
        states=data["states"],
        events=data["events"],
        vars=data["vars"],
    )


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
    (``REFLEX_MINIFY_STATES`` / ``REFLEX_MINIFY_EVENTS`` / ``REFLEX_MINIFY_VARS``)
    is enabled and the entry exists in the config; ``None`` otherwise. Nothing
    is memoized per class: the name caches of the callers already ask once per
    state, handler and var.

    Attributes:
        config: Parsed ``minify.json``, or ``None``.
        states_enabled: Whether ``REFLEX_MINIFY_STATES`` is on.
        events_enabled: Whether ``REFLEX_MINIFY_EVENTS`` is on.
        vars_enabled: Whether ``REFLEX_MINIFY_VARS`` is on.
        source: What the resolver was built from, if read from disk.
    """

    config: MinifyConfig | None
    states_enabled: bool
    events_enabled: bool
    vars_enabled: bool
    source: _ConfigSource | None = None

    _digest: str | None = dataclasses.field(default=None, repr=False)

    def digest(self) -> str:
        """Digest the wire names this resolver rewrites.

        The config and the modes are fixed for the life of an instance, so the
        result is memoized here. Installing another resolver -- which is what
        editing ``minify.json`` or toggling a mode at runtime does -- yields a
        fresh instance and therefore a fresh digest, with no invalidation to
        coordinate. Deliberately independent of which states have registered:
        keying on that made the answer depend on when it was first asked for.

        A map is skipped entirely when its ``REFLEX_MINIFY_*`` mode is off, so
        toggling a mode registers as a mismatch just as editing the file does.

        Returns:
            A short hex digest, or ``""`` when no name is rewritten.
        """
        if self._digest is None:
            self._digest = self._compute_digest()
        return self._digest

    def _compute_digest(self) -> str:
        """Hash the config entries that reach the wire.

        Returns:
            A short hex digest, or ``""`` when no name is rewritten.
        """
        if self.config is None:
            return ""
        payload: dict[str, Any] = {
            key: section
            for key, enabled, section in (
                (
                    "states",
                    self.states_enabled,
                    {
                        path: entry["id"]
                        for path, entry in self.config["states"].items()
                    },
                ),
                ("events", self.events_enabled, self.config["events"]),
                ("vars", self.vars_enabled, self.config["vars"]),
            )
            if enabled and section
        }
        if not payload:
            return ""
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]

    @classmethod
    def from_disk(cls, source: _ConfigSource | None = None) -> MinifyNameResolver:
        """Build a resolver from ``minify.json`` (uncached) and env vars.

        Malformed configs degrade gracefully to ``config=None`` with a warning.

        Args:
            source: The file and modes to build from; read now if omitted.

        Returns:
            A configured resolver.
        """
        if source is None:
            source = _ConfigSource.read()
        try:
            config = _parse_minify_config(source.content)
        except ValueError as e:
            logger.warning(
                f"{source.path} could not be loaded: {e}; minification disabled."
            )
            config = None
        states, events, vars_ = source.modes
        return cls(
            config=config,
            states_enabled=states,
            events_enabled=events,
            vars_enabled=vars_,
            source=source,
        )

    def resolve_state_name(self, state_cls: type[BaseState]) -> str | None:  # noqa: D102
        if self.config is None or not self.states_enabled:
            return None
        entry = self.config["states"].get(get_state_full_path(state_cls))
        return None if entry is None else entry["id"]

    def resolve_handler_name(  # noqa: D102
        self, state_cls: type[BaseState], handler_name: str
    ) -> str | None:
        if not self.events_enabled:
            return None
        return self._resolve_member(_EVENTS, state_cls, handler_name)

    def resolve_var_name(  # noqa: D102
        self, state_cls: type[BaseState], var_name: str
    ) -> str | None:
        if not self.vars_enabled:
            return None
        return self._resolve_member(_VARS, state_cls, var_name)

    def _resolve_member(
        self, kind: _MemberKind, state_cls: type[BaseState], name: str
    ) -> str | None:
        """Look up the id ``minify.json`` gives a member of a state.

        Args:
            kind: The kind of member.
            state_cls: The state the member belongs to.
            name: The member's Python name.

        Returns:
            The minified id, or ``None`` when the member has no entry.
        """
        if self.config is None:
            return None
        return self.config[kind.key].get(get_state_full_path(state_cls), {}).get(name)


def install_minify_resolver() -> None:
    """Install a fresh :class:`MinifyNameResolver` into the active context.

    Registered states get their Vars rebuilt under the new names; a Var built
    from them before the install keeps the old ones, which the compiler
    rejects (see :func:`raise_for_stale_names`).
    """
    from reflex_base.registry import RegistrationContext

    ctx = RegistrationContext.ensure_context()
    ctx.set_name_resolver(MinifyNameResolver.from_disk())


# Set by :func:`force_default_names`; keeps the ensure-hook from reinstalling.
_default_names_forced = False


@contextlib.contextmanager
def force_default_names() -> Iterator[None]:
    """Pin the block to built-in names, ignoring ``minify.json``.

    The ``reflex minify`` commands read the config rather than apply it: with
    the configured names live, a duplicate id aborts the app import from
    ``BaseState.__init_subclass__`` before the command can report it. Must be
    entered before the app is imported.

    Yields:
        ``None``, with the default resolver installed.
    """
    global _default_names_forced
    from reflex_base.registry import DefaultNameResolver, RegistrationContext

    ctx = RegistrationContext.ensure_context()
    previous_resolver = ctx.name_resolver
    previous_forced = _default_names_forced
    _default_names_forced = True
    ctx.set_name_resolver(DefaultNameResolver())
    try:
        yield
    finally:
        _default_names_forced = previous_forced
        ctx.set_name_resolver(previous_resolver)


def ensure_minify_resolver_for_active_context() -> None:
    """Install the resolver for the ``minify.json`` of the app being run.

    The resolver follows that file, so an app loaded after another one in the
    same process -- like an ``AppHarness`` test app next to the repository's
    own -- never gets names from the other app's ``minify.json``: without a
    file of its own it gets the built-in names, with a different one its own.
    An edit to the file or a toggled mode is picked up on the next call, e.g.
    by a hot reload. Cheap when nothing changed, so it is safe to wire into
    hot paths like :func:`reflex.utils.prerequisites.get_app`. A resolver the
    user installed in place of the built-in ones is left alone.
    """
    from reflex_base.registry import DefaultNameResolver, RegistrationContext

    if _default_names_forced:
        return
    ctx = RegistrationContext.ensure_context()
    resolver = ctx.name_resolver
    source = _ConfigSource.read()
    if isinstance(resolver, MinifyNameResolver):
        if source.content is None:
            ctx.set_name_resolver(DefaultNameResolver())
            return
        if resolver.source == source:
            return
    elif type(resolver) is not DefaultNameResolver or source.content is None:
        return
    ctx.set_name_resolver(MinifyNameResolver.from_disk(source))


def _collect_missing_entries(
    states: Iterable[type[BaseState]],
    config: MinifyConfig,
    *,
    include_states: bool = True,
    kinds: Iterable[_MemberKind] = _MEMBER_KINDS,
) -> list[str]:
    """Label the registered names ``config`` has no entry for.

    Args:
        states: The state classes to inventory.
        config: The configuration to check against.
        include_states: Whether to report states with no entry.
        kinds: The kinds of member to report when they have no entry.

    Returns:
        Sorted ``state:<path>`` / ``event:<path>.<handler>`` / ``var:<path>.<var>``
        labels.
    """
    kinds = tuple(kinds)
    config_states = config["states"]
    missing: list[str] = []
    for state_cls in states:
        state_path = get_state_full_path(state_cls)
        if include_states and state_path not in config_states:
            missing.append(f"state:{state_path}")
        for kind in kinds:
            ids = config[kind.key].get(state_path, {})
            missing.extend(
                f"{kind.label}:{state_path}.{name}"
                for name in kind.names(state_cls)
                if name not in ids
            )
    missing.sort()
    return missing


def _find_missing_entries() -> list[str]:
    """Registered names the installed resolver has no minified id for.

    A kind of name is only reported when its ``REFLEX_MINIFY_*`` mode is on,
    since a disabled mode emits full names by design.

    Returns:
        Sorted ``state:<path>`` / ``event:<path>.<handler>`` / ``var:<path>.<var>``
        labels; empty when no :class:`MinifyNameResolver` with a config is
        installed.
    """
    from reflex_base.registry import RegistrationContext

    ctx = RegistrationContext.try_get()
    if ctx is None:
        return []
    resolver = ctx.name_resolver
    if not isinstance(resolver, MinifyNameResolver) or resolver.config is None:
        return []
    # Walks the same set as validate_minify_config, so the warning and
    # 'reflex minify validate' never disagree about what is missing.
    return _collect_missing_entries(
        collect_all_states(),
        resolver.config,
        include_states=resolver.states_enabled,
        kinds=[
            kind
            for kind, enabled in (
                (_EVENTS, resolver.events_enabled),
                (_VARS, resolver.vars_enabled),
            )
            if enabled
        ],
    )


def warn_if_config_stale() -> None:
    """Warn when code has states, handlers or vars ``minify.json`` doesn't cover.

    Those names compile unminified, mixing minified and raw names on the wire.
    No-op unless a resolver with a config is installed and a mode is enabled.
    """
    missing = _find_missing_entries()
    if not missing:
        return
    extra = len(missing) - _STALE_WARNING_LIMIT
    shown = ", ".join(missing[:_STALE_WARNING_LIMIT])
    more = f" (+{extra} more)" if extra > 0 else ""
    logger.warning(
        f"{MINIFY_JSON} is out of date, so these names compile unminified: "
        f"{shown}{more}. Run 'reflex minify sync' to assign ids; "
        "'reflex minify validate' lists every missing entry."
    )


def clear_config_cache() -> None:
    """Reload ``minify.json`` and reinstall the resolver."""
    install_minify_resolver()


# A dotted run of identifiers starting at one that holds a default state name,
# which always contains the ``___`` module separator.
_DEFAULT_NAME_RUN = re.compile(r"(?<![\w$])[\w$]*___[\w$]*(?:\.[\w$]+)*")


def _renamed_default_references() -> dict[str, str]:
    """Map the unminified spelling of every renamed state and handler to a label.

    Returns:
        ``{default spelling: what it names}``; empty when nothing is renamed.
    """
    from reflex_base.registry import RegistrationContext, scheme_digest
    from reflex_base.utils.format import format_state_name

    if not scheme_digest():
        return {}
    ctx = RegistrationContext.get()
    references: dict[str, str] = {}
    for state_cls in collect_all_states():
        default_name = state_cls._get_default_full_name()
        label = get_state_full_path(state_cls)
        if default_name != state_cls.get_full_name():
            # Every default spelling of its handlers and vars starts with one
            # of these, so they need no entries of their own; the vars of a
            # state keeping its name are checked by their state's local.
            references[default_name] = references[format_state_name(default_name)] = (
                f"state {label}"
            )
            continue
        for name in state_cls.event_handlers:
            if ctx.get_handler_name(state_cls, name) != name:
                references[f"{default_name}.{name}"] = f"event handler {label}.{name}"
    return references


def raise_for_stale_names(outputs: Iterable[tuple[str, str]]) -> None:
    """Reject compiled code naming a state, handler or var unlike the active resolver.

    Installing a resolver rebuilds the Vars each state holds, but not a Var
    built from them beforehand -- e.g. by a module-level component imported
    before this app's ``minify.json`` was loaded, or while another app's was.
    Such code would read a context the frontend never provides, or send an
    event the backend never registered, or read a var key it never sends.
    Caught by the unminified spelling of a renamed state or handler, and by
    each state local or var key once handed out that no state or var goes by
    now -- which text merely looking like one never was.

    Args:
        outputs: ``(path, code)`` pairs of the compiled frontend.

    Raises:
        ReflexError: If any code names something unlike the active resolver.
    """
    from reflex_base.registry import RegistrationContext
    from reflex_base.utils.exceptions import ReflexError
    from reflex_base.utils.format import (
        STATE_MEMBER_READ,
        format_state_local,
        format_var_key,
        issued_states,
        issued_var_keys,
    )

    references = _renamed_default_references()
    registered: set[type[BaseState]] | None = None
    live_keys: dict[type[BaseState], set[str]] = {}
    found: dict[str, tuple[str, str]] = {}
    for path, code in outputs:
        if references:
            for match in _DEFAULT_NAME_RUN.finditer(code):
                prefix = ""
                for segment in match.group().split("."):
                    prefix = f"{prefix}.{segment}" if prefix else segment
                    if prefix in references:
                        found.setdefault(prefix, (references[prefix], path))
                        break
        for match in STATE_MEMBER_READ.finditer(code):
            local, member = match.groups()
            if not (owners := issued_states(local)):
                continue
            if registered is None:
                registered = set(RegistrationContext.get().base_states.values())
            # An unregistered owner, e.g. one replaced by a hot reload, keeps
            # its cached name, so only settle for one if nothing else fits.
            matching = [c for c in owners if format_state_local(c) == local]
            state_cls = next(
                (c for c in matching if c in registered),
                matching[0] if matching else None,
            )
            if state_cls is None:
                labels = sorted(f"state {get_state_full_path(c)}" for c in owners)
                found.setdefault(local, (" or ".join(labels), path))
                continue
            if member is None:
                continue
            if state_cls not in live_keys:
                live_keys[state_cls] = {
                    format_var_key(state_cls, n)
                    for n in set(issued_var_keys(state_cls).values())
                }
            if member in live_keys[state_cls]:
                continue
            # A key of this state, or of one that had its local before.
            for owner in (state_cls, *owners):
                if (name := issued_var_keys(owner).get(member)) is not None:
                    found.setdefault(
                        f"{local}.{member}",
                        (f"var {get_state_full_path(owner)}.{name}", path),
                    )
                    break
    if not found:
        return
    details = "\n".join(
        f"  {label}, as {spelling!r} in {path}"
        for spelling, (label, path) in sorted(found.items())
    )
    msg = (
        "The compiled frontend refers to names the active name resolver does "
        f"not use:\n{details}\n"
        "They come from Vars built while another resolver was installed, e.g. by "
        "a component created at import time of a module loaded before this app "
        f"directory (and its {MINIFY_JSON}) was, or while another app's was. "
        "Import the app from its directory, or create those components inside "
        "the page function."
    )
    raise ReflexError(msg)


# Base-54 encoding for minified names
# Using letters (a-z, A-Z) plus $ and _ which are valid JS identifier chars
_MINIFY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$_"
_MINIFY_BASE = len(_MINIFY_CHARS)  # 54
_MINIFY_CHARS_SET = frozenset(_MINIFY_CHARS)


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

    Starts with the module whose code defines the state, so states relocated
    for pickling (e.g. by ``ComponentState.create()``) keep their source path.

    Args:
        state_cls: The state class.

    Returns:
        e.g. ``"myapp.state.AppState.UserState"``.
    """
    module = state_cls._get_source_module()
    class_hierarchy: list[str] = []
    current: type[BaseState] | None = state_cls
    while current is not None:
        class_hierarchy.append(current.__name__)
        current = current.get_parent_state()  # type: ignore[union-attr]
    class_hierarchy.reverse()
    return ".".join([module, *class_hierarchy])


def get_parent_key(state_cls: type[BaseState]) -> str | None:
    """Return the config key of ``state_cls``'s parent state.

    Args:
        state_cls: The state class.

    Returns:
        The parent's :func:`get_state_full_path`, or ``None`` for root states.
    """
    parent = state_cls.get_parent_state()
    return get_state_full_path(parent) if parent is not None else None


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

    A sync of an empty config, filling every gap: ids start from ``"a"`` in
    each sibling group, skipping the parent's own id. Output is byte-stable.

    Args:
        root_state: Optional subtree root.

    Returns:
        A complete :class:`MinifyConfig`.
    """
    return sync_minify_config(
        MinifyConfig(version=SCHEMA_VERSION, states={}, events={}, vars={}),
        root_state,
        reassign_deleted=True,
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
    existing_ids: Collection[int],
    reassign_deleted: bool,
    for_states: bool = False,
    skip: Collection[int] = (),
) -> dict[str, str]:
    """Assign minified ids to ``new_keys`` while skipping ``existing_ids``.

    Keys are sorted for deterministic output.

    Args:
        new_keys: Keys needing new ids.
        existing_ids: Already-used integer ids in the same scope.
        reassign_deleted: When ``True``, scan from 0 (filling gaps);
            otherwise start past the max of ``existing_ids``.
        for_states: Whether the ids name states, which skip the ids
            :func:`_is_state_id` rejects.
        skip: Ids to avoid that are not in the scope, so do not move its max.

    Returns:
        Mapping from key to its newly-assigned minified id.
    """
    pool = {*existing_ids, *skip}
    next_id = 0 if reassign_deleted else max(existing_ids, default=-1) + 1
    out: dict[str, str] = {}
    for key in sorted(new_keys):
        while next_id in pool or (
            for_states and not _is_state_id(int_to_minified_name(next_id))
        ):
            next_id += 1
        out[key] = int_to_minified_name(next_id)
        pool.add(next_id)
        next_id += 1
    return out


def _state_id_scope(
    states: dict[str, StateEntry], parent_key: str | None, exclude: Collection[str]
) -> tuple[set[int], set[int]]:
    """Get the ids a state under ``parent_key`` may not take.

    Args:
        states: The state entries.
        parent_key: The config path of the parent, ``None`` for a root.
        exclude: The paths whose own ids do not count.

    Returns:
        ``(sibling ids, parent ids)``; the parent's id is avoided so the
        leading segment of a relative path can only ever mean the parent.
    """
    siblings = {
        minified_name_to_int(entry["id"])
        for path, entry in states.items()
        if entry["parent"] == parent_key and path not in exclude
    }
    parent_entry = states.get(parent_key) if parent_key is not None else None
    parent = (
        set() if parent_entry is None else {minified_name_to_int(parent_entry["id"])}
    )
    return siblings, parent


def _assign_state_ids(
    states: dict[str, StateEntry],
    state_paths: Collection[str],
    parent_key: str | None,
    reassign_deleted: bool,
) -> dict[str, str]:
    """Assign ids to states under ``parent_key``, avoiding their scope's ids.

    Args:
        states: The state entries.
        state_paths: The paths needing ids.
        parent_key: The config path of their parent, ``None`` for roots.
        reassign_deleted: Whether an id may fill a gap.

    Returns:
        Mapping from path to its newly-assigned id.
    """
    siblings, parent = _state_id_scope(states, parent_key, set(state_paths))
    return _assign_next_ids(
        state_paths, siblings, reassign_deleted, for_states=True, skip=parent
    )


def _reassign_duplicate_ids(
    ids: dict[str, str], reassign_deleted: bool, live: Collection[str]
) -> None:
    """Give a new id to every name but one of those sharing an id.

    The one kept is a live name if any shares the id -- a served frontend may
    be using it -- else the first by sort order.

    Args:
        ids: The ``{name: id}`` map of one state, modified in place.
        reassign_deleted: Whether a replacement id may fill a gap.
        live: The names the code still has.
    """
    kept: set[str] = set()
    duplicates: list[str] = []
    for name in sorted(ids, key=lambda name: (name not in live, name)):
        if ids[name] in kept:
            duplicates.append(name)
        else:
            kept.add(ids[name])
    if duplicates:
        ids.update(
            _assign_next_ids(
                duplicates, {minified_name_to_int(i) for i in kept}, reassign_deleted
            )
        )


def _rehome_ambiguous_ids(
    states: dict[str, StateEntry], reassign_deleted: bool
) -> None:
    """Replace the state ids :func:`_is_state_id` rejects, in place.

    Files written before that rule may hold them, orphaned entries included,
    and the app refuses to load such a file. Parents come first, so a child is
    checked against its parent's final id.

    Args:
        states: The state entries to fix up, modified in place.
        reassign_deleted: Whether a replacement id may fill a gap.
    """
    for state_path in sorted(states):
        entry = states[state_path]
        if _is_state_id(entry["id"]):
            continue
        entry["id"] = _assign_state_ids(
            states, (state_path,), entry["parent"], reassign_deleted
        )[state_path]


def _rehome_conflicting_ids(
    states: dict[str, StateEntry],
    all_states: Iterable[type[BaseState]],
    reassign_deleted: bool,
    reparented: set[str],
) -> None:
    """Move an id this sync put in conflict, in place.

    Healing a stored parent keeps the entry's id, which can land it on its new
    parent's id or on one a sibling already holds; a parent assigned in this
    run can likewise land on a preserved child's id. Only entries this sync
    moved give way, plus any child sharing its parent's id -- moving the parent
    instead would cascade. An entry whose scope did not change keeps the id a
    served frontend may still be using; a duplicate that was already in the
    file is left for ``validate`` to report. Walks ancestors first, so a parent
    is final when its children are checked.

    Args:
        states: The state entries to fix up, modified in place.
        all_states: State classes in depth-first order.
        reassign_deleted: Whether a replacement id may fill a gap.
        reparented: Paths whose stored parent this sync healed.
    """
    for state_cls in all_states:
        state_path = get_state_full_path(state_cls)
        entry = states.get(state_path)
        if entry is None or entry["parent"] is None:
            continue
        siblings, parent = _state_id_scope(states, entry["parent"], (state_path,))
        state_id = minified_name_to_int(entry["id"])
        shares_parent_id = state_id in parent
        if state_id not in siblings and not shares_parent_id:
            continue
        if state_path not in reparented and not shares_parent_id:
            continue
        entry["id"] = _assign_state_ids(
            states, (state_path,), entry["parent"], reassign_deleted
        )[state_path]


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
    warnings: list[str] = []

    all_states = collect_all_states(root_state)

    # Group siblings by parent key: live entries via their actual parent class,
    # orphans via the parent recorded in the config — so id reuse between a
    # dead entry and a live sibling is detected.
    path_to_cls = {get_state_full_path(s): s for s in all_states}
    parent_to_pairs: dict[str | None, list[tuple[str, str]]] = {}
    for state_path, entry in config["states"].items():
        state_cls = path_to_cls.get(state_path)
        if state_cls is not None:
            parent_key = get_parent_key(state_cls)
            if entry["parent"] != parent_key:
                warnings.append(
                    f"Stale parent for '{state_path}': config has "
                    f"{entry['parent']!r}, actual is {parent_key!r}. "
                    "Run 'reflex minify sync' to fix."
                )
            label = state_path
        else:
            parent_key = entry["parent"]
            label = f"{state_path} (orphaned)"
        parent_to_pairs.setdefault(parent_key, []).append((label, entry["id"]))

        # A state sharing its parent's id makes a relative path ambiguous,
        # which misresolves substate lookups rather than failing. Checked
        # against the actual parent, which is the tree a lookup walks. An
        # orphan resolves no name at runtime, and its id stays reserved at the
        # value a served frontend may still hold, so it is exempt.
        parent_entry = (
            config["states"].get(parent_key)
            if parent_key and state_cls is not None
            else None
        )
        if parent_entry is not None and parent_entry["id"] == entry["id"]:
            errors.append(
                f"State '{state_path}' reuses the id '{entry['id']}' of its parent "
                f"'{parent_key}'. Delete {MINIFY_JSON} and re-run "
                "'reflex minify init'."
            )

    errors.extend(
        _ambiguous_state_id_message(state_path, entry["id"])
        for state_path, entry in config["states"].items()
        if not _is_state_id(entry["id"])
    )

    for parent_key, pairs in parent_to_pairs.items():
        parent_name = parent_key if parent_key is not None else "root"
        errors.extend(
            f"Duplicate state_id='{mid}' under '{parent_name}': {paths}"
            for mid, paths in _find_duplicate_ids(pairs).items()
        )

    code_state_paths = {get_state_full_path(state_cls) for state_cls in all_states}

    missing = _collect_missing_entries(all_states, config)

    # Check for orphaned entries (in config but not in code)
    warnings.extend(
        f"Orphaned state in config: {state_path}"
        for state_path in config["states"]
        if state_path not in code_state_paths
    )

    for kind in _MEMBER_KINDS:
        code_names = collect_member_names(all_states, kind)
        for state_path, ids in config[kind.key].items():
            if duplicates := _find_duplicate_ids(ids.items()):
                errors.append(
                    _duplicate_member_ids_message(kind, state_path, duplicates)
                )
            if state_path not in code_names:
                warnings.append(f"Orphaned {kind.key} for state: {state_path}")
            else:
                warnings.extend(
                    f"Orphaned {kind.label} in config: {state_path}.{name}"
                    for name in ids
                    if name not in code_names[state_path]
                )

    return errors, warnings, missing


def collect_member_names(
    states: Iterable[type[BaseState]], kind: _MemberKind
) -> dict[str, set[str]]:
    """Map each state's config path to its members of one kind.

    Args:
        states: The state classes to inventory.
        kind: The kind of member to collect.

    Returns:
        ``state_path -> {name}`` for every given state.
    """
    return {
        get_state_full_path(state_cls): set(kind.names(state_cls))
        for state_cls in states
    }


def _sync_member_ids(
    kind: _MemberKind,
    existing: dict[str, dict[str, str]],
    all_states: Iterable[type[BaseState]],
    reassign_deleted: bool,
    prune: bool,
) -> dict[str, dict[str, str]]:
    """Bring one ``{state_path: {name: id}}`` section in line with the code.

    Args:
        kind: The kind of member the section numbers.
        existing: The section as configured.
        all_states: The state classes in the code.
        reassign_deleted: Whether a new id may fill a gap.
        prune: Whether to drop the members and states no longer in the code.

    Returns:
        The updated section; ids a member already has are kept.
    """
    code_names = collect_member_names(all_states, kind)
    section = {state_path: dict(ids) for state_path, ids in existing.items()}
    if prune:
        section = {
            state_path: kept
            for state_path, ids in section.items()
            if (
                kept := {
                    name: member_id
                    for name, member_id in ids.items()
                    if name in code_names.get(state_path, ())
                }
            )
        }
    # Ids are unique within each state.
    for state_path, ids in section.items():
        _reassign_duplicate_ids(
            ids, reassign_deleted, code_names.get(state_path, frozenset())
        )
    for state_path, names in code_names.items():
        ids = section.get(state_path, {})
        if new_names := [name for name in names if name not in ids]:
            ids.update(
                _assign_next_ids(
                    new_names,
                    {minified_name_to_int(member_id) for member_id in ids.values()},
                    reassign_deleted,
                )
            )
            section[state_path] = ids
    return section


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
        reassign_deleted: If True, fill id gaps left by removed entries.
            Retained orphan ids stay reserved unless pruned.
        prune: If True, remove entries for states, events and vars that no
            longer exist.

    Returns:
        The updated configuration.
    """
    all_states = collect_all_states(root_state)
    path_to_parent_key = {get_state_full_path(s): get_parent_key(s) for s in all_states}

    new_states: dict[str, StateEntry] = {
        k: StateEntry(id=v["id"], parent=v["parent"])
        for k, v in existing_config["states"].items()
    }

    # Prune orphaned entries if requested
    if prune:
        new_states = {k: v for k, v in new_states.items() if k in path_to_parent_key}

    # Every configured id stays reserved within its sibling group -- orphans
    # under their recorded parent, so their ids are never reused. Live entries
    # get their stored parent healed to the actual value.
    reparented: set[str] = set()
    for state_path, entry in new_states.items():
        parent_key = path_to_parent_key.get(state_path, entry["parent"])
        if parent_key != entry["parent"]:
            reparented.add(state_path)
        entry["parent"] = parent_key

    # Find states that need IDs assigned, grouped by parent key.
    parent_key_to_new_children: dict[str | None, list[str]] = {}
    for state_path, parent_key in path_to_parent_key.items():
        if state_path not in new_states:
            parent_key_to_new_children.setdefault(parent_key, []).append(state_path)

    # Depth-first order assigns a parent before its children look at its id.
    for parent_key, children in parent_key_to_new_children.items():
        assigned = _assign_state_ids(new_states, children, parent_key, reassign_deleted)
        for state_path, minified_name in assigned.items():
            new_states[state_path] = StateEntry(id=minified_name, parent=parent_key)

    _rehome_ambiguous_ids(new_states, reassign_deleted)
    _rehome_conflicting_ids(new_states, all_states, reassign_deleted, reparented)

    members = {
        kind.key: _sync_member_ids(
            kind, existing_config[kind.key], all_states, reassign_deleted, prune
        )
        for kind in _MEMBER_KINDS
    }
    return MinifyConfig(
        version=SCHEMA_VERSION,
        states=new_states,
        events=members["events"],
        vars=members["vars"],
    )
