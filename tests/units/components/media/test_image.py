import numpy as np
import PIL
import pytest
from PIL.Image import Image as Img

import reflex as rx
from reflex.components.next.image import Image  # type: ignore
from reflex.utils.serializers import serialize, serialize_image
from reflex.vars.sequence import StringVar


@pytest.fixture
def pil_image() -> Img:
    """Get an image.

    Returns:
        A random PIL image.
    """
    imarray = np.random.rand(100, 100, 3) * 255
    return PIL.Image.fromarray(imarray.astype("uint8")).convert("RGBA")  # type: ignore


def test_serialize_image(pil_image: Img):
    """Test that serializing an image works.

    Args:
        pil_image: The image to serialize.
    """
    data = serialize(pil_image)
    assert isinstance(data, str)
    assert data == serialize_image(pil_image)
    assert data.startswith("data:image/png;base64,")


def test_set_src_str():
    """Test that setting the src works."""
    image = rx.image(src="pic2.jpeg")
    # when using next/image, we explicitly create a _var_is_str Var
    assert str(image.src) in (  # type: ignore
        '"pic2.jpeg"',
        "'pic2.jpeg'",
        "`pic2.jpeg`",
    )
    # For plain rx.el.img, an explicit var is not created, so the quoting happens later
    # assert str(image.src) == "pic2.jpeg"  # type: ignore


def test_set_src_img(pil_image: Img):
    """Test that setting the src works.

    Args:
        pil_image: The image to serialize.
    """
    image = Image.create(src=pil_image)
    assert str(image.src._js_expr) == '"' + serialize_image(pil_image) + '"'  # type: ignore


def test_render(pil_image: Img):
    """Test that rendering an image works.

    Args:
        pil_image: The image to serialize.
    """
    image = Image.create(src=pil_image)
    assert isinstance(image.src, StringVar)  # type: ignore
