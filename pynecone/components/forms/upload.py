"""A file upload component."""

from typing import Dict

from pynecone.components.component import EVENT_ARG, Component
from pynecone.components.forms.input import Input
from pynecone.components.layout.box import Box
from pynecone.event import EventChain
from pynecone.var import BaseVar, Var

upload_file = BaseVar(name="e => File(e)", type_=EventChain)


class Upload(Component):
    """A file upload component."""

    library = "react-dropzone"

    tag = "ReactDropzone"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an upload component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The upload component.
        """
        # The file input to use.
        upload = Input.create(type_="file")
        upload.special_props = {BaseVar(name="{...getInputProps()}", type_=None)}

        # The dropzone to use.
        zone = Box.create(upload, *children, **props)
        zone.special_props = {BaseVar(name="{...getRootProps()}", type_=None)}

        # Create the component.
        return super().create(zone, on_drop=upload_file)

    @classmethod
    def get_controlled_triggers(cls) -> Dict[str, Var]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            "on_drop": EVENT_ARG,
        }

    def _render(self):
        out = super()._render()
        out.args = ("getRootProps", "getInputProps")
        return out
