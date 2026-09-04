"""Other classes."""

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from .base import BaseHTML


class Details(BaseHTML):
    """Display the details element."""

    tag = "details"

    open: Var[bool] = field(
        doc="Indicates whether the details will be visible (expanded) to the user"
    )


class Dialog(BaseHTML):
    """Display the dialog element."""

    tag = "dialog"

    open: Var[bool] = field(
        doc="Indicates whether the dialog is active and can be interacted with"
    )


class Summary(BaseHTML):
    """Display the summary element.

    Used as a summary or caption for a <details> element.
    """

    tag = "summary"


class Slot(BaseHTML):
    """Display the slot element.

    Used as a placeholder inside a web component.
    """

    tag = "slot"


class Template(BaseHTML):
    """Display the template element.

    Used for declaring fragments of HTML that can be cloned and inserted in the document.
    """

    tag = "template"


class Math(BaseHTML):
    """Display the math element.

    Represents a mathematical expression.
    """

    tag = "math"


class Html(BaseHTML):
    """Display the html element."""

    tag = "html"

    manifest: Var[str] = field(
        doc="Specifies the URL of the document's cache manifest (obsolete in HTML5)"
    )


details = Details.create
dialog = Dialog.create
summary = Summary.create
slot = Slot.create
template = Template.create
math = Math.create
html = Html.create
