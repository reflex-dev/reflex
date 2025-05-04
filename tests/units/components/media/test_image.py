"""""Unit tests for the Image component."""
import numpy as np
import PIL
import pytest
from PIL.Image import Image as Img

import reflex as rx
from reflex.components.core.cond import cond
from reflex.components.next.image import Image
from reflex.utils.serializers import serialize, serialize_image
from reflex.vars.base import Var
from reflex.vars.sequence import StringVar


@pytest.fixture
def pil_image() -> Img:
    """Get an image.

    Returns:
        A random PIL image.
    """
    imarray = np.random.rand(100, 100, 3) * 255
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
    # when using next/image, we explicitly create a _var_is_str Var
    assert str(image.src) in (  # pyright: ignore [reportAttributeAccessIssue]
        '"pic2.jpeg"',
        "'pic2.jpeg'",
        "`pic2.jpeg`",
    )


def test_set_src_img(pil_image: Img):
    """Test that setting the src works.

    Args:
        pil_image: The image to serialize.
    """
    image = Image.create(src=pil_image)
    assert str(image.src._js_expr) == '"' + serialize_image(pil_image) + '"' # pyright: ignore [reportOptionalMemberAccess]


def test_render_no_fallback():
    """Test rendering an image without a fallback."""
    image = Image.create(src="test.png", width=100, height=100)
    rendered = image.render()

    # Check basic tag render
    assert rendered["tag"] == "Image"
    assert rendered["library"] == "next/image"
    assert "onError" not in rendered["props"] # No fallback means no automatic onError handler

    # Check imports and hooks (should NOT include fallback specifics)
    imports = image._get_all_imports()
    hooks = image._get_all_hooks()
    assert "useState" not in imports.get("react", set())
    assert hooks is None or "useState(false)" not in hooks


def test_render_with_fallback():
    """Test rendering an image with a fallback component."""
    fallback_component = rx.text("Image failed to load")
    image = Image.create(
        src="test.png", width=100, height=100, fallback=fallback_component
    )

    # Check imports and hooks (SHOULD include fallback specifics)
    imports = image._get_all_imports()
    hooks = image._get_all_hooks() or ""

    assert "react" in imports
    assert "useState" in imports["react"]
    assert "useState(false)" in hooks

    # Check overall structure is conditional
    rendered = image.render()
    assert rendered["tag"] == "Cond"
    assert isinstance(rendered["cond"], Var)
    assert rendered["cond"]._var_name == "image_error"
    assert rendered["cond"]._var_is_string is False

    # Check the true branch (fallback)
    true_branch = rendered["comp1"]
    assert true_branch["tag"] == "Text"
    assert "Image failed to load" in true_branch["contents"] # type: ignore

    # Check the false branch (original image)
    false_branch = rendered["comp2"]
    assert false_branch["tag"] == "Image"
    assert false_branch["library"] == "next/image"

    # Check that the onError handler is set on the original image tag within the Cond
    assert "onError" in false_branch["props"]
    on_error_handler = false_branch["props"]["onError"]
    assert isinstance(on_error_handler, Var)
    assert on_error_handler._var_name == '() => setImageError(true)'

    # Check that requirements from fallback are merged (in this case, just the text component has basic imports)
    fallback_imports = fallback_component._get_all_imports()
    for lib, fields in fallback_imports.items():
        assert lib in imports
        assert fields.issubset(imports[lib])

    # Test with a fallback that has its own hooks/imports
    # (Using rx.color_mode_button which has internal state)
    complex_fallback = rx.color_mode_button()
    image_complex = Image.create(
        src="test2.png", fallback=complex_fallback
    )
    complex_imports = image_complex._get_all_imports()
    complex_hooks = image_complex._get_all_hooks() or ""
    fallback_hooks = complex_fallback._get_all_hooks() or ""

    assert "useState" in complex_imports.get("react", set()) # From Image fallback
    assert "useColorMode" in complex_imports.get("@chakra-ui/react", set()) # From fallback component
    assert "useState(false)" in complex_hooks # From Image fallback
    assert fallback_hooks in complex_hooks # Hooks from fallback component are included
