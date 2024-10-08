"""Integration tests for media components."""

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness


def MediaApp():
    """Reflex app with generated images."""
    import httpx
    from PIL import Image

    import reflex as rx

    class State(rx.State):
        def _blue(self, format=None) -> Image.Image:
            img = Image.new("RGB", (200, 200), "blue")
            if format is not None:
                img.format = format  # type: ignore
            return img

        @rx.var(cache=True)
        def img_default(self) -> Image.Image:
            return self._blue()

        @rx.var(cache=True)
        def img_bmp(self) -> Image.Image:
            return self._blue(format="BMP")

        @rx.var(cache=True)
        def img_jpg(self) -> Image.Image:
            return self._blue(format="JPEG")

        @rx.var(cache=True)
        def img_png(self) -> Image.Image:
            return self._blue(format="PNG")

        @rx.var(cache=True)
        def img_gif(self) -> Image.Image:
            return self._blue(format="GIF")

        @rx.var(cache=True)
        def img_webp(self) -> Image.Image:
            return self._blue(format="WEBP")

        @rx.var(cache=True)
        def img_from_url(self) -> Image.Image:
            img_url = "https://picsum.photos/id/1/200/300"
            img_resp = httpx.get(img_url, follow_redirects=True)
            return Image.open(img_resp)  # type: ignore

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
        )


@pytest.fixture()
def media_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start MediaApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=MediaApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.mark.asyncio
async def test_media_app(media_app: AppHarness):
    """Display images, ensure the data uri mime type is correct and images load.

    Args:
        media_app: harness for MediaApp app
    """
    assert media_app.app_instance is not None, "app is not running"
    driver = media_app.frontend()

    # wait for the backend connection to send the token
    token_input = driver.find_element(By.ID, "token")
    token = media_app.poll_for_value(token_input)
    assert token

    # check out the images
    default_img = driver.find_element(By.ID, "default")
    bmp_img = driver.find_element(By.ID, "bmp")
    jpg_img = driver.find_element(By.ID, "jpg")
    png_img = driver.find_element(By.ID, "png")
    gif_img = driver.find_element(By.ID, "gif")
    webp_img = driver.find_element(By.ID, "webp")
    from_url_img = driver.find_element(By.ID, "from_url")

    def check_image_loaded(img, check_width=" == 200", check_height=" == 200"):
        return driver.execute_script(
            "console.log(arguments); return arguments[1].complete "
            '&& typeof arguments[1].naturalWidth != "undefined" '
            f"&& arguments[1].naturalWidth {check_width} ",
            '&& typeof arguments[1].naturalHeight != "undefined" '
            f"&& arguments[1].naturalHeight {check_height} ",
            img,
        )

    default_img_src = default_img.get_attribute("src")
    assert default_img_src is not None
    assert default_img_src.startswith("data:image/png;base64")
    assert check_image_loaded(default_img)

    bmp_img_src = bmp_img.get_attribute("src")
    assert bmp_img_src is not None
    assert bmp_img_src.startswith("data:image/bmp;base64")
    assert check_image_loaded(bmp_img)

    jpg_img_src = jpg_img.get_attribute("src")
    assert jpg_img_src is not None
    assert jpg_img_src.startswith("data:image/jpeg;base64")
    assert check_image_loaded(jpg_img)

    png_img_src = png_img.get_attribute("src")
    assert png_img_src is not None
    assert png_img_src.startswith("data:image/png;base64")
    assert check_image_loaded(png_img)

    gif_img_src = gif_img.get_attribute("src")
    assert gif_img_src is not None
    assert gif_img_src.startswith("data:image/gif;base64")
    assert check_image_loaded(gif_img)

    webp_img_src = webp_img.get_attribute("src")
    assert webp_img_src is not None
    assert webp_img_src.startswith("data:image/webp;base64")
    assert check_image_loaded(webp_img)

    from_url_img_src = from_url_img.get_attribute("src")
    assert from_url_img_src is not None
    assert from_url_img_src.startswith("data:image/jpeg;base64")
    assert check_image_loaded(
        from_url_img,
        check_width=" == 200",
        check_height=" == 300",
    )
