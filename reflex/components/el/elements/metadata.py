"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Optional, Union

from reflex.components.el.element import Element
from reflex.vars import Var as Var

from .base import BaseHTML


class Base(BaseHTML):  # noqa: E742
    """Display the base element."""

    tag = "base"

    tag = "base"
    href: Optional[Var[Union[str, int, bool]]] = None
    target: Optional[Var[Union[str, int, bool]]] = None


class Head(BaseHTML):  # noqa: E742
    """Display the head element."""

    tag = "head"


class Link(BaseHTML):  # noqa: E742
    """Display the link element."""

    tag = "link"

    cross_origin: Optional[Var[Union[str, int, bool]]] = None
    href: Optional[Var[Union[str, int, bool]]] = None
    href_lang: Optional[Var[Union[str, int, bool]]] = None
    integrity: Optional[Var[Union[str, int, bool]]] = None
    media: Optional[Var[Union[str, int, bool]]] = None
    referrer_policy: Optional[Var[Union[str, int, bool]]] = None
    rel: Optional[Var[Union[str, int, bool]]] = None
    sizes: Optional[Var[Union[str, int, bool]]] = None
    type: Optional[Var[Union[str, int, bool]]] = None


class Meta(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the meta element."""

    tag = "meta"
    char_set: Optional[Var[Union[str, int, bool]]] = None
    content: Optional[Var[Union[str, int, bool]]] = None
    http_equiv: Optional[Var[Union[str, int, bool]]] = None
    name: Optional[Var[Union[str, int, bool]]] = None


class Title(Element):  # noqa: E742
    """Display the title element."""

    tag = "title"
