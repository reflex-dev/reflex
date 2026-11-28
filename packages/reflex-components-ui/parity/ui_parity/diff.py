"""Compare two screenshots, a pixel at a time, ignoring anti-aliasing.

The method is pixelmatch's: a perceptual color distance in YIQ space, and a
pixel that differs is set aside when it sits on an anti-aliased edge of either
image, since two renderings of one shape disagree there by nature.
"""

from __future__ import annotations

import dataclasses

import numpy as np
from PIL import Image

# The largest YIQ distance of two colors: black against white.
MAX_DELTA = 35215.0

# How a diff image paints a differing pixel, an anti-aliased one, and one of a
# region only one of the images covers.
DIFFERENT = (255, 0, 0)
ANTIALIASED = (255, 200, 0)

# The compared images are drawn this faint under the marks.
FADE = 0.1


@dataclasses.dataclass(frozen=True)
class ImageDiff:
    """What differs between two images.

    Attributes:
        width: The width of the compared area, the wider of the two images.
        height: The height of the compared area, the taller of the two.
        differing: The pixels that differ, anti-aliased ones left out.
        antialiased: The differing pixels set aside as anti-aliasing.
        image: The reference, faded, with the differing pixels marked.
    """

    width: int
    height: int
    differing: int
    antialiased: int
    image: Image.Image

    @property
    def ratio(self) -> float:
        """The share of the compared area that differs.

        Returns:
            The differing pixels over all pixels, from 0 to 1.
        """
        return self.differing / (self.width * self.height)


def _rgb(image: Image.Image) -> np.ndarray:
    """Read an image as opaque colors, blended with white where transparent.

    Args:
        image: The image.

    Returns:
        The colors as floats, in an array of height by width by 3.
    """
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float64)
    alpha = rgba[..., 3:] / 255.0
    return 255.0 + (rgba[..., :3] - 255.0) * alpha


def _yiq(rgb: np.ndarray) -> np.ndarray:
    """Convert colors to YIQ, where distance follows what an eye sees.

    Args:
        rgb: The colors, in an array whose last axis is red, green and blue.

    Returns:
        The same array with luma, in-phase and quadrature on the last axis.
    """
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return np.stack(
        [
            red * 0.29889531 + green * 0.58662247 + blue * 0.11448223,
            red * 0.59597799 - green * 0.27417610 - blue * 0.32180189,
            red * 0.21147017 - green * 0.52261711 + blue * 0.31114694,
        ],
        axis=-1,
    )


def _has_many_siblings(luma: np.ndarray, x: int, y: int) -> bool:
    """Check whether a pixel is part of a flat area.

    Args:
        luma: The brightness of an image.
        x: The column of the pixel.
        y: The row of the pixel.

    Returns:
        Whether more than two of the pixels around it have its brightness,
        counting the image's border as one.
    """
    height, width = luma.shape
    top, bottom = max(y - 1, 0), min(y + 1, height - 1)
    left, right = max(x - 1, 0), min(x + 1, width - 1)
    on_border = x in (left, right) or y in (top, bottom)
    window = luma[top : bottom + 1, left : right + 1]
    same = int(np.count_nonzero(window == luma[y, x])) - 1
    return same + on_border > 2


def _is_antialiased(luma: np.ndarray, other: np.ndarray, x: int, y: int) -> bool:
    """Check whether a pixel sits on an anti-aliased edge.

    It does when its neighbors hold at most two of its brightness, one clearly
    darker and one clearly brighter, and the darkest or the brightest of them
    belongs to a flat area in both images.

    Args:
        luma: The brightness of the image the pixel is read from.
        other: The brightness of the image it is compared with.
        x: The column of the pixel.
        y: The row of the pixel.

    Returns:
        Whether the pixel is anti-aliasing.
    """
    height, width = luma.shape
    top, bottom = max(y - 1, 0), min(y + 1, height - 1)
    left, right = max(x - 1, 0), min(x + 1, width - 1)
    equal = int(x in (left, right) or y in (top, bottom))
    darkest = brightest = 0.0
    darkest_at = brightest_at = (x, y)
    for row in range(top, bottom + 1):
        for column in range(left, right + 1):
            if row == y and column == x:
                continue
            delta = luma[row, column] - luma[y, x]
            if delta == 0:
                equal += 1
                if equal > 2:
                    return False
            elif delta < darkest:
                darkest, darkest_at = delta, (column, row)
            elif delta > brightest:
                brightest, brightest_at = delta, (column, row)
    if darkest == 0 or brightest == 0:
        return False
    return (
        _has_many_siblings(luma, *darkest_at) and _has_many_siblings(other, *darkest_at)
    ) or (
        _has_many_siblings(luma, *brightest_at)
        and _has_many_siblings(other, *brightest_at)
    )


def diff_images(
    reference: Image.Image,
    candidate: Image.Image,
    threshold: float = 0.01,
    include_antialiasing: bool = False,
) -> ImageDiff:
    """Compare two images.

    Images of different sizes are compared from their top left corner, and
    every pixel only one of them covers differs.

    Args:
        reference: The image the candidate should look like.
        candidate: The image under test.
        threshold: How far a pixel's color may be off before it differs, from
            0 (any difference) to 1 (black against white).
        include_antialiasing: Whether an anti-aliased pixel counts as
            differing.

    Returns:
        The count of differing pixels and an image marking them.
    """
    width = max(reference.width, candidate.width)
    height = max(reference.height, candidate.height)
    shared_width = min(reference.width, candidate.width)
    shared_height = min(reference.height, candidate.height)

    first = _yiq(_rgb(reference))
    second = _yiq(_rgb(candidate))
    delta = first[:shared_height, :shared_width] - second[:shared_height, :shared_width]
    distance = (
        0.5053 * delta[..., 0] ** 2
        + 0.299 * delta[..., 1] ** 2
        + 0.1957 * delta[..., 2] ** 2
    )

    # Faded brightness of the reference, on white where it has no pixel.
    canvas = np.full((height, width, 3), 255.0)
    faded = 255.0 + (first[..., 0] - 255.0) * FADE
    canvas[: reference.height, : reference.width] = faded[..., None]

    different = np.ones((height, width), dtype=bool)
    different[:shared_height, :shared_width] = distance > MAX_DELTA * threshold**2
    antialiased = 0
    if not include_antialiasing:
        first_luma, second_luma = first[..., 0], second[..., 0]
        for y, x in zip(
            *np.nonzero(different[:shared_height, :shared_width]), strict=True
        ):
            # Only where both images have neighbors to read.
            if _is_antialiased(
                first_luma[:shared_height, :shared_width],
                second_luma[:shared_height, :shared_width],
                int(x),
                int(y),
            ) or _is_antialiased(
                second_luma[:shared_height, :shared_width],
                first_luma[:shared_height, :shared_width],
                int(x),
                int(y),
            ):
                different[y, x] = False
                canvas[y, x] = ANTIALIASED
                antialiased += 1
    canvas[different] = DIFFERENT
    return ImageDiff(
        width=width,
        height=height,
        differing=int(np.count_nonzero(different)),
        antialiased=antialiased,
        image=Image.fromarray(canvas.round().astype(np.uint8), "RGB"),
    )
