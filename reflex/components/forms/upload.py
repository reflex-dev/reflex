"""A file upload component."""

from typing import Dict, List, Optional

from reflex.components.component import EVENT_ARG, Component
from reflex.components.forms.input import Input
from reflex.components.layout.box import Box
from reflex.event import EventChain
from reflex.vars import BaseVar, Var

upload_file = BaseVar(name="e => File(e)", type_=EventChain)


class Upload(Component):
    """A file upload component."""

    library = "react-dropzone"

    tag = "ReactDropzone"

    is_default = True

    # The list of accepted file types. This should be a dictionary of MIME types as keys and array of file formats as
    # values.
    # supported MIME types: https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
    accept: Var[Optional[Dict[str, List]]]

    # Whether the dropzone is disabled.
    disabled: Var[bool]

    # The maximum number of files that can be uploaded.
    max_files: Var[int]

    # The maximum file size (bytes) that can be uploaded.
    max_size: Var[int]

    # The minimum file size (bytes) that can be uploaded.
    min_size: Var[int]

    # Whether to allow multiple files to be uploaded.
    multiple: Var[bool] = True  # type: ignore

    # Whether to disable click to upload.
    no_click: Var[bool]

    # Whether to disable drag and drop.
    no_drag: Var[bool]

    # Whether to disable using the space/enter keys to upload.
    no_keyboard: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an upload component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The upload component.
        """
        # get only upload component props
        supported_props = cls.get_props()
        upload_props = {
            key: value for key, value in props.items() if key in supported_props
        }
        # The file input to use.
        upload = Input.create(type_="file")
        upload.special_props = {BaseVar(name="{...getInputProps()}", type_=None)}

        # The dropzone to use.
        zone = Box.create(
            upload,
            *children,
            **{k: v for k, v in props.items() if k not in supported_props}
        )
        zone.special_props = {BaseVar(name="{...getRootProps()}", type_=None)}

        # Create the component.
        return super().create(zone, on_drop=upload_file, **upload_props)

    def get_controlled_triggers(self) -> Dict[str, Var]:
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
