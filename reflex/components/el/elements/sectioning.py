"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.vars import Var as Var

from .base import BaseHTML


class Body(BaseHTML):  # noqa: E742
    """Display the body element."""

    tag: str = "body"

    bgcolor: Var[Union[str, int, bool]]
    background: Var[Union[str, int, bool]]


class Address(BaseHTML):  # noqa: E742
    """Display the address element."""

    tag: str = "address"


class Article(BaseHTML):  # noqa: E742
    """Display the article element."""

    tag: str = "article"


class Aside(BaseHTML):  # noqa: E742
    """Display the aside element."""

    tag: str = "aside"


class Footer(BaseHTML):  # noqa: E742
    """Display the footer element."""

    tag: str = "footer"


class Header(BaseHTML):  # noqa: E742
    """Display the header element."""

    tag: str = "header"


class H1(BaseHTML):  # noqa: E742
    """Display the h1 element."""

    tag: str = "h1"


class H2(BaseHTML):  # noqa: E742
    """Display the h1 element."""

    tag: str = "h2"


class H3(BaseHTML):  # noqa: E742
    """Display the h1 element."""

    tag: str = "h3"


class H4(BaseHTML):  # noqa: E742
    """Display the h1 element."""

    tag: str = "h4"


class H5(BaseHTML):  # noqa: E742
    """Display the h1 element."""

    tag: str = "h5"


class H6(BaseHTML):  # noqa: E742
    """Display the h1 element."""

    tag: str = "h6"


class Main(BaseHTML):  # noqa: E742
    """Display the main element."""

    tag: str = "main"


class Nav(BaseHTML):  # noqa: E742
    """Display the nav element."""

    tag: str = "nav"


class Section(BaseHTML):  # noqa: E742
    """Display the section element."""

    tag: str = "section"
