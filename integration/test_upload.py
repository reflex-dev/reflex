"""Integration tests for file upload."""

from __future__ import annotations

import asyncio
import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver


def UploadFile():
    """App for testing dynamic routes."""
    from typing import Dict, List

    import reflex as rx

    class UploadState(rx.State):
        _file_data: Dict[str, str] = {}
        event_order: List[str] = []
        progress_dicts: List[dict] = []

        async def handle_upload(self, files: List[rx.UploadFile]):
            for file in files:
                upload_data = await file.read()
                self._file_data[file.filename or ""] = upload_data.decode("utf-8")

        async def handle_upload_secondary(self, files: List[rx.UploadFile]):
            for file in files:
                upload_data = await file.read()
                self._file_data[file.filename or ""] = upload_data.decode("utf-8")
                yield UploadState.chain_event

        def upload_progress(self, progress):
            assert progress
            self.event_order.append("upload_progress")
            self.progress_dicts.append(progress)

        def chain_event(self):
            self.event_order.append("chain_event")

    def index():
        return rx.vstack(
            rx.input(
                value=UploadState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
            rx.heading("Default Upload"),
            rx.upload.root(
                rx.vstack(
                    rx.button("Select File"),
                    rx.text("Drag and drop files here or click to select files"),
                ),
            ),
            rx.button(
                "Upload",
                on_click=lambda: UploadState.handle_upload(rx.upload_files()),  # type: ignore
                id="upload_button",
            ),
            rx.box(
                rx.foreach(
                    rx.selected_files,
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
                on_click=UploadState.handle_upload_secondary(  # type: ignore
                    rx.upload_files(
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
                    UploadState.progress_dicts,  # type: ignore
                    lambda d: rx.text(d.to_string()),
                )
            ),
            rx.button(
                "Cancel",
                on_click=rx.cancel_upload("secondary"),
                id="cancel_button_secondary",
            ),
        )

    app = rx.App(state=rx.State)
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
        app_source=UploadFile,  # type: ignore
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
    token_input = driver.find_element(By.ID, "token")
    assert token_input
    # wait for the backend connection to send the token
    token = upload_file.poll_for_value(token_input)
    assert token is not None
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

    # look up the backend state and assert on uploaded contents
    async def get_file_data():
        return (
            (await upload_file.get_state(substate_token))
            .substates[state_name]
            ._file_data
        )

    file_data = await AppHarness._poll_for_async(get_file_data)
    assert isinstance(file_data, dict)
    assert file_data[exp_name] == exp_contents

    # check that the selected files are displayed
    selected_files = driver.find_element(By.ID, f"selected_files{suffix}")
    assert selected_files.text == exp_name

    state = await upload_file.get_state(substate_token)
    if secondary:
        # only the secondary form tracks progress and chain events
        assert state.substates[state_name].event_order.count("upload_progress") == 1
        assert state.substates[state_name].event_order.count("chain_event") == 1


@pytest.mark.asyncio
async def test_upload_file_multiple(tmp_path, upload_file: AppHarness, driver):
    """Submit several file uploads and check that they arrived on the backend.

    Args:
        tmp_path: pytest tmp_path fixture
        upload_file: harness for UploadFile app.
        driver: WebDriver instance.
    """
    assert upload_file.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input
    # wait for the backend connection to send the token
    token = upload_file.poll_for_value(token_input)
    assert token is not None
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

    time.sleep(0.2)

    # check that the selected files are displayed
    selected_files = driver.find_element(By.ID, "selected_files")
    assert selected_files.text == "\n".join(exp_files)

    # do the upload
    upload_button.click()

    # look up the backend state and assert on uploaded contents
    async def get_file_data():
        return (
            (await upload_file.get_state(substate_token))
            .substates[state_name]
            ._file_data
        )

    file_data = await AppHarness._poll_for_async(get_file_data)
    assert isinstance(file_data, dict)
    for exp_name, exp_contents in exp_files.items():
        assert file_data[exp_name] == exp_contents


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
    token_input = driver.find_element(By.ID, "token")
    assert token_input
    # wait for the backend connection to send the token
    token = upload_file.poll_for_value(token_input)
    assert token is not None

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
    assert selected_files.text == "\n".join(exp_files)

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
    token_input = driver.find_element(By.ID, "token")
    assert token_input
    # wait for the backend connection to send the token
    token = upload_file.poll_for_value(token_input)
    assert token is not None
    state_name = upload_file.get_state_name("_upload_state")
    state_full_name = upload_file.get_full_state_name(["_upload_state"])
    substate_token = f"{token}_{state_full_name}"

    upload_box = driver.find_elements(By.XPATH, "//input[@type='file']")[1]
    upload_button = driver.find_element(By.ID, f"upload_button_secondary")
    cancel_button = driver.find_element(By.ID, f"cancel_button_secondary")

    exp_name = "large.txt"
    target_file = tmp_path / exp_name
    with target_file.open("wb") as f:
        f.seek(1024 * 1024 * 256)
        f.write(b"0")

    upload_box.send_keys(str(target_file))
    upload_button.click()
    await asyncio.sleep(0.3)
    cancel_button.click()

    # look up the backend state and assert on progress
    state = await upload_file.get_state(substate_token)
    assert state.substates[state_name].progress_dicts
    assert exp_name not in state.substates[state_name]._file_data

    target_file.unlink()
