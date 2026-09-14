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


def docs_metadata(path: str, title: str, description: str | None) -> tuple[str, str]:
    """Build distinct search snippets using the page's product hierarchy.

    Args:
        path: The app-relative documentation route.
        title: The page heading.
        description: A summary extracted from the document, when available.

    Returns:
        The search title and description.
    """
    acronyms = {
        "ai": "AI",
        "api": "API",
        "cli": "CLI",
        "html": "HTML",
        "css": "CSS",
        "mcp": "MCP",
        "sdk": "SDK",
    }
    parents = [
        " ".join(acronyms.get(word, word.capitalize()) for word in part.split("-"))
        for part in path.strip("/").split("/")[:-1]
    ]
    if title.lower() == "index" and parents:
        title = " ".join(
            acronyms.get(word, word.capitalize())
            for word in path.strip("/").split("/")[-1].split("-")
        )
    title = " ".join(acronyms.get(word.lower(), word) for word in title.split())
    context = [
        parent for parent in reversed(parents) if parent.lower() != title.lower()
    ]
    subject = " · ".join([title, *context])
    summary = (
        description
        or f"{subject}: documentation, examples, and reference for building Python web applications with Reflex."
    )
    return f"{subject} · Reflex Docs", truncate_meta_description(summary)
