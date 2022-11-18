"""Display the title of the current page."""

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
