"""A file upload component."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from reflex.components.base.fragment import Fragment
from reflex.components.component import (
    Component,
    ComponentNamespace,
    MemoizationLeaf,
    StatefulComponent,
)
from reflex.components.el.elements.forms import Input
from reflex.components.radix.themes.layout.box import Box
from reflex.config import environment
from reflex.constants import Dirs
from reflex.constants.compiler import Hooks, Imports
from reflex.event import (
    CallableEventSpec,
    EventChain,
    EventHandler,
    EventSpec,
    call_event_fn,
    parse_args_spec,
    run_script,
)
from reflex.utils import format
from reflex.utils.imports import ImportVar
from reflex.vars import VarData
from reflex.vars.base import Var, get_unique_variable_name
from reflex.vars.sequence import LiteralStringVar

DEFAULT_UPLOAD_ID: str = "default"

upload_files_context_var_data: VarData = VarData(
    imports={
        "react": "useContext",
        f"$/{Dirs.CONTEXTS_PATH}": "UploadFilesContext",
    },
    hooks={
        "const [filesById, setFilesById] = useContext(UploadFilesContext);": None,
    },
)


def upload_file(id_: str = DEFAULT_UPLOAD_ID) -> Var:
    """Get the file upload drop trigger.

    This var is passed to the dropzone component to update the file list when a
    drop occurs.

    Args:
        id_: The id of the upload to get the drop trigger for.

    Returns:
        A var referencing the file upload drop trigger.
    """
    id_var = LiteralStringVar.create(id_)
    var_name = f"""e => setFilesById(filesById => {{
    const updatedFilesById = Object.assign({{}}, filesById);
    updatedFilesById[{id_var!s}] = e;
    return updatedFilesById;
  }})
    """

    return Var(
        _js_expr=var_name,
        _var_type=EventChain,
        _var_data=VarData.merge(
            upload_files_context_var_data, id_var._get_all_var_data()
        ),
    )


def selected_files(id_: str = DEFAULT_UPLOAD_ID) -> Var:
    """Get the list of selected files.

    Args:
        id_: The id of the upload to get the selected files for.

    Returns:
        A var referencing the list of selected file paths.
    """
    id_var = LiteralStringVar.create(id_)
    return Var(
        _js_expr=f"(filesById[{id_var!s}] ? filesById[{id_var!s}].map((f) => (f.path || f.name)) : [])",
        _var_type=List[str],
        _var_data=VarData.merge(
            upload_files_context_var_data, id_var._get_all_var_data()
        ),
    ).guess_type()


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
    # component via `run_script` (otherwise backend could never clear files).
    func = Var("__clear_selected_files")._as_ref()
    return run_script(f"{func}({id_!r})")


def cancel_upload(upload_id: str) -> EventSpec:
    """Cancel an upload.

    Args:
        upload_id: The id of the upload to cancel.

    Returns:
        An event spec that cancels the upload when triggered.
    """
    controller = Var(f"__upload_controllers_{upload_id}")._as_ref()
    return run_script(f"{controller}?.abort()")


def get_upload_dir() -> Path:
    """Get the directory where uploaded files are stored.

    Returns:
        The directory where uploaded files are stored.
    """
    Upload.is_used = True

    uploaded_files_dir = environment.REFLEX_UPLOADED_FILES_DIR.get()
    uploaded_files_dir.mkdir(parents=True, exist_ok=True)
    return uploaded_files_dir


uploaded_files_url_prefix = Var(
    _js_expr="getBackendURL(env.UPLOAD)",
    _var_data=VarData(
        imports={
            f"$/{Dirs.STATE_PATH}": "getBackendURL",
            "$/env.json": ImportVar(tag="env", is_default=True),
        }
    ),
).to(str)


def get_upload_url(file_path: str | Var[str]) -> Var[str]:
    """Get the URL of an uploaded file.

    Args:
        file_path: The path of the uploaded file.

    Returns:
        The URL of the uploaded file to be rendered from the frontend (as a str-encoded Var).
    """
    Upload.is_used = True

    return Var.create(f"{uploaded_files_url_prefix}/{file_path}")


def _on_drop_spec(files: Var) -> Tuple[Var[Any]]:
    """Args spec for the on_drop event trigger.

    Args:
        files: The files to upload.

    Returns:
        Signature for on_drop handler including the files to upload.
    """
    return (files,)


class UploadFilesProvider(Component):
    """AppWrap component that provides a dict of selected files by ID via useContext."""

    library = f"$/{Dirs.CONTEXTS_PATH}"
    tag = "UploadFilesProvider"


class GhostUpload(Fragment):
    """A ghost upload component."""

    # Fired when files are dropped.
    on_drop: EventHandler[_on_drop_spec]


class Upload(MemoizationLeaf):
    """A file upload component."""

    library = "react-dropzone@14.3.5"

    tag = ""

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
    multiple: Var[bool]

    # Whether to disable click to upload.
    no_click: Var[bool]

    # Whether to disable drag and drop.
    no_drag: Var[bool]

    # Whether to disable using the space/enter keys to upload.
    no_keyboard: Var[bool]

    # Marked True when any Upload component is created.
    is_used: ClassVar[bool] = False

    # Fired when files are dropped.
    on_drop: EventHandler[_on_drop_spec]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an upload component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The upload component.
        """
        # Mark the Upload component as used in the app.
        cls.is_used = True

        props.setdefault("multiple", True)

        # Apply the default classname
        given_class_name = props.pop("class_name", [])
        if isinstance(given_class_name, str):
            given_class_name = [given_class_name]
        props["class_name"] = ["rx-Upload", *given_class_name]

        # get only upload component props
        supported_props = cls.get_props().union({"on_drop"})
        upload_props = {
            key: value for key, value in props.items() if key in supported_props
        }

        # Create the component.
        upload_props["id"] = props.get("id", DEFAULT_UPLOAD_ID)

        if upload_props.get("on_drop") is None:
            # If on_drop is not provided, save files to be uploaded later.
            upload_props["on_drop"] = upload_file(upload_props["id"])
        else:
            on_drop = upload_props["on_drop"]
            if isinstance(on_drop, Callable):
                # Call the lambda to get the event chain.
                on_drop = call_event_fn(on_drop, _on_drop_spec)
            if isinstance(on_drop, EventSpec):
                # Update the provided args for direct use with on_drop.
                on_drop = on_drop.with_args(
                    args=tuple(
                        cls._update_arg_tuple_for_on_drop(arg_value)
                        for arg_value in on_drop.args
                    ),
                )
            upload_props["on_drop"] = on_drop

        input_props_unique_name = get_unique_variable_name()
        root_props_unique_name = get_unique_variable_name()

        event_var, callback_str = StatefulComponent._get_memoized_event_triggers(
            GhostUpload.create(on_drop=upload_props["on_drop"])
        )["on_drop"]

        upload_props["on_drop"] = event_var

        upload_props = {
            format.to_camel_case(key): value for key, value in upload_props.items()
        }

        use_dropzone_arguments = Var.create(
            {
                "onDrop": event_var,
                **upload_props,
            }
        )

        left_side = f"const {{getRootProps: {root_props_unique_name}, getInputProps: {input_props_unique_name}}} "
        right_side = f"useDropzone({use_dropzone_arguments!s})"

        var_data = VarData.merge(
            VarData(
                imports=Imports.EVENTS,
                hooks={Hooks.EVENTS: None},
            ),
            event_var._get_all_var_data(),
            use_dropzone_arguments._get_all_var_data(),
            VarData(
                hooks={
                    callback_str: None,
                    f"{left_side} = {right_side};": None,
                },
                imports={
                    "react-dropzone": "useDropzone",
                    **Imports.EVENTS,
                },
            ),
        )

        # The file input to use.
        upload = Input.create(type="file")
        upload.special_props = [
            Var(
                _js_expr=f"{{...{input_props_unique_name}()}}",
                _var_type=None,
                _var_data=var_data,
            )
        ]

        # The dropzone to use.
        zone = Box.create(
            upload,
            *children,
            **{k: v for k, v in props.items() if k not in supported_props},
        )
        zone.special_props = [
            Var(
                _js_expr=f"{{...{root_props_unique_name}()}}",
                _var_type=None,
                _var_data=var_data,
            )
        ]

        return super().create(
            zone,
        )

    @classmethod
    def _update_arg_tuple_for_on_drop(cls, arg_value: tuple[Var, Var]):
        """Helper to update caller-provided EventSpec args for direct use with on_drop.

        Args:
            arg_value: The arg tuple to update (if necessary).

        Returns:
            The updated arg_value tuple when arg is "files", otherwise the original arg_value.
        """
        if arg_value[0]._js_expr == "files":
            placeholder = parse_args_spec(_on_drop_spec)[0]
            return (arg_value[0], placeholder)
        return arg_value

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        return {
            (5, "UploadFilesProvider"): UploadFilesProvider.create(),
        }


class StyledUpload(Upload):
    """The styled Upload Component."""

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the styled upload component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The styled upload component.
        """
        # Set default props.
        props.setdefault("border", "1px dashed var(--accent-12)")
        props.setdefault("padding", "5em")
        props.setdefault("textAlign", "center")

        # Mark the Upload component as used in the app.
        Upload.is_used = True

        return super().create(
            *children,
            **props,
        )


class UploadNamespace(ComponentNamespace):
    """Upload component namespace."""

    root = Upload.create
    __call__ = StyledUpload.create


upload = UploadNamespace()
