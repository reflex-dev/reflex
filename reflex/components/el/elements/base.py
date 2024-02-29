from typing import Optional, Union

from reflex.components.el.element import Element
from reflex.vars import Var as Var


class BaseHTML(Element):
    """Base class for common attributes."""

    #  Provides a hint for generating a keyboard shortcut for the current element.
    access_key: Optional[Var[Union[str, int, bool]]] = None

    # Controls whether and how text input is automatically capitalized as it is entered/edited by the user.
    auto_capitalize: Optional[Var[Union[str, int, bool]]] = None

    # Indicates whether the element's content is editable.
    content_editable: Optional[Var[Union[str, int, bool]]] = None

    # Defines the ID of a <menu> element which will serve as the element's context menu.
    context_menu: Optional[Var[Union[str, int, bool]]] = None

    # Defines the text direction. Allowed values are ltr (Left-To-Right) or rtl (Right-To-Left)
    dir: Optional[Var[Union[str, int, bool]]] = None

    # Defines whether the element can be dragged.
    draggable: Optional[Var[Union[str, int, bool]]] = None

    # Hints what media types the media element is able to play.
    enter_key_hint: Optional[Var[Union[str, int, bool]]] = None

    # Defines whether the element is hidden.
    hidden: Optional[Var[Union[str, int, bool]]] = None

    # Defines the type of the element.
    input_mode: Optional[Var[Union[str, int, bool]]] = None

    # Defines the name of the element for metadata purposes.
    item_prop: Optional[Var[Union[str, int, bool]]] = None

    # Defines the language used in the element.
    lang: Optional[Var[Union[str, int, bool]]] = None

    # Defines the role of the element.
    role: Optional[Var[Union[str, int, bool]]] = None

    # Assigns a slot in a shadow DOM shadow tree to an element.
    slot: Optional[Var[Union[str, int, bool]]] = None

    # Defines whether the element may be checked for spelling errors.
    spell_check: Optional[Var[Union[str, int, bool]]] = None

    # Defines the position of the current element in the tabbing order.
    tab_index: Optional[Var[Union[str, int, bool]]] = None

    # Defines a tooltip for the element.
    title: Optional[Var[Union[str, int, bool]]] = None
