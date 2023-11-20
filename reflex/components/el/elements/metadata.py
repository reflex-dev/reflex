"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.components.el.element import Element
from reflex.vars import Var as Var_

from .base import BaseHTML


class Base(BaseHTML):  # noqa: E742
    """Display the base element."""

    tag = "base"

    tag = "base"
    href: Var_[Union[str, int, bool]]
    target: Var_[Union[str, int, bool]]


class Head(BaseHTML):  # noqa: E742
    """Display the head element."""

    tag = "head"


class Link(BaseHTML):  # noqa: E742
    """Display the link element."""

    tag = "link"

    cross_origin: Var_[Union[str, int, bool]]
    href: Var_[Union[str, int, bool]]
    href_lang: Var_[Union[str, int, bool]]
    integrity: Var_[Union[str, int, bool]]
    media: Var_[Union[str, int, bool]]
    referrer_policy: Var_[Union[str, int, bool]]
    rel: Var_[Union[str, int, bool]]
    sizes: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]


class Meta(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the meta element."""

    tag = "meta"
    char_set: Var_[Union[str, int, bool]]
    content: Var_[Union[str, int, bool]]
    http_equiv: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]


class Style(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the style element."""

    tag = "style"
    media: Var_[Union[str, int, bool]]
    scoped: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]


class Title(Element):  # noqa: E742
    """Display the title element."""

    tag = "title"
