import pytest

try:
    # PIL is only available in python 3.8+
    import numpy as np
    import PIL
    from PIL.Image import Image as Img

    import nextpy as xt
    from nextpy.components.media.image import Image, serialize_image  # type: ignore
    from nextpy.utils.serializers import serialize

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
        image = xt.image(src="pic2.jpeg")
        assert str(image.src) == "{`pic2.jpeg`}"  # type: ignore

    def test_set_src_img(pil_image: Img):
        """Test that setting the src works.

        Args:
            pil_image: The image to serialize.
        """
        image = Image.create(src=pil_image)
        assert str(image.src._var_name) == serialize_image(pil_image)  # type: ignore

    def test_render(pil_image: Img):
        """Test that rendering an image works.

        Args:
            pil_image: The image to serialize.
        """
        image = Image.create(src=pil_image)
        assert image.src._var_is_string  # type: ignore

except ImportError:

    def test_pillow_import():
        """Make sure the Python version is less than 3.8."""
        import sys

        assert sys.version_info < (3, 8)
