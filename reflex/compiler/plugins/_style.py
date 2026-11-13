"""Reuse normalization of unchanged literal app styles during a page walk."""

from typing import Any

from reflex_base.constants.base import REFLEX_VAR_OPENING_TAG
from reflex_base.style import Style


def _literal_style_key(value: Any) -> tuple | None:
    """Snapshot literal containers, declining dynamic or custom style values.

    Args:
        value: A raw style rule or one of its nested values.

    Returns:
        A mutation-sensitive key, or None when conversion must remain uncached.
    """
    value_type = type(value)
    if value_type is str:
        return (str, value) if REFLEX_VAR_OPENING_TAG not in value else None
    if value_type is float:
        return (float, value.hex())
    if value_type is int or value_type is bool or value_type is type(None):
        return (value_type, value)
    if value_type is dict:
        entries = []
        for key, item in value.items():
            if type(key) is not str or (item_key := _literal_style_key(item)) is None:
                return None
            entries.append((key, item_key))
        return (dict, tuple(entries))
    if value_type is list:
        items = []
        for item in value:
            if (item_key := _literal_style_key(item)) is None:
                return None
            items.append(item_key)
        return (list, tuple(items))
    return None


def _copy_style_containers(value: Any) -> Any:
    """Copy normalized mutable containers while retaining immutable Var leaves.

    Args:
        value: A normalized style value.

    Returns:
        A value whose nested dictionaries and lists belong to the caller.
    """
    if type(value) is dict:
        return {key: _copy_style_containers(item) for key, item in value.items()}
    if type(value) is list:
        return [_copy_style_containers(item) for item in value]
    return value


class _AppStyleCache:
    """Cache literal normalization while preserving mutations and node ownership."""

    def __init__(self) -> None:
        """Create a cache scoped to one bound page walk."""
        self._styles: dict[int, tuple[tuple, Style]] = {}

    def __call__(self, rule: dict[str, Any]) -> Style:
        """Normalize a rule, reusing conversion only while its contents match.

        Args:
            rule: The current class or factory style rule.

        Returns:
            A normalized style with independently owned mutable containers.
        """
        key = _literal_style_key(rule)
        if key is None:
            return Style(rule)
        cached = self._styles.get(id(rule))
        if cached is None or cached[0] != key:
            cached = self._styles[id(rule)] = (key, Style(rule))
        normalized = cached[1]
        result = Style()
        dict.update(
            result,
            {key: _copy_style_containers(value) for key, value in normalized.items()},
        )
        result._var_data = normalized._var_data
        return result
