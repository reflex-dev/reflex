"""Radix form component."""

from __future__ import annotations

from hashlib import md5
from typing import Any, Dict, Iterator, Literal

from jinja2 import Environment

from reflex.components.component import Component, ComponentNamespace
from reflex.components.radix.themes.components.text_field import TextFieldInput
from reflex.components.tags.tag import Tag
from reflex.constants.base import Dirs
from reflex.constants.event import EventTriggers
from reflex.event import EventChain
from reflex.utils import imports
from reflex.utils.format import format_event_chain, to_camel_case
from reflex.vars import BaseVar, Var

from .base import RadixPrimitiveComponentWithClassName

FORM_DATA = Var.create("form_data")
HANDLE_SUBMIT_JS_JINJA2 = Environment().from_string(
    """
    const handleSubmit_{{ handle_submit_unique_name }} = useCallback((ev) => {
        const $form = ev.target
        ev.preventDefault()
        const {{ form_data }} = {...Object.fromEntries(new FormData($form).entries()), ...{{ field_ref_mapping }}}

        {{ on_submit_event_chain }}

        if ({{ reset_on_submit }}) {
            $form.reset()
        }
    })
    """
)


class FormComponent(RadixPrimitiveComponentWithClassName):
    """Base class for all @radix-ui/react-form components."""

    library = "@radix-ui/react-form@^0.0.3"


class FormRoot(FormComponent):
    """The root component of a radix form."""

    tag = "Root"

    alias = "RadixFormRoot"

    # If true, the form will be cleared after submit.
    reset_on_submit: Var[bool] = False  # type: ignore

    # The name used to make this form's submit handler function unique.
    handle_submit_unique_name: Var[str]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Event triggers for radix form root.

        Returns:
            The triggers for event supported by Root.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_SUBMIT: lambda e0: [FORM_DATA],
            EventTriggers.ON_CLEAR_SERVER_ERRORS: lambda: [],
        }

    @classmethod
    def create(cls, *children, **props):
        """Create a form component.

        Args:
            *children: The children of the form.
            **props: The properties of the form.

        Returns:
            The form component.
        """
        if "handle_submit_unique_name" in props:
            return super().create(*children, **props)

        # Render the form hooks and use the hash of the resulting code to create a unique name.
        props["handle_submit_unique_name"] = ""
        form = super().create(*children, **props)
        form.handle_submit_unique_name = md5(
            str(form.get_hooks()).encode("utf-8")
        ).hexdigest()
        return form

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            {
                "react": {imports.ImportVar(tag="useCallback")},
                f"/{Dirs.STATE_PATH}": {
                    imports.ImportVar(tag="getRefValue"),
                    imports.ImportVar(tag="getRefValues"),
                },
            },
        )

    def _get_hooks(self) -> str | None:
        if EventTriggers.ON_SUBMIT not in self.event_triggers:
            return
        return HANDLE_SUBMIT_JS_JINJA2.render(
            handle_submit_unique_name=self.handle_submit_unique_name,
            form_data=FORM_DATA,
            field_ref_mapping=str(Var.create_safe(self._get_form_refs())),
            on_submit_event_chain=format_event_chain(
                self.event_triggers[EventTriggers.ON_SUBMIT]
            ),
            reset_on_submit=self.reset_on_submit,
        )

    def _render(self) -> Tag:
        render_tag = (
            super()
            ._render()
            .remove_props(
                "reset_on_submit",
                "handle_submit_unique_name",
                to_camel_case(EventTriggers.ON_SUBMIT),
            )
        )
        if EventTriggers.ON_SUBMIT in self.event_triggers:
            render_tag.add_props(
                **{
                    EventTriggers.ON_SUBMIT: BaseVar(
                        _var_name=f"handleSubmit_{self.handle_submit_unique_name}",
                        _var_type=EventChain,
                    )
                }
            )
        return render_tag

    def _get_form_refs(self) -> Dict[str, Any]:
        # Send all the input refs to the handler.
        form_refs = {}
        for ref in self.get_refs():
            # when ref start with refs_ it's an array of refs, so we need different method
            # to collect data
            if ref.startswith("refs_"):
                ref_var = Var.create_safe(ref[:-3]).as_ref()
                form_refs[ref[5:-3]] = Var.create_safe(
                    f"getRefValues({str(ref_var)})", _var_is_local=False
                )._replace(merge_var_data=ref_var._var_data)
            else:
                ref_var = Var.create_safe(ref).as_ref()
                form_refs[ref[4:]] = Var.create_safe(
                    f"getRefValue({str(ref_var)})", _var_is_local=False
                )._replace(merge_var_data=ref_var._var_data)
        return form_refs

    def _apply_theme(self, theme: Component):
        return {
            "width": "260px",
            **self.style,
        }

    def _get_vars(self) -> Iterator[Var]:
        yield from super()._get_vars()
        yield from self._get_form_refs().values()


class FormField(FormComponent):
    """A form field component."""

    tag = "Field"

    alias = "RadixFormField"

    # The name of the form field, that is passed down to the control and used to match with validation messages.
    name: Var[str]

    # Flag to mark the form field as invalid, for server side validation.
    server_invalid: Var[bool]

    def _apply_theme(self, theme: Component):
        return {
            "display": "grid",
            "margin_bottom": "10px",
            **self.style,
        }


class FormLabel(FormComponent):
    """A form label component."""

    tag = "Label"

    alias = "RadixFormLabel"

    def _apply_theme(self, theme: Component):
        return {
            "font_size": "15px",
            "font_weight": "500",
            "line_height": "35px",
            **self.style,
        }


class FormControl(FormComponent):
    """A form control component."""

    tag = "Control"

    alias = "RadixFormControl"

    @classmethod
    def create(cls, *children, **props):
        """Create a Form Control component.

        Args:
            *children: The children of the form.
            **props: The properties of the form.

        Raises:
            ValueError: If the number of children is greater than 1.
            TypeError: If a child exists but it is not a TextFieldInput.

        Returns:
            The form control component.
        """
        if len(children) > 1:
            raise ValueError(
                f"FormControl can only have at most one child, got {len(children)} children"
            )
        for child in children:
            if not isinstance(child, TextFieldInput):
                raise TypeError(
                    "Only Radix TextFieldInput is allowed as child of FormControl"
                )
        return super().create(*children, **props)


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


class FormMessage(FormComponent):
    """A form message component."""

    tag = "Message"

    alias = "RadixFormMessage"

    # Used to target a specific field by name when rendering outside of a Field part.
    name: Var[str]

    # Used to indicate on which condition the message should be visible.
    match: Var[LiteralMatcher]

    # Forces the message to be shown. This is useful when using server-side validation.
    force_match: Var[bool]

    def _apply_theme(self, theme: Component):
        return {
            "font_size": "13px",
            "opacity": "0.8",
            "color": "white",
            **self.style,
        }


class FormValidityState(FormComponent):
    """A form validity state component."""

    tag = "ValidityState"
    alias = "RadixFormValidityState"


class FormSubmit(FormComponent):
    """A form submit component."""

    tag = "Submit"
    alias = "RadixFormSubmit"


# This class is created mainly for reflex-web docs.
class Form(FormRoot):
    """The Form component."""

    pass


class FormNamespace(ComponentNamespace):
    """Form components."""

    root = staticmethod(FormRoot.create)
    control = staticmethod(FormControl.create)
    field = staticmethod(FormField.create)
    label = staticmethod(FormLabel.create)
    message = staticmethod(FormMessage.create)
    submit = staticmethod(FormSubmit.create)
    validity_state = staticmethod(FormValidityState.create)
    __call__ = staticmethod(Form.create)


form = FormNamespace()
