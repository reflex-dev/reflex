# This is an auto-generated file. Do not edit. See ../generate.py.
from typing import Union
from pynecone.var import Var
from pynecone.el.element import Element

class Html(Element):
    """Display the html element."""

    tag = "html"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    manifest: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

html = Html.create


class Base(Element):
    """Display the base element."""

    tag = "base"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    href: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    target: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

base = Base.create


class Head(Element):
    """Display the head element."""

    tag = "head"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

head = Head.create


class Link(Element):
    """Display the link element."""

    tag = "link"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    cross_origin: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    href: Var[Union[str, int, bool]]
    href_lang: Var[Union[str, int, bool]]
    integrity: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    media: Var[Union[str, int, bool]]
    referrer_policy: Var[Union[str, int, bool]]
    rel: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    sizes: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]

link = Link.create


class Meta(Element):
    """Display the meta element."""

    tag = "meta"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    char_set: Var[Union[str, int, bool]]
    content: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    http_equiv: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

meta = Meta.create


class Style(Element):
    """Display the style element."""

    tag = "style"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    media: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    scoped: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]

style = Style.create


class Title(Element):
    """Display the title element."""

    tag = "title"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

title = Title.create


class Body(Element):
    """Display the body element."""

    tag = "body"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    background: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

body = Body.create


class Address(Element):
    """Display the address element."""

    tag = "address"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

address = Address.create


class Article(Element):
    """Display the article element."""

    tag = "article"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

article = Article.create


class Aside(Element):
    """Display the aside element."""

    tag = "aside"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

aside = Aside.create


class Footer(Element):
    """Display the footer element."""

    tag = "footer"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

footer = Footer.create


class Header(Element):
    """Display the header element."""

    tag = "header"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

header = Header.create


class H1(Element):
    """Display the h1 element."""

    tag = "h1"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

h1 = H1.create


class H2(Element):
    """Display the h2 element."""

    tag = "h2"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

h2 = H2.create


class H3(Element):
    """Display the h3 element."""

    tag = "h3"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

h3 = H3.create


class H4(Element):
    """Display the h4 element."""

    tag = "h4"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

h4 = H4.create


class H5(Element):
    """Display the h5 element."""

    tag = "h5"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

h5 = H5.create


class H6(Element):
    """Display the h6 element."""

    tag = "h6"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

h6 = H6.create


class Main(Element):
    """Display the main element."""

    tag = "main"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

main = Main.create


class Nav(Element):
    """Display the nav element."""

    tag = "nav"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

nav = Nav.create


class Section(Element):
    """Display the section element."""

    tag = "section"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

section = Section.create


class Blockquote(Element):
    """Display the blockquote element."""

    tag = "blockquote"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    cite: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

blockquote = Blockquote.create


class Dd(Element):
    """Display the dd element."""

    tag = "dd"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

dd = Dd.create


class Div(Element):
    """Display the div element."""

    tag = "div"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

div = Div.create


class Dl(Element):
    """Display the dl element."""

    tag = "dl"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

dl = Dl.create


class Dt(Element):
    """Display the dt element."""

    tag = "dt"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

dt = Dt.create


class Figcaption(Element):
    """Display the figcaption element."""

    tag = "figcaption"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

figcaption = Figcaption.create


class Figure(Element):
    """Display the figure element."""

    tag = "figure"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

figure = Figure.create


class Hr(Element):
    """Display the hr element."""

    tag = "hr"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    color: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

hr = Hr.create


class Li(Element):
    """Display the li element."""

    tag = "li"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    value: Var[Union[str, int, bool]]

li = Li.create


class Menu(Element):
    """Display the menu element."""

    tag = "menu"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]

menu = Menu.create


class Ol(Element):
    """Display the ol element."""

    tag = "ol"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    reversed: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    start: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]

ol = Ol.create


class P(Element):
    """Display the p element."""

    tag = "p"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

p = P.create


class Pre(Element):
    """Display the pre element."""

    tag = "pre"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

pre = Pre.create


class Ul(Element):
    """Display the ul element."""

    tag = "ul"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

ul = Ul.create


class A(Element):
    """Display the a element."""

    tag = "a"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    download: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    href: Var[Union[str, int, bool]]
    href_lang: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    media: Var[Union[str, int, bool]]
    ping: Var[Union[str, int, bool]]
    referrer_policy: Var[Union[str, int, bool]]
    rel: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    shape: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    target: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

a = A.create


class Abbr(Element):
    """Display the abbr element."""

    tag = "abbr"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

abbr = Abbr.create


class B(Element):
    """Display the b element."""

    tag = "b"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

b = B.create


class Bdi(Element):
    """Display the bdi element."""

    tag = "bdi"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

bdi = Bdi.create


class Bdo(Element):
    """Display the bdo element."""

    tag = "bdo"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

bdo = Bdo.create


class Br(Element):
    """Display the br element."""

    tag = "br"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

br = Br.create


class Cite(Element):
    """Display the cite element."""

    tag = "cite"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

cite = Cite.create


class Code(Element):
    """Display the code element."""

    tag = "code"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

code = Code.create


class Data(Element):
    """Display the data element."""

    tag = "data"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    value: Var[Union[str, int, bool]]

data = Data.create


class Dfn(Element):
    """Display the dfn element."""

    tag = "dfn"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

dfn = Dfn.create


class Em(Element):
    """Display the em element."""

    tag = "em"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

em = Em.create


class I(Element):
    """Display the i element."""

    tag = "i"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

i = I.create


class Kbd(Element):
    """Display the kbd element."""

    tag = "kbd"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

kbd = Kbd.create


class Mark(Element):
    """Display the mark element."""

    tag = "mark"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

mark = Mark.create


class Q(Element):
    """Display the q element."""

    tag = "q"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    cite: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

q = Q.create


class Rp(Element):
    """Display the rp element."""

    tag = "rp"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

rp = Rp.create


class Rt(Element):
    """Display the rt element."""

    tag = "rt"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

rt = Rt.create


class Ruby(Element):
    """Display the ruby element."""

    tag = "ruby"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

ruby = Ruby.create


class S(Element):
    """Display the s element."""

    tag = "s"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

s = S.create


class Samp(Element):
    """Display the samp element."""

    tag = "samp"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

samp = Samp.create


class Small(Element):
    """Display the small element."""

    tag = "small"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

small = Small.create


class Span(Element):
    """Display the span element."""

    tag = "span"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

span = Span.create


class Strong(Element):
    """Display the strong element."""

    tag = "strong"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

strong = Strong.create


class Sub(Element):
    """Display the sub element."""

    tag = "sub"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

sub = Sub.create


class Sup(Element):
    """Display the sup element."""

    tag = "sup"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

sup = Sup.create


class Time(Element):
    """Display the time element."""

    tag = "time"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    date_time: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

time = Time.create


class U(Element):
    """Display the u element."""

    tag = "u"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

u = U.create


class Var(Element):
    """Display the var element."""

    tag = "var"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

var = Var.create


class Wbr(Element):
    """Display the wbr element."""

    tag = "wbr"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

wbr = Wbr.create


class Area(Element):
    """Display the area element."""

    tag = "area"

    access_key: Var[Union[str, int, bool]]
    alt: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    coords: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    download: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    href: Var[Union[str, int, bool]]
    href_lang: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    media: Var[Union[str, int, bool]]
    ping: Var[Union[str, int, bool]]
    referrer_policy: Var[Union[str, int, bool]]
    rel: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    shape: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    target: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

area = Area.create


class Audio(Element):
    """Display the audio element."""

    tag = "audio"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    auto_play: Var[Union[str, int, bool]]
    buffered: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    controls: Var[Union[str, int, bool]]
    cross_origin: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    loop: Var[Union[str, int, bool]]
    muted: Var[Union[str, int, bool]]
    preload: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

audio = Audio.create


class Img(Element):
    """Display the img element."""

    tag = "img"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    alt: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    border: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    cross_origin: Var[Union[str, int, bool]]
    decoding: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    height: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    intrinsicsize: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    ismap: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    loading: Var[Union[str, int, bool]]
    referrer_policy: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    sizes: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    src_set: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    use_map: Var[Union[str, int, bool]]
    width: Var[Union[str, int, bool]]

img = Img.create


class Map(Element):
    """Display the map element."""

    tag = "map"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

map = Map.create


class Track(Element):
    """Display the track element."""

    tag = "track"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    default: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    kind: Var[Union[str, int, bool]]
    label: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    src_lang: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

track = Track.create


class Video(Element):
    """Display the video element."""

    tag = "video"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    auto_play: Var[Union[str, int, bool]]
    buffered: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    controls: Var[Union[str, int, bool]]
    cross_origin: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    height: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    loop: Var[Union[str, int, bool]]
    muted: Var[Union[str, int, bool]]
    plays_inline: Var[Union[str, int, bool]]
    poster: Var[Union[str, int, bool]]
    preload: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    width: Var[Union[str, int, bool]]

video = Video.create


class Embed(Element):
    """Display the embed element."""

    tag = "embed"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    height: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]
    width: Var[Union[str, int, bool]]

embed = Embed.create


class Iframe(Element):
    """Display the iframe element."""

    tag = "iframe"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    allow: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    csp: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    height: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    loading: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    referrer_policy: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    sandbox: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    src_doc: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    width: Var[Union[str, int, bool]]

iframe = Iframe.create


class Object(Element):
    """Display the object element."""

    tag = "object"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    border: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    data: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    height: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]
    use_map: Var[Union[str, int, bool]]
    width: Var[Union[str, int, bool]]

object = Object.create


class Picture(Element):
    """Display the picture element."""

    tag = "picture"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

picture = Picture.create


class Portal(Element):
    """Display the portal element."""

    tag = "portal"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

portal = Portal.create


class Source(Element):
    """Display the source element."""

    tag = "source"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    media: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    sizes: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    src_set: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]

source = Source.create


class Svg(Element):
    """Display the svg element."""

    tag = "svg"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

svg = Svg.create


class Math(Element):
    """Display the math element."""

    tag = "math"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

math = Math.create


class Canvas(Element):
    """Display the canvas element."""

    tag = "canvas"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    height: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    width: Var[Union[str, int, bool]]

canvas = Canvas.create


class Noscript(Element):
    """Display the noscript element."""

    tag = "noscript"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

noscript = Noscript.create


class Script(Element):
    """Display the script element."""

    tag = "script"

    access_key: Var[Union[str, int, bool]]
    async_: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    char_set: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    cross_origin: Var[Union[str, int, bool]]
    defer: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    integrity: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    language: Var[Union[str, int, bool]]
    referrer_policy: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]

script = Script.create


class Del(Element):
    """Display the del_ element."""

    tag = "del_"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    cite: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    date_time: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

del_ = Del.create


class Ins(Element):
    """Display the ins element."""

    tag = "ins"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    cite: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    date_time: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

ins = Ins.create


class Caption(Element):
    """Display the caption element."""

    tag = "caption"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

caption = Caption.create


class Col(Element):
    """Display the col element."""

    tag = "col"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    span: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

col = Col.create


class Colgroup(Element):
    """Display the colgroup element."""

    tag = "colgroup"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    span: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

colgroup = Colgroup.create


class Table(Element):
    """Display the table element."""

    tag = "table"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    background: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    border: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    summary: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

table = Table.create


class Tbody(Element):
    """Display the tbody element."""

    tag = "tbody"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

tbody = Tbody.create


class Td(Element):
    """Display the td element."""

    tag = "td"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    background: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    col_span: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    headers: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    row_span: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

td = Td.create


class Tfoot(Element):
    """Display the tfoot element."""

    tag = "tfoot"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

tfoot = Tfoot.create


class Th(Element):
    """Display the th element."""

    tag = "th"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    background: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    col_span: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    headers: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    row_span: Var[Union[str, int, bool]]
    scope: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

th = Th.create


class Thead(Element):
    """Display the thead element."""

    tag = "thead"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

thead = Thead.create


class Tr(Element):
    """Display the tr element."""

    tag = "tr"

    access_key: Var[Union[str, int, bool]]
    align: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    bgcolor: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

tr = Tr.create


class Button(Element):
    """Display the button element."""

    tag = "button"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    auto_focus: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    disabled: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    form_action: Var[Union[str, int, bool]]
    form_enc_type: Var[Union[str, int, bool]]
    form_method: Var[Union[str, int, bool]]
    form_no_validate: Var[Union[str, int, bool]]
    form_target: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]
    value: Var[Union[str, int, bool]]

button = Button.create


class Datalist(Element):
    """Display the datalist element."""

    tag = "datalist"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

datalist = Datalist.create


class Fieldset(Element):
    """Display the fieldset element."""

    tag = "fieldset"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    disabled: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

fieldset = Fieldset.create


class Form(Element):
    """Display the form element."""

    tag = "form"

    accept: Var[Union[str, int, bool]]
    accept_charset: Var[Union[str, int, bool]]
    access_key: Var[Union[str, int, bool]]
    action: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    auto_complete: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enc_type: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    method: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    no_validate: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    target: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

form = Form.create


class Input(Element):
    """Display the input element."""

    tag = "input"

    accept: Var[Union[str, int, bool]]
    access_key: Var[Union[str, int, bool]]
    alt: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    auto_complete: Var[Union[str, int, bool]]
    auto_focus: Var[Union[str, int, bool]]
    capture: Var[Union[str, int, bool]]
    checked: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    dirname: Var[Union[str, int, bool]]
    disabled: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    form_action: Var[Union[str, int, bool]]
    form_enc_type: Var[Union[str, int, bool]]
    form_method: Var[Union[str, int, bool]]
    form_no_validate: Var[Union[str, int, bool]]
    form_target: Var[Union[str, int, bool]]
    height: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    list: Var[Union[str, int, bool]]
    max: Var[Union[str, int, bool]]
    max_length: Var[Union[str, int, bool]]
    min_length: Var[Union[str, int, bool]]
    min: Var[Union[str, int, bool]]
    multiple: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    pattern: Var[Union[str, int, bool]]
    placeholder: Var[Union[str, int, bool]]
    read_only: Var[Union[str, int, bool]]
    required: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    size: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    src: Var[Union[str, int, bool]]
    step: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    type: Var[Union[str, int, bool]]
    use_map: Var[Union[str, int, bool]]
    value: Var[Union[str, int, bool]]
    width: Var[Union[str, int, bool]]

input = Input.create


class Label(Element):
    """Display the label element."""

    tag = "label"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    html_for: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

label = Label.create


class Legend(Element):
    """Display the legend element."""

    tag = "legend"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

legend = Legend.create


class Meter(Element):
    """Display the meter element."""

    tag = "meter"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    high: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    low: Var[Union[str, int, bool]]
    max: Var[Union[str, int, bool]]
    min: Var[Union[str, int, bool]]
    optimum: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    value: Var[Union[str, int, bool]]

meter = Meter.create


class Optgroup(Element):
    """Display the optgroup element."""

    tag = "optgroup"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    disabled: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    label: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

optgroup = Optgroup.create


class Option(Element):
    """Display the option element."""

    tag = "option"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    disabled: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    label: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    selected: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    value: Var[Union[str, int, bool]]

option = Option.create


class Output(Element):
    """Display the output element."""

    tag = "output"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    html_for: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

output = Output.create


class Progress(Element):
    """Display the progress element."""

    tag = "progress"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    max: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    value: Var[Union[str, int, bool]]

progress = Progress.create


class Select(Element):
    """Display the select element."""

    tag = "select"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    auto_complete: Var[Union[str, int, bool]]
    auto_focus: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    disabled: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    multiple: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    required: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    size: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

select = Select.create


class Textarea(Element):
    """Display the textarea element."""

    tag = "textarea"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    auto_complete: Var[Union[str, int, bool]]
    auto_focus: Var[Union[str, int, bool]]
    cols: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    dirname: Var[Union[str, int, bool]]
    disabled: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    form: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    max_length: Var[Union[str, int, bool]]
    min_length: Var[Union[str, int, bool]]
    name: Var[Union[str, int, bool]]
    placeholder: Var[Union[str, int, bool]]
    read_only: Var[Union[str, int, bool]]
    required: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    rows: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]
    wrap: Var[Union[str, int, bool]]

textarea = Textarea.create


class Details(Element):
    """Display the details element."""

    tag = "details"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    open: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

details = Details.create


class Dialog(Element):
    """Display the dialog element."""

    tag = "dialog"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    open: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

dialog = Dialog.create


class Summary(Element):
    """Display the summary element."""

    tag = "summary"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

summary = Summary.create


class Slot(Element):
    """Display the slot element."""

    tag = "slot"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

slot = Slot.create


class Template(Element):
    """Display the template element."""

    tag = "template"

    access_key: Var[Union[str, int, bool]]
    auto_capitalize: Var[Union[str, int, bool]]
    content_editable: Var[Union[str, int, bool]]
    context_menu: Var[Union[str, int, bool]]
    dir: Var[Union[str, int, bool]]
    draggable: Var[Union[str, int, bool]]
    enter_key_hint: Var[Union[str, int, bool]]
    hidden: Var[Union[str, int, bool]]
    input_mode: Var[Union[str, int, bool]]
    item_prop: Var[Union[str, int, bool]]
    lang: Var[Union[str, int, bool]]
    role: Var[Union[str, int, bool]]
    slot: Var[Union[str, int, bool]]
    spell_check: Var[Union[str, int, bool]]
    tab_index: Var[Union[str, int, bool]]
    title: Var[Union[str, int, bool]]
    translate: Var[Union[str, int, bool]]

template = Template.create
