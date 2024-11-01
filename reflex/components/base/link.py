"""Display the title of the current page."""

from reflex.components.component import Component
from reflex.vars.base import Var


class RawLink(Component):
    """A component that displays the title of the current page."""

    tag = "link"

    # The href.
    href: Var[str]

    # The type of link.
    rel: Var[str]


class ScriptTag(Component):
    """A script tag with the specified type and source."""

    tag = "script"

    # The type of script represented.
    type_: Var[str]

    # The URI of an external script.
    source: Var[str]

    # Metadata to verify the content of the script.
    integrity: Var[str]

    # Whether to allow cross-origin requests.
    crossorigin: Var[str]

    # Indicates which referrer to send when fetching the script.
    referrer_policy: Var[str]

    # Whether to asynchronously load the script.
    is_async: Var[bool]

    # Whether to defer loading the script.
    defer: Var[bool]
