"""Display the title of the current page."""

from reflex.components.component import Component
from reflex.ivars.base import ImmutableVar


class RawLink(Component):
    """A component that displays the title of the current page."""

    tag = "link"

    # The href.
    href: ImmutableVar[str]

    # The type of link.
    rel: ImmutableVar[str]


class ScriptTag(Component):
    """A script tag with the specified type and source."""

    tag = "script"

    # The type of script represented.
    type_: ImmutableVar[str]

    # The URI of an external script.
    source: ImmutableVar[str]

    # Metadata to verify the content of the script.
    integrity: ImmutableVar[str]

    # Whether to allow cross-origin requests.
    crossorigin: ImmutableVar[str]

    # Indicates which referrer to send when fetching the script.
    referrer_policy: ImmutableVar[str]

    # Whether to asynchronously load the script.
    is_async: ImmutableVar[bool]

    # Whether to defer loading the script.
    defer: ImmutableVar[bool]
