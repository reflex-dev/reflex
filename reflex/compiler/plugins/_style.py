"""Reuse normalization of shared app style rules during a page walk."""

from typing import Any

from reflex_base.style import Style


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
    """Normalize each app style rule once per page walk."""

    def __init__(self) -> None:
        """Create a cache scoped to one bound page walk."""
        self._styles: dict[int, tuple[dict[str, Any], Style]] = {}

    def __call__(self, rule: dict[str, Any]) -> Style:
        """Normalize a rule, reusing the result for the same rule object.

        Args:
            rule: The current class or factory style rule.

        Returns:
            A normalized style with independently owned mutable containers.
        """
        # The entry keeps the rule alive, so its id cannot be reused.
        cached = self._styles.get(id(rule))
        if cached is None or cached[0] is not rule:
            cached = self._styles[id(rule)] = (rule, Style(rule))
        normalized = cached[1]
        result = Style()
        dict.update(
            result,
            {key: _copy_style_containers(value) for key, value in normalized.items()},
        )
        result._var_data = normalized._var_data
        return result
