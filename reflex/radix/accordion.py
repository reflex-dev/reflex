"""The Radix accordion component."""
from typing import List, Literal, Union

from reflex.components import Component
from reflex.vars import Var


class AccordionComponent(Component):
    """Base class for all accordion components."""

    library = "@radix-ui/react-accordion"
    is_default = False

    # Whether to use a child.
    as_child: Var[bool]


class AccordionRoot(AccordionComponent):
    """Radix accordion root. The onValueChange prop is not currently supported."""

    tag = "Root"
    alias = "AccordionRoot"

    type_: Var[Literal["single", "multiple"]]
    value: Var[Union[str, List[str]]]
    default_value: Var[Union[str, List[str]]]
    collapsible: Var[bool]
    disabled: Var[bool]
    dir: Var[Literal["ltr", "rtl"]]
    orientation: Var[Literal["horizontal", "vertical"]]


class AccordionItem(AccordionComponent):
    """Radix accordion item."""

    tag = "Item"
    alias = "AccordionItem"

    disabled: Var[bool]
    value: Var[str]


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

    force_mount: Var[bool]
