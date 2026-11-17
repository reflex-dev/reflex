"""Naming helpers shared by the component library pages and sidebar."""

from reflex.utils.format import to_snake_case, to_title_case


def get_display_name(name: str) -> str:
    """Turn a library category or component key into a display label.

    Args:
        name: A key such as ``Data-Display`` or ``data_table``.

    Returns:
        The title-cased label, e.g. ``Data Display``.
    """
    # Dashed keys like "Data-Display" snake-case to "data__display".
    normalized = to_snake_case(name).replace("__", "_")
    if normalized == "html":
        return "HTML"
    if normalized == "svg":
        return "SVG"
    return to_title_case(normalized, sep=" ")
