"""Radix primitive components (https://www.radix-ui.com/primitives)."""

from .accordion import (
    AccordionContent,
    AccordionHeader,
    AccordionItem,
    AccordionRoot,
    AccordionTrigger,
    ChevronDownIcon,
)

accordion_root = AccordionRoot.create
accordion_item = AccordionItem.create
accordion_trigger = AccordionTrigger.create
accordion_content = AccordionContent.create
accordion_header = AccordionHeader.create
chevron_down_icon = ChevronDownIcon.create
