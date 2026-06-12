"""Parse the keyboard shortcut string from ``FrontendInspectorPlugin(shortcut=...)``."""

from __future__ import annotations

import dataclasses

from reflex_base.utils.exceptions import ConfigError

_MODIFIER_ALIASES = {
    "cmd": "meta",
    "command": "meta",
    "super": "meta",
    "win": "meta",
    "windows": "meta",
    "option": "alt",
    "opt": "alt",
    "control": "ctrl",
}

_VALID_MODIFIERS = ("alt", "ctrl", "meta", "shift")


@dataclasses.dataclass(frozen=True, slots=True)
class Shortcut:
    """A normalized keyboard shortcut.

    ``key`` is lower-case and matched against ``KeyboardEvent.key.toLowerCase()``
    in the browser. The four boolean fields map onto the corresponding
    ``KeyboardEvent`` modifier properties.
    """

    key: str
    alt: bool = False
    ctrl: bool = False
    meta: bool = False
    shift: bool = False

    def to_json_payload(self) -> dict[str, str | bool]:
        """Return the shortcut as a JSON-serialisable dict.

        Returns:
            The shortcut fields as a plain dict, suitable for ``json.dumps``.
        """
        return dataclasses.asdict(self)


def parse_shortcut(value: str) -> Shortcut:
    """Parse a ``"alt+x"``-style shortcut string.

    Args:
        value: The raw shortcut from the config.

    Returns:
        A normalized :class:`Shortcut`.

    Raises:
        ConfigError: If the string is empty, has no key, or contains an
            unknown modifier.
    """
    if not value or not value.strip():
        msg = "FrontendInspectorPlugin shortcut must be a non-empty string."
        raise ConfigError(msg)

    parts = [p.strip().lower() for p in value.split("+")]
    if any(not p for p in parts):
        msg = f"FrontendInspectorPlugin shortcut={value!r} has empty segments."
        raise ConfigError(msg)

    *raw_modifiers, key = parts

    modifiers: set[str] = set()
    for raw in raw_modifiers:
        normalized = _MODIFIER_ALIASES.get(raw, raw)
        if normalized not in _VALID_MODIFIERS:
            msg = (
                f"FrontendInspectorPlugin shortcut={value!r} contains unknown "
                f"modifier {raw!r}; expected one of "
                f"{_VALID_MODIFIERS + tuple(_MODIFIER_ALIASES)}."
            )
            raise ConfigError(msg)
        modifiers.add(normalized)

    return Shortcut(
        key=key,
        alt="alt" in modifiers,
        ctrl="ctrl" in modifiers,
        meta="meta" in modifiers,
        shift="shift" in modifiers,
    )
