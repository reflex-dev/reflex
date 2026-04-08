"""Custom Accordion component."""

from typing import Any, Literal

from reflex_components_core.core.foreach import foreach
from reflex_components_core.el.elements.typography import Div

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex.vars.object import ObjectVar
from reflex_ui.components.base_ui import PACKAGE_NAME, BaseUIComponent
from reflex_ui.components.icons.hugeicon import icon

LiteralOrientation = Literal["horizontal", "vertical"]

ITEMS_TYPE = list[dict[str, str | Component]]


class ClassNames:
    """Class names for accordion components."""

    ROOT = "flex flex-col justify-center shadow-small border border-secondary-a4 divide-y divide-secondary-a4 overflow-hidden rounded-xl"
    ITEM = ""
    HEADER = ""
    TRIGGER = "group relative flex w-full items-center justify-between gap-4 bg-secondary-1 hover:bg-secondary-3 px-6 py-4 text-md font-semibold text-secondary-12 transition-colors disabled:cursor-not-allowed disabled:bg-secondary-3 disabled:text-secondary-8 disabled:[&_svg]:text-secondary-8 [&_svg]:text-secondary-11"
    PANEL = "h-[var(--accordion-panel-height)] overflow-hidden text-base text-secondary-11 font-medium transition-[height] ease-out data-[ending-style]:h-0 data-[starting-style]:h-0 border-t border-secondary-a4"
    PANEL_DIV = "py-4 px-6"
    TRIGGER_ICON = "size-4 shrink-0 transition-all ease-out group-data-[panel-open]:scale-110 group-data-[panel-open]:rotate-45"


class AccordionBaseComponent(BaseUIComponent):
    """Base component for accordion components."""

    library = f"{PACKAGE_NAME}/accordion"

    @property
    def import_var(self):
        """Return the import variable for the accordion component."""
        return ImportVar(tag="Accordion", package_path="", install=False)


class AccordionRoot(AccordionBaseComponent):
    """Groups all parts of the accordion."""

    tag = "Accordion.Root"

    # The uncontrolled value of the item(s) that should be initially expanded. To render a controlled accordion, use the `value` prop instead.
    default_value: Var[list[Any]]

    # The controlled value of the item(s) that should be expanded. To render an uncontrolled accordion, use the `default_value` prop instead.
    value: Var[list[Any]]

    # Event handler called when an accordion item is expanded or collapsed. Provides the new value as an argument.
    on_value_change: EventHandler[passthrough_event_spec(list[str])]

    # Allows the browser's built-in page search to find and expand the panel contents. Overrides the `keep_mounted` prop and uses `hidden="until-found"` to hide the element without removing it from the DOM. Defaults to False.
    hidden_until_found: Var[bool]

    # Whether multiple items can be open at the same time. Defaults to True.
    multiple: Var[bool]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether to loop keyboard focus back to the first item when the end of the list is reached while using the arrow keys. Defaults to True.
    loop_focus: Var[bool]

    # The visual orientation of the accordion. Controls whether roving focus uses left/right or up/down arrow keys. Defaults to 'vertical'.
    orientation: Var[LiteralOrientation]

    # Whether to keep the element in the DOM while the panel is closed. This prop is ignored when hidden_until_found is used. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the accordion root component.

        Returns:
            The component.
        """
        props["data-slot"] = "accordion"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class AccordionItem(AccordionBaseComponent):
    """Groups an accordion header with the corresponding panel."""

    tag = "Accordion.Item"

    # The value that identifies this item.
    value: Var[str]

    # Event handler called when the panel is opened or closed.
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the accordion item component.

        Returns:
            The component.
        """
        props["data-slot"] = "accordion-item"
        cls.set_class_name(ClassNames.ITEM, props)
        return super().create(*children, **props)


class AccordionHeader(AccordionBaseComponent):
    """A heading that labels the corresponding panel."""

    tag = "Accordion.Header"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the accordion header component.

        Returns:
            The component.
        """
        props["data-slot"] = "accordion-header"
        cls.set_class_name(ClassNames.HEADER, props)
        return super().create(*children, **props)


class AccordionTrigger(AccordionBaseComponent):
    """A button that opens and closes the corresponding panel."""

    tag = "Accordion.Trigger"

    # Whether the component renders a native `<button>` element when replacing it via the `render` prop. Set to `false` if the rendered element is not a button (e.g. `<div>`). Defaults to True.
    native_button: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the accordion trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "accordion-trigger"
        cls.set_class_name(ClassNames.TRIGGER, props)
        return super().create(*children, **props)


class AccordionPanel(AccordionBaseComponent):
    """A collapsible panel with the accordion item contents."""

    tag = "Accordion.Panel"

    # Allows the browser's built-in page search to find and expand the panel contents. Overrides the `keep_mounted` prop and uses `hidden="until-found"` to hide the element without removing it from the DOM. Defaults to False.
    hidden_until_found: Var[bool]

    # Whether to keep the element in the DOM while the panel is closed. This prop is ignored when `hidden_until_found` is used. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the accordion panel component.

        Returns:
            The component.
        """
        props["data-slot"] = "accordion-panel"
        cls.set_class_name(ClassNames.PANEL, props)
        return super().create(*children, **props)


class HighLevelAccordion(AccordionRoot):
    """High level wrapper for the Accordion component."""

    items: Var[ITEMS_TYPE] | ITEMS_TYPE

    _item_props = {"on_open_change", "disabled"}
    _trigger_props = {"native_button"}
    _panel_props = {"hidden_until_found", "keep_mounted"}

    @classmethod
    def create(
        cls,
        items: Var[ITEMS_TYPE] | ITEMS_TYPE,
        **props,
    ) -> BaseUIComponent:
        """Create a high level accordion component.

        Args:
            items: List of dictionaries with 'trigger', 'content', and optional 'value' and 'disabled' keys.
            **props: Additional properties to apply to the accordion component.

        Returns:
            The accordion component with all necessary subcomponents.
        """
        # Extract props for different parts
        item_props = {k: props.pop(k) for k in cls._item_props & props.keys()}
        trigger_props = {k: props.pop(k) for k in cls._trigger_props & props.keys()}
        panel_props = {k: props.pop(k) for k in cls._panel_props & props.keys()}

        if isinstance(items, Var):
            accordion_items = foreach(
                items,
                lambda item: cls._create_accordion_item_dynamic(
                    item, item_props, trigger_props, panel_props
                ),
            )
            return AccordionRoot.create(accordion_items, **props)
        accordion_items = [
            cls._create_accordion_item(
                item, index, item_props, trigger_props, panel_props
            )
            for index, item in enumerate(items)
        ]
        return AccordionRoot.create(*accordion_items, **props)

    @classmethod
    def _create_trigger_icon(cls) -> Component:
        """Create the accordion trigger icon.

        Returns:
            The component.
        """
        return icon(
            "PlusSignIcon",
            class_name=ClassNames.TRIGGER_ICON,
            data_slot="accordion-trigger-icon",
        )

    @classmethod
    def _create_accordion_item(
        cls,
        item: dict[str, str | Component],
        index: int,
        item_props: dict,
        trigger_props: dict,
        panel_props: dict,
    ) -> BaseUIComponent:
        """Create a single accordion item from a dictionary (for normal lists).

        Returns:
            The component.
        """
        return AccordionItem.create(
            AccordionHeader.create(
                AccordionTrigger.create(
                    item.get("trigger"),
                    cls._create_trigger_icon(),
                    **trigger_props,
                ),
            ),
            AccordionPanel.create(
                Div.create(
                    item.get("content"),
                    class_name=ClassNames.PANEL_DIV,
                    data_slot="accordion-panel-div",
                ),
                **panel_props,
            ),
            value=item.get("value", f"item-{index + 1}"),
            disabled=item.get("disabled", False),
            **item_props,
        )

    @classmethod
    def _create_accordion_item_dynamic(
        cls,
        item: ObjectVar[dict[str, str | Component]],
        item_props: dict,
        trigger_props: dict,
        panel_props: dict,
    ) -> BaseUIComponent:
        """Create a single accordion item from a dictionary (for Var items).

        Returns:
            The component.
        """
        return AccordionItem.create(
            AccordionHeader.create(
                AccordionTrigger.create(
                    item["trigger"],
                    cls._create_trigger_icon(),
                    **trigger_props,
                ),
            ),
            AccordionPanel.create(
                Div.create(
                    item["content"],
                    class_name=ClassNames.PANEL_DIV,
                    data_slot="accordion-panel-div",
                ),
                **panel_props,
            ),
            value=item.get("value", ""),
            disabled=item.get("disabled", False).bool(),
            **item_props,
        )


class Accordion(ComponentNamespace):
    """Namespace for Accordion components."""

    root = staticmethod(AccordionRoot.create)
    item = staticmethod(AccordionItem.create)
    header = staticmethod(AccordionHeader.create)
    trigger = staticmethod(AccordionTrigger.create)
    panel = staticmethod(AccordionPanel.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelAccordion.create)


accordion = Accordion()
