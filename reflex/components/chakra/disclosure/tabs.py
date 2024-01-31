"""Tab components."""

from typing import List, Optional, Tuple

from reflex.components.chakra import (
    ChakraComponent,
    LiteralColorScheme,
    LiteralTabsVariant,
    LiteralTagAlign,
)
from reflex.components.component import Component
from reflex.vars import Var


class Tabs(ChakraComponent):
    """An accessible tabs component that provides keyboard interactions and ARIA attributes described in the WAI-ARIA Tabs Design Pattern. Tabs, provides context and state for all components."""

    tag = "Tabs"

    # The alignment of the tabs ("center" | "end" | "start").
    align: Var[LiteralTagAlign]

    # The initial index of the selected tab (in uncontrolled mode).
    default_index: Var[int]

    # The id of the tab.
    id_: Var[str]

    # If true, tabs will stretch to width of the tablist.
    is_fitted: Var[bool]

    # Performance booster. If true, rendering of the tab panel's will be deferred until it is selected.
    is_lazy: Var[bool]

    # If true, the tabs will be manually activated and display its panel by pressing Space or Enter. If false, the tabs will be automatically activated and their panel is displayed when they receive focus.
    is_manual: Var[bool]

    # The orientation of the tab list.
    orientation: Var[str]

    # "line" | "enclosed" | "enclosed-colored" | "soft-rounded" | "solid-rounded" | "unstyled"
    variant: Var[LiteralTabsVariant]

    # The color scheme of the tabs.
    color_scheme: Var[LiteralColorScheme]

    # Index of the selected tab (in controlled mode).
    index: Var[int]

    @classmethod
    def create(
        cls, *children, items: Optional[List[Tuple[str, str]]] = None, **props
    ) -> Component:
        """Create a tab component.

        Args:
            *children: The children of the component.
            items: The items for the tabs component, a list of tuple (label, panel)
            **props: The properties of the component.

        Returns:
            The tab component
        """
        if len(children) == 0:
            tabs = []
            panels = []
            if not items:
                items = []
            for label, panel in items:
                tabs.append(Tab.create(label))
                panels.append(TabPanel.create(panel))
            children = [TabList.create(*tabs), TabPanels.create(*panels)]  # type: ignore
        return super().create(*children, **props)


class Tab(ChakraComponent):
    """An element that serves as a label for one of the tab panels and can be activated to display that panel.."""

    tag = "Tab"

    # If true, the Tab won't be toggleable.
    is_disabled: Var[bool]

    # If true, the Tab will be selected.
    is_selected: Var[bool]

    # The id of the tab.
    id_: Var[str]

    # The id of the panel.
    panel_id: Var[str]

    _valid_parents: List[str] = ["TabList"]


class TabList(ChakraComponent):
    """Wrapper for the Tab components."""

    tag = "TabList"

    _valid_parents: List[str] = ["Tabs"]


class TabPanels(ChakraComponent):
    """Wrapper for the Tab components."""

    tag = "TabPanels"

    _valid_parents: List[str] = ["Tabs"]


class TabPanel(ChakraComponent):
    """An element that contains the content associated with a tab."""

    tag = "TabPanel"

    _valid_parents: List[str] = ["TabPanels"]
