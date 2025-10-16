"""Base classes."""

from typing import Literal

from reflex.components.el.element import Element
from reflex.vars.base import Var

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

    # Provides a hint for generating a keyboard shortcut for the current element.
    access_key: Var[str]

    # Controls whether and how text input is automatically capitalized as it is entered/edited by the user.
    auto_capitalize: Var[AutoCapitalize]

    # Indicates whether the element's content is editable.
    content_editable: Var[ContentEditable]

    # Defines the ID of a <menu> element which will serve as the element's context menu.
    context_menu: Var[str]

    # Defines the text direction. Allowed values are ltr (Left-To-Right) or rtl (Right-To-Left)
    dir: Var[str]

    # Defines whether the element can be dragged.
    draggable: Var[bool]

    # Hints what media types the media element is able to play.
    enter_key_hint: Var[EnterKeyHint]

    # Defines whether the element is hidden.
    hidden: Var[bool]

    # Defines the type of the element.
    input_mode: Var[InputMode]

    # Defines the name of the element for metadata purposes.
    item_prop: Var[str]

    # Defines the language used in the element.
    lang: Var[str]

    # Defines the role of the element.
    role: Var[AriaRole]

    # Assigns a slot in a shadow DOM shadow tree to an element.
    slot: Var[str]

    # Defines whether the element may be checked for spelling errors.
    spell_check: Var[bool]

    # Defines the position of the current element in the tabbing order.
    tab_index: Var[int]

    # Defines a tooltip for the element.
    title: Var[str]
