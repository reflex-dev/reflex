"""A form: the native element, its fields, and messages for what is not valid."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Any, ClassVar, Literal

from reflex_base.components.component import (
    BaseComponent,
    Component,
    ComponentNamespace,
    field,
)
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_base.utils.form import FormData as _FormData
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_components_core.core.debounce import DebounceInput
from reflex_components_core.el.elements.forms import BaseInput, Select, Textarea
from reflex_components_core.el.elements.forms import Form as HTMLForm

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components._group import literal
from reflex_components_ui.constants import WEB_DIR
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.form import FORM, FORM_FIELD, FORM_LABEL, FORM_MESSAGE

# A form control composes with native form controls only: an input, select
# or textarea, or a component rendering one.
_FORM_CONTROL_CHILD_TYPES = (BaseInput, Select, Textarea, DebounceInput)

_SCRIPT = f"$/{WEB_DIR}/behaviors/form-validity.js"


def _handler(name: str) -> Var:
    """Get one of the functions that show the validity of a form's controls.

    Args:
        name: The name of the function.

    Returns:
        The function, with its import.
    """
    return Var(name, _var_data=VarData(imports={_SCRIPT: [ImportVar(tag=name)]}))


# What reads the validity of the controls of a form, all the JavaScript of
# one: a form without a message has none.
_INVALID = _handler("invalid")
_CHANGED = _handler("changed")
_LEFT = _handler("left")
_CLEARED = _handler("cleared")
_FOCUS_INVALID = _handler("focusInvalid")

# Numbers the fields whose control is given no id of its own.
_ids = itertools.count(1)


def _find(component: BaseComponent, kind: type | tuple[type, ...]) -> Iterator[Any]:
    """Find the components of a kind below another, at any depth.

    Args:
        component: Where to look.
        kind: The class of what is looked for.

    Yields:
        Each one, in the order of the tree.
    """
    for child in component.children:
        if isinstance(child, kind):
            yield child
        yield from _find(child, kind)


def _native(control: Component) -> Component:
    """Find the native control a component renders.

    Args:
        control: A form control, or a component that draws a box around one.

    Returns:
        The component that renders the input, the select or the textarea.
    """
    if isinstance(control, UIComponent) and control.tag == "div":
        return control.children[0]  # pyright: ignore[reportReturnType]
    return control


def _give(control: Component, prop: str, value: Any) -> Any:
    """Give a control an attribute, unless it has it already.

    Args:
        control: The component that renders the control.
        prop: The attribute.
        value: Its value.

    Returns:
        The value the control has now.
    """
    if prop in control.get_fields():
        current = getattr(control, prop)
        if current is None:
            setattr(control, prop, value)
            return value
        return current
    return control.custom_attrs.setdefault(prop, value)


class FormRoot(HTMLForm, UIComponent):
    """The root component of a radix form.

    The form element of Reflex comes first: it renders the submit it handles
    over what an rx.ui element renders.
    """

    tag = "form"

    styles: ClassVar[ComponentStyles] = FORM

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child."
    )

    on_clear_server_errors: EventHandler[no_args_event_spec] = field(
        doc="Fired when the errors are cleared."
    )

    def _set_slot(self) -> None:
        """Render the form itself: it is the element that submits."""

    def _post_init(self, *args, **kwargs):
        """Initialize the form, and see whether it has validity to show.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        self._has_messages = next(_find(self, FormMessage), None) is not None

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the form, its script included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        if self._has_messages:
            yield _INVALID
            yield _CHANGED
            yield _LEFT
            yield _CLEARED

    def _render(self) -> CommonTag:
        """Render the form.

        Returns:
            The tag. A form with messages reads the validity of its controls
            where it changes, and server errors are cleared where Radix
            clears them: on a submit and on a reset.
        """
        tag = super()._render()
        clear = tag.props.get("onClearServerErrors")
        tag = tag.remove_props("onClearServerErrors")
        handlers: dict[str, list[str]] = {}
        if self._has_messages:
            handlers = {
                "onInvalid": [str(_INVALID)],
                "onChangeCapture": [str(_CHANGED)],
                "onBlurCapture": [str(_LEFT)],
                "onReset": [str(_CLEARED)],
            }
        var_data = None
        if clear is not None:
            clear = LiteralVar.create(clear)
            var_data = clear._get_all_var_data()
            for prop in ("onReset", "onSubmitCapture"):
                handlers.setdefault(prop, []).append(f"({clear!s})")
        for prop, functions in handlers.items():
            calls = "; ".join(f"{function}(event)" for function in functions)
            tag = tag.add_props(**{
                prop: Var(f"((event) => {{ {calls}; }})", _var_data=var_data)
            })
        return tag


class FormField(UIComponent):
    """A form field component."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = FORM_FIELD

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child."
    )

    name: Var[str] = field(
        doc="The name of the form field, that is passed down to the control and used to match with validation messages."
    )

    server_invalid: Var[bool] = field(
        doc="Flag to mark the form field as invalid, for server side validation."
    )

    def _set_slot(self) -> None:
        """Render the field itself."""

    def _post_init(self, *args, **kwargs):
        """Initialize the field: name its control, and point its labels at it.

        Radix hands the name and an id through a context. Here the field
        finds its control and its labels while compiling, below it at any
        depth.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        control_id: Any = None
        for control in _find(self, Component):
            if not getattr(control, "_is_field_control", False):
                continue
            if self.name is not None:
                _give(control, "name", self.name)
            if control_id is None:
                control_id = control.id
                if control_id is None:
                    control_id = control.id = LiteralVar.create(
                        f"rx-form-field-{next(_ids)}"
                    )
            if self.server_invalid is not None:
                control.custom_attrs.setdefault(
                    "aria-invalid",
                    Var(
                        f"({self.server_invalid!s} || undefined)",
                        _var_data=self.server_invalid._get_all_var_data(),
                    ),
                )
        if control_id is not None:
            for label in _find(self, FormLabel):
                label.custom_attrs.setdefault("htmlFor", control_id)

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes off the element.

        Returns:
            The props read as styles, and the ones the field hands down.
        """
        return [*super()._exclude_props(), "name", "server_invalid"]

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the field, its script included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        if (
            self.server_invalid is not None
            and literal(self.server_invalid) is not False
        ):
            yield _FOCUS_INVALID

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the field.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, marked as the field of the messages inside it, and as
            invalid when the server says so.
        """
        tag = super()._render(props).add_props(**{"data-rx-form-field": ""})
        invalid = self.server_invalid
        if invalid is None or literal(invalid) is False:
            return tag
        flag = (
            ""
            if literal(invalid) is True
            else Var(
                f'({invalid!s} ? "" : undefined)',
                _var_data=invalid._get_all_var_data(),
            )
        )
        # A ref that is new when the server finds the field invalid, so that
        # React calls it then: the control takes the focus, as in Radix.
        focus = (
            _FOCUS_INVALID
            if literal(invalid) is True
            else Var(
                f"({invalid!s} ? {_FOCUS_INVALID!s} : undefined)",
                _var_data=VarData.merge(
                    invalid._get_all_var_data(), _FOCUS_INVALID._get_all_var_data()
                ),
            )
        )
        return tag.add_props(
            ref=focus, **{"data-invalid": flag, "data-server-invalid": flag}
        )


class FormLabel(UIComponent):
    """A form label component."""

    tag = "label"

    styles: ClassVar[ComponentStyles] = FORM_LABEL

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child."
    )

    def _set_slot(self) -> None:
        """Render the label itself."""


class FormControl(UIComponent):
    """A form control component."""

    tag = "input"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child."
    )

    name: Var[str] = field(
        doc="The name of the control, in place of the name of the enclosing form field."
    )

    # Named by the field around it, which points its labels at it.
    _is_field_control: ClassVar[bool] = True

    @classmethod
    def create(cls, *children, **props):
        """Create a Form Control component.

        The control renders an input, or the native form control its child
        renders, which then takes the enclosing form field's name and
        validation messages.

        Args:
            *children: The control to render, if any.
            **props: The properties of the form control.

        Returns:
            The form control component.

        Raises:
            ValueError: If more than one child is given.
            TypeError: If the child does not render a native form control.
        """
        if len(children) > 1:
            msg = f"FormControl can only have at most one child, got {len(children)} children"
            raise ValueError(msg)
        for child in children:
            if not isinstance(child, _FORM_CONTROL_CHILD_TYPES):
                msg = (
                    "The child of rx.ui.form.control must render a native form "
                    "control: rx.ui.input, rx.ui.text_area, rx.debounce_input, "
                    "rx.el.input, rx.el.select or rx.el.textarea, not "
                    f"{type(child).__name__}. Give other controls such as "
                    "rx.ui.checkbox or rx.ui.select a `name` and place them "
                    "under rx.ui.form.root or rx.ui.form.field instead."
                )
                raise TypeError(msg)
            # The child is the control: what the field gives a control goes
            # to the native element it renders.
            native = _native(child)
            native._is_field_control = True  # pyright: ignore[reportAttributeAccessIssue]
            name = props.get("name")
            if name is not None:
                _give(native, "name", LiteralVar.create(name))
            return child
        return super().create(**props)

    def _set_slot(self) -> None:
        """Render the input itself: a child is returned in its place."""


LiteralMatcher = Literal[
    "badInput",
    "patternMismatch",
    "rangeOverflow",
    "rangeUnderflow",
    "stepMismatch",
    "tooLong",
    "tooShort",
    "typeMismatch",
    "valid",
    "valueMissing",
]


class FormMessage(UIComponent):
    """A form message component."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = FORM_MESSAGE

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child."
    )

    name: Var[str] = field(
        doc="Used to target a specific field by name when rendering outside of a Field part."
    )

    match: Var[LiteralMatcher] = field(
        doc="Used to indicate on which condition the message should be visible."
    )

    force_match: Var[bool] = field(
        doc="Forces the message to be shown. This is useful when using server-side validation."
    )

    def _set_slot(self) -> None:
        """Render the message itself."""

    def _exclude_props(self) -> list[str]:
        """Keep the props that are rendered as data off the element.

        Returns:
            The props read as styles, and the ones of the message.
        """
        return [*super()._exclude_props(), "name", "match", "force_match"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the message.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag. A message with a condition is hidden until its script
            finds that the condition holds, or it is forced to show.
        """
        tag = super()._render(props).add_props(**{"data-rx-form-message": ""})
        if self.name is not None:
            tag = tag.add_props(**{"data-name": self.name})
        if self.match is None:
            return tag
        tag = tag.add_props(**{"data-match": self.match})
        force = self.force_match
        if force is None or literal(force) is False:
            return tag.add_props(hidden=True)
        if literal(force) is True:
            return tag.add_props(**{"data-force": ""})
        var_data = force._get_all_var_data()
        return tag.add_props(
            hidden=Var(f"!({force!s})", _var_type=bool, _var_data=var_data),
            **{"data-force": Var(f'({force!s} ? "" : undefined)', _var_data=var_data)},
        )


class FormValidityState(UIComponent):
    """A form validity state component."""

    tag = "span"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child."
    )

    def _set_slot(self) -> None:
        """Render the element itself."""


class FormSubmit(UIComponent):
    """A form submit component."""

    tag = "button"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child."
    )

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the button that submits the form.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, or the child rendered in its place, with the type of a
            submit button.
        """
        return super()._render(props).add_props(type="submit")


# This class is created mainly for reflex-web docs.
class Form(FormRoot):
    """The Form component."""


class FormNamespace(ComponentNamespace):
    """Form components."""

    # Stubbed as a class so ``rx.ui.form.FormData`` works in type annotations.
    _stub_as_class: ClassVar[bool] = True

    root = staticmethod(FormRoot.create)
    control = staticmethod(FormControl.create)
    field = staticmethod(FormField.create)
    label = staticmethod(FormLabel.create)
    message = staticmethod(FormMessage.create)
    submit = staticmethod(FormSubmit.create)
    validity_state = staticmethod(FormValidityState.create)
    FormData = _FormData
    __call__ = staticmethod(Form.create)


form = FormNamespace()
