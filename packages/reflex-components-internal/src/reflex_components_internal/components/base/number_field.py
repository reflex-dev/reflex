"""Custom number field component."""

from typing import Any, Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_components_internal.components.base_ui import PACKAGE_NAME, BaseUIComponent
from reflex_components_internal.components.icons.hugeicon import hi
from reflex_components_internal.utils.twmerge import cn

LiteralDirection = Literal["horizontal", "vertical"]
LiteralNumberFieldSize = Literal["xs", "sm", "md", "lg", "xl"]

NUMBER_FIELD_SIZE_VARIANTS = {
    "xs": "h-7 rounded-ui-xs text-xs",
    "sm": "h-8 rounded-ui-sm text-sm",
    "md": "h-9 rounded-ui-md text-sm",
    "lg": "h-10 rounded-ui-lg text-sm",
    "xl": "h-12 rounded-ui-xl text-base",
}


class ClassNames:
    """Class names for number field components."""

    ROOT = "flex w-full max-w-64 flex-col gap-1.5 text-secondary-12 data-[disabled]:opacity-70"
    SCRUB_AREA = "inline-flex w-fit cursor-ew-resize touch-none items-center gap-1 text-sm font-medium text-secondary-12 select-none data-[disabled]:cursor-not-allowed data-[disabled]:text-secondary-8 data-[readonly]:cursor-default data-[scrubbing]:cursor-none"
    SCRUB_AREA_CURSOR = "fixed top-0 left-0 z-50 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-ui-sm border border-secondary-a4 bg-secondary-1 p-1 text-secondary-12 shadow-small"
    GROUP = "inline-flex w-full items-stretch overflow-hidden border border-secondary-a4 bg-secondary-1 text-secondary-12 transition-[border-color,box-shadow] hover:border-secondary-a6 focus-within:border-primary-a6 focus-within:shadow-[0_0_0_2px_var(--primary-4)] data-[disabled]:border-secondary-4 data-[disabled]:bg-secondary-3 data-[invalid]:border-destructive-10 data-[invalid]:focus-within:border-destructive-a11 data-[invalid]:focus-within:shadow-[0_0_0_2px_var(--destructive-4)]"
    INPUT = "h-full min-w-0 flex-1 bg-transparent px-2 text-center font-medium tabular-nums text-secondary-12 outline-none placeholder:text-secondary-9 data-[disabled]:cursor-not-allowed data-[disabled]:text-secondary-8"
    DECREMENT = "flex aspect-square h-full shrink-0 cursor-pointer items-center justify-center border-r border-secondary-a4 text-secondary-11 transition-colors hover:bg-secondary-3 hover:text-secondary-12 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-4 data-[disabled]:cursor-not-allowed data-[disabled]:bg-secondary-3 data-[disabled]:text-secondary-8 [&_svg]:size-4"
    INCREMENT = "flex aspect-square h-full shrink-0 cursor-pointer items-center justify-center border-l border-secondary-a4 text-secondary-11 transition-colors hover:bg-secondary-3 hover:text-secondary-12 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-4 data-[disabled]:cursor-not-allowed data-[disabled]:bg-secondary-3 data-[disabled]:text-secondary-8 [&_svg]:size-4"


class NumberFieldBaseComponent(BaseUIComponent):
    """Base component for number field components."""

    library = f"{PACKAGE_NAME}/number-field"

    @property
    def import_var(self):
        """Return the import variable for the number field component."""
        return ImportVar(tag="NumberField", package_path="", install=False)


class NumberFieldRoot(NumberFieldBaseComponent):
    """Group all parts of the number field and manage its state."""

    tag = "NumberField.Root"

    # The minimum value.
    min: Var[int | float]

    # The maximum value.
    max: Var[int | float]

    # Whether direct text entry may be outside the min/max range. Defaults to False.
    allow_out_of_range: Var[bool]

    # The step used while Alt is held. Defaults to 0.1.
    small_step: Var[int | float]

    # The normal step amount. Defaults to 1.
    step: Var[int | float | Literal["any"]]

    # The step used while Shift is held. Defaults to 10.
    large_step: Var[int | float]

    # Whether the user must enter a value. Defaults to False.
    required: Var[bool]

    # Whether the component ignores user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether the user cannot change the value. Defaults to False.
    read_only: Var[bool]

    # Identifies the field when a form is submitted.
    name: Var[str]

    # Identifies the form that owns the hidden input.
    form: Var[str]

    # The controlled numeric value.
    value: Var[int | float | None]

    # The initial uncontrolled numeric value.
    default_value: Var[int | float]

    # Whether the mouse wheel changes the value while focused and hovered.
    allow_wheel_scrub: Var[bool]

    # Whether stepping snaps to the nearest step. Defaults to False.
    snap_on_step: Var[bool]

    # Intl.NumberFormat options used to format the value.
    format: Var[dict[str, Any]]

    # Event handler called when the numeric value changes.
    on_value_change: EventHandler[passthrough_event_spec(int | float | None, dict)]

    # Event handler called when the numeric value is committed.
    on_value_committed: EventHandler[passthrough_event_spec(int | float | None, dict)]

    # The locale used to format the input value.
    locale: Var[str | list[str]]

    # A ref to access the hidden input element.
    input_ref: Var[Any]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the number field root component.

        Returns:
            The component.
        """
        props["data-slot"] = "number-field"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class NumberFieldScrubArea(NumberFieldBaseComponent):
    """An interactive area that changes the value when dragged."""

    tag = "NumberField.ScrubArea"

    # The cursor movement direction. Defaults to "horizontal".
    direction: Var[LiteralDirection]

    # Pixels the cursor must move before the value changes. Defaults to 2.
    pixel_sensitivity: Var[int | float]

    # Distance from the center at which the cursor loops around.
    teleport_distance: Var[int | float]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the number field scrub area component.

        Returns:
            The component.
        """
        props["data-slot"] = "number-field-scrub-area"
        cls.set_class_name(ClassNames.SCRUB_AREA, props)
        return super().create(*children, **props)


class NumberFieldScrubAreaCursor(NumberFieldBaseComponent):
    """A custom cursor displayed while scrubbing."""

    tag = "NumberField.ScrubAreaCursor"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the number field scrub area cursor component.

        Returns:
            The component.
        """
        props["data-slot"] = "number-field-scrub-area-cursor"
        cls.set_class_name(ClassNames.SCRUB_AREA_CURSOR, props)
        return super().create(*children, **props)


class NumberFieldGroup(NumberFieldBaseComponent):
    """Group the input with the increment and decrement buttons."""

    tag = "NumberField.Group"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the number field group component.

        Returns:
            The component.
        """
        props["data-slot"] = "number-field-group"
        cls.set_class_name(ClassNames.GROUP, props)
        return super().create(*children, **props)


class NumberFieldDecrement(NumberFieldBaseComponent):
    """A stepper button that decreases the field value."""

    tag = "NumberField.Decrement"

    # Whether the rendered element is a native button. Defaults to True.
    native_button: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the number field decrement button.

        Returns:
            The component.
        """
        props["data-slot"] = "number-field-decrement"
        cls.set_class_name(ClassNames.DECREMENT, props)
        return super().create(*children, **props)


class NumberFieldInput(NumberFieldBaseComponent):
    """The native input control in the number field."""

    tag = "NumberField.Input"

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the number field input component.

        Returns:
            The component.
        """
        props["data-slot"] = "number-field-input"
        cls.set_class_name(ClassNames.INPUT, props)
        return super().create(*children, **props)


class NumberFieldIncrement(NumberFieldBaseComponent):
    """A stepper button that increases the field value."""

    tag = "NumberField.Increment"

    # Whether the rendered element is a native button. Defaults to True.
    native_button: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the number field increment button.

        Returns:
            The component.
        """
        props["data-slot"] = "number-field-increment"
        cls.set_class_name(ClassNames.INCREMENT, props)
        return super().create(*children, **props)


class HighLevelNumberField(NumberFieldRoot):
    """High-level wrapper for a complete number field."""

    # The number field size. Defaults to "md".
    size: Var[LiteralNumberFieldSize]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create a complete number field or use explicit children.

        Args:
            *children: Optional custom number field children.
            **props: Additional properties to apply to the number field root.

        Returns:
            The number field component.

        Raises:
            ValueError: If size is not a supported number field size.
        """
        size = props.pop("size", "md")
        if size not in NUMBER_FIELD_SIZE_VARIANTS:
            available_sizes = ", ".join(NUMBER_FIELD_SIZE_VARIANTS)
            msg = f"Invalid size: {size}. Available sizes: {available_sizes}"
            raise ValueError(msg)

        if children:
            return NumberFieldRoot.create(*children, **props)

        return NumberFieldRoot.create(
            NumberFieldGroup.create(
                NumberFieldDecrement.create(
                    hi("MinusSignIcon"),
                    aria_label="Decrease value",
                ),
                NumberFieldInput.create(),
                NumberFieldIncrement.create(
                    hi("PlusSignIcon"),
                    aria_label="Increase value",
                ),
                class_name=cn(NUMBER_FIELD_SIZE_VARIANTS[size]),
            ),
            **props,
        )


class NumberField(ComponentNamespace):
    """Namespace for number field components."""

    root = staticmethod(NumberFieldRoot.create)
    scrub_area = staticmethod(NumberFieldScrubArea.create)
    scrub_area_cursor = staticmethod(NumberFieldScrubAreaCursor.create)
    group = staticmethod(NumberFieldGroup.create)
    decrement = staticmethod(NumberFieldDecrement.create)
    input = staticmethod(NumberFieldInput.create)
    increment = staticmethod(NumberFieldIncrement.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelNumberField.create)


number_field = NumberField()
