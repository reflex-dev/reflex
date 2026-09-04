"""Reflex integrations docs."""

from pathlib import Path

DOCS_DIR = Path(__file__).parent


def get_doc(name: str) -> str:
    """Read a doc by name (without .md extension).

    Returns:
        The component.
    """
    return (DOCS_DIR / f"{name}.md").read_text()


def list_docs() -> list[str]:
    """List all available doc names.

    Returns:
        The component.
    """
    return sorted(p.stem for p in DOCS_DIR.glob("*.md"))
