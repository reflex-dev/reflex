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
    """A component that creates a script tag with the speacified type and source."""

    type: Var[str]

    source: Var[str]

    integrity: Optional[Var[str]] = None

    crossorigin: Optional[Var[str]] = None

    referrer_policy: Optional[Var[str]] = None

    is_async: Optional[Var[bool]] = None
    
    defer: Optional[Var[bool]] = None



    def _render(self) -> Tag:
        return Tag(name="script").add_props(
            src=            self.source,
            type=           self.type,
            defer=          "defer" if self.defer else "",
            async_=          "async" if self.is_async else "", #Using _ as a postfix  as to avoid using reserved word
            integrity=      self.integrity,
            crossOrigin=    self.crossorigin,
            referrerPolicy= self.referrer_policy,
        )
