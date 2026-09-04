"""Reflex documentation bundled as a Python package."""

from pathlib import Path

DOCS_DIR = Path(__file__).parent / "_docs"


def list_docs() -> list[str]:
    """List bundled doc paths, relative to ``DOCS_DIR``.

    Returns:
        Sorted POSIX-style paths to each bundled markdown file.
    """
    return sorted(p.relative_to(DOCS_DIR).as_posix() for p in DOCS_DIR.rglob("*.md"))


def get_doc(rel_path: str) -> str:
    """Read a bundled doc by its path relative to ``DOCS_DIR``.

    Args:
        rel_path: Path to the markdown file, relative to ``DOCS_DIR``
            (e.g. ``"vars/custom_vars.md"``).

    Returns:
        The contents of the markdown file.
    """
    return (DOCS_DIR / rel_path).read_text(encoding="utf-8")


__all__ = ["DOCS_DIR", "get_doc", "list_docs"]
