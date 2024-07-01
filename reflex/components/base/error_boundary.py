"""A React Error Boundary component that catches unhandled frontend exceptions."""

from typing import Any, Dict, Union

from reflex.compiler.compiler import _compile_component
from reflex.components.component import Component
from reflex.components.el import div, p
from reflex.components.tags import Tag
from reflex.constants import EventTriggers, Hooks
from reflex.vars import Var


class ErrorBoundary(Component):
    """A React Error Boundary component that catches unhandled frontend exceptions."""

    library = "react-error-boundary"
    tag = "ErrorBoundary"

    def _render(self, props: Union[Dict[str, Any], None] = None) -> Tag:
        """Define how to render the component in React.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag to render.

        """
        # Create the base tag.
        tag = Tag(
            name=self.tag if not self.alias else self.alias,
            special_props=self.special_props,
        )

        if props is None:
            # Add component props to the tag.
            props = {
                attr[:-1] if attr.endswith("_") else attr: getattr(self, attr)
                for attr in self.get_props()
            }

            # Add ref to element if `id` is not None.
            ref = self.get_ref()
            if ref is not None:
                props["ref"] = Var.create(
                    ref, _var_is_local=False, _var_is_string=False
                )
        else:
            props = props.copy()

        props.update(
            **{
                trigger: handler
                for trigger, handler in self.event_triggers.items()
                if trigger not in {EventTriggers.ON_MOUNT, EventTriggers.ON_UNMOUNT}
            },
            key=self.key,
            id=self.id,
            class_name=self.class_name,
        )
        props.update(self._get_style())
        props.update(self.custom_attrs)

        # remove excluded props from prop dict before adding to tag.
        for prop_to_exclude in self._exclude_props():
            props.pop(prop_to_exclude, None)

        props["onError"] = Var.create_safe(
            "logFrontendError", _var_is_string=False, _var_is_local=False
        )
        props["FallbackComponent"] = Var.create_safe(
            "Fallback", _var_is_string=False, _var_is_local=False
        )

        return tag.add_props(**props)

    def _get_events_hooks(self) -> Dict[str, None]:
        """Get the hooks required by events referenced in this component.

        Returns:
            The hooks for the events.
        """
        return {Hooks.FRONTEND_ERRORS: None}

    def add_custom_code(self) -> list[str]:
        """Add custom Javascript code into the page that contains this component.

        Custom code is inserted at module level, after any imports.

        Returns:
            The custom code to add.
        """
        fallback_container = div(
            p("Ooops...Unknown Reflex error has occured:"),
            p(
                Var.create("error.message", _var_is_local=False, _var_is_string=False),
                color_scheme="red",
            ),
            p("Please contact the support."),
        )

        compiled_fallback = _compile_component(fallback_container)

        return [
            f"""
                function Fallback({{ error, resetErrorBoundary }}) {{
                    return (
                        {compiled_fallback}
                    );
                }}
            """
        ]


error_boundary = ErrorBoundary.create
