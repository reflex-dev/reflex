"""Radix primitive components (https://www.radix-ui.com/primitives)."""

from .accordion import (
    AccordionContent,
    AccordionHeader,
    AccordionRoot,
    AccordionTrigger,
    accordion_item,
)
from .drawer import (
    drawer_close,
    drawer_content,
    drawer_description,
    drawer_overlay,
    drawer_portal,
    drawer_root,
    drawer_title,
    drawer_trigger,
)
from .form import (
    form_control,
    form_field,
    form_label,
    form_message,
    form_root,
    form_submit,
    form_validity_state,
)
from .progress import progress
from .slider import slider

# accordion
accordion = AccordionRoot.create
accordion_root = AccordionRoot.create
accordion_header = AccordionHeader.create
accordion_trigger = AccordionTrigger.create
accordion_content = AccordionContent.create
