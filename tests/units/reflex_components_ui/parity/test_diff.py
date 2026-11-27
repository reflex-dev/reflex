"""Tests for the image diff of the parity harness."""

from collections.abc import Callable

import numpy as np
import pytest
from PIL import Image
from ui_parity.diff import ANTIALIASED, DIFFERENT, ImageDiff, diff_images

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
# How the diff image draws black: the reference faded to a tenth.
FADED_BLACK = (230, 230, 230)

Color = tuple[int, int, int]


def fixture(width: int, height: int, color: Callable[[int, int], Color]) -> Image.Image:
    """Draw a fixture image.

    Args:
        width: The width of the image.
        height: The height of the image.
        color: The color of the pixel at a column and a row.

    Returns:
        The image.
    """
    image = Image.new("RGB", (width, height))
    image.putdata([color(x, y) for y in range(height) for x in range(width)])
    return image


def pixels(image: Image.Image) -> list[Color]:
    """Read the colors of an image.

    Args:
        image: The image.

    Returns:
        The color of each pixel, row by row.
    """
    return [tuple(color) for row in np.asarray(image).tolist() for color in row]


def square(left: int) -> Image.Image:
    """Draw a black square of 4 pixels on a white image of 10.

    Args:
        left: The first column of the square.

    Returns:
        The image.
    """
    return fixture(
        10,
        10,
        lambda x, y: BLACK if left <= x < left + 4 and 2 <= y < 6 else WHITE,
    )


def numbers(diff: ImageDiff) -> tuple[int, int, int, int]:
    """Get the counts of a diff.

    Args:
        diff: The diff.

    Returns:
        The width, the height, the differing and the anti-aliased pixels.
    """
    return (diff.width, diff.height, diff.differing, diff.antialiased)


def test_equal_images_do_not_differ():
    diff = diff_images(square(2), square(2), threshold=0)
    assert numbers(diff) == (10, 10, 0, 0)
    assert diff.ratio == 0
    # The reference, faded, and no mark.
    assert pixels(diff.image) == [
        FADED_BLACK if 2 <= x < 6 and 2 <= y < 6 else WHITE
        for y in range(10)
        for x in range(10)
    ]


def test_moved_shape_differs_where_it_left_and_where_it_arrived():
    diff = diff_images(square(2), square(3))
    assert numbers(diff) == (10, 10, 8, 0)
    assert diff.ratio == pytest.approx(0.08)
    assert pixels(diff.image) == [
        DIFFERENT
        if x in (2, 6) and 2 <= y < 6
        else FADED_BLACK
        if 2 <= x < 6 and 2 <= y < 6
        else WHITE
        for y in range(10)
        for x in range(10)
    ]


def test_antialiased_edge_is_set_aside():
    hard = fixture(7, 7, lambda x, y: BLACK if x < 3 else WHITE)
    soft = fixture(7, 7, lambda x, y: BLACK if x < 3 else GRAY if x == 3 else WHITE)
    diff = diff_images(hard, soft)
    assert numbers(diff) == (7, 7, 0, 7)
    assert pixels(diff.image) == [
        FADED_BLACK if x < 3 else ANTIALIASED if x == 3 else WHITE
        for y in range(7)
        for x in range(7)
    ]
    # The same pixels count when anti-aliasing is not ignored.
    assert numbers(diff_images(hard, soft, include_antialiasing=True)) == (7, 7, 7, 0)


def test_threshold_is_the_color_distance_that_counts():
    gray = Image.new("RGB", (4, 4), (100, 100, 100))
    near = Image.new("RGB", (4, 4), (102, 102, 102))
    far = Image.new("RGB", (4, 4), (103, 103, 103))
    assert numbers(diff_images(gray, near, threshold=0)) == (4, 4, 16, 0)
    assert numbers(diff_images(gray, near, threshold=0.01)) == (4, 4, 0, 0)
    assert numbers(diff_images(gray, far, threshold=0.01)) == (4, 4, 16, 0)


def test_images_of_different_sizes_differ_where_only_one_reaches():
    diff = diff_images(Image.new("RGB", (4, 4), WHITE), Image.new("RGB", (6, 5), WHITE))
    assert numbers(diff) == (6, 5, 14, 0)
    assert pixels(diff.image) == [
        WHITE if x < 4 and y < 4 else DIFFERENT for y in range(5) for x in range(6)
    ]
