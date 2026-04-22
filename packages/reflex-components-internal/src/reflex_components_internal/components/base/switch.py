"""Custom switch component."""

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_ui.components.base_ui import PACKAGE_NAME, BaseUIComponent


class ClassNames:
    """Class names for switch components."""

    ROOT = "relative flex h-5 w-8 rounded-full bg-secondary-4 p-0.5 transition-colors duration-200 ease-out before:absolute before:rounded-full before:outline-offset-2 before:outline-primary-8 focus-visible:before:inset-0 data-[checked]:bg-primary-9 disabled:opacity-50 disabled:cursor-not-allowed cursor-default"
    THUMB = "aspect-square h-full rounded-full bg-white transition-transform duration-200 ease-out data-[checked]:translate-x-3 shadow-small"


class SwitchBaseComponent(BaseUIComponent):
    """Base component for switch components."""

    library = f"{PACKAGE_NAME}/switch"

    @property
    def import_var(self):
        """Return the import variable for the switch component."""
        return ImportVar(tag="Switch", package_path="", install=False)


class SwitchRoot(SwitchBaseComponent):
    """Represents the switch itself. Renders a <span> element and a hidden input beside it."""

    tag = "Switch.Root"

    # Identifies the field when a form is submitted.
    name: Var[str]

    # The value of the switch when it is checked. Used for form submission. Defaults to 'on'.
    value: Var[str]

    # Whether the switch is initially active. To render a controlled switch, use the checked prop instead. Defaults to False.
    default_checked: Var[bool]

    # Whether the switch is currently active. To render an uncontrolled switch, use the default_checked prop instead.
    checked: Var[bool]

    # Event handler called when the switch is activated or deactivated.
    on_checked_change: EventHandler[passthrough_event_spec(bool)]

    # Whether the component renders a native <button> element when replacing it via the render prop. Set to false if the rendered element is not a button (e.g. <div>). Defaults to True.
    native_button: Var[bool]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether the user should be unable to activate or deactivate the switch. Defaults to False.
    read_only: Var[bool]

    # Whether the user must activate the switch before submitting a form. Defaults to False.
    required: Var[bool]

    # A ref to access the hidden <input> element.
    input_ref: Var[str]

    # The value of the switch when it is unchecked. Used for form submission when unchecked. Defaults to not submitting any value.
    unchecked_value: Var[str]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the switch root component.

        Returns:
            The component.
        """
        props["data-slot"] = "switch"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class SwitchThumb(SwitchBaseComponent):
    """The movable part of the switch that indicates whether the switch is on or off. Renders a span."""

    tag = "Switch.Thumb"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the switch thumb component.

        Returns:
            The component.
        """
        props["data-slot"] = "switch-thumb"
        cls.set_class_name(ClassNames.THUMB, props)
        return super().create(*children, **props)


class HighLevelSwitch(SwitchRoot):
    """High-level wrapper for the Switch component."""

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create a complete switch component.

        Args:
            *children: Additional children to include in the switch.
            **props: Additional properties to apply to the switch component.

        Returns:
            The switch component.
        """
        return SwitchRoot.create(
            SwitchThumb.create(),
            *children,
            **props,
        )


class Switch(ComponentNamespace):
    """Namespace for Switch components."""

    root = staticmethod(SwitchRoot.create)
    thumb = staticmethod(SwitchThumb.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelSwitch.create)


switch = Switch()
