"""Integration tests for media components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Locator, Page

from reflex.testing import AppHarness

from . import utils


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
            img_url = "https://picsum.photos/id/1/200/300"
            img_resp = httpx.get(img_url, follow_redirects=True)
            img_bytes = img_resp.content
            return Image.open(io.BytesIO(img_bytes))

        @rx.var
        def generated_image(self) -> str:
            # Generate a 150x150 red PNG and write it to the upload directory.
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
                value=State.router.session.client_token,
                read_only=True,
                id="token",
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


def check_image_loaded(
    page: Page, img: Locator, expected_width: int = 200, expected_height: int = 200
) -> bool:
    """Check whether an image element has fully loaded with expected dimensions.

    Args:
        page: Playwright page.
        img: Locator for the image element.
        expected_width: Expected natural width.
        expected_height: Expected natural height.

    Returns:
        True if the image is complete and matches the expected dimensions.
    """
    return img.evaluate(
        """(el, [w, h]) => (
            el.complete
            && typeof el.naturalWidth != 'undefined'
            && el.naturalWidth === w
            && typeof el.naturalHeight != 'undefined'
            && el.naturalHeight === h
        )""",
        [expected_width, expected_height],
    )


@pytest.fixture(scope="module")
def media_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start MediaApp app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    tmp_path = tmp_path_factory.mktemp("media_app")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("REFLEX_UPLOADED_FILES_DIR", str(tmp_path / "uploads"))

        with AppHarness.create(
            root=tmp_path,
            app_source=MediaApp,
        ) as harness:
            yield harness


def test_media_app(media_app: AppHarness, page: Page):
    """Display images, ensure the data uri mime type is correct and images load.

    Args:
        media_app: harness for MediaApp app
        page: Playwright page.
    """
    assert media_app.frontend_url is not None
    page.goto(media_app.frontend_url)

    # wait for the backend connection to send the token
    utils.poll_for_token(page)

    # check out the images
    default_img = page.locator("#default")
    bmp_img = page.locator("#bmp")
    jpg_img = page.locator("#jpg")
    png_img = page.locator("#png")
    gif_img = page.locator("#gif")
    webp_img = page.locator("#webp")
    from_url_img = page.locator("#from_url")
    uploaded_img = page.locator("#uploaded")

    default_img_src = default_img.get_attribute("src")
    assert default_img_src is not None
    assert default_img_src.startswith("data:image/png;base64")
    assert check_image_loaded(page, default_img)

    bmp_img_src = bmp_img.get_attribute("src")
    assert bmp_img_src is not None
    assert bmp_img_src.startswith("data:image/bmp;base64")
    assert check_image_loaded(page, bmp_img)

    jpg_img_src = jpg_img.get_attribute("src")
    assert jpg_img_src is not None
    assert jpg_img_src.startswith("data:image/jpeg;base64")
    assert check_image_loaded(page, jpg_img)

    png_img_src = png_img.get_attribute("src")
    assert png_img_src is not None
    assert png_img_src.startswith("data:image/png;base64")
    assert check_image_loaded(page, png_img)

    gif_img_src = gif_img.get_attribute("src")
    assert gif_img_src is not None
    assert gif_img_src.startswith("data:image/gif;base64")
    assert check_image_loaded(page, gif_img)

    webp_img_src = webp_img.get_attribute("src")
    assert webp_img_src is not None
    assert webp_img_src.startswith("data:image/webp;base64")
    assert check_image_loaded(page, webp_img)

    from_url_img_src = from_url_img.get_attribute("src")
    assert from_url_img_src is not None
    assert from_url_img_src.startswith("data:image/jpeg;base64")
    assert check_image_loaded(page, from_url_img, expected_height=300)

    uploaded_img_src = uploaded_img.get_attribute("src")
    assert uploaded_img_src is not None
    assert "generated.png" in uploaded_img_src
    assert check_image_loaded(page, uploaded_img, 150, 150)
