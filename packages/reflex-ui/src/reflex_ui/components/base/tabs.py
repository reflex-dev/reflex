"""Custom tabs component."""

from typing import Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_ui.components.base_ui import PACKAGE_NAME, BaseUIComponent

LiteralOrientation = Literal["horizontal", "vertical"]


class ClassNames:
    """Class names for tabs components."""

    ROOT = "flex flex-col gap-2"
    LIST = "bg-secondary-3 inline-flex gap-1 p-1 items-center justify-start rounded-ui-md relative z-0"
    TAB = "h-7 px-1.5 rounded-ui-sm justify-center items-center gap-1.5 inline-flex text-sm font-medium text-secondary-11 cursor-pointer z-[1] hover:text-secondary-12 transition-color text-nowrap data-[active]:text-secondary-12 data-[disabled]:cursor-not-allowed data-[disabled]:text-secondary-8"
    INDICATOR = "absolute top-1/2 left-0 -z-1 h-7 w-(--active-tab-width) -translate-y-1/2 translate-x-(--active-tab-left) rounded-ui-sm bg-secondary-1 shadow-small transition-all duration-200 ease-in-out"
    PANEL = "flex flex-col gap-2"


class TabsBaseComponent(BaseUIComponent):
    """Base component for tabs components."""

    library = f"{PACKAGE_NAME}/tabs"

    @property
    def import_var(self):
        """Return the import variable for the tabs component."""
        return ImportVar(tag="Tabs", package_path="", install=False)


class TabsRoot(TabsBaseComponent):
    """Groups the tabs and the corresponding panels. Renders a <div> element."""

    tag = "Tabs.Root"

    # The default value. Use when the component is not controlled. When the value is null, no Tab will be selected. Defaults to 0.
    default_value: Var[str | int]

    # The value of the currently selected Tab. Use when the component is controlled. When the value is null, no Tab will be selected.
    value: Var[str | int]

    # Callback invoked when new value is being set.
    on_value_change: EventHandler[passthrough_event_spec(str | dict)]

    # The component orientation (layout flow direction). Defaults to "horizontal".
    orientation: Var[LiteralOrientation]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the tabs root component.

        Returns:
            The component.
        """
        props["data-slot"] = "tabs"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class TabsList(TabsBaseComponent):
    """Groups the individual tab buttons. Renders a <div> element."""

    tag = "Tabs.List"

    # Whether to automatically change the active tab on arrow key focus. Otherwise, tabs will be activated using Enter or Spacebar key press. Defaults to False.
    activate_on_focus: Var[bool]

    # Whether to loop keyboard focus back to the first item when the end of the list is reached while using the arrow keys. Defaults to True.
    loop_focus: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the tabs list component.

        Returns:
            The component.
        """
        props["data-slot"] = "tabs-list"
        cls.set_class_name(ClassNames.LIST, props)
        return super().create(*children, **props)


class TabsTab(TabsBaseComponent):
    """An individual interactive tab button that toggles the corresponding panel. Renders a <button> element."""

    tag = "Tabs.Tab"

    # The value of the Tab. When not specified, the value is the child position index.
    value: Var[str | int]

    # Whether the component renders a native <button> element when replacing it via the render prop. Set to false if the rendered element is not a button (e.g. <div>). Defaults to True.
    native_button: Var[bool]

    # Whether the Tab is disabled. Defaults to false.
    disabled: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the tabs tab component.

        Returns:
            The component.
        """
        props["data-slot"] = "tabs-tab"
        cls.set_class_name(ClassNames.TAB, props)
        return super().create(*children, **props)


class TabsIndicator(TabsBaseComponent):
    """A visual indicator that can be styled to match the position of the currently active tab. Renders a <span> element."""

    tag = "Tabs.Indicator"

    # Whether to render itself before React hydrates. This minimizes the time that the indicator isn't visible after server-side rendering. Defaults to False.
    render_before_hydration: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the tabs indicator component.

        Returns:
            The component.
        """
        props["data-slot"] = "tabs-indicator"
        cls.set_class_name(ClassNames.INDICATOR, props)
        return super().create(*children, **props)


class TabsPanel(TabsBaseComponent):
    """A panel displayed when the corresponding tab is active. Renders a <div> element."""

    tag = "Tabs.Panel"

    # The value of the TabPanel. It will be shown when the Tab with the corresponding value is selected. If not provided, it will fall back to the index of the panel. It is recommended to explicitly provide it, as it's required for the tab panel to be rendered on the server.
    value: Var[str | int]

    # Whether to keep the HTML element in the DOM while the panel is hidden. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the tabs panel component.

        Returns:
            The component.
        """
        props["data-slot"] = "tabs-panel"
        cls.set_class_name(ClassNames.PANEL, props)
        return super().create(*children, **props)


class Tabs(ComponentNamespace):
    """Namespace for Tabs components."""

    root = __call__ = staticmethod(TabsRoot.create)
    list = staticmethod(TabsList.create)
    tab = staticmethod(TabsTab.create)
    panel = staticmethod(TabsPanel.create)
    indicator = staticmethod(TabsIndicator.create)
    class_names = ClassNames


tabs = Tabs()
