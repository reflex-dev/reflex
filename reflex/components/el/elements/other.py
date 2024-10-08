"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""

from typing import Union

from reflex.vars.base import Var

from .base import BaseHTML


class Details(BaseHTML):
    """Display the details element."""

    tag = "details"

    # Indicates whether the details will be visible (expanded) to the user
    open: Var[Union[str, int, bool]]


class Dialog(BaseHTML):
    """Display the dialog element."""

    tag = "dialog"

    # Indicates whether the dialog is active and can be interacted with
    open: Var[Union[str, int, bool]]


class Summary(BaseHTML):
    """Display the summary element."""

    tag = "summary"
    # No unique attributes, only common ones are inherited; used as a summary or caption for a <details> element


class Slot(BaseHTML):
    """Display the slot element."""

    tag = "slot"
    # No unique attributes, only common ones are inherited; used as a placeholder inside a web component


class Template(BaseHTML):
    """Display the template element."""

    tag = "template"
    # No unique attributes, only common ones are inherited; used for declaring fragments of HTML that can be cloned and inserted in the document


class Math(BaseHTML):
    """Display the math element."""

    tag = "math"
    # No unique attributes, only common ones are inherited; used for displaying mathematical expressions


class Html(BaseHTML):
    """Display the html element."""

    tag = "html"

    # Specifies the URL of the document's cache manifest (obsolete in HTML5)
    manifest: Var[Union[str, int, bool]]


details = Details.create
dialog = Dialog.create
summary = Summary.create
slot = Slot.create
template = Template.create
math = Math.create
html = Html.create
