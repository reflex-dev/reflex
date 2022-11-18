"""Typography components."""

from pynecone.components.component import Component

from .heading import Heading
from .markdown import Markdown
from .text import Text


def span(text: str, **kwargs) -> Component:
    """Create a span component.

    Args:
        text: The text to display.
        **kwargs: The keyword arguments to pass to the Text component.

    Returns:
        The span component.
    """
    return Text.create(text, as_="span", **kwargs)


__all__ = [f for f in dir() if f[0].isupper() or f in ("span",)]  # type: ignore
