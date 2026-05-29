"""Custom input component."""

from typing import ClassVar, Literal

from reflex_components_core.el.elements.forms import Button
from reflex_components_core.el.elements.forms import Input as ReflexInput
from reflex_components_core.el.elements.inline import Span
from reflex_components_core.el.elements.typography import Div

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec, set_focus, set_value
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var, get_unique_variable_name
from reflex_components_internal.components.base_ui import PACKAGE_NAME, BaseUIComponent
from reflex_components_internal.components.icons.hugeicon import hi
from reflex_components_internal.utils.twmerge import cn

INPUT_SIZE_VARIANTS = {
    "xs": "px-1.5 h-7 rounded-ui-xs gap-1.5",
    "sm": "px-2 h-8 rounded-ui-sm gap-2",
    "md": "px-2.5 h-9 rounded-ui-md gap-2",
    "lg": "px-3 h-10 rounded-ui-lg gap-2.5",
    "xl": "px-3.5 h-12 rounded-ui-xl gap-3",
}

LiteralControlSize = Literal["xs", "sm", "md", "lg", "xl"]

DEFAULT_INPUT_ATTRS = {
    "autoComplete": "off",
    "autoCapitalize": "none",
    "autoCorrect": "off",
    "spellCheck": "false",
}


class ClassNames:
    """Class names for input components."""

    INPUT = "outline-none bg-transparent text-secondary-12 placeholder:text-secondary-10 text-sm leading-normal peer disabled:text-secondary-8 disabled:placeholder:text-secondary-8 w-full data-[disabled]:pointer-events-none font-medium"
    DIV = "flex flex-row items-center focus-within:shadow-[0px_0px_0px_2px_var(--primary-4)] focus-within:border-primary-a6 not-data-[invalid]:focus-within:hover:border-primary-a6 bg-white dark:bg-secondary-3 shrink-0 border border-secondary-4 hover:border-secondary-a6 transition-[color,box-shadow] text-secondary-9 [&_svg]:pointer-events-none has-data-[disabled]:border-secondary-4 has-data-[disabled]:bg-secondary-3 has-data-[disabled]:text-secondary-8 has-data-[disabled]:cursor-not-allowed cursor-text has-data-[invalid]:border-destructive-10 has-data-[invalid]:focus-within:border-destructive-a11 has-data-[invalid]:focus-within:shadow-[0px_0px_0px_2px_var(--destructive-4)] has-data-[invalid]:hover:border-destructive-a11 shadow-[0_1px_2px_0_rgba(0,0,0,0.02),0_1px_4px_0_rgba(0,0,0,0.02)] dark:shadow-none dark:border-secondary-5"


class InputBaseComponent(BaseUIComponent):
    """Base component for an input."""

    library = f"{PACKAGE_NAME}/input"

    @property
    def import_var(self):
        """Return the import variable for the input component."""
        return ImportVar(tag="Input", package_path="", install=False)


class InputRoot(InputBaseComponent, ReflexInput):
    """Root component for an input."""

    tag = "Input"
    on_value_change: EventHandler[passthrough_event_spec(str, dict)]
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> "InputRoot":
        """Create a high level input component with simplified API.

        Returns:
            The component.
        """
        props["data-slot"] = "input"
        cls.set_class_name(ClassNames.INPUT, props)
        return super().create(*children, **props)  # ty:ignore[invalid-return-type]


class HighLevelInput(InputBaseComponent):
    """High level wrapper for the Input component with simplified API."""

    # Size of the input.
    size: Var[LiteralControlSize]

    # Icon to display in the input.
    icon: Var[str]

    # Whether to show the clear button.
    show_clear_button: ClassVar[bool]

    # Events to fire when the clear button is clicked.
    clear_events: Var[list[EventHandler]]

    _el_input_props = {
        "default_value",
        "on_value_change",
        "accept",
        "alt",
        "auto_complete",
        "auto_focus",
        "capture",
        "checked",
        "default_checked",
        "form",
        "form_action",
        "form_enc_type",
        "form_method",
        "form_no_validate",
        "form_target",
        "list",
        "max",
        "max_length",
        "min_length",
        "min",
        "multiple",
        "pattern",
        "placeholder",
        "read_only",
        "required",
        "src",
        "step",
        "type",
        "value",
        "on_key_down",
        "on_key_up",
        "on_change",
        "on_focus",
        "on_blur",
        "disabled",
        "name",
    }

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create a high level input component with simplified API.

        Returns:
            The component.
        """
        # Extract and prepare input props
        input_props = {k: props.pop(k) for k in cls._el_input_props & props.keys()}

        # Extract component props
        icon = props.pop("icon", "")
        size = props.pop("size", "md")
        id = props.pop("id", get_unique_variable_name())
        class_name = props.pop("class_name", "")
        show_clear_button = props.pop("show_clear_button", True)
        clear_events = props.pop("clear_events", [])
        # Configure input with merged attributes
        custom_attrs_override = props.pop("custom_attrs", {})
        input_props.update({
            "id": id,
            "custom_attrs": {
                **DEFAULT_INPUT_ATTRS,
                **custom_attrs_override,
            },
        })

        return Div.create(
            (
                Span.create(
                    hi(icon, class_name="text-secondary-12 size-4 pointer-events-none"),
                    aria_hidden="true",
                )
                if icon
                else None
            ),
            InputRoot.create(**input_props),
            (cls._create_clear_button(id, clear_events) if show_clear_button else None),
            *children,
            on_click=set_focus(id),
            class_name=cn(f"{ClassNames.DIV} {INPUT_SIZE_VARIANTS[size]}", class_name),
            **props,
        )  # ty:ignore[invalid-return-type]

    @staticmethod
    def _create_clear_button(id: str, clear_events: list[EventHandler]) -> Button:
        """Create the clear button component.

        Returns:
            The component.
        """
        return Button.create(
            hi("CancelCircleIcon"),
            type="button",
            on_click=[
                set_value(id, ""),
                set_focus(id).stop_propagation,
                *clear_events,
            ],
            tab_index=-1,
            class_name="opacity-100 peer-placeholder-shown:opacity-0 hover:text-secondary-12 transition-colors peer-placeholder-shown:pointer-events-none peer-disabled:pointer-events-none peer-disabled:opacity-0 h-full text-secondary-11",
        )

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "size",
            "icon",
            "show_clear_button",
            "clear_events",
        ]


class Input(ComponentNamespace):
    """Namespace for Input components."""

    root = staticmethod(InputRoot.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelInput.create)


input = Input()
