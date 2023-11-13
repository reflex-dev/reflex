"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.el.element import Element
from reflex.vars import Var as Var_
from .base import BaseHTML


class Canvas(BaseHTML):  # Inherits common attributes from BaseMeta
    """Display the canvas element."""

    tag = "canvas"
    height: Var_[Union[str, int, bool]]
    width: Var_[Union[str, int, bool]]


class Noscript(BaseHTML):  # noqa: E742
    """Display the noscript element."""

    tag = "noscript"


class Script(BaseHTML):  # Inherits common attributes from BaseMeta
    """Display the script element."""

    tag = "script"
    async_: Var_[Union[str, int, bool]]
    char_set: Var_[Union[str, int, bool]]
    cross_origin: Var_[Union[str, int, bool]]
    defer: Var_[Union[str, int, bool]]
    integrity: Var_[Union[str, int, bool]]
    language: Var_[Union[str, int, bool]]
    referrer_policy: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]
