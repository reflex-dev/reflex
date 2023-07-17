"""Next.js script wrappers and inline script functionality.

https://nextjs.org/docs/app/api-reference/components/script
"""
from typing import Optional, Set

from reflex.components.component import Component
from reflex.event import EventHandler
from reflex.vars import Var


class Script(Component):
    """Next.js script component.

    Note that this component differs from reflex.components.base.document.Script
    in that it is intended for use with custom and user-defined scripts.
    """

    library = "next/script"
    tag = "Script"
    is_default = True

    # Required unless inline script is used
    src: Optional[Var[str]] = None

    # When the script will execute: afterInteractive | beforeInteractive | lazyOnload
    strategy: Var[str] = "afterInteractive"  # type: ignore

    # Execute code after the script has finished loading.
    on_load: Optional[EventHandler] = None

    # Execute code after the script has finished loading and every time the component is mounted.
    on_ready: Optional[EventHandler] = None

    # Execute code if the script fails to load.
    on_error: Optional[EventHandler] = None

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an inline or user-defined script.

        If a string is provided as the first child, it will be rendered as an inline script
        otherwise the `src` prop must be provided.

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

    def get_triggers(self) -> Set[str]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return super().get_triggers() | {"on_load", "on_ready", "on_error"}
