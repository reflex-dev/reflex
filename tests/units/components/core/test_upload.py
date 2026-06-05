import json
from typing import Any, cast
from urllib.parse import quote

import pytest
from reflex_base.event import EventChain, EventHandler, EventSpec, parse_args_spec
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.core._upload import _extra_upload_args
from reflex_components_core.core.upload import (
    GhostUpload,
    StyledUpload,
    Upload,
    UploadNamespace,
    _on_drop_spec,  # pyright: ignore [reportAttributeAccessIssue]
    cancel_upload,
    get_upload_url,
)
from starlette.exceptions import HTTPException
from starlette.requests import Request

import reflex as rx
from reflex import event
from reflex.state import State


class UploadStateTest(State):
    """Test upload state."""

    @event
    def drop_handler(self, files: Any):
        """Handle the drop event.

        Args:
            files: The files dropped.
        """

    @event
    def not_drop_handler(self, not_files: Any):
        """Handle the drop event without defining the files argument.

        Args:
            not_files: The files dropped.
        """

    @event
    async def upload_alias_handler(self, uploads: list[rx.UploadFile]):
        """Handle uploaded files with a non-default parameter name."""

    @event
    async def upload_with_field(self, files: list[rx.UploadFile], field: str):
        """Handle uploaded files for a specific field."""

    @event
    async def upload_with_reserved_arg(
        self, files: list[rx.UploadFile], upload_id: str
    ):
        """Handle uploaded files with a bound arg that shadows a reserved key."""


class StreamingUploadStateTest(State):
    """Test state for streaming uploads."""

    @event(background=True)
    async def chunk_drop_handler(self, chunk_iter: rx.UploadChunkIterator):
        """Handle streamed upload chunks."""

    @event(background=True)
    async def chunk_upload_alias_handler(self, stream: rx.UploadChunkIterator):
        """Handle streamed upload chunks with a non-default parameter name."""

    async def chunk_drop_handler_not_background(
        self, chunk_iter: rx.UploadChunkIterator
    ):
        """Invalid handler used to validate background-task requirement."""

    @event(background=True)
    async def chunk_drop_handler_missing_annotation(self, chunk_iter):
        """Invalid handler missing the UploadChunkIterator annotation."""


def test_cancel_upload():
    spec = cancel_upload("foo_id")
    assert isinstance(spec, EventSpec)


def test_get_upload_url():
    url = get_upload_url("foo_file")
    assert isinstance(url, Var)


def test__on_drop_spec():
    assert isinstance(_on_drop_spec(LiteralVar.create([])), tuple)


@pytest.mark.parametrize("component", [Upload, GhostUpload])
def test_on_drop_rejected_uses_file_rejection_payload_spec(component):
    rejected_spec = component.get_event_triggers()["on_drop_rejected"]
    placeholders, _ = parse_args_spec(rejected_spec)

    assert placeholders[0]._var_type == list[dict[str, Any]]


def test_upload_files_chunk_requires_background():
    with pytest.raises(TypeError) as err:
        event.resolve_upload_chunk_handler_param(
            cast(
                EventHandler, StreamingUploadStateTest.chunk_drop_handler_not_background
            )
        )

    assert (
        err.value.args[0]
        == "@rx.event(background=True) is required for upload_files_chunk handler "
        f"`{StreamingUploadStateTest.get_full_name()}.chunk_drop_handler_not_background`."
    )


def test_upload_files_chunk_requires_iterator_annotation():
    with pytest.raises(ValueError) as err:
        event.resolve_upload_chunk_handler_param(
            cast(
                EventHandler,
                StreamingUploadStateTest.chunk_drop_handler_missing_annotation,
            )
        )

    assert (
        err.value.args[0]
        == f"`{StreamingUploadStateTest.get_full_name()}.chunk_drop_handler_missing_annotation` "
        "handler should have a parameter annotated as rx.UploadChunkIterator"
    )


def test_upload_create():
    up_comp_1 = Upload.create()
    assert isinstance(up_comp_1, Upload)
    assert up_comp_1.is_used

    # reset is_used
    Upload.is_used = False

    up_comp_2 = Upload.create(
        id="foo_id",
        on_drop=UploadStateTest.drop_handler([]),
    )
    assert isinstance(up_comp_2, Upload)
    assert up_comp_2.is_used

    # reset is_used
    Upload.is_used = False

    up_comp_3 = Upload.create(
        id="foo_id",
        on_drop=UploadStateTest.drop_handler,
    )
    assert isinstance(up_comp_3, Upload)
    assert up_comp_3.is_used

    # reset is_used
    Upload.is_used = False

    up_comp_4 = Upload.create(
        id="foo_id",
        on_drop=UploadStateTest.not_drop_handler([]),
    )
    assert isinstance(up_comp_4, Upload)
    assert up_comp_4.is_used

    # reset is_used
    Upload.is_used = False

    up_comp_5 = Upload.create(
        id="foo_id",
        on_drop=StreamingUploadStateTest.chunk_drop_handler(
            rx.upload_files_chunk(upload_id="foo_id")  # pyright: ignore[reportArgumentType]
        ),
    )
    assert isinstance(up_comp_5, Upload)
    assert up_comp_5.is_used

    up_comp_6 = Upload.create(
        id="foo_id",
        on_drop=StreamingUploadStateTest.chunk_upload_alias_handler(
            rx.upload_files_chunk(upload_id="foo_id")  # pyright: ignore[reportArgumentType]
        ),
    )
    assert isinstance(up_comp_6, Upload)
    assert up_comp_6.is_used


def test_upload_button_handlers_allow_custom_param_names():
    legacy_button = rx.button(
        "Upload",
        on_click=UploadStateTest.upload_alias_handler(
            cast(Any, rx.upload_files(upload_id="foo_id"))
        ),
    )
    legacy_chain = cast(EventChain, legacy_button.event_triggers["on_click"])
    legacy_event = cast(EventSpec, legacy_chain.events[0])
    legacy_arg_names = [arg[0]._js_expr for arg in legacy_event.args]
    assert legacy_event.client_handler_name == "uploadFiles"
    assert legacy_arg_names[:3] == ["files", "uploads", "upload_param_name"]

    chunk_button = rx.button(
        "Upload",
        on_click=StreamingUploadStateTest.chunk_upload_alias_handler(
            rx.upload_files_chunk(upload_id="foo_id")  # pyright: ignore[reportArgumentType]
        ),
    )
    chunk_chain = cast(EventChain, chunk_button.event_triggers["on_click"])
    chunk_event = cast(EventSpec, chunk_chain.events[0])
    chunk_arg_names = [arg[0]._js_expr for arg in chunk_event.args]
    assert chunk_event.client_handler_name == "uploadFiles"
    assert chunk_arg_names[:3] == ["files", "stream", "upload_param_name"]


def test_upload_files_event_spec_carries_upload_provider_app_wrap():
    """Upload button event specs carry UploadFilesProvider through VarData."""
    button = rx.button(
        "Upload",
        on_click=UploadStateTest.drop_handler(
            cast(Any, rx.upload_files(upload_id="foo_id"))
        ),
    )
    chain = cast(EventChain, button.event_triggers["on_click"])
    upload_event = cast(EventSpec, chain.events[0])

    var_data = VarData.merge(
        *(arg_value._get_all_var_data() for _, arg_value in upload_event.args)
    )

    assert var_data is not None
    assert any(
        priority == 5 and wrapper.tag == "UploadFilesProvider"
        for priority, wrapper in var_data.app_wraps
    )


# Matches UPLOAD_EVENT_ARG_NAMES_KEY in reflex_base.event and the web template.
# The constant isn't part of the module's public import surface (event/__init__.py
# proxies attribute access through EventNamespace), so it's mirrored here.
UPLOAD_EVENT_ARG_NAMES_KEY = "__reflex_event_arg_names"


def test_upload_files_preserves_bound_event_args():
    field = Var(_js_expr="field", _var_type=str)
    spec = cast(
        EventSpec,
        UploadStateTest.upload_with_field(
            cast(Any, rx.upload_files(upload_id="foo_id")),
            cast(Any, field),
        ),
    )
    arg_values = {arg[0]._js_expr: arg[1]._js_expr for arg in spec.args}

    # The bound arg stays a flat payload entry (keyed by its param name) and is
    # advertised in the manifest so the client knows to forward it.
    assert arg_values["field"] == "field"
    assert "field" in arg_values[UPLOAD_EVENT_ARG_NAMES_KEY]
    assert isinstance(Upload.create(id="foo_id", on_drop=spec), Upload)


def test_upload_files_multiple_upload_args_raises():
    from reflex_base.utils.exceptions import EventHandlerTypeError

    with pytest.raises(EventHandlerTypeError, match="multiple file upload arguments"):
        UploadStateTest.upload_with_field(
            cast(Any, rx.upload_files(upload_id="foo_id")),
            cast(Any, rx.upload_files(upload_id="bar_id")),
        )


def test_upload_files_bound_arg_reserved_name_raises():
    """A bound arg sharing a reserved upload key name is rejected at build time."""
    from reflex_base.utils.exceptions import EventHandlerTypeError

    with pytest.raises(EventHandlerTypeError, match="reserved upload argument"):
        UploadStateTest.upload_with_reserved_arg(
            cast(Any, rx.upload_files(upload_id="foo_id")),
            cast(Any, Var(_js_expr="some_id", _var_type=str)),
        )


@pytest.fixture
def upload_request():
    """Build an upload request carrying a given reflex-event-args header value.

    Returns:
        A factory taking the header value (or ``None`` to omit the header).
    """

    def _build(header_value: str | None) -> Request:
        headers = (
            [(b"reflex-event-args", header_value.encode())]
            if header_value is not None
            else []
        )
        return Request({"type": "http", "headers": headers})

    return _build


def test_extra_upload_args_decodes_json_object(upload_request):
    request = upload_request(quote(json.dumps({"field": "value"})))
    assert _extra_upload_args(request) == {"field": "value"}


def test_extra_upload_args_missing_header_returns_empty(upload_request):
    assert _extra_upload_args(upload_request(None)) == {}
    assert _extra_upload_args(upload_request("")) == {}


@pytest.mark.parametrize(
    "header_value",
    [quote("[1, 2, 3]"), quote('"foo"'), quote("42"), quote("null")],
)
def test_extra_upload_args_non_object_raises(upload_request, header_value):
    """A header encoding valid JSON that is not an object is a bad request."""
    with pytest.raises(HTTPException) as exc_info:
        _extra_upload_args(upload_request(header_value))
    assert exc_info.value.status_code == 400


def test_extra_upload_args_malformed_json_raises(upload_request):
    """A header that is not valid JSON is a bad request, not a 500."""
    with pytest.raises(HTTPException) as exc_info:
        _extra_upload_args(upload_request(quote("{not json")))
    assert exc_info.value.status_code == 400


def test_styled_upload_create():
    styled_up_comp_1 = StyledUpload.create()
    assert isinstance(styled_up_comp_1, StyledUpload)
    assert styled_up_comp_1.is_used

    # reset is_used
    StyledUpload.is_used = False

    styled_up_comp_2 = StyledUpload.create(
        id="foo_id",
        on_drop=UploadStateTest.drop_handler([]),
    )
    assert isinstance(styled_up_comp_2, StyledUpload)
    assert styled_up_comp_2.is_used

    # reset is_used
    StyledUpload.is_used = False

    styled_up_comp_3 = StyledUpload.create(
        id="foo_id",
        on_drop=UploadStateTest.drop_handler,
    )
    assert isinstance(styled_up_comp_3, StyledUpload)
    assert styled_up_comp_3.is_used

    # reset is_used
    StyledUpload.is_used = False

    styled_up_comp_4 = StyledUpload.create(
        id="foo_id",
        on_drop=UploadStateTest.not_drop_handler([]),
    )
    assert isinstance(styled_up_comp_4, StyledUpload)
    assert styled_up_comp_4.is_used


def test_upload_namespace():
    up_ns = UploadNamespace()
    assert isinstance(up_ns, UploadNamespace)

    assert isinstance(up_ns(id="foo_id"), StyledUpload)
    assert isinstance(up_ns.root(id="foo_id"), Upload)
