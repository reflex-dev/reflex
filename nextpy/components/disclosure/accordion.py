"""Container to stack elements with spacing."""

from typing import List, Optional, Union

from nextpy.components.component import Component
from nextpy.components.libs.chakra import ChakraComponent
from nextpy.core.vars import Var


class Accordion(ChakraComponent):
    """The wrapper that uses cloneElement to pass props to AccordionItem children."""

    tag = "Accordion"

    # If true, multiple accordion items can be expanded at once.
    allow_multiple: Var[bool]

    # If true, any expanded accordion item can be collapsed again.
    allow_toggle: Var[bool]

    # The initial index(es) of the expanded accordion item(s).
    default_index: Var[Optional[List[int]]]

    # The index(es) of the expanded accordion item
    index: Var[Union[int, List[int]]]

    # If true, height animation and transitions will be disabled.
    reduce_motion: Var[bool]

    @classmethod
    def create(
        cls,
        *children,
        items=None,
        icon_pos="right",
        allow_multiple: Optional[Var[bool]] = None,
        allow_toggle: Optional[Var[bool]] = None,
        **props
    ) -> Component:
        """Create an accordion component.

        Args:
            *children: The children of the component.
            items: The items of the accordion component: list of tuples (label,panel)
            icon_pos: The position of the arrow icon of the accordion. "right", "left" or None
            allow_multiple: The allow_multiple property of the accordion. (True or False)
            allow_toggle: The allow_toggle property of the accordion. (True or False)
            **props: The properties of the component.

        Returns:
            The accordion component
        """
        if len(children) == 0:
            children = []
            if not items:
                items = []
            for label, panel in items:
                if icon_pos == "right":
                    button = AccordionButton.create(label, AccordionIcon.create())
                elif icon_pos == "left":
                    button = AccordionButton.create(AccordionIcon.create(), label)
                else:
                    button = AccordionButton.create(label)

                children.append(
                    AccordionItem.create(
                        button,
                        AccordionPanel.create(panel),
                    )
                )

        # if allow_multiple is True, allow_toggle is implicitely used and does not need to be defined
        if allow_multiple:
            props.update({"allow_multiple": allow_multiple})
        elif allow_toggle:
            props.update({"allow_toggle": allow_toggle})
        return super().create(*children, **props)


class AccordionItem(ChakraComponent):
    """A single accordion item."""

    tag = "AccordionItem"

    # A unique id for the accordion item.
    id_: Var[str]

    # If true, the accordion item will be disabled.
    is_disabled: Var[bool]

    # If true, the accordion item will be focusable.
    is_focusable: Var[bool]


class AccordionButton(ChakraComponent):
    """The button that toggles the expand/collapse state of the accordion item. This button must be wrapped in an element with role heading."""

    tag = "AccordionButton"


class AccordionPanel(ChakraComponent):
    """The container for the details to be revealed."""

    tag = "AccordionPanel"


class AccordionIcon(ChakraComponent):
    """A chevron-down icon that rotates based on the expanded/collapsed state."""

    tag = "AccordionIcon"
