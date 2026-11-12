"""Integration test for ``rx.download`` with inline data.

iOS WebKit ignores the ``download`` attribute of ``data:`` urls and only shows
the file, so data has to be saved through a ``blob:`` url. The page runs under a
``connect-src`` policy that does not allow ``data:``, so the frontend has to
decode the data itself rather than fetch it.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DownloadApp():
    """App downloading inline data from the frontend and from a backend event."""
    import reflex as rx

    class State(rx.State):
        text: str = "var;text#%41 ä"
        base64_url: str = "data:text/plain;base64,aGk%3D#part"
        text_url: str = "data:text/plain,a%20b%FF#part"

        @rx.event
        def download_bytes(self):
            return rx.download(data=b"backend,bytes\n", filename="backend.csv")

    @rx.page("/")
    def index():
        return rx.box(
            rx.input(
                value=State.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button(
                "text",
                on_click=rx.download(data="frontend;text#%41", filename="frontend.txt"),
                id="download-text",
            ),
            rx.button(
                "var",
                on_click=rx.download(data=State.text, filename="var.txt"),
                id="download-var",
            ),
            rx.button(
                "base64 url",
                on_click=rx.download(data=State.base64_url, filename="base64.txt"),
                id="download-base64-url",
            ),
            rx.button(
                "text url",
                on_click=rx.download(data=State.text_url, filename="text.txt"),
                id="download-text-url",
            ),
            rx.button("bytes", on_click=State.download_bytes, id="download-bytes"),
        )

    app = rx.App(  # noqa: F841
        head_components=[
            rx.el.meta(
                http_equiv="Content-Security-Policy",
                content="connect-src 'self' http: ws:",
            )
        ]
    )


@pytest.fixture(scope="module")
def download_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start DownloadApp via AppHarness.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("download_app"),
        app_source=DownloadApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.mark.parametrize(
    ("button_id", "filename", "content"),
    [
        ("download-text", "frontend.txt", b"frontend;text#%41"),
        ("download-var", "var.txt", '"var;text#%41 \u00e4"'.encode()),
        ("download-base64-url", "base64.txt", b"hi"),
        ("download-text-url", "text.txt", b"a b\xff"),
        ("download-bytes", "backend.csv", b"backend,bytes\n"),
    ],
)
def test_download_data_through_blob_url(
    download_app: AppHarness,
    page: Page,
    button_id: str,
    filename: str,
    content: bytes,
):
    """Inline data downloads from a blob: url with its file name and content.

    The page runs under a ``connect-src`` policy that blocks fetching ``data:``
    urls.

    Args:
        download_app: AppHarness running the test app.
        page: Playwright page.
        button_id: The id of the button that starts the download.
        filename: The expected file name.
        content: The expected file content.
    """
    assert download_app.frontend_url is not None

    page.goto(download_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    with page.expect_download() as download_info:
        page.click(f"#{button_id}")
    download = download_info.value

    assert download.url.startswith("blob:")
    assert download.suggested_filename == filename
    assert Path(download.path()).read_bytes() == content
