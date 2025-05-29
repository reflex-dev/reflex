from typing import Any

from reflex import event
from reflex.components.core.upload import (
    StyledUpload,
    Upload,
    UploadNamespace,
    _on_drop_spec,  # pyright: ignore [reportAttributeAccessIssue]
    cancel_upload,
    get_upload_url,
)
from reflex.event import EventSpec
from reflex.state import State
from reflex.vars.base import LiteralVar, Var


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


def test_cancel_upload():
    spec = cancel_upload("foo_id")
    assert isinstance(spec, EventSpec)


def test_get_upload_url():
    url = get_upload_url("foo_file")
    assert isinstance(url, Var)


def test__on_drop_spec():
    assert isinstance(_on_drop_spec(LiteralVar.create([])), tuple)


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
