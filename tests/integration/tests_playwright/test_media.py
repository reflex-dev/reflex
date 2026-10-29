"""Integration tests for media components."""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def MediaApp():
    """Reflex app with generated images."""
    import io

    import httpx
    from PIL import Image

    import reflex as rx

    class State(rx.State):
        def _blue(self, format=None) -> Image.Image:
            img = Image.new("RGB", (200, 200), "blue")
            if format is not None:
                img.format = format
            return img

        @rx.var
        def img_default(self) -> Image.Image:
            return self._blue()

        @rx.var
        def img_bmp(self) -> Image.Image:
            return self._blue(format="BMP")

        @rx.var
        def img_jpg(self) -> Image.Image:
            return self._blue(format="JPEG")

        @rx.var
        def img_png(self) -> Image.Image:
            return self._blue(format="PNG")

        @rx.var
        def img_gif(self) -> Image.Image:
            return self._blue(format="GIF")

        @rx.var
        def img_webp(self) -> Image.Image:
            return self._blue(format="WEBP")

        @rx.var
        def img_from_url(self) -> Image.Image:
            img_url = "https://raw.githubusercontent.com/reflex-dev/reflex/dd96aea556948ea95217ef1d8b5431546dc58363/docs/images/reflex-image-generation-app.png"
            img_resp = httpx.get(img_url, follow_redirects=True)
            return Image.open(io.BytesIO(img_resp.content))

        @rx.var
        def generated_image(self) -> str:
            img = Image.new("RGB", (150, 150), "red")
            upload_dir = rx.get_upload_dir()
            upload_dir.mkdir(parents=True, exist_ok=True)
            img.save(upload_dir / "generated.png")
            return "generated.png"

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                value=State.router.session.client_token, read_only=True, id="token"
            ),
            rx.image(src=State.img_default, alt="Default image", id="default"),
            rx.image(src=State.img_bmp, alt="BMP image", id="bmp"),
            rx.image(src=State.img_jpg, alt="JPG image", id="jpg"),
            rx.image(src=State.img_png, alt="PNG image", id="png"),
            rx.image(src=State.img_gif, alt="GIF image", id="gif"),
            rx.image(src=State.img_webp, alt="WEBP image", id="webp"),
            rx.image(src=State.img_from_url, alt="Image from URL", id="from_url"),
            rx.image(
                src=rx.get_upload_url(State.generated_image),
                alt="Uploaded image",
                id="uploaded",
            ),
        )


@pytest.fixture
def media_app(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> Generator[AppHarness, None, None]:
    """Start the media app with an isolated upload directory.

    Yields:
        The running app harness.
    """
    monkeypatch.setenv("REFLEX_UPLOADED_FILES_DIR", str(tmp_path / "uploads"))

    with AppHarness.create(
        root=tmp_path,
        app_source=MediaApp,
    ) as harness:
        yield harness


def test_media_app(media_app: AppHarness, page: Page) -> None:
    """Verify image MIME types, upload URLs, and decoded dimensions."""
    assert media_app.app_instance is not None, "app is not running"
    assert media_app.frontend_url is not None
    page.goto(media_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    image_data = {
        "default": ("image/png", 200, 200),
        "bmp": ("image/bmp", 200, 200),
        "jpg": ("image/jpeg", 200, 200),
        "png": ("image/png", 200, 200),
        "gif": ("image/gif", 200, 200),
        "webp": ("image/webp", 200, 200),
        "from_url": ("image/png", 1280, 733),
        "uploaded": ("generated.png", 150, 150),
    }
    for image_id, (src_part, width, height) in image_data.items():
        image = page.locator(f"#{image_id}")
        expect(image).to_have_attribute("src", re.compile(re.escape(src_part)))
        page.wait_for_function(
            "([id, width, height]) => {"
            " const image = document.getElementById(id);"
            " return image?.complete && image.naturalWidth === width"
            " && image.naturalHeight === height;"
            "}",
            arg=[image_id, width, height],
        )
