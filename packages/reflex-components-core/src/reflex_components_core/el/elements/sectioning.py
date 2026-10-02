"""Sectioning classes."""

from .base import BaseHTML


class Body(BaseHTML):
    """Display the body element."""

    tag = "body"


class Address(BaseHTML):
    """Display the address element."""

    tag = "address"


class Article(BaseHTML):
    """Display the article element."""

    tag = "article"


class Aside(BaseHTML):
    """Display the aside element."""

    tag = "aside"


class Footer(BaseHTML):
    """Display the footer element."""

    tag = "footer"


class Header(BaseHTML):
    """Display the header element."""

    tag = "header"


class H1(BaseHTML):
    """Display the h1 element."""

    tag = "h1"


class H2(BaseHTML):
    """Display the h1 element."""

    tag = "h2"


class H3(BaseHTML):
    """Display the h1 element."""

    tag = "h3"


class H4(BaseHTML):
    """Display the h1 element."""

    tag = "h4"


class H5(BaseHTML):
    """Display the h1 element."""

    tag = "h5"


class H6(BaseHTML):
    """Display the h1 element."""

    tag = "h6"


class Main(BaseHTML):
    """Display the main element."""

    tag = "main"


class Nav(BaseHTML):
    """Display the nav element."""

    tag = "nav"


class Section(BaseHTML):
    """Display the section element."""

    tag = "section"


address = Address.create
article = Article.create
aside = Aside.create
body = Body.create
header = Header.create
footer = Footer.create
h1 = H1.create
h2 = H2.create
h3 = H3.create
h4 = H4.create
h5 = H5.create
h6 = H6.create
main = Main.create
nav = Nav.create
section = Section.create
