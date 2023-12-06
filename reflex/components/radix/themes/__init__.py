"""Namespace for components provided by the @radix-ui/themes library."""
from .base import Theme, ThemePanel
from .components import *
from .layout import *
from .typography import *

theme = Theme.create
theme_panel = ThemePanel.create

accordion_root = AccordionRoot.create
accordion_item = AccordionItem.create
accordion_trigger = AccordionTrigger.create
accordion_content = AccordionContent.create
accordion_header = AccordionHeader.create
chevron_down_icon = ChevronDownIcon.create

