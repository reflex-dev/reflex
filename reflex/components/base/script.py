"""Next.js script wrappers and inline script functionality.

https://nextjs.org/docs/app/api-reference/components/script
"""

from __future__ import annotations

from typing import Literal, Union

from reflex.components.component import Component
from reflex.event import EventHandler
from reflex.vars import Var

REFERRAL_POLICY_LITERAL = Literal[
    "",
    "no-referrer",
    "no-referrer-when-downgrade",
    "origin",
    "origin-when-cross-origin",
    "same-origin",
    "strict-origin",
    "strict-origin-when-cross-origin",
    "unsafe-url",
]


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
        Var.create_safe("afterInteractive", _var_is_string=True)
    )
    # Indicates the type of script represented
    type: Var[str]

    # Specifies if the script(and dependencies for module scripts) will be fetched in parallel to parsing and evaluated as soon as available
    async_: Var[bool]

    # Indicate to a browser that the script is meant to be executed after the document has been parsed, but before firing DOMContentLoaded event
    defer: Var[bool]
    # Contains inline metadata that a user agent can use to verify that a fetched resource has been delivered without unexpected manipulation
    integrity: Var[str]

    # Sets the mode of the request to an HTTP CORS Request.
    crossorigin: Var[str]

    # Provides a hint of the relative priority to use when fetching an external script.
    fetchpriority: Var[Literal["high", "low", "auto"]]
    #  indicate that the script should not be executed in browsers that support ES modules.
    nomodule: Var[bool]

    # Indicates which referrer to send when fetching the script, or resources fetched by the script
    referrerpolicy: Var[REFERRAL_POLICY_LITERAL]

    # Specifies that you want the browser to send an Attribution-Reporting-Eligible header along with the script resource request.
    attributionsrc: Var[Union[str, bool]]

    # Explicitly indicates that certain operations should be blocked on the fetching of the script
    blocking: Var[str]
    # Triggered when the script is loading
    on_load: EventHandler[lambda: []]

    # Triggered when the script has loaded
    on_ready: EventHandler[lambda: []]

    # Triggered when the script has errored
    on_error: EventHandler[lambda: []]

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
            raise ValueError("Must provide inline script or `src` prop.")
        return super().create(*children, **props)


script = Script.create
