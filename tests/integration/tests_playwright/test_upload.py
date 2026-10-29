"""Playwright integration tests for upload, streaming, and download behavior."""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import Page, expect
from reflex_base.constants.event import Endpoint

import reflex as rx
from reflex.testing import AppHarness


def UploadFile():
    """Build the upload app used by these browser tests."""
    import reflex as rx

    large_data = "DUMMY" * 1024 * 512

    class UploadState(rx.State):
        upload_done: bool = False
        progress_dicts: list[dict] = []
        stream_progress_dicts: list[dict] = []
        large_data: str = ""
        quaternary_names: list[str] = []
        quaternary_field: str = ""
        stream_chunk_records: list[str] = []
        stream_completed_files: list[str] = []
        stream_field: str = ""

        @rx.event
        async def handle_upload(self, files: list[rx.UploadFile]):
            self.upload_done = False
            for file in files:
                target = rx.get_upload_dir() / (file.name or "INVALID")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(await file.read())
            self.upload_done = True

        @rx.event
        async def handle_upload_secondary(self, files: list[rx.UploadFile]):
            self.upload_done = False
            for file in files:
                target = rx.get_upload_dir() / (file.name or "INVALID")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(await file.read())
                self.large_data = large_data
                yield UploadState.chain_event

        @rx.event
        def upload_progress(self, progress: dict):
            assert progress
            self.progress_dicts.append(progress)

        @rx.event
        def chain_event(self):
            assert self.large_data == large_data
            self.large_data = ""
            self.upload_done = True

        @rx.event
        def stream_upload_progress(self, progress: dict):
            assert progress
            self.stream_progress_dicts.append(progress)

        @rx.event
        async def handle_upload_tertiary(self, files: list[rx.UploadFile]):
            self.upload_done = False
            for file in files:
                target = rx.get_upload_dir() / (file.name or "INVALID")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(await file.read())
            self.upload_done = True

        @rx.event
        async def handle_upload_quaternary(
            self, files: list[rx.UploadFile], field: str
        ):
            self.upload_done = False
            self.quaternary_names = [file.name for file in files if file.name]
            self.quaternary_field = field
            self.upload_done = True

        @rx.event(background=True)
        async def handle_upload_stream(
            self, chunk_iter: rx.UploadChunkIterator, field: str
        ):
            async with self:
                self.upload_done = False
                self.stream_field = field
            upload_dir = rx.get_upload_dir() / "streaming"
            handles: dict[str, Any] = {}
            try:
                async for chunk in chunk_iter:
                    target = upload_dir / chunk.filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    handle = handles.get(chunk.filename)
                    if handle is None:
                        handle = (
                            target.open("r+b") if target.exists() else target.open("wb")
                        )
                        handles[chunk.filename] = handle
                    handle.seek(chunk.offset)
                    handle.write(chunk.data)
                    async with self:
                        self.stream_chunk_records.append(
                            f"{chunk.filename}:{chunk.offset}:{len(chunk.data)}"
                        )
            finally:
                for handle in handles.values():
                    handle.close()
            async with self:
                self.stream_completed_files = sorted(handles)
                self.upload_done = True

        @rx.event
        def do_download(self):
            return rx.download(rx.get_upload_url("test.txt"))

        @rx.event
        def clear_uploads(self):
            import shutil

            shutil.rmtree(rx.get_upload_dir(), ignore_errors=True)
            self.reset()

    def index():
        from typing import Any, cast

        def upload_control(upload_id=None):
            return rx.upload.root(
                rx.vstack(
                    rx.button("Select File"),
                    rx.text("Drag and drop files here or click to select files"),
                ),
                **({"id": upload_id} if upload_id is not None else {}),
            )

        return rx.vstack(
            rx.input(
                value=cast(Any, UploadState.upload_done).to_string(),
                read_only=True,
                id="upload_done",
            ),
            rx.button(
                "Clear Uploaded Files",
                id="clear_uploads",
                on_click=UploadState.clear_uploads,
            ),
            rx.heading("Default Upload"),
            upload_control(),
            rx.button(
                "Upload",
                on_click=lambda: UploadState.handle_upload(rx.upload_files()),
                id="upload_button",
            ),
            rx.box(
                rx.foreach(rx.selected_files(), lambda name: rx.text(name, as_="p")),
                id="selected_files",
            ),
            rx.button("Clear", on_click=rx.clear_selected_files, id="clear_button"),
            rx.heading("Secondary Upload"),
            upload_control("secondary"),
            rx.button(
                "Upload",
                on_click=UploadState.handle_upload_secondary(
                    rx.upload_files(
                        upload_id="secondary",
                        on_upload_progress=UploadState.upload_progress,
                    )
                ),
                id="upload_button_secondary",
            ),
            rx.box(
                rx.foreach(
                    rx.selected_files("secondary"), lambda name: rx.text(name, as_="p")
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
                    UploadState.progress_dicts, lambda item: rx.text(item.to_string())
                ),
                id="progress_dicts",
            ),
            rx.button(
                "Cancel",
                on_click=rx.cancel_upload("secondary"),
                id="cancel_button_secondary",
            ),
            rx.heading("Tertiary Upload/Download"),
            upload_control("tertiary"),
            rx.button(
                "Upload",
                on_click=UploadState.handle_upload_tertiary(
                    rx.upload_files(upload_id="tertiary")
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
                    cast(Any, rx.upload_files(upload_id="quaternary")),
                    "resume-field",
                ),
                id="quaternary",
            ),
            rx.text(
                cast(Any, UploadState.quaternary_names).to_string(),
                id="quaternary_files",
            ),
            rx.input(
                value=UploadState.quaternary_field,
                read_only=True,
                id="quaternary_field",
            ),
            rx.heading("Streaming Upload"),
            upload_control("streaming"),
            rx.button(
                "Upload",
                on_click=UploadState.handle_upload_stream(
                    cast(
                        Any,
                        rx.upload_files_chunk(
                            upload_id="streaming",
                            on_upload_progress=UploadState.stream_upload_progress,
                        ),
                    ),
                    "stream-field",
                ),
                id="upload_button_streaming",
            ),
            rx.box(
                rx.foreach(
                    rx.selected_files("streaming"), lambda name: rx.text(name, as_="p")
                ),
                id="selected_files_streaming",
            ),
            rx.button(
                "Cancel",
                on_click=rx.cancel_upload("streaming"),
                id="cancel_button_streaming",
            ),
            rx.text(
                cast(Any, UploadState.stream_chunk_records).to_string(),
                id="stream_chunk_records",
            ),
            rx.text(
                cast(Any, UploadState.stream_completed_files).to_string(),
                id="stream_completed_files",
            ),
            rx.input(value=UploadState.stream_field, read_only=True, id="stream_field"),
            rx.vstack(
                rx.foreach(
                    UploadState.stream_progress_dicts,
                    lambda item: rx.text(item.to_string()),
                ),
                id="stream_progress_dicts",
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def uploaded_files_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create the app's isolated upload directory.

    Returns:
        The isolated directory for uploaded files.
    """
    return tmp_path_factory.mktemp("uploaded_files")


@pytest.fixture(scope="module")
def upload_file(
    tmp_path_factory: pytest.TempPathFactory, uploaded_files_dir: Path
) -> Generator[AppHarness, None, None]:
    """Start the upload app with the isolated upload directory configured.

    Yields:
        The running app harness.
    """
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFLEX_UPLOADED_FILES_DIR", str(uploaded_files_dir))
    try:
        with AppHarness.create(
            root=tmp_path_factory.mktemp("upload_file"), app_source=UploadFile
        ) as harness:
            yield harness
    finally:
        monkeypatch.undo()


@pytest.fixture(autouse=True)
def clear_uploaded_files(uploaded_files_dir: Path):
    """Clear backend upload artifacts before and after each test."""

    def clear_contents():
        for child in uploaded_files_dir.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()

    clear_contents()
    yield
    clear_contents()


@pytest.fixture
def opened_page(upload_file: AppHarness, page: Page) -> Page:
    """Open the upload app in the browser.

    Returns:
        The page after navigation.
    """
    assert upload_file.frontend_url is not None
    page.goto(upload_file.frontend_url)
    return page


def _file_input(page: Page, upload_id: str | None = None):
    """Locate the native file input for an upload component.

    Returns:
        The file input locator.
    """
    if upload_id is not None:
        return page.locator(f"#{upload_id} input[type=file]")
    return page.locator("input[type=file]").first


def _upload_done(page: Page) -> None:
    expect(page.locator("#upload_done")).to_have_value("true", timeout=30_000)


def _progress(page: Page, selector: str) -> list[dict]:
    return [
        json.loads(line) for line in page.locator(f"{selector} > p").all_text_contents()
    ]


def _wait_for_progress_to_stop(page: Page, selector: str) -> list[dict]:
    previous = _progress(page, selector)
    stable = 0
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        page.wait_for_timeout(1000)
        current = _progress(page, selector)
        stable = stable + 1 if current == previous else 0
        if stable >= 3:
            return current
        previous = current
    message = "Upload progress kept changing after cancellation"
    raise TimeoutError(message)


def _write_file(tmp_path: Path, name: str, contents: str) -> Path:
    target = tmp_path / name
    target.write_text(contents)
    return target


@pytest.mark.parametrize("upload_id", [None, "secondary"])
def test_upload_file(
    tmp_path: Path, upload_file: AppHarness, opened_page: Page, upload_id: str | None
):
    """Upload a file through each buffered upload control."""
    page = opened_page
    page.locator("#clear_uploads").click()
    suffix = f"_{upload_id}" if upload_id else ""
    target = _write_file(tmp_path, "test.txt", "test file contents!")
    _file_input(page, upload_id).set_input_files(target)
    expect(page.locator(f"#selected_files{suffix}")).to_contain_text("test.txt")
    page.locator(f"#upload_button{suffix}").click()
    _upload_done(page)
    assert (rx.get_upload_dir() / "test.txt").read_text() == "test file contents!"
    if upload_id == "secondary":
        expect(page.locator("#progress_dicts > p")).not_to_have_count(0)
        page.wait_for_function(
            """selector => {
              const entries = document.querySelectorAll(`${selector} > p`);
              if (!entries.length) return false;
              return JSON.parse(entries[entries.length - 1].textContent).progress === 1;
            }""",
            arg="#progress_dicts",
            timeout=30_000,
        )


def test_upload_file_multiple(
    tmp_path: Path, upload_file: AppHarness, opened_page: Page
):
    """Upload multiple selected files and verify each backend artifact."""
    files = {
        "test1.txt": "test file contents!",
        "test2.txt": "this is test file number 2!",
        "reflex.txt": "reflex is awesome!",
    }
    targets = [
        _write_file(tmp_path, name, contents) for name, contents in files.items()
    ]
    _file_input(opened_page).set_input_files(targets)
    expect(opened_page.locator("#selected_files")).to_contain_text("reflex.txt")
    opened_page.locator("#upload_button").click()
    _upload_done(opened_page)
    for name, contents in files.items():
        assert (rx.get_upload_dir() / name).read_text() == contents


def test_upload_file_with_bound_arg(
    tmp_path: Path, upload_file: AppHarness, opened_page: Page
):
    """A bound argument from an upload drop handler reaches the backend."""
    target = _write_file(tmp_path, "bound_arg.txt", "bound arg upload contents!")
    _file_input(opened_page, "quaternary").set_input_files(target)
    _upload_done(opened_page)
    expect(opened_page.locator("#quaternary_field")).to_have_value("resume-field")
    expect(opened_page.locator("#quaternary_files")).to_contain_text("bound_arg.txt")


@pytest.mark.parametrize("upload_id", [None, "secondary"])
def test_clear_files(
    tmp_path: Path, upload_file: AppHarness, opened_page: Page, upload_id: str | None
):
    """Clear selected files from either buffered upload control."""
    suffix = f"_{upload_id}" if upload_id else ""
    targets = [
        _write_file(tmp_path, "test1.txt", "first"),
        _write_file(tmp_path, "test2.txt", "second"),
    ]
    _file_input(opened_page, upload_id).set_input_files(targets)
    expect(opened_page.locator(f"#selected_files{suffix}")).to_contain_text("test2.txt")
    opened_page.locator(f"#clear_button{suffix}").click()
    expect(opened_page.locator(f"#selected_files{suffix}")).to_be_empty()


@pytest.mark.parametrize(
    ("upload_id", "progress_selector", "filename", "size", "partial_subdir"),
    [
        pytest.param(
            "secondary",
            "#progress_dicts",
            "large.txt",
            1024 * 1024,
            None,
            id="buffered",
        ),
        pytest.param(
            "streaming",
            "#stream_progress_dicts",
            "cancel_stream.txt",
            2 * 1024 * 1024,
            "streaming",
            id="streaming",
        ),
    ],
)
def test_cancel_upload(
    tmp_path: Path,
    upload_file: AppHarness,
    opened_page: Page,
    upload_id: str,
    progress_selector: str,
    filename: str,
    size: int,
    partial_subdir: str | None,
):
    """Cancel active buffered and streaming uploads without final progress."""
    page = opened_page
    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "downloadThroughput": 1024 * 1024 / 8,
            "uploadThroughput": 1024 * 1024 / 8,
            "latency": 200,
        },
    )
    target = tmp_path / filename
    target.write_bytes(b"0" * size)
    _file_input(page, upload_id).set_input_files(target)
    page.locator(f"#upload_button_{upload_id}").click()
    page.wait_for_function(
        "selector => document.querySelectorAll(`${selector} > p`).length >= 2",
        arg=progress_selector,
        timeout=20_000,
    )
    page.locator(f"#cancel_button_{upload_id}").click()
    assert all(
        record["progress"] != 1
        for record in _wait_for_progress_to_stop(page, progress_selector)
    )
    assert not (rx.get_upload_dir() / filename).exists()
    if partial_subdir:
        partial = rx.get_upload_dir() / partial_subdir / filename
        assert partial.exists()
        assert partial.stat().st_size < target.stat().st_size
    cdp.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "downloadThroughput": -1,
            "uploadThroughput": -1,
            "latency": 0,
        },
    )


def test_upload_chunk_file(tmp_path: Path, upload_file: AppHarness, opened_page: Page):
    """Stream multiple files in chunks and verify complete backend files."""
    files = {"stream1.txt": "ABCD" * 262_144, "stream2.txt": "WXYZ" * 262_144}
    targets = [
        _write_file(tmp_path, name, contents) for name, contents in files.items()
    ]
    page = opened_page
    _file_input(page, "streaming").set_input_files(targets)
    expect(page.locator("#selected_files_streaming")).to_contain_text("stream2.txt")
    page.locator("#upload_button_streaming").click()
    expect(page.locator("#stream_chunk_records")).to_contain_text(
        "stream1.txt", timeout=30_000
    )
    expect(page.locator("#stream_completed_files")).to_contain_text(
        "stream2.txt", timeout=30_000
    )
    _upload_done(page)
    expect(page.locator("#stream_field")).to_have_value("stream-field")
    for name, contents in files.items():
        assert (rx.get_upload_dir() / "streaming" / name).read_text() == contents


def test_upload_download_file(
    tmp_path: Path, upload_file: AppHarness, opened_page: Page
):
    """Download an uploaded file from both frontend and backend events."""
    target = _write_file(tmp_path, "test.txt", "test file contents!")
    _file_input(opened_page, "tertiary").set_input_files(target)
    opened_page.locator("#upload_button_tertiary").click()
    _upload_done(opened_page)
    for selector in ("#download-frontend", "#download-backend"):
        with opened_page.expect_download() as download_info:
            opened_page.locator(selector).click()
        downloaded = tmp_path / f"{selector[1:]}.txt"
        download_info.value.save_as(downloaded)
        assert downloaded.read_text() == "test file contents!"


@pytest.mark.parametrize(
    ("filename", "contents", "attachment", "mime_type"),
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
    tmp_path: Path,
    upload_file: AppHarness,
    opened_page: Page,
    filename: str,
    contents: str,
    attachment: bool,
    mime_type: str,
):
    """Uploaded files use safe content headers and force non-PDF downloads."""
    target = _write_file(tmp_path, filename, contents)
    _file_input(opened_page, "tertiary").set_input_files(target)
    opened_page.locator("#upload_button_tertiary").click()
    _upload_done(opened_page)
    upload_url = f"{Endpoint.UPLOAD.get_url()}/{filename}"
    response = httpx.get(upload_url)
    assert response.status_code == 200
    assert response.text == contents
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-type"] == mime_type
    if attachment:
        assert response.headers["content-disposition"] == "attachment"
    else:
        assert "content-disposition" not in response.headers
    if filename == "malicious.html":
        dialogs: list[str] = []

        def dismiss_dialog(dialog):
            dialogs.append(dialog.message)
            dialog.dismiss()

        opened_page.on("dialog", dismiss_dialog)
        with opened_page.expect_download() as download_info:
            opened_page.goto(upload_url)
        downloaded = tmp_path / filename
        download_info.value.save_as(downloaded)
        assert downloaded.read_text() == contents
        assert not dialogs


def test_on_drop(tmp_path: Path, upload_file: AppHarness, opened_page: Page):
    """Selecting a file through the dropzone calls its bound upload handler."""
    target = _write_file(tmp_path, "drop_test.txt", "dropped file contents!")
    _file_input(opened_page, "quaternary").set_input_files(target)
    _upload_done(opened_page)
    expect(opened_page.locator("#quaternary_field")).to_have_value("resume-field")
    expect(opened_page.locator("#quaternary_files")).to_contain_text("drop_test.txt")
