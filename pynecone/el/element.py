from pynecone import utils
from pynecone.components.component import Component


class Element(Component):
    def render(self) -> str:
        """Render the component.

        Returns:
            The code to render the component.
        """
        tag = self._render()
        return str(
            tag.add_props(
                **self.event_triggers,
                key=self.key,
                id=self.id,
                style=self.style,
                class_name=self.class_name,
            ).set(
                contents=utils.join(
                    [str(tag.contents)] + [child.render() for child in self.children]
                ).strip(),
            )
        )

    def __eq__(self, other):
        return isinstance(other, Element) and self.tag == other.tag
