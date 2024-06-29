"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""

from typing import Union

from reflex.components.el.element import Element
from reflex.vars import Var as Var

from .base import BaseHTML


class Base(BaseHTML):  # noqa: E742
    """Display the base element."""

    tag = "base"

    tag = "base"
    href: Var[Union[str, int, bool]]
    target: Var[Union[str, int, bool]]


class Head(BaseHTML):  # noqa: E742
    """Display the head element."""

    tag = "head"


class Link(BaseHTML):  # noqa: E742
    """Display the link element."""

    tag = "link"

    cross_origin: Var[Union[str, int, bool]]
    href: Var[Union[str, int, bool]]
    href_lang: Var[Union[str, int, bool]]
    integrity: Var[Union[str, int, bool]]
    media: Var[Union[str, int, bool]]
    referrer_policy: Var[Union[str, int, bool]]
    rel: Var[Union[str, int, bool]]
    sizes: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]


class Meta(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the meta element."""

    tag = "meta"
    char_set: Var[Union[str, int, bool]]
    content: Var[Union[str, int, bool]]
    http_equiv: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]


class Title(Element):  # noqa: E742
    """Display the title element."""

    tag = "title"


# Had to be named with an underscore so it doesnt conflict with reflex.style Style in pyi
class StyleEl(Element):  # noqa: E742
    """Display the style element."""

    tag = "style"

    media: Var[Union[str, int, bool]]


base = Base.create
head = Head.create
link = Link.create
meta = Meta.create
title = Title.create
style = StyleEl.create
