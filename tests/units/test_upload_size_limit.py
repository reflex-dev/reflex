"""Tests for upload file size limit enforcement in the upload handler."""

import io
import unittest.mock
from unittest.mock import AsyncMock, patch

import pytest
import reflex as rx
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.responses import JSONResponse

from reflex.app import upload

# Use a small limit for tests to avoid allocating large buffers.
_TEST_MAX_SIZE = 500  # 500 bytes
_TEST_MAX_FILES = 2


def _make_upload_file(filename: str, content: bytes, *, report_size: bool = True):
    """Create a StarletteUploadFile with given content."""
    file = StarletteUploadFile(filename=filename, file=io.BytesIO(content))
    file.size = len(content) if report_size else None
    return file


_SENTINEL = object()


def _make_request_mock(files, content_length=_SENTINEL):
    """Create a mock Starlette Request with the given files.

    Args:
        files: List of upload files.
        content_length: If provided, set as the raw content-length header value.
            Pass an int for valid values, or a raw string (e.g. "", "  ", "abc")
            to test malformed header handling. Omit to leave the header unset.
    """
    request_mock = unittest.mock.Mock()
    headers = {
        "reflex-client-token": "test-token",
        "reflex-event-handler": "fake_state.handle_upload",
    }
    if content_length is not _SENTINEL:
        headers["content-length"] = str(content_length) if isinstance(content_length, int) else content_length
    request_mock.headers = headers

    async def form():  # noqa: RUF029
        files_mock = unittest.mock.Mock()
        files_mock.getlist = lambda key: files
        return files_mock

    request_mock.form = form
    return request_mock


def _mock_config(upload_max_size=_TEST_MAX_SIZE, upload_max_files=_TEST_MAX_FILES):
    """Create a mock config with given upload limits."""
    config = unittest.mock.Mock()
    config.upload_max_size = upload_max_size
    config.upload_max_files = upload_max_files
    return config


class _FakeState:
    """A minimal fake state that has a handle_upload method with correct annotations."""

    def handle_upload(self, files: list[rx.UploadFile]):
        pass

    def get_substate(self, path):
        return self


def _make_app_mock():
    """Create a mock app whose state manager returns a _FakeState."""
    app_mock = unittest.mock.Mock()
    app_mock.state_manager.get_state = AsyncMock(return_value=_FakeState())
    return app_mock


# --- Config default tests ---


def test_default_upload_max_size():
    """Default upload_max_size should be 10 MB."""
    from reflex.config import get_config

    config = get_config()
    assert config.upload_max_size == 10 * 1024 * 1024


def test_default_upload_max_files():
    """Default upload_max_files should be 10."""
    from reflex.config import get_config

    config = get_config()
    assert config.upload_max_files == 10


def test_negative_upload_max_size_rejected():
    """Negative upload_max_size should raise ConfigError."""
    from reflex.config import Config
    from reflex.utils.exceptions import ConfigError

    with pytest.raises(ConfigError, match="upload_max_size must be >= 0"):
        Config(app_name="test", upload_max_size=-1, _skip_plugins_checks=True)


def test_negative_upload_max_files_rejected():
    """Negative upload_max_files should raise ConfigError."""
    from reflex.config import Config
    from reflex.utils.exceptions import ConfigError

    with pytest.raises(ConfigError, match="upload_max_files must be >= 0"):
        Config(app_name="test", upload_max_files=-1, _skip_plugins_checks=True)


# --- Content-Length pre-check tests ---


@pytest.mark.asyncio
async def test_content_length_over_limit_rejected():
    """Request with Content-Length exceeding total limit is rejected before form parsing."""
    app_mock = unittest.mock.Mock()
    max_request_size = _TEST_MAX_SIZE * _TEST_MAX_FILES

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock([], content_length=max_request_size + 1)
        response = await upload_fn(request)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_content_length_under_limit_passes_precheck():
    """Request with Content-Length under the total limit passes the pre-check."""
    small_file = _make_upload_file("ok.txt", b"x" * 100)
    app_mock = _make_app_mock()

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock([small_file], content_length=100)
        response = await upload_fn(request)

    # Content-Length is under the limit, file is small — should reach
    # the streaming response (event processing), not a 413.
    assert not isinstance(response, JSONResponse) or response.status_code != 413


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_value",
    ["not-a-number", "", "   ", "12.5", "1e3"],
    ids=["text", "empty", "whitespace", "float", "scientific"],
)
async def test_malformed_content_length_returns_400(bad_value):
    """Non-integer Content-Length header returns 400 Bad Request."""
    app_mock = unittest.mock.Mock()

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock([], content_length=bad_value)
        response = await upload_fn(request)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 400


# --- Per-file size enforcement tests ---


@pytest.mark.asyncio
async def test_file_over_limit_rejected_413():
    """Oversized file is rejected with HTTP 413 by the upload handler."""
    oversized = _make_upload_file("big.bin", b"x" * (_TEST_MAX_SIZE + 1))
    app_mock = _make_app_mock()

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock([oversized])
        response = await upload_fn(request)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_file_over_limit_rejected_by_chunked_read():
    """File with size=None but content over limit is rejected during chunked read."""
    oversized_no_size = _make_upload_file(
        "big.bin", b"x" * (_TEST_MAX_SIZE + 1), report_size=False
    )
    app_mock = _make_app_mock()

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock([oversized_no_size])
        response = await upload_fn(request)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_file_under_limit_not_rejected():
    """File under the limit passes the size enforcement and reaches event processing."""
    small = _make_upload_file("ok.txt", b"x" * 100)
    app_mock = _make_app_mock()

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock([small])
        response = await upload_fn(request)

    # Handler should proceed past size checks to event processing.
    # It returns a StreamingResponse on success, never a 413 JSONResponse.
    assert not isinstance(response, JSONResponse) or response.status_code != 413


# --- Max files tests ---


@pytest.mark.asyncio
async def test_too_many_files_rejected_with_400():
    """Uploading more files than upload_max_files is rejected with 400."""
    files = [
        _make_upload_file(f"file{i}.txt", b"x" * 10)
        for i in range(_TEST_MAX_FILES + 1)
    ]
    app_mock = unittest.mock.Mock()

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock(files)
        response = await upload_fn(request)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_files_within_limit_not_rejected_for_count():
    """Uploading files within upload_max_files passes the count check."""
    files = [
        _make_upload_file(f"file{i}.txt", b"x" * 10) for i in range(_TEST_MAX_FILES)
    ]
    app_mock = _make_app_mock()

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock(files)
        response = await upload_fn(request)

    # Should not be rejected for file count — reaches event processing.
    assert not isinstance(response, JSONResponse) or response.status_code not in (400, 413)


# --- Limit disabled tests ---


@pytest.mark.asyncio
async def test_size_limit_disabled_allows_large_file():
    """When upload_max_size=0, large files are not rejected for size."""
    large = _make_upload_file("big.bin", b"x" * 1000)
    app_mock = _make_app_mock()

    with patch(
        "reflex.app.get_config",
        return_value=_mock_config(upload_max_size=0, upload_max_files=0),
    ):
        upload_fn = upload(app_mock)
        request = _make_request_mock([large])
        response = await upload_fn(request)

    # With limits disabled, should never get a 413.
    assert not isinstance(response, JSONResponse) or response.status_code != 413


# --- Filename sanitization test ---


@pytest.mark.asyncio
async def test_error_message_does_not_contain_filename():
    """413 error message should not echo back the attacker-controlled filename."""
    evil_name = "<script>alert('xss')</script>.bin"
    oversized = _make_upload_file(evil_name, b"x" * (_TEST_MAX_SIZE + 1))
    app_mock = _make_app_mock()

    with patch("reflex.app.get_config", return_value=_mock_config()):
        upload_fn = upload(app_mock)
        request = _make_request_mock([oversized])
        response = await upload_fn(request)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 413
    body = response.body.decode()
    assert evil_name not in body
