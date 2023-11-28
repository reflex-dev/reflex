"""Form components."""
from __future__ import annotations

from hashlib import md5
from typing import Any, Dict, Iterator

from jinja2 import Environment

from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent
from reflex.components.tags import Tag
from reflex.constants import Dirs, EventTriggers
from reflex.event import EventChain
from reflex.utils import imports
from reflex.utils.format import format_event_chain, to_camel_case
from reflex.vars import BaseVar, Var

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


class Form(ChakraComponent):
    """A form component."""

    tag = "Box"

    # What the form renders to.
    as_: Var[str] = "form"  # type: ignore

    # If true, the form will be cleared after submit.
    reset_on_submit: Var[bool] = False  # type: ignore

    # The name used to make this form's submit handler function unique
    handle_submit_unique_name: Var[str]

    @classmethod
    def create(cls, *children, **props) -> Component:
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
        code_hash = md5(str(form.get_hooks()).encode("utf-8")).hexdigest()
        form.handle_submit_unique_name = code_hash
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

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_SUBMIT: lambda e0: [FORM_DATA],
        }

    def _get_vars(self) -> Iterator[Var]:
        yield from super()._get_vars()
        yield from self._get_form_refs().values()


class FormControl(ChakraComponent):
    """Provide context to form components."""

    tag = "FormControl"

    # If true, the form control will be disabled.
    is_disabled: Var[bool]

    # If true, the form control will be invalid.
    is_invalid: Var[bool]

    # If true, the form control will be readonly
    is_read_only: Var[bool]

    # If true, the form control will be required.
    is_required: Var[bool]

    # The label text used to inform users as to what information is requested for a text field.
    label: Var[str]

    @classmethod
    def create(
        cls,
        *children,
        label=None,
        input=None,
        help_text=None,
        error_message=None,
        **props,
    ) -> Component:
        """Create a form control component.

        Args:
            *children: The children of the form control.
            label: The label of the form control.
            input: The input of the form control.
            help_text: The help text of the form control.
            error_message: The error message of the form control.
            **props: The properties of the form control.

        Raises:
            AttributeError: raise an error if missing required kwargs.

        Returns:
            The form control component.
        """
        if len(children) == 0:
            children = []

            if label:
                children.append(FormLabel.create(*label))

            if not input:
                raise AttributeError("input keyword argument is required")
            children.append(input)

            if help_text:
                children.append(FormHelperText.create(*help_text))

            if error_message:
                children.append(FormErrorMessage.create(*error_message))

        return super().create(*children, **props)


class FormHelperText(ChakraComponent):
    """A form helper text component."""

    tag = "FormHelperText"


class FormLabel(ChakraComponent):
    """A form label component."""

    tag = "FormLabel"

    # Link
    html_for: Var[str]


class FormErrorMessage(ChakraComponent):
    """A form error message component."""

    tag = "FormErrorMessage"
