"""Naming helpers shared by the component library pages and sidebar."""

from reflex.utils.format import to_snake_case, to_title_case

from reflex_docs.utils.acronyms import uppercase_acronyms


def get_display_name(name: str) -> str:
    """Turn a library category or component key into a display label.

    Args:
        name: A key such as ``Data-Display`` or ``data_table``.

    Returns:
        The title-cased label with acronyms kept, e.g. ``Data Display`` or
        ``HTML Embed``.
    """
    # Dashed keys like "Data-Display" snake-case to "data__display".
    normalized = to_snake_case(name).replace("__", "_")
    return uppercase_acronyms(to_title_case(normalized, sep=" "))
