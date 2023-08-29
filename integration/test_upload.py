"""Integration tests for file upload."""
from __future__ import annotations

import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness


def UploadFile():
    """App for testing dynamic routes."""
    import reflex as rx

    class UploadState(rx.State):
        _file_data: dict[str, str] = {}

        async def handle_upload(self, files: list[rx.UploadFile]):
            for file in files:
                upload_data = await file.read()
                self._file_data[file.filename or ""] = upload_data.decode("utf-8")

        @rx.var
        def token(self) -> str:
            return self.get_token()

    def index():
        return rx.vstack(
            rx.input(value=UploadState.token, is_read_only=True, id="token"),
            rx.upload(
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
                    lambda f: rx.text(f),
                ),
                id="selected_files",
            ),
            rx.button(
                "Clear",
                on_click=rx.clear_selected_files,
                id="clear_button",
            ),
        )

    app = rx.App(state=UploadState)
    app.add_page(index)
    app.compile()


@pytest.fixture(scope="session")
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
        assert upload_file.poll_for_clients()
        yield driver
    finally:
        driver.quit()


def test_upload_file(tmp_path, upload_file: AppHarness, driver):
    """Submit a file upload and check that it arrived on the backend.

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

    upload_box = driver.find_element(By.XPATH, "//input[@type='file']")
    assert upload_box
    upload_button = driver.find_element(By.ID, "upload_button")
    assert upload_button

    exp_name = "test.txt"
    exp_contents = "test file contents!"
    target_file = tmp_path / exp_name
    target_file.write_text(exp_contents)

    upload_box.send_keys(str(target_file))
    upload_button.click()

    # look up the backend state and assert on uploaded contents
    backend_state = upload_file.app_instance.state_manager.states[token]
    time.sleep(0.5)
    assert backend_state._file_data[exp_name] == exp_contents

    # check that the selected files are displayed
    selected_files = driver.find_element(By.ID, "selected_files")
    assert selected_files.text == exp_name


def test_upload_file_multiple(tmp_path, upload_file: AppHarness, driver):
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
    backend_state = upload_file.app_instance.state_manager.states[token]
    time.sleep(0.5)
    for exp_name, exp_contents in exp_files.items():
        assert backend_state._file_data[exp_name] == exp_contents


def test_clear_files(tmp_path, upload_file: AppHarness, driver):
    """Select then clear several file uploads and check that they are cleared.

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

    clear_button = driver.find_element(By.ID, "clear_button")
    assert clear_button
    clear_button.click()

    # check that the selected files are cleared
    selected_files = driver.find_element(By.ID, "selected_files")
    assert selected_files.text == ""
