"""Display the title of the current page."""
from typing import Optional

from reflex.components.component import Component
from reflex.vars import Var


class RawLink(Component):
    """A component that displays the title of the current page."""

    tag: str = "link"

    # The href.
    href: Optional[Var[str]] = None

    # The type of link.
    rel: Optional[Var[str]] = None


class ScriptTag(Component):
    """A script tag with the specified type and source."""

    tag: str = "script"

    # The type of script represented.
    type_: Optional[Var[str]] = None

    # The URI of an external script.
    source: Optional[Var[str]] = None

    # Metadata to verify the content of the script.
    integrity: Optional[Var[str]] = None

    # Whether to allow cross-origin requests.
    crossorigin: Optional[Var[str]] = None

    # Indicates which referrer to send when fetching the script.
    referrer_policy: Optional[Var[str]] = None

    # Whether to asynchronously load the script.
    is_async: Optional[Var[bool]] = None

    # Whether to defer loading the script.
    defer: Optional[Var[bool]] = None
