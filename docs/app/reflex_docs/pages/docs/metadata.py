"""SEO metadata helpers for docs routes."""


def truncate_meta_description(description: str, max_len: int = 155) -> str:
    """Return a search-snippet-safe meta description.

    Args:
        description: The candidate description.
        max_len: The maximum output length.

    Returns:
        The original description when it fits, otherwise a word-boundary
        truncation with a trailing ellipsis.
    """
    description = " ".join(description.split()).strip()
    if len(description) <= max_len:
        return description
    # Reserve one character for the trailing ellipsis so the result never
    # exceeds max_len, even when the leading slice has no word boundary.
    truncated = description[: max_len - 1].rsplit(" ", 1)[0].rstrip(",.;:")
    return f"{truncated}…"
