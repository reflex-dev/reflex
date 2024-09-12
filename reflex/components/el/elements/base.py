"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""

from typing import Union

from reflex.components.el.element import Element
from reflex.ivars.base import ImmutableVar


class BaseHTML(Element):
    """Base class for common attributes."""

    #  Provides a hint for generating a keyboard shortcut for the current element.
    access_key: ImmutableVar[Union[str, int, bool]]

    # Controls whether and how text input is automatically capitalized as it is entered/edited by the user.
    auto_capitalize: ImmutableVar[Union[str, int, bool]]

    # Indicates whether the element's content is editable.
    content_editable: ImmutableVar[Union[str, int, bool]]

    # Defines the ID of a <menu> element which will serve as the element's context menu.
    context_menu: ImmutableVar[Union[str, int, bool]]

    # Defines the text direction. Allowed values are ltr (Left-To-Right) or rtl (Right-To-Left)
    dir: ImmutableVar[Union[str, int, bool]]

    # Defines whether the element can be dragged.
    draggable: ImmutableVar[Union[str, int, bool]]

    # Hints what media types the media element is able to play.
    enter_key_hint: ImmutableVar[Union[str, int, bool]]

    # Defines whether the element is hidden.
    hidden: ImmutableVar[Union[str, int, bool]]

    # Defines the type of the element.
    input_mode: ImmutableVar[Union[str, int, bool]]

    # Defines the name of the element for metadata purposes.
    item_prop: ImmutableVar[Union[str, int, bool]]

    # Defines the language used in the element.
    lang: ImmutableVar[Union[str, int, bool]]

    # Defines the role of the element.
    role: ImmutableVar[Union[str, int, bool]]

    # Assigns a slot in a shadow DOM shadow tree to an element.
    slot: ImmutableVar[Union[str, int, bool]]

    # Defines whether the element may be checked for spelling errors.
    spell_check: ImmutableVar[Union[str, int, bool]]

    # Defines the position of the current element in the tabbing order.
    tab_index: ImmutableVar[Union[str, int, bool]]

    # Defines a tooltip for the element.
    title: ImmutableVar[Union[str, int, bool]]
