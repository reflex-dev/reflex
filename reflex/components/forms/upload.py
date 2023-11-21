"""A file upload component."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from reflex import constants
from reflex.components.component import Component
from reflex.components.forms.input import Input
from reflex.components.layout.box import Box
from reflex.constants import Dirs
from reflex.event import CallableEventSpec, EventChain, EventSpec, call_script
from reflex.utils import imports
from reflex.vars import BaseVar, CallableVar, Var, VarData

DEFAULT_UPLOAD_ID: str = "default"

upload_files_context_var_data: VarData = VarData(  # type: ignore
    imports={
        "react": {imports.ImportVar(tag="useContext")},
        f"/{Dirs.CONTEXTS_PATH}": {
            imports.ImportVar(tag="UploadFilesContext"),
        },
    },
    hooks={
        "const [filesById, setFilesById] = useContext(UploadFilesContext);",
    },
)


@CallableVar
def upload_file(id_: str = DEFAULT_UPLOAD_ID) -> BaseVar:
    """Get the file upload drop trigger.

    This var is passed to the dropzone component to update the file list when a
    drop occurs.

    Args:
        id_: The id of the upload to get the drop trigger for.

    Returns:
        A var referencing the file upload drop trigger.
    """
    return BaseVar(
        _var_name=f"e => setFilesById(filesById => ({{...filesById, {id_}: e}}))",
        _var_type=EventChain,
        _var_data=upload_files_context_var_data,
    )


@CallableVar
def selected_files(id_: str = DEFAULT_UPLOAD_ID) -> BaseVar:
    """Get the list of selected files.

    Args:
        id_: The id of the upload to get the selected files for.

    Returns:
        A var referencing the list of selected file paths.
    """
    return BaseVar(
        _var_name=f"(filesById.{id_} ? filesById.{id_}.map((f) => (f.path || f.name)) : [])",
        _var_type=List[str],
        _var_data=upload_files_context_var_data,
    )


@CallableEventSpec
def clear_selected_files(id_: str = DEFAULT_UPLOAD_ID) -> EventSpec:
    """Clear the list of selected files.

    Args:
        id_: The id of the upload to clear.

    Returns:
        An event spec that clears the list of selected files when triggered.
    """
    # UploadFilesProvider assigns a special function to clear selected files
    # into the shared global refs object to make it accessible outside a React
    # component via `call_script` (otherwise backend could never clear files).
    return call_script(f"refs['__clear_selected_files']({id_!r})")


def cancel_upload(upload_id: str) -> EventSpec:
    """Cancel an upload.

    Args:
        upload_id: The id of the upload to cancel.

    Returns:
        An event spec that cancels the upload when triggered.
    """
    return call_script(f"upload_controllers[{upload_id!r}]?.abort()")


class UploadFilesProvider(Component):
    """AppWrap component that provides a dict of selected files by ID via useContext."""

    library = f"/{Dirs.CONTEXTS_PATH}"
    tag = "UploadFilesProvider"


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
        upload_props["id"] = props.get("id", DEFAULT_UPLOAD_ID)
        return super().create(
            zone, on_drop=upload_file(upload_props["id"]), **upload_props
        )

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            constants.EventTriggers.ON_DROP: lambda e0: [e0],
        }

    def _render(self):
        out = super()._render()
        out.args = ("getRootProps", "getInputProps")
        return out

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {
            (5, "UploadFilesProvider"): UploadFilesProvider(),
        }
