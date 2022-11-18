"""Handle styling."""

from typing import Optional

from pynecone import utils
from pynecone.var import Var


def convert(style_dict):
    """Format a style dictionary.

    Args:
        style_dict: The style dictionary to format.

    Returns:
        The formatted style dictionary.
    """
    out = {}
    for key, value in style_dict.items():
        key = utils.to_camel_case(key)
        if isinstance(value, dict):
            out[key] = convert(value)
        elif isinstance(value, Var):
            out[key] = str(value)
        else:
            out[key] = value
    return out


class Style(dict):
    """A style dictionary."""

    def __init__(self, style_dict: Optional[dict] = None):
        """Initialize the style.

        Args:
            style_dict: The style dictionary.
        """
        style_dict = style_dict or {}
        super().__init__(convert(style_dict))
