import numpy as np
import PIL
import pytest
from PIL.Image import Image as Img

import reflex as rx
from reflex.utils.serializers import serialize, serialize_image


@pytest.fixture
def pil_image() -> Img:
    """Get an image.

    Returns:
        A random PIL image.
    """
    rng = np.random.default_rng()
    imarray = rng.random((100, 100, 3)) * 255
    return PIL.Image.fromarray(imarray.astype("uint8")).convert("RGBA")  # pyright: ignore [reportAttributeAccessIssue]


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
    assert str(image.src) == '"pic2.jpeg"'  # pyright: ignore [reportAttributeAccessIssue]
