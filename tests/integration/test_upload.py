"""Integration tests for file upload."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page, expect
from reflex_base.constants.event import Endpoint

import reflex as rx
from reflex.testing import AppHarness

from . import utils


def UploadFile():
    """App for testing dynamic routes."""
    import shutil

    import reflex as rx

    LARGE_DATA = "DUMMY" * 1024 * 512

    class UploadState(rx.State):
        upload_done: rx.Field[bool] = rx.field(False)
        event_order: rx.Field[list[str]] = rx.field([])
        progress_dicts: rx.Field[list[dict]] = rx.field([])
        stream_progress_dicts: rx.Field[list[dict]] = rx.field([])
        disabled: rx.Field[bool] = rx.field(False)
        large_data: rx.Field[str] = rx.field("")
        quaternary_names: rx.Field[list[str]] = rx.field([])
        stream_chunk_records: rx.Field[list[str]] = rx.field([])
        stream_completed_files: rx.Field[list[str]] = rx.field([])

        @rx.event
        async def handle_upload(self, files: list[rx.UploadFile]):
            self.upload_done = False
            for file in files:
                upload_data = await file.read()
                if not file.name:
                    continue
                local_file = rx.get_upload_dir() / file.name
                local_file.parent.mkdir(parents=True, exist_ok=True)
                local_file.write_bytes(upload_data)
            self.upload_done = True

        @rx.event
        async def handle_upload_secondary(self, files: list[rx.UploadFile]):
            self.upload_done = False
            for file in files:
                upload_data = await file.read()
                if not file.name:
                    continue
                local_file = rx.get_upload_dir() / file.name
                local_file.parent.mkdir(parents=True, exist_ok=True)
                local_file.write_bytes(upload_data)
                self.large_data = LARGE_DATA
                yield UploadState.chain_event

        @rx.event
        def upload_progress(self, progress):
            assert progress
            print(self.event_order)
            self.progress_dicts.append(progress)

        @rx.event
        def chain_event(self):
            assert self.large_data == LARGE_DATA
            self.large_data = ""
            self.upload_done = True
            self.event_order.append("chain_event")
            print(self.event_order)

        @rx.event
        def stream_upload_progress(self, progress):
            assert progress
            self.stream_progress_dicts.append(progress)

        @rx.event
        async def handle_upload_tertiary(self, files: list[rx.UploadFile]):
            self.upload_done = False
            for file in files:
                (rx.get_upload_dir() / (file.name or "INVALID")).write_bytes(
                    await file.read()
                )
            self.upload_done = True

        @rx.event
        async def handle_upload_quaternary(self, files: list[rx.UploadFile]):
            self.upload_done = False
            self.quaternary_names = [file.name for file in files if file.name]
            self.upload_done = True

        @rx.event(background=True)
        async def handle_upload_stream(self, chunk_iter: rx.UploadChunkIterator):
            async with self:
                self.upload_done = False
            upload_dir = rx.get_upload_dir() / "streaming"
            file_handles: dict[str, Any] = {}

            try:
                async for chunk in chunk_iter:
                    path = upload_dir / chunk.filename
                    path.parent.mkdir(parents=True, exist_ok=True)

                    fh = file_handles.get(chunk.filename)
                    if fh is None:
                        fh = path.open("r+b") if path.exists() else path.open("wb")
                        file_handles[chunk.filename] = fh

                    fh.seek(chunk.offset)
                    fh.write(chunk.data)

                    async with self:
                        self.stream_chunk_records.append(
                            f"{chunk.filename}:{chunk.offset}:{len(chunk.data)}"
                        )
            finally:
                for fh in file_handles.values():
                    fh.close()

            async with self:
                self.stream_completed_files = sorted(file_handles)
                self.upload_done = True

        @rx.event
        def do_download(self):
            return rx.download(rx.get_upload_url("test.txt"))

        @rx.event
        def clear_uploads(self):
            shutil.rmtree(rx.get_upload_dir(), ignore_errors=True)
            self.reset()

    def index():
        return rx.vstack(
            rx.input(
                value=UploadState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.input(
                value=UploadState.upload_done.to_string(),
                read_only=True,
                id="upload_done",
            ),
            rx.button(
                "Clear Uploaded Files",
                id="clear_uploads",
                on_click=UploadState.clear_uploads,
            ),
            rx.heading("Default Upload"),
            rx.upload.root(
                rx.vstack(
                    rx.button("Select File"),
                    rx.text("Drag and drop files here or click to select files"),
                ),
                disabled=UploadState.disabled,
            ),
            rx.button(
                "Upload",
                on_click=lambda: UploadState.handle_upload(rx.upload_files()),  # pyright: ignore [reportArgumentType]
                id="upload_button",
            ),
            rx.box(
                rx.foreach(
                    rx.selected_files(),
                    lambda f: rx.text(f, as_="p"),
                ),
                id="selected_files",
            ),
            rx.button(
                "Clear",
                on_click=rx.clear_selected_files,
                id="clear_button",
            ),
            rx.heading("Secondary Upload"),
            rx.upload.root(
                rx.vstack(
                    rx.button("Select File"),
                    rx.text("Drag and drop files here or click to select files"),
                ),
                id="secondary",
            ),
            rx.button(
                "Upload",
                on_click=UploadState.handle_upload_secondary(
                    rx.upload_files(  # pyright: ignore [reportArgumentType]
                        upload_id="secondary",
                        on_upload_progress=UploadState.upload_progress,
                    ),
                ),
                id="upload_button_secondary",
            ),
            rx.box(
                rx.foreach(
                    rx.selected_files("secondary"),
                    lambda f: rx.text(f, as_="p"),
                ),
                id="selected_files_secondary",
            ),
            rx.button(
                "Clear",
                on_click=rx.clear_selected_files("secondary"),
                id="clear_button_secondary",
            ),
            rx.vstack(
                rx.foreach(
                    UploadState.progress_dicts,
                    lambda d: rx.text(d.to_string()),
                ),
                id="progress_dicts",
            ),
            rx.button(
                "Cancel",
                on_click=rx.cancel_upload("secondary"),
                id="cancel_button_secondary",
            ),
            rx.heading("Tertiary Upload/Download"),
            rx.upload.root(
                rx.vstack(
                    rx.button("Select File"),
                    rx.text("Drag and drop files here or click to select files"),
                ),
                id="tertiary",
            ),
            rx.button(
                "Upload",
                on_click=UploadState.handle_upload_tertiary(
                    rx.upload_files(  # pyright: ignore [reportArgumentType]
                        upload_id="tertiary",
                    ),
                ),
                id="upload_button_tertiary",
            ),
            rx.button(
                "Download - Frontend",
                on_click=rx.download(rx.get_upload_url("test.txt")),
                id="download-frontend",
            ),
            rx.button(
                "Download - Backend",
                on_click=UploadState.do_download,
                id="download-backend",
            ),
            rx.upload.root(
                rx.vstack(
                    rx.button("Select File"),
                    rx.text("Drag and drop files here or click to select files"),
                ),
                on_drop=UploadState.handle_upload_quaternary(
                    rx.upload_files(  # pyright: ignore [reportArgumentType]
                        upload_id="quaternary",
                    ),
                ),
                id="quaternary",
            ),
            rx.text(
                UploadState.quaternary_names.to_string(),
                id="quaternary_files",
            ),
            rx.heading("Streaming Upload"),
            rx.upload.root(
                rx.vstack(
                    rx.button("Select File"),
                    rx.text("Drag and drop files here or click to select files"),
                ),
                id="streaming",
            ),
            rx.button(
                "Upload",
                on_click=UploadState.handle_upload_stream(
                    rx.upload_files_chunk(  # pyright: ignore [reportArgumentType]
                        upload_id="streaming",
                        on_upload_progress=UploadState.stream_upload_progress,
                    )
                ),
                id="upload_button_streaming",
            ),
            rx.box(
                rx.foreach(
                    rx.selected_files("streaming"),
                    lambda f: rx.text(f, as_="p"),
                ),
                id="selected_files_streaming",
            ),
            rx.button(
                "Cancel",
                on_click=rx.cancel_upload("streaming"),
                id="cancel_button_streaming",
            ),
            rx.text(
                UploadState.stream_chunk_records.to_string(),
                id="stream_chunk_records",
            ),
            rx.text(
                UploadState.stream_completed_files.to_string(),
                id="stream_completed_files",
            ),
            rx.vstack(
                rx.foreach(
                    UploadState.stream_progress_dicts,
                    lambda d: rx.text(d.to_string()),
                ),
                id="stream_progress_dicts",
            ),
            rx.text(UploadState.event_order.to_string(), id="event-order"),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def upload_file(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start UploadFile app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv(
        "REFLEX_UPLOADED_FILES_DIR", str(tmp_path_factory.mktemp("uploaded_files"))
    )
    try:
        with AppHarness.create(
            root=tmp_path_factory.mktemp("upload_file"),
            app_source=UploadFile,
        ) as harness:
            yield harness
    finally:
        monkeypatch.undo()


def _goto_app(upload_file: AppHarness, page: Page) -> None:
    """Navigate to the upload app and wait for the token to appear.

    Args:
        upload_file: AppHarness instance.
        page: Playwright page.
    """
    assert upload_file.frontend_url is not None
    page.goto(upload_file.frontend_url)
    utils.poll_for_token(page)


@pytest.mark.parametrize("secondary", [False, True])
def test_upload_file(tmp_path, upload_file: AppHarness, page: Page, secondary: bool):
    """Submit a file upload and check that it arrived on the backend.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        page: Playwright page instance.
        secondary: whether to use the secondary upload form
    """
    assert upload_file.app_instance is not None
    _goto_app(upload_file, page)
    page.locator("#clear_uploads").click()

    suffix = "_secondary" if secondary else ""

    upload_box = page.locator("input[type='file']").nth(1 if secondary else 0)
    upload_button = page.locator(f"#upload_button{suffix}")

    exp_name = "test.txt"
    exp_contents = "test file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    upload_box.set_input_files(str(target_file))
    upload_button.click()

    # check that the selected files are displayed
    selected_files = page.locator(f"#selected_files{suffix}")
    expect(selected_files).to_have_text(exp_name)

    # Wait for the upload to complete.
    expect(page.locator("#upload_done")).to_have_value("true")

    if secondary:
        event_order_displayed = page.locator("#event-order")
        expect(event_order_displayed).to_contain_text("chain_event")
        progress_dicts = page.locator("xpath=//*[@id='progress_dicts']/p")
        expect(progress_dicts.first).to_be_visible()
        last_progress = progress_dicts.last.text_content() or ""
        assert json.loads(last_progress)["progress"] == 1

    # look up the backend state and assert on uploaded contents
    actual_contents = (rx.get_upload_dir() / exp_name).read_text()
    assert actual_contents == exp_contents


@pytest.mark.asyncio
async def test_upload_file_multiple(tmp_path, upload_file: AppHarness, page: Page):
    """Submit several file uploads and check that they arrived on the backend.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        page: Playwright page instance.
    """
    assert upload_file.app_instance is not None
    _goto_app(upload_file, page)
    page.locator("#clear_uploads").click()

    upload_box = page.locator("input[type='file']").first
    upload_button = page.locator("#upload_button")

    exp_files = {
        "test1.txt": "test file contents!",
        "test2.txt": "this is test file number 2!",
        "reflex.txt": "reflex is awesome!",
    }
    target_paths = []
    for exp_name, exp_contents in exp_files.items():
        target_file = tmp_path / exp_name
        target_file.write_text(exp_contents)
        target_paths.append(str(target_file))

    upload_box.set_input_files(target_paths)

    await asyncio.sleep(0.2)

    # check that the selected files are displayed
    selected_files = page.locator("#selected_files")
    assert [
        Path(name).name for name in (selected_files.text_content() or "").split("\n")
    ] == [Path(name).name for name in exp_files]

    # do the upload
    upload_button.click()

    # Wait for the upload to complete.
    expect(page.locator("#upload_done")).to_have_value("true")

    for exp_name, exp_content in exp_files.items():
        actual_contents = (rx.get_upload_dir() / exp_name).read_text()
        assert actual_contents == exp_content


@pytest.mark.parametrize("secondary", [False, True])
def test_clear_files(tmp_path, upload_file: AppHarness, page: Page, secondary: bool):
    """Select then clear several file uploads and check that they are cleared.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        page: Playwright page instance.
        secondary: whether to use the secondary upload form.
    """
    assert upload_file.app_instance is not None
    _goto_app(upload_file, page)
    page.locator("#clear_uploads").click()

    suffix = "_secondary" if secondary else ""

    upload_box = page.locator("input[type='file']").nth(1 if secondary else 0)

    exp_files = {
        "test1.txt": "test file contents!",
        "test2.txt": "this is test file number 2!",
        "reflex.txt": "reflex is awesome!",
    }
    target_paths = []
    for exp_name, exp_contents in exp_files.items():
        target_file = tmp_path / exp_name
        target_file.write_text(exp_contents)
        target_paths.append(str(target_file))

    upload_box.set_input_files(target_paths)

    time.sleep(0.2)

    # check that the selected files are displayed
    selected_files = page.locator(f"#selected_files{suffix}")
    assert [
        Path(name).name for name in (selected_files.text_content() or "").split("\n")
    ] == [Path(name).name for name in exp_files]

    page.locator(f"#clear_button{suffix}").click()

    # check that the selected files are cleared
    expect(page.locator(f"#selected_files{suffix}")).to_have_text("")


# TODO: drag and drop directory
# https://gist.github.com/florentbr/349b1ab024ca9f3de56e6bf8af2ac69e


@pytest.mark.asyncio
async def test_cancel_upload(tmp_path, upload_file: AppHarness, page: Page):
    """Submit a large file upload and cancel it.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        page: Playwright page instance.
    """
    assert upload_file.app_instance is not None
    assert upload_file.frontend_url is not None
    page.goto(upload_file.frontend_url)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "downloadThroughput": 1024 * 1024 / 8,  # 1 Mbps
            "uploadThroughput": 1024 * 1024 / 8,  # 1 Mbps
            "latency": 200,  # 200ms
        },
    )
    utils.poll_for_token(page)

    upload_box = page.locator("input[type='file']").nth(1)
    upload_button = page.locator("#upload_button_secondary")
    cancel_button = page.locator("#cancel_button_secondary")

    exp_name = "large.txt"
    target_file = tmp_path / exp_name
    with target_file.open("wb") as f:
        f.seek(1024 * 1024)  # 1 MB file, should upload in ~8 seconds
        f.write(b"0")

    upload_box.set_input_files(str(target_file))
    upload_button.click()
    await asyncio.sleep(1)
    cancel_button.click()

    # Wait a bit for the upload to get cancelled.
    await asyncio.sleep(12)

    # But there should never be a final progress record for a cancelled upload.
    for p in page.locator("xpath=//*[@id='progress_dicts']/p").all():
        text = p.text_content() or ""
        assert json.loads(text)["progress"] != 1

    assert not (rx.get_upload_dir() / exp_name).exists()

    target_file.unlink()


@pytest.mark.asyncio
async def test_upload_chunk_file(tmp_path, upload_file: AppHarness, page: Page):
    """Submit a streaming upload and check that chunks are processed incrementally."""
    assert upload_file.app_instance is not None
    _goto_app(upload_file, page)
    page.locator("#clear_uploads").click()

    upload_box = page.locator("input[type='file']").nth(4)
    upload_button = page.locator("#upload_button_streaming")
    selected_files = page.locator("#selected_files_streaming")
    chunk_records_display = page.locator("#stream_chunk_records")
    completed_files_display = page.locator("#stream_completed_files")

    exp_files = {
        "stream1.txt": "ABCD" * 262_144,
        "stream2.txt": "WXYZ" * 262_144,
    }
    target_paths = []
    for exp_name, exp_contents in exp_files.items():
        target_file = tmp_path / exp_name
        target_file.write_text(exp_contents)
        target_paths.append(str(target_file))

    upload_box.set_input_files(target_paths)

    await asyncio.sleep(0.2)

    assert [
        Path(name).name for name in (selected_files.text_content() or "").split("\n")
    ] == [Path(name).name for name in exp_files]

    upload_button.click()

    expect(chunk_records_display).to_contain_text("stream1.txt")

    expect(completed_files_display).to_contain_text("stream1.txt")
    expect(completed_files_display).to_contain_text("stream2.txt")

    # Wait for the upload to complete.
    expect(page.locator("#upload_done")).to_have_value("true")

    for exp_name, exp_contents in exp_files.items():
        assert (
            rx.get_upload_dir() / "streaming" / exp_name
        ).read_text() == exp_contents


@pytest.mark.asyncio
async def test_cancel_upload_chunk(
    tmp_path,
    upload_file: AppHarness,
    page: Page,
):
    """Submit a large streaming upload and cancel it."""
    assert upload_file.app_instance is not None
    assert upload_file.frontend_url is not None
    page.goto(upload_file.frontend_url)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "downloadThroughput": 1024 * 1024 / 8,  # 1 Mbps
            "uploadThroughput": 1024 * 1024 / 8,  # 1 Mbps
            "latency": 200,  # 200ms
        },
    )
    utils.poll_for_token(page)

    upload_box = page.locator("input[type='file']").nth(4)
    upload_button = page.locator("#upload_button_streaming")
    cancel_button = page.locator("#cancel_button_streaming")

    exp_name = "cancel_stream.txt"
    target_file = tmp_path / exp_name
    with target_file.open("wb") as f:
        f.seek(2 * 1024 * 1024)
        f.write(b"0")

    upload_box.set_input_files(str(target_file))
    upload_button.click()
    await asyncio.sleep(2)
    cancel_button.click()

    await asyncio.sleep(11)

    # But there should never be a final progress record for a cancelled upload.
    for p in page.locator("xpath=//*[@id='stream_progress_dicts']/p").all():
        text = p.text_content() or ""
        assert json.loads(text)["progress"] != 1

    assert not (rx.get_upload_dir() / exp_name).exists()

    partial_path = rx.get_upload_dir() / "streaming" / exp_name
    assert partial_path.exists()
    assert partial_path.stat().st_size < target_file.stat().st_size

    target_file.unlink()
    if partial_path.exists():
        partial_path.unlink()


def test_upload_download_file(
    tmp_path,
    upload_file: AppHarness,
    page: Page,
):
    """Submit a file upload and then fetch it with rx.download.

    This checks the special case `getBackendURL` logic in the _download event
    handler in state.js.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        page: Playwright page instance.
    """
    assert upload_file.app_instance is not None
    _goto_app(upload_file, page)
    page.locator("#clear_uploads").click()

    upload_box = page.locator("input[type='file']").nth(2)
    upload_button = page.locator("#upload_button_tertiary")

    exp_name = "test.txt"
    exp_contents = "test file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    upload_box.set_input_files(str(target_file))
    upload_button.click()

    # Wait for the upload to complete.
    expect(page.locator("#upload_done")).to_have_value("true")

    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    # Download via event embedded in frontend code.
    with page.expect_download() as download_info:
        page.locator("#download-frontend").click()
    download = download_info.value
    frontend_path = download_dir / exp_name
    download.save_as(str(frontend_path))
    assert frontend_path.read_text() == exp_contents
    frontend_path.unlink()

    # Download via backend event handler.
    with page.expect_download() as download_info:
        page.locator("#download-backend").click()
    download = download_info.value
    backend_path = download_dir / exp_name
    download.save_as(str(backend_path))
    assert backend_path.read_text() == exp_contents


@pytest.mark.parametrize(
    ("exp_name", "exp_contents", "expect_attachment", "expected_mime_type"),
    [
        (
            "malicious.html",
            "<html><body><script>alert('xss')</script></body></html>",
            True,
            "text/html; charset=utf-8",
        ),
        ("document.pdf", "%PDF-1.4 fake pdf contents", False, "application/pdf"),
        ("readme.txt", "plain text contents", True, "text/plain; charset=utf-8"),
    ],
    ids=["html", "pdf", "txt"],
)
def test_uploaded_file_security_headers(
    tmp_path,
    upload_file: AppHarness,
    page: Page,
    exp_name: str,
    exp_contents: str,
    expect_attachment: bool,
    expected_mime_type: str,
):
    """Upload a file and verify security headers on the served response.

    For non-PDF files, Content-Disposition: attachment must be set to force a
    download.  For PDF files, Content-Disposition must NOT be set so the browser
    can render them inline, but Content-Type: application/pdf is always present.
    X-Content-Type-Options: nosniff is always required.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        page: Playwright page instance.
        exp_name: filename to upload.
        exp_contents: file contents to upload.
        expect_attachment: whether the response should force a download.
        expected_mime_type: expected Content-Type mime type.
    """
    import httpx

    assert upload_file.app_instance is not None
    _goto_app(upload_file, page)
    page.locator("#clear_uploads").click()

    upload_box = page.locator("input[type='file']").nth(2)
    upload_button = page.locator("#upload_button_tertiary")

    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    upload_box.set_input_files(str(target_file))
    upload_button.click()

    expect(page.locator("#upload_done")).to_have_value("true")

    # Fetch the uploaded file directly via httpx and check security headers.
    upload_url = f"{Endpoint.UPLOAD.get_url()}/{exp_name}"
    resp = httpx.get(upload_url)
    assert resp.status_code == 200
    assert resp.text == exp_contents
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["content-type"] == expected_mime_type

    if expect_attachment:
        assert resp.headers["content-disposition"] == "attachment"
    else:
        assert "content-disposition" not in resp.headers

    if not expect_attachment:
        # PDF: no browser download test needed, skip the rest.
        return

    # No dialog should appear (the file should be downloaded, not rendered).
    dialog_seen = {"value": False}

    def _on_dialog(d):
        dialog_seen["value"] = True
        d.dismiss()

    page.on("dialog", _on_dialog)

    # Navigate to the uploaded HTML file. Content-Disposition: attachment means
    # the browser triggers a download rather than rendering the HTML.
    with page.expect_download() as download_info:
        page.goto(upload_url)
    download = download_info.value

    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    downloaded_file = download_dir / exp_name
    download.save_as(str(downloaded_file))

    assert dialog_seen["value"] is False, "unexpected alert was displayed"
    assert downloaded_file.read_text() == exp_contents


def test_on_drop(
    tmp_path,
    upload_file: AppHarness,
    page: Page,
):
    """Test the on_drop event handler.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        page: Playwright page instance.
    """
    assert upload_file.app_instance is not None
    _goto_app(upload_file, page)
    page.locator("#clear_uploads").click()

    # quaternary upload (4th file input, index 3)
    upload_box = page.locator("input[type='file']").nth(3)

    exp_name = "drop_test.txt"
    exp_contents = "dropped file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    # Simulate file drop by directly setting the file input
    upload_box.set_input_files(str(target_file))

    # Wait for the upload to complete.
    expect(page.locator("#upload_done")).to_have_value("true")

    def exp_name_in_quaternary():
        quaternary_files = page.locator("#quaternary_files").text_content() or ""
        if quaternary_files:
            files = json.loads(quaternary_files)
            return exp_name in files
        return False

    # Poll until the file names appear in the display
    AppHarness._poll_for(exp_name_in_quaternary)

    assert exp_name_in_quaternary()
