"""Integration tests for file upload."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from reflex_base.constants.event import Endpoint
from selenium.webdriver.common.by import By

import reflex as rx
from reflex.testing import AppHarness, WebDriver

from .utils import poll_for_navigation


def UploadFile():
    """App for testing dynamic routes."""
    import reflex as rx

    LARGE_DATA = "DUMMY" * 1024 * 512

    class UploadState(rx.State):
        _file_data: dict[str, str] = {}
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
            for file in files:
                upload_data = await file.read()
                self._file_data[file.name or ""] = upload_data.decode("utf-8")

        @rx.event
        async def handle_upload_secondary(self, files: list[rx.UploadFile]):
            for file in files:
                upload_data = await file.read()
                self._file_data[file.name or ""] = upload_data.decode("utf-8")
                self.large_data = LARGE_DATA
                yield UploadState.chain_event

        @rx.event
        def upload_progress(self, progress):
            assert progress
            self.event_order.append("upload_progress")
            self.progress_dicts.append(progress)

        @rx.event
        def chain_event(self):
            assert self.large_data == LARGE_DATA
            self.large_data = ""
            self.event_order.append("chain_event")

        @rx.event
        def stream_upload_progress(self, progress):
            assert progress
            self.stream_progress_dicts.append(progress)

        @rx.event
        async def handle_upload_tertiary(self, files: list[rx.UploadFile]):
            for file in files:
                (rx.get_upload_dir() / (file.name or "INVALID")).write_bytes(
                    await file.read()
                )

        @rx.event
        async def handle_upload_quaternary(self, files: list[rx.UploadFile]):
            self.quaternary_names = [file.name for file in files if file.name]

        @rx.event(background=True)
        async def handle_upload_stream(self, chunk_iter: rx.UploadChunkIterator):
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

        @rx.event
        def do_download(self):
            return rx.download(rx.get_upload_url("test.txt"))

    def index():
        return rx.vstack(
            rx.input(
                value=UploadState.router.session.client_token,
                read_only=True,
                id="token",
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
                )
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
    with AppHarness.create(
        root=tmp_path_factory.mktemp("upload_file"),
        app_source=UploadFile,
    ) as harness:
        yield harness


@pytest.fixture
def driver(upload_file: AppHarness):
    """Get an instance of the browser open to the upload_file app.

    Args:
        upload_file: harness for DynamicRoute app

    Yields:
        WebDriver instance.
    """
    assert upload_file.app_instance is not None, "app is not running"
    driver = upload_file.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def poll_for_token(driver: WebDriver, upload_file: AppHarness) -> str:
    """Poll for the token input to be populated.

    Args:
        driver: WebDriver instance.
        upload_file: harness for UploadFile app.

    Returns:
        token value
    """
    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )
    # wait for the backend connection to send the token
    token = upload_file.poll_for_value(token_input)
    assert token is not None
    return token


@pytest.mark.parametrize("secondary", [False, True])
@pytest.mark.asyncio
async def test_upload_file(
    tmp_path, upload_file: AppHarness, driver: WebDriver, secondary: bool
):
    """Submit a file upload and check that it arrived on the backend.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
        secondary: whether to use the secondary upload form
    """
    assert upload_file.app_instance is not None
    token = poll_for_token(driver, upload_file)
    full_state_name = upload_file.get_full_state_name(["_upload_state"])
    state_name = upload_file.get_state_name("_upload_state")
    substate_token = f"{token}_{full_state_name}"

    suffix = "_secondary" if secondary else ""

    upload_box = driver.find_elements(By.XPATH, "//input[@type='file']")[
        1 if secondary else 0
    ]
    assert upload_box
    upload_button = driver.find_element(By.ID, f"upload_button{suffix}")
    assert upload_button

    exp_name = "test.txt"
    exp_contents = "test file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    upload_box.send_keys(str(target_file))
    upload_button.click()

    # check that the selected files are displayed
    selected_files = driver.find_element(By.ID, f"selected_files{suffix}")
    assert Path(selected_files.text).name == Path(exp_name).name

    if secondary:
        event_order_displayed = driver.find_element(By.ID, "event-order")
        AppHarness.expect(lambda: "chain_event" in event_order_displayed.text)

        state = await upload_file.get_state(substate_token)
        # only the secondary form tracks progress and chain events
        assert state.substates[state_name].event_order.count("upload_progress") == 1  # pyright: ignore[reportAttributeAccessIssue]
        assert state.substates[state_name].event_order.count("chain_event") == 1  # pyright: ignore[reportAttributeAccessIssue]

    # look up the backend state and assert on uploaded contents
    async def get_file_data():
        return (
            (await upload_file.get_state(substate_token))
            .substates[state_name]
            ._file_data  # pyright: ignore[reportAttributeAccessIssue]
        )

    file_data = await AppHarness._poll_for_async(get_file_data)
    assert isinstance(file_data, dict)
    normalized_file_data = {Path(k).name: v for k, v in file_data.items()}
    assert normalized_file_data[Path(exp_name).name] == exp_contents


@pytest.mark.asyncio
async def test_upload_file_multiple(tmp_path, upload_file: AppHarness, driver):
    """Submit several file uploads and check that they arrived on the backend.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
    """
    assert upload_file.app_instance is not None
    token = poll_for_token(driver, upload_file)
    full_state_name = upload_file.get_full_state_name(["_upload_state"])
    state_name = upload_file.get_state_name("_upload_state")
    substate_token = f"{token}_{full_state_name}"

    upload_box = driver.find_element(By.XPATH, "//input[@type='file']")
    assert upload_box
    upload_button = driver.find_element(By.ID, "upload_button")
    assert upload_button

    exp_files = {
        "test1.txt": "test file contents!",
        "test2.txt": "this is test file number 2!",
        "reflex.txt": "reflex is awesome!",
    }
    for exp_name, exp_contents in exp_files.items():
        target_file = tmp_path / exp_name
        target_file.write_text(exp_contents)
        upload_box.send_keys(str(target_file))

    await asyncio.sleep(0.2)

    # check that the selected files are displayed
    selected_files = driver.find_element(By.ID, "selected_files")
    assert [Path(name).name for name in selected_files.text.split("\n")] == [
        Path(name).name for name in exp_files
    ]

    # do the upload
    upload_button.click()

    # look up the backend state and assert on uploaded contents
    async def get_file_data():
        return (
            (await upload_file.get_state(substate_token))
            .substates[state_name]
            ._file_data  # pyright: ignore[reportAttributeAccessIssue]
        )

    file_data = await AppHarness._poll_for_async(get_file_data)
    assert isinstance(file_data, dict)
    normalized_file_data = {Path(k).name: v for k, v in file_data.items()}
    for exp_name, exp_contents in exp_files.items():
        assert normalized_file_data[Path(exp_name).name] == exp_contents


@pytest.mark.parametrize("secondary", [False, True])
def test_clear_files(
    tmp_path, upload_file: AppHarness, driver: WebDriver, secondary: bool
):
    """Select then clear several file uploads and check that they are cleared.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
        secondary: whether to use the secondary upload form.
    """
    assert upload_file.app_instance is not None
    poll_for_token(driver, upload_file)

    suffix = "_secondary" if secondary else ""

    upload_box = driver.find_elements(By.XPATH, "//input[@type='file']")[
        1 if secondary else 0
    ]
    assert upload_box
    upload_button = driver.find_element(By.ID, f"upload_button{suffix}")
    assert upload_button

    exp_files = {
        "test1.txt": "test file contents!",
        "test2.txt": "this is test file number 2!",
        "reflex.txt": "reflex is awesome!",
    }
    for exp_name, exp_contents in exp_files.items():
        target_file = tmp_path / exp_name
        target_file.write_text(exp_contents)
        upload_box.send_keys(str(target_file))

    time.sleep(0.2)

    # check that the selected files are displayed
    selected_files = driver.find_element(By.ID, f"selected_files{suffix}")
    assert [Path(name).name for name in selected_files.text.split("\n")] == [
        Path(name).name for name in exp_files
    ]

    clear_button = driver.find_element(By.ID, f"clear_button{suffix}")
    assert clear_button
    clear_button.click()

    # check that the selected files are cleared
    selected_files = driver.find_element(By.ID, f"selected_files{suffix}")
    assert selected_files.text == ""


# TODO: drag and drop directory
# https://gist.github.com/florentbr/349b1ab024ca9f3de56e6bf8af2ac69e


@pytest.mark.asyncio
async def test_cancel_upload(tmp_path, upload_file: AppHarness, driver: WebDriver):
    """Submit a large file upload and cancel it.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
    """
    assert upload_file.app_instance is not None
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "downloadThroughput": 1024 * 1024 / 8,  # 1 Mbps
            "uploadThroughput": 1024 * 1024 / 8,  # 1 Mbps
            "latency": 200,  # 200ms
        },
    )
    token = poll_for_token(driver, upload_file)
    state_name = upload_file.get_state_name("_upload_state")
    state_full_name = upload_file.get_full_state_name(["_upload_state"])
    substate_token = f"{token}_{state_full_name}"

    upload_box = driver.find_elements(By.XPATH, "//input[@type='file']")[1]
    upload_button = driver.find_element(By.ID, "upload_button_secondary")
    cancel_button = driver.find_element(By.ID, "cancel_button_secondary")

    exp_name = "large.txt"
    target_file = tmp_path / exp_name
    with target_file.open("wb") as f:
        f.seek(1024 * 1024)  # 1 MB file, should upload in ~8 seconds
        f.write(b"0")

    upload_box.send_keys(str(target_file))
    upload_button.click()
    await asyncio.sleep(1)
    cancel_button.click()

    # Wait a bit for the upload to get cancelled.
    await asyncio.sleep(12)

    # Get interim progress dicts saved in the on_upload_progress handler.
    async def _progress_dicts():
        state = await upload_file.get_state(substate_token)
        return state.substates[state_name].progress_dicts  # pyright: ignore[reportAttributeAccessIssue]

    # We should have _some_ progress
    assert await AppHarness._poll_for_async(_progress_dicts)

    # But there should never be a final progress record for a cancelled upload.
    for p in await _progress_dicts():
        assert p["progress"] != 1

    state = await upload_file.get_state(substate_token)
    file_data = state.substates[state_name]._file_data  # pyright: ignore[reportAttributeAccessIssue]
    assert isinstance(file_data, dict)
    normalized_file_data = {Path(k).name: v for k, v in file_data.items()}
    assert Path(exp_name).name not in normalized_file_data

    target_file.unlink()


@pytest.mark.asyncio
async def test_upload_chunk_file(tmp_path, upload_file: AppHarness, driver: WebDriver):
    """Submit a streaming upload and check that chunks are processed incrementally."""
    assert upload_file.app_instance is not None
    token = poll_for_token(driver, upload_file)
    state_name = upload_file.get_state_name("_upload_state")
    state_full_name = upload_file.get_full_state_name(["_upload_state"])
    substate_token = f"{token}_{state_full_name}"

    upload_box = driver.find_elements(By.XPATH, "//input[@type='file']")[4]
    upload_button = driver.find_element(By.ID, "upload_button_streaming")
    selected_files = driver.find_element(By.ID, "selected_files_streaming")
    chunk_records_display = driver.find_element(By.ID, "stream_chunk_records")
    completed_files_display = driver.find_element(By.ID, "stream_completed_files")

    exp_files = {
        "stream1.txt": "ABCD" * 262_144,
        "stream2.txt": "WXYZ" * 262_144,
    }
    for exp_name, exp_contents in exp_files.items():
        target_file = tmp_path / exp_name
        target_file.write_text(exp_contents)
        upload_box.send_keys(str(target_file))

    await asyncio.sleep(0.2)

    assert [Path(name).name for name in selected_files.text.split("\n")] == [
        Path(name).name for name in exp_files
    ]

    upload_button.click()

    AppHarness.expect(lambda: "stream1.txt" in chunk_records_display.text)

    async def _stream_completed():
        state = await upload_file.get_state(substate_token)
        return (
            len(
                state.substates[state_name].stream_completed_files  # pyright: ignore[reportAttributeAccessIssue]
            )
            == 2
        )

    await AppHarness._poll_for_async(_stream_completed)

    state = await upload_file.get_state(substate_token)
    substate = cast(Any, state.substates[state_name])
    chunk_records = substate.stream_chunk_records

    assert len(chunk_records) > 2
    assert {Path(record.split(":")[0]).name for record in chunk_records} == {
        "stream1.txt",
        "stream2.txt",
    }
    assert substate.stream_completed_files == ["stream1.txt", "stream2.txt"]

    AppHarness.expect(
        lambda: (
            "stream1.txt" in completed_files_display.text
            and "stream2.txt" in completed_files_display.text
        )
    )

    for exp_name, exp_contents in exp_files.items():
        assert (
            rx.get_upload_dir() / "streaming" / exp_name
        ).read_text() == exp_contents


@pytest.mark.asyncio
async def test_cancel_upload_chunk(
    tmp_path,
    upload_file: AppHarness,
    driver: WebDriver,
):
    """Submit a large streaming upload and cancel it."""
    assert upload_file.app_instance is not None
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "downloadThroughput": 1024 * 1024 / 8,  # 1 Mbps
            "uploadThroughput": 1024 * 1024 / 8,  # 1 Mbps
            "latency": 200,  # 200ms
        },
    )
    token = poll_for_token(driver, upload_file)
    state_name = upload_file.get_state_name("_upload_state")
    state_full_name = upload_file.get_full_state_name(["_upload_state"])
    substate_token = f"{token}_{state_full_name}"

    upload_box = driver.find_elements(By.XPATH, "//input[@type='file']")[4]
    upload_button = driver.find_element(By.ID, "upload_button_streaming")
    cancel_button = driver.find_element(By.ID, "cancel_button_streaming")

    exp_name = "cancel_stream.txt"
    target_file = tmp_path / exp_name
    with target_file.open("wb") as f:
        f.seek(2 * 1024 * 1024)
        f.write(b"0")

    upload_box.send_keys(str(target_file))
    upload_button.click()
    await asyncio.sleep(1)
    cancel_button.click()

    await asyncio.sleep(12)

    async def _stream_progress_dicts():
        state = await upload_file.get_state(substate_token)
        return (
            state.substates[state_name].stream_progress_dicts  # pyright: ignore[reportAttributeAccessIssue]
        )

    assert await AppHarness._poll_for_async(_stream_progress_dicts)

    for progress in await _stream_progress_dicts():
        assert progress["progress"] != 1

    state = await upload_file.get_state(substate_token)
    substate = cast(Any, state.substates[state_name])
    assert substate.stream_completed_files == []
    assert substate.stream_chunk_records

    partial_path = rx.get_upload_dir() / "streaming" / exp_name
    assert partial_path.exists()
    assert partial_path.stat().st_size < target_file.stat().st_size

    target_file.unlink()
    if partial_path.exists():
        partial_path.unlink()


def test_upload_download_file(
    tmp_path,
    upload_file: AppHarness,
    driver: WebDriver,
):
    """Submit a file upload and then fetch it with rx.download.

    This checks the special case `getBackendURL` logic in the _download event
    handler in state.js.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
    """
    assert upload_file.app_instance is not None
    poll_for_token(driver, upload_file)

    upload_box = driver.find_elements(By.XPATH, "//input[@type='file']")[2]
    assert upload_box
    upload_button = driver.find_element(By.ID, "upload_button_tertiary")
    assert upload_button

    exp_name = "test.txt"
    exp_contents = "test file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    upload_box.send_keys(str(target_file))
    upload_button.click()

    # Download via event embedded in frontend code.
    download_frontend = driver.find_element(By.ID, "download-frontend")
    with poll_for_navigation(driver):
        download_frontend.click()
    assert urlsplit(driver.current_url).path == f"/{Endpoint.UPLOAD.value}/test.txt"
    assert driver.find_element(by=By.TAG_NAME, value="body").text == exp_contents

    # Go back and wait for the app to reload.
    with poll_for_navigation(driver):
        driver.back()
    poll_for_token(driver, upload_file)

    # Download via backend event handler.
    download_backend = driver.find_element(By.ID, "download-backend")
    with poll_for_navigation(driver):
        download_backend.click()
    assert urlsplit(driver.current_url).path == f"/{Endpoint.UPLOAD.value}/test.txt"
    assert driver.find_element(by=By.TAG_NAME, value="body").text == exp_contents


@pytest.mark.asyncio
async def test_on_drop(
    tmp_path,
    upload_file: AppHarness,
    driver: WebDriver,
):
    """Test the on_drop event handler.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
    """
    assert upload_file.app_instance is not None
    token = poll_for_token(driver, upload_file)
    full_state_name = upload_file.get_full_state_name(["_upload_state"])
    state_name = upload_file.get_state_name("_upload_state")
    substate_token = f"{token}_{full_state_name}"

    upload_box = driver.find_elements(By.XPATH, "//input[@type='file']")[
        3
    ]  # quaternary upload
    assert upload_box

    exp_name = "drop_test.txt"
    exp_contents = "dropped file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    # Simulate file drop by directly setting the file input
    upload_box.send_keys(str(target_file))

    # Wait for the on_drop event to be processed
    await asyncio.sleep(0.5)

    async def exp_name_in_quaternary():
        state = await upload_file.get_state(substate_token)
        return exp_name in state.substates[state_name].quaternary_names  # pyright: ignore[reportAttributeAccessIssue]

    # Poll until the file names appear in the display
    await AppHarness._poll_for_async(exp_name_in_quaternary)

    # Verify through state that the file names were captured correctly
    state = await upload_file.get_state(substate_token)
    assert exp_name in state.substates[state_name].quaternary_names  # pyright: ignore[reportAttributeAccessIssue]
