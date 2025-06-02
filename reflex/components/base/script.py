"""Next.js script wrappers and inline script functionality.

https://nextjs.org/docs/app/api-reference/components/script
"""

from __future__ import annotations

from typing import Literal

from reflex.components.component import Component
from reflex.event import EventHandler, no_args_event_spec
from reflex.vars.base import LiteralVar, Var


class Script(Component):
    """Next.js script component.

    Note that this component differs from reflex.components.base.document.NextScript
    in that it is intended for use with custom and user-defined scripts.

    It also differs from reflex.components.base.link.ScriptTag, which is the plain
    HTML <script> tag which does not work when rendering a component.
    """

    library = "next/script"
    tag = "Script"
    is_default = True

    # Required unless inline script is used
    src: Var[str]

    # When the script will execute: afterInteractive (defer-like behavior) | beforeInteractive | lazyOnload (async-like behavior)
    strategy: Var[Literal["afterInteractive", "beforeInteractive", "lazyOnload"]] = (
        LiteralVar.create("afterInteractive")
    )

    # Triggered when the script is loading
    on_load: EventHandler[no_args_event_spec]

    # Triggered when the script has loaded
    on_ready: EventHandler[no_args_event_spec]

    # Triggered when the script has errored
    on_error: EventHandler[no_args_event_spec]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an inline or user-defined script.

        If a string is provided as the first child, it will be rendered as an inline script
        otherwise the `src` prop must be provided.

        The following event triggers are provided:

        on_load: Execute code after the script has finished loading.
        on_ready: Execute code after the script has finished loading and every
            time the component is mounted.
        on_error: Execute code if the script fails to load.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.

        Raises:
            ValueError: when neither children nor `src` are specified.
        """
        if not children and not props.get("src"):
            msg = "Must provide inline script or `src` prop."
            raise ValueError(msg)
        return super().create(*children, **props)


script = Script.create
