"""Integration tests for media components."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

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
    driver, img, expected_width: int = 200, expected_height: int = 200
) -> bool:
    """Check whether an image element has fully loaded with expected dimensions.

    Args:
        driver: WebDriver instance.
        img: The image WebElement.
        expected_width: Expected natural width.
        expected_height: Expected natural height.

    Returns:
        True if the image is complete and matches the expected dimensions.
    """
    return driver.execute_script(
        "return arguments[0].complete "
        '&& typeof arguments[0].naturalWidth != "undefined" '
        "&& arguments[0].naturalWidth === arguments[1] "
        '&& typeof arguments[0].naturalHeight != "undefined" '
        "&& arguments[0].naturalHeight === arguments[2]",
        img,
        expected_width,
        expected_height,
    )


@pytest.fixture
def media_app(tmp_path, monkeypatch) -> Generator[AppHarness, None, None]:
    """Start MediaApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture
        monkeypatch: pytest monkeypatch fixture

    Yields:
        running AppHarness instance
    """
    monkeypatch.setenv("REFLEX_UPLOADED_FILES_DIR", str(tmp_path / "uploads"))

    with AppHarness.create(
        root=tmp_path,
        app_source=MediaApp,
    ) as harness:
        yield harness


def test_media_app(media_app: AppHarness):
    """Display images, ensure the data uri mime type is correct and images load.

    Args:
        media_app: harness for MediaApp app
    """
    assert media_app.app_instance is not None, "app is not running"
    driver = media_app.frontend()

    # wait for the backend connection to send the token
    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )
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
    uploaded_img = driver.find_element(By.ID, "uploaded")

    default_img_src = default_img.get_attribute("src")
    assert default_img_src is not None
    assert default_img_src.startswith("data:image/png;base64")
    assert check_image_loaded(driver, default_img)

    bmp_img_src = bmp_img.get_attribute("src")
    assert bmp_img_src is not None
    assert bmp_img_src.startswith("data:image/bmp;base64")
    assert check_image_loaded(driver, bmp_img)

    jpg_img_src = jpg_img.get_attribute("src")
    assert jpg_img_src is not None
    assert jpg_img_src.startswith("data:image/jpeg;base64")
    assert check_image_loaded(driver, jpg_img)

    png_img_src = png_img.get_attribute("src")
    assert png_img_src is not None
    assert png_img_src.startswith("data:image/png;base64")
    assert check_image_loaded(driver, png_img)

    gif_img_src = gif_img.get_attribute("src")
    assert gif_img_src is not None
    assert gif_img_src.startswith("data:image/gif;base64")
    assert check_image_loaded(driver, gif_img)

    webp_img_src = webp_img.get_attribute("src")
    assert webp_img_src is not None
    assert webp_img_src.startswith("data:image/webp;base64")
    assert check_image_loaded(driver, webp_img)

    from_url_img_src = from_url_img.get_attribute("src")
    assert from_url_img_src is not None
    assert from_url_img_src.startswith("data:image/jpeg;base64")
    assert check_image_loaded(driver, from_url_img, expected_height=300)

    uploaded_img_src = uploaded_img.get_attribute("src")
    assert uploaded_img_src is not None
    assert "generated.png" in uploaded_img_src
    assert check_image_loaded(driver, uploaded_img, 150, 150)
