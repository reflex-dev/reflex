"""Base classes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.vars.base import Var

from reflex_components_core.el.element import Element

AutoCapitalize = Literal["off", "none", "on", "sentences", "words", "characters"]
ContentEditable = Literal["inherit", "plaintext-only"] | bool
EnterKeyHint = Literal["enter", "done", "go", "next", "previous", "search", "send"]
InputMode = Literal[
    "none", "text", "tel", "url", "email", "numeric", "decimal", "search", "search"
]
AriaRole = Literal[
    "alert",
    "alertdialog",
    "application",
    "article",
    "banner",
    "button",
    "cell",
    "checkbox",
    "columnheader",
    "combobox",
    "complementary",
    "contentinfo",
    "definition",
    "dialog",
    "directory",
    "document",
    "feed",
    "figure",
    "form",
    "grid",
    "gridcell",
    "group",
    "heading",
    "img",
    "link",
    "list",
    "listbox",
    "listitem",
    "log",
    "main",
    "marquee",
    "math",
    "menu",
    "menubar",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "navigation",
    "none",
    "note",
    "option",
    "presentation",
    "progressbar",
    "radio",
    "radiogroup",
    "region",
    "row",
    "rowgroup",
    "rowheader",
    "scrollbar",
    "search",
    "searchbox",
    "separator",
    "slider",
    "spinbutton",
    "status",
    "switch",
    "tab",
    "table",
    "tablist",
    "tabpanel",
    "term",
    "textbox",
    "timer",
    "toolbar",
    "tooltip",
    "tree",
    "treegrid",
    "treeitem",
]


class BaseHTML(Element):
    """Base class for common attributes."""

    access_key: Var[str] = field(
        doc="Provides a hint for generating a keyboard shortcut for the current element."
    )

    auto_capitalize: Var[AutoCapitalize] = field(
        doc="Controls whether and how text input is automatically capitalized as it is entered/edited by the user."
    )

    content_editable: Var[ContentEditable] = field(
        doc="Indicates whether the element's content is editable."
    )

    context_menu: Var[str] = field(
        doc="Defines the ID of a <menu> element which will serve as the element's context menu."
    )

    dir: Var[str] = field(
        doc="Defines the text direction. Allowed values are ltr (Left-To-Right) or rtl (Right-To-Left)"
    )

    draggable: Var[bool] = field(doc="Defines whether the element can be dragged.")

    enter_key_hint: Var[EnterKeyHint] = field(
        doc="Hints what media types the media element is able to play."
    )

    hidden: Var[bool] = field(doc="Defines whether the element is hidden.")

    input_mode: Var[InputMode] = field(doc="Defines the type of the element.")

    item_prop: Var[str] = field(
        doc="Defines the name of the element for metadata purposes."
    )

    lang: Var[str] = field(doc="Defines the language used in the element.")

    role: Var[AriaRole] = field(doc="Defines the role of the element.")

    slot: Var[str] = field(
        doc="Assigns a slot in a shadow DOM shadow tree to an element."
    )

    spell_check: Var[bool] = field(
        doc="Defines whether the element may be checked for spelling errors."
    )

    tab_index: Var[int] = field(
        doc="Defines the position of the current element in the tabbing order."
    )

    title: Var[str] = field(doc="Defines a tooltip for the element.")


class RawTextBaseHTML(BaseHTML):
    """Base class for HTML elements with raw-text (RCDATA) content models.

    Raw-text elements (``<title>``, ``<style>``, ``<textarea>``, ``<script>``,
    ``<noscript>``) parse their content as text rather than child markup. A
    JSX component child stringifies as ``[object Object]``, so a stateful
    ``Bare`` child must be captured inside the element's snapshot body
    rather than being independently memoized as a sibling JSX call.
    """

    _memoization_mode = MemoizationMode(recursive=False)


class VoidBaseHTML(BaseHTML):
    """Base class for void HTML elements (no children allowed).

    Void elements (``<area>``, ``<base>``, ``<br>``, ``<col>``, ``<embed>``,
    ``<hr>``, ``<img>``, ``<input>``, ``<link>``, ``<meta>``, ``<source>``,
    ``<track>``, ``<wbr>``) cannot have children. A stateful ``Bare`` child
    must stay inside the element's snapshot body rather than being
    independently memoized into an invalid JSX call.
    """

    _memoization_mode = MemoizationMode(recursive=False)
