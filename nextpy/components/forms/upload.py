"""A file upload component."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from nextpy.components.component import Component
from nextpy.components.forms.input import Input
from nextpy.components.layout.box import Box
from nextpy.constants import EventTriggers
from nextpy.core.event import EventChain
from nextpy.core.vars import BaseVar, Var

files_state: str = "const [files, setFiles] = useState([]);"
upload_file: BaseVar = BaseVar(
    _var_name="e => setFiles((files) => e)", _var_type=EventChain
)

# Use this var along with the Upload component to render the list of selected files.
selected_files: BaseVar = BaseVar(
    _var_name="files.map((f) => f.name)", _var_type=List[str]
)

clear_selected_files: BaseVar = BaseVar(
    _var_name="_e => setFiles((files) => [])", _var_type=EventChain
)


class Upload(Component):
    """A file upload component."""

    library = "react-dropzone@14.2.3"

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
            *children: The children of the component.
            **props: The properties of the component.

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
        upload.special_props = {
            BaseVar(_var_name="{...getInputProps()}", _var_type=None)
        }

        # The dropzone to use.
        zone = Box.create(
            upload,
            *children,
            **{k: v for k, v in props.items() if k not in supported_props},
        )
        zone.special_props = {BaseVar(_var_name="{...getRootProps()}", _var_type=None)}

        # Create the component.
        return super().create(zone, on_drop=upload_file, **upload_props)

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_DROP: lambda e0: [e0],
        }

    def _render(self):
        out = super()._render()
        out.args = ("getRootProps", "getInputProps")
        return out

    def _get_hooks(self) -> str | None:
        return (super()._get_hooks() or "") + files_state
