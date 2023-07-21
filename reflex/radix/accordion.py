"""The Radix accordion component."""
from typing import List, Literal, Optional, Union

from reflex.components import Component


class AccordionComponent(Component):
    """Base class for all accordion components."""

    library = "@radix-ui/react-accordion"
    is_default = False

    # Whether to use a child.
    as_child: bool


class AccordionRoot(AccordionComponent):
    """Radix accordion root. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "AccordionRoot"

    type: Literal["single", "multiple"]
    value: Optional[Union[str, List[str]]]
    default_value: Optional[Union[str, List[str]]]
    collapsible: Optional[bool]
    disabled: Optional[bool]
    dir: Optional[Literal["ltr", "rtl"]]
    orientation: Optional[Literal["horizontal", "vertical"]]


class AccordionItem(AccordionComponent):
    """Radix accordion item."""

    tag = "Item"
    alias = "AccordionItem"

    disabled: Optional[bool]
    value: str


class AccordionHeader(AccordionComponent):
    """Radix accordion header."""

    tag = "Header"
    alias = "AccordionHeader"


class AccordionTrigger(AccordionComponent):
    """Radix accordion trigger."""

    tag = "Trigger"
    alias = "AccordionTrigger"


class AccordionContent(AccordionComponent):
    """Radix accordion content."""

    tag = "Content"
    alias = "AccordionContent"

    force_mount: Optional[bool]
