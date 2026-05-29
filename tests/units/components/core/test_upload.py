from typing import Any, cast

import pytest
from reflex_base.event import EventChain, EventHandler, EventSpec, parse_args_spec
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.core.upload import (
    GhostUpload,
    StyledUpload,
    Upload,
    UploadNamespace,
    _on_drop_spec,
    cancel_upload,
    get_upload_url,
)

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
            rx.upload_files_chunk(upload_id="foo_id")
        ),
    )
    assert isinstance(up_comp_5, Upload)
    assert up_comp_5.is_used

    up_comp_6 = Upload.create(
        id="foo_id",
        on_drop=StreamingUploadStateTest.chunk_upload_alias_handler(
            rx.upload_files_chunk(upload_id="foo_id")
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
            rx.upload_files_chunk(upload_id="foo_id")
        ),
    )
    chunk_chain = cast(EventChain, chunk_button.event_triggers["on_click"])
    chunk_event = cast(EventSpec, chunk_chain.events[0])
    chunk_arg_names = [arg[0]._js_expr for arg in chunk_event.args]
    assert chunk_event.client_handler_name == "uploadFiles"
    assert chunk_arg_names[:3] == ["files", "stream", "upload_param_name"]


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
