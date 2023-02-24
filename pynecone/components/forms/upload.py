"""A file upload component."""

from pynecone.components.component import Component
from pynecone.components.forms.input import Input
from pynecone.event import EventChain
from pynecone.var import BaseVar, Var


upload_file = BaseVar(name="e => File(e)", type_=EventChain)


class Upload(Input):
    """A file upload component."""

    # The type of input.
    type_: Var[str] = "file"  # type: ignore

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an upload component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The upload component.
        """
        return super().create(*children, **props, on_change=upload_file)