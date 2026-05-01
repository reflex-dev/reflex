"""Integration tests for file upload."""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
from reflex_base.constants.event import Endpoint
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

import reflex as rx
from reflex.testing import AppHarness


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
def uploaded_files_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create and return a temporary directory for uploaded files.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories

    Returns:
        dir where uploaded files will be saved in the test (rx.get_upload_dir())
    """
    return tmp_path_factory.mktemp("uploaded_files")


@pytest.fixture(scope="module")
def upload_file(
    tmp_path_factory: pytest.TempPathFactory, uploaded_files_dir: Path
) -> Generator[AppHarness, None, None]:
    """Start UploadFile app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture
        uploaded_files_dir: dir where uploaded files will be saved in the test (rx.get_upload_dir())

    Yields:
        running AppHarness instance
    """
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv(
        "REFLEX_UPLOADED_FILES_DIR",
        str(uploaded_files_dir),
    )
    try:
        with AppHarness.create(
            root=tmp_path_factory.mktemp("upload_file"),
            app_source=UploadFile,
        ) as harness:
            yield harness
    finally:
        monkeypatch.undo()


@pytest.fixture(autouse=True)
def clear_uploaded_files(uploaded_files_dir: Path):
    """Clear the reflex uploaded files directory before and after each test.

    Args:
        uploaded_files_dir: dir where uploaded files will be saved in the test (rx.get_upload_dir())
    """

    def _clear_contents():
        if not uploaded_files_dir.exists():
            return
        for child in uploaded_files_dir.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()

    _clear_contents()
    yield
    _clear_contents()


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


@pytest.fixture
def simulate_slow_network(driver: WebDriver) -> Generator[None, None, None]:
    """Throttle network speed to 1 Mbps / 200ms latency to reduce race condition window.

    Restores unthrottled conditions on teardown so the throttle cannot bleed
    into other tests if the driver scope is ever widened.

    Args:
        driver: WebDriver instance

    Yields:
        None while the throttle is active.
    """
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
    yield
    driver.execute_cdp_cmd(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "downloadThroughput": -1,
            "uploadThroughput": -1,
            "latency": 0,
        },
    )


def _wrap_find_elements_by_xpath(
    driver: WebDriver, xpath: str
) -> Callable[[], list[WebElement]]:
    """Helper fixture factory for finding elements by xpath.

    Args:
        driver: WebDriver instance
        xpath: xpath string to find elements

    Returns:
        A callable that returns the list of found elements.
    """

    def _finder():
        return driver.find_elements(By.XPATH, xpath)

    return _finder


@pytest.fixture
def progress_dicts(driver: WebDriver) -> Callable[[], list[WebElement]]:
    """For retrieving the list of progress dictionary elements.

    Args:
        driver: WebDriver instance

    Returns:
        A callable that returns the list of progress dictionary elements.
    """
    return _wrap_find_elements_by_xpath(driver, "//*[@id='progress_dicts']/p")


@pytest.fixture
def stream_progress_dicts(driver: WebDriver) -> Callable[[], list[WebElement]]:
    """For retrieving the list of streaming upload progress dictionary elements.

    Args:
        driver: WebDriver instance

    Returns:
        A callable that returns the list of streaming upload progress dictionary elements.
    """
    return _wrap_find_elements_by_xpath(driver, "//*[@id='stream_progress_dicts']/p")


async def poll_for_stopped_progress(
    get_progress_dicts: Callable[[], list[WebElement]],
    iterations: int = 20,
    delay: int | float = 1.0,
    stable_iterations: int = 3,
) -> list[dict]:
    """Poll for progress dictionaries to stop updating.

    Args:
        get_progress_dicts: A callable that returns the list of progress dictionary elements.
        iterations: Maximum number of iterations to poll for.
        delay: Delay in seconds between iterations.
        stable_iterations: Number of consecutive iterations with no new progress dictionaries before considering it stopped.

    Returns:
        The stable list of deserialized progress dicts.

    Raises:
        TimeoutError: If progress dictionaries keep updating beyond the maximum iterations.
    """
    remaining_stable_iterations = stable_iterations
    last_progress_dicts_content = [p.text for p in get_progress_dicts()]
    for _ in range(iterations):
        await asyncio.sleep(delay)
        progress_dicts_content = [p.text for p in get_progress_dicts()]
        if progress_dicts_content == last_progress_dicts_content:
            # Content remains stable, decrement remaining_stable_iterations
            remaining_stable_iterations -= 1
            if remaining_stable_iterations <= 0:
                return [json.loads(t) for t in last_progress_dicts_content]
        else:
            # Progress dicts content changed, we must start over counting stable iterations.
            remaining_stable_iterations = stable_iterations
            last_progress_dicts_content = progress_dicts_content
    msg = f"Progress dictionaries kept updating after {iterations} iterations ({iterations * delay} seconds)."
    raise TimeoutError(msg)


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


def get_upload_box(driver: WebDriver, upload_root_id: str | None = None) -> WebElement:
    """Find the file input belonging to a specific rx.upload.root, by its id.

    When ``upload_root_id`` is None, returns the first ``input[type=file]``
    on the page (the default upload form, which has no id).

    Args:
        driver: WebDriver instance.
        upload_root_id: id of the ``rx.upload.root`` whose file input to return,
            or None for the default (first) upload form.

    Returns:
        The matching file input WebElement.
    """
    if upload_root_id is not None:
        return driver.find_element(
            By.XPATH, f"//*[@id='{upload_root_id}']//input[@type='file']"
        )
    return driver.find_element(By.XPATH, "//input[@type='file']")


@pytest.mark.parametrize("upload_root_id", [None, "secondary"])
def test_upload_file(
    tmp_path,
    upload_file: AppHarness,
    driver: WebDriver,
    progress_dicts: Callable[[], list[WebElement]],
    upload_root_id: str | None,
):
    """Submit a file upload and check that it arrived on the backend.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
        progress_dicts: callable to retrieve progress dictionary elements.
        upload_root_id: ID of the upload root element, or None for the default.
    """
    assert upload_file.app_instance is not None
    poll_for_token(driver, upload_file)
    clear_btn = driver.find_element(By.ID, "clear_uploads")
    clear_btn.click()

    suffix = f"_{upload_root_id}" if upload_root_id else ""

    upload_box = get_upload_box(driver, upload_root_id=upload_root_id)
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

    # Wait for the upload to complete.
    upload_done = driver.find_element(By.ID, "upload_done")
    assert upload_file.poll_for_value(upload_done, exp_not_equal="false") == "true"

    if upload_root_id == "secondary":
        event_order_displayed = driver.find_element(By.ID, "event-order")
        AppHarness.expect(lambda: "chain_event" in event_order_displayed.text)
        final_progress = progress_dicts()
        assert len(final_progress) > 0
        assert json.loads(final_progress[-1].text)["progress"] == 1

    # look up the backend state and assert on uploaded contents
    actual_contents = (rx.get_upload_dir() / exp_name).read_text()
    assert actual_contents == exp_contents


@pytest.mark.asyncio
async def test_upload_file_multiple(tmp_path, upload_file: AppHarness, driver):
    """Submit several file uploads and check that they arrived on the backend.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
    """
    assert upload_file.app_instance is not None
    poll_for_token(driver, upload_file)
    clear_btn = driver.find_element(By.ID, "clear_uploads")
    clear_btn.click()

    upload_box = get_upload_box(driver)
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

    # Wait for the upload to complete.
    upload_done = driver.find_element(By.ID, "upload_done")
    assert upload_file.poll_for_value(upload_done, exp_not_equal="false") == "true"

    for exp_name, exp_content in exp_files.items():
        actual_contents = (rx.get_upload_dir() / exp_name).read_text()
        assert actual_contents == exp_content


@pytest.mark.parametrize("upload_root_id", [None, "secondary"])
def test_clear_files(
    tmp_path, upload_file: AppHarness, driver: WebDriver, upload_root_id: str | None
):
    """Select then clear several file uploads and check that they are cleared.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
        upload_root_id: ID of the upload root element, or None for the default.
    """
    assert upload_file.app_instance is not None
    poll_for_token(driver, upload_file)
    clear_btn = driver.find_element(By.ID, "clear_uploads")
    clear_btn.click()

    suffix = f"_{upload_root_id}" if upload_root_id else ""

    upload_box = get_upload_box(driver, upload_root_id=upload_root_id)
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


@pytest.mark.usefixtures("simulate_slow_network")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "upload_root_id",
        "progress_fixture",
        "exp_name",
        "file_size_bytes",
        "partial_subdir",
    ),
    [
        pytest.param(
            "secondary",
            "progress_dicts",
            "large.txt",
            1024 * 1024,
            None,
            id="buffered",
        ),
        pytest.param(
            "streaming",
            "stream_progress_dicts",
            "cancel_stream.txt",
            2 * 1024 * 1024,
            "streaming",
            id="streaming",
        ),
    ],
)
async def test_cancel_upload(
    request: pytest.FixtureRequest,
    tmp_path,
    upload_file: AppHarness,
    driver: WebDriver,
    upload_root_id: str,
    progress_fixture: str,
    exp_name: str,
    file_size_bytes: int,
    partial_subdir: str | None,
):
    """Submit a large file upload and cancel it.

    Covers both the standard upload form and the streaming-chunk upload form;
    the latter additionally writes a partial file to a subdirectory under
    ``rx.get_upload_dir()`` which is verified to be smaller than the source.

    Args:
        request: pytest request fixture, used to resolve the parametrized progress fixture.
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
        upload_root_id: id of the rx.upload.root component to drive; also the suffix used for its upload/cancel button ids.
        progress_fixture: name of the fixture providing the progress dicts callable.
        exp_name: name of the file to upload.
        file_size_bytes: size of the file to create, in bytes.
        partial_subdir: subdirectory under the upload dir where a partial file is expected, or None if no partial file is written.
    """
    assert upload_file.app_instance is not None
    progress_dicts: Callable[[], list[WebElement]] = request.getfixturevalue(
        progress_fixture
    )
    poll_for_token(driver, upload_file)

    upload_box = get_upload_box(driver, upload_root_id=upload_root_id)
    upload_button = driver.find_element(By.ID, f"upload_button_{upload_root_id}")
    cancel_button = driver.find_element(By.ID, f"cancel_button_{upload_root_id}")

    target_file = tmp_path / exp_name
    with target_file.open("wb") as f:
        f.seek(file_size_bytes)
        f.write(b"0")

    upload_box.send_keys(str(target_file))
    upload_button.click()
    # Check for at least 2 progress updates to ensure the upload is active.
    AppHarness.expect(lambda: len(progress_dicts()) >= 2)
    cancel_button.click()

    # There should never be a final progress record for a cancelled upload.
    for p in await poll_for_stopped_progress(progress_dicts):
        assert p["progress"] != 1

    assert not (rx.get_upload_dir() / exp_name).exists()

    if partial_subdir is not None:
        partial_path = rx.get_upload_dir() / partial_subdir / exp_name
        assert partial_path.exists()
        assert partial_path.stat().st_size < target_file.stat().st_size

    target_file.unlink()


@pytest.mark.asyncio
async def test_upload_chunk_file(tmp_path, upload_file: AppHarness, driver: WebDriver):
    """Submit a streaming upload and check that chunks are processed incrementally."""
    assert upload_file.app_instance is not None
    poll_for_token(driver, upload_file)
    clear_btn = driver.find_element(By.ID, "clear_uploads")
    clear_btn.click()

    upload_box = get_upload_box(driver, upload_root_id="streaming")
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

    AppHarness.expect(
        lambda: (
            "stream1.txt" in completed_files_display.text
            and "stream2.txt" in completed_files_display.text
        )
    )

    # Wait for the upload to complete.
    upload_done = driver.find_element(By.ID, "upload_done")
    assert upload_file.poll_for_value(upload_done, exp_not_equal="false") == "true"

    for exp_name, exp_contents in exp_files.items():
        assert (
            rx.get_upload_dir() / "streaming" / exp_name
        ).read_text() == exp_contents


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
    clear_btn = driver.find_element(By.ID, "clear_uploads")
    clear_btn.click()

    upload_box = get_upload_box(driver, upload_root_id="tertiary")
    assert upload_box
    upload_button = driver.find_element(By.ID, "upload_button_tertiary")
    assert upload_button

    exp_name = "test.txt"
    exp_contents = "test file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    upload_box.send_keys(str(target_file))
    upload_button.click()

    # Wait for the upload to complete.
    upload_done = driver.find_element(By.ID, "upload_done")
    assert upload_file.poll_for_value(upload_done, exp_not_equal="false") == "true"

    # Configure the download directory using CDP.
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(download_dir)},
    )

    downloaded_file = download_dir / exp_name

    # Download via event embedded in frontend code.
    download_frontend = driver.find_element(By.ID, "download-frontend")
    download_frontend.click()
    AppHarness.expect(lambda: downloaded_file.exists())
    assert downloaded_file.read_text() == exp_contents
    downloaded_file.unlink()

    # Download via backend event handler.
    download_backend = driver.find_element(By.ID, "download-backend")
    download_backend.click()
    AppHarness.expect(lambda: downloaded_file.exists())
    assert downloaded_file.read_text() == exp_contents


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
    driver: WebDriver,
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
        driver: WebDriver instance.
        exp_name: filename to upload.
        exp_contents: file contents to upload.
        expect_attachment: whether the response should force a download.
        expected_mime_type: expected Content-Type mime type.
    """
    import httpx

    assert upload_file.app_instance is not None
    poll_for_token(driver, upload_file)
    clear_btn = driver.find_element(By.ID, "clear_uploads")
    clear_btn.click()

    upload_box = get_upload_box(driver, upload_root_id="tertiary")
    upload_button = driver.find_element(By.ID, "upload_button_tertiary")

    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    upload_box.send_keys(str(target_file))
    upload_button.click()

    upload_done = driver.find_element(By.ID, "upload_done")
    assert upload_file.poll_for_value(upload_done, exp_not_equal="false") == "true"

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

    # Configure the download directory using CDP.
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(download_dir)},
    )

    downloaded_file = download_dir / exp_name

    # Navigate to the uploaded HTML file in the browser and verify the script
    # does not execute (Content-Disposition: attachment prevents rendering).
    driver.get(upload_url)
    # If the browser rendered the HTML, an alert('xss') dialog would appear.
    # Verify no alert is present — the file should be downloaded, not rendered.
    with pytest.raises(NoAlertPresentException):
        alert = driver.switch_to.alert
        alert.dismiss()

    # Also verify the file was downloaded with the correct contents.
    AppHarness.expect(lambda: downloaded_file.exists())
    assert downloaded_file.read_text() == exp_contents


def test_on_drop(
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
    poll_for_token(driver, upload_file)
    clear_btn = driver.find_element(By.ID, "clear_uploads")
    clear_btn.click()

    upload_box = get_upload_box(driver, upload_root_id="quaternary")
    assert upload_box

    exp_name = "drop_test.txt"
    exp_contents = "dropped file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    # Simulate file drop by directly setting the file input
    upload_box.send_keys(str(target_file))

    # Wait for the upload to complete.
    upload_done = driver.find_element(By.ID, "upload_done")
    assert upload_file.poll_for_value(upload_done, exp_not_equal="false") == "true"

    def exp_name_in_quaternary():
        quaternary_files = driver.find_element(By.ID, "quaternary_files").text
        if quaternary_files:
            files = json.loads(quaternary_files)
            return exp_name in files
        return False

    # Poll until the file names appear in the display
    AppHarness._poll_for(exp_name_in_quaternary)

    assert exp_name_in_quaternary()
