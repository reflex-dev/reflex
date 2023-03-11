"""Display the title of the current page."""

from typing import Optional

from pynecone.components.component import Component
from pynecone.components.tags import Tag
from pynecone.var import Var


class Link(Component):
    """A component that displays the title of the current page."""

    # The href.
    href: Var[str]

    # The type of link.
    rel: Var[str]

    def _render(self) -> Tag:
        return Tag(name="link").add_props(
            href=self.href,
            rel=self.rel,
        )


class ScriptTag(Component):
    """A component that creates a script tag with the speacified type and source.


    Args:
        type: This attribute indicates the type of script represented.
            The value of this attribute will be one of the following:

            - module: This value causes the code to be treated as a JavaScript module.
            - importmap: This value indicates that the body of the element
                contains an import map.
            - Any value: The embedded content is treated as a data block, and won't be
                processed by the browser.
            - blocking: This attribute explicitly indicates that certain operations
                should be blocked on the fetching of the script.

        source: This attribute specifies the URI of an external script; this can be
            used as an alternative to embedding a script directly within a document.

        integrity: This attribute contains inline metadata that a user agent can use
            to verify that a fetched resource has been delivered free of unexpected manipulation

        crossorigin: To allow error logging for sites which use a separate domain for static media,
            use this attribute.

        referrer_policy: Indicates which referrer to send when fetching the script, or resources fetched by the script
            refrence: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/script#:~:text=Indicates%20which%20referrer%20to%20send%20when%20fetching%20the%20script%2C%20or%20resources%20fetched%20by%20the%20script%3A

        is_async: This attribute allows the elimination of parser-blocking JavaScript where the browser would have to
            load and evaluate scripts before continuing to parse. defer has a similar effect in this case.

        defer: This Boolean attribute is set to indicate to a browser that the script is
            meant to be executed after the document has been parsed, but before firing DOMContentLoaded.

    """

    tag = "script"

    type: Var[str]

    source: Var[str]

    integrity: Optional[Var[str]]

    crossorigin: Optional[Var[str]]

    referrer_policy: Optional[Var[str]]

    is_async: Optional[Var[bool]]

    defer: Optional[Var[bool]]
