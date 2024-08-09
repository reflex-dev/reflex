"""String utility functions."""

import sys


def remove_prefix(text: str, prefix: str) -> str:
    """Remove a prefix from a string, if present.
    This can be removed once we drop support for Python 3.8.

    Args:
        text: The string to remove the prefix from.
        prefix: The prefix to remove.

    Returns:
        The string with the prefix removed, if present.
    """
    if sys.version_info >= (3, 9):
        return text.removeprefix(prefix)
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text
