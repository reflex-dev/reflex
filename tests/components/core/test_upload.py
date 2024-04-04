from reflex.components.core.upload import (
    Upload,
    _on_drop_spec,  # type: ignore
    cancel_upload,
    get_upload_url,
)
from reflex.event import EventSpec
from reflex.state import State
from reflex.vars import Var


class TestUploadState(State):
    """Test upload state."""

    def drop_handler(self, files):
        """Handle the drop event.

        Args:
            files: The files dropped.
        """
        pass

    def not_drop_handler(self, not_files):
        """Handle the drop event without defining the files argument.

        Args:
            not_files: The files dropped.
        """
        pass


def test_cancel_upload():
    spec = cancel_upload("foo_id")
    assert isinstance(spec, EventSpec)


def test_get_upload_url():
    url = get_upload_url("foo_file")
    assert isinstance(url, Var)


def test__on_drop_spec():
    assert isinstance(_on_drop_spec(Var.create([])), list)


def test_upload_create():
    up_comp_1 = Upload.create()
    assert isinstance(up_comp_1, Upload)
    assert up_comp_1.is_used

    # reset is_used
    Upload.is_used = False

    up_comp_2 = Upload.create(
        id="foo_id",
        on_drop=TestUploadState.drop_handler([]),  # type: ignore
    )
    assert isinstance(up_comp_2, Upload)
    assert up_comp_2.is_used

    # reset is_used
    Upload.is_used = False

    up_comp_3 = Upload.create(
        id="foo_id",
        on_drop=TestUploadState.drop_handler,
    )
    assert isinstance(up_comp_3, Upload)
    assert up_comp_3.is_used

    # reset is_used
    Upload.is_used = False

    up_comp_4 = Upload.create(
        id="foo_id",
        on_drop=TestUploadState.not_drop_handler([]),  # type: ignore
    )
    assert isinstance(up_comp_4, Upload)
    assert up_comp_4.is_used
