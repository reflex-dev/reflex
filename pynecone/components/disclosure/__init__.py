"""Disclosure components."""

from .accordion import (
    Accordion,
    AccordionButton,
    AccordionIcon,
    AccordionItem,
    AccordionPanel,
)
from .tabs import Tab, TabList, TabPanel, TabPanels, Tabs
from .visuallyhidden import VisuallyHidden

__all__ = [f for f in dir() if f[0].isupper()]  # type: ignore
