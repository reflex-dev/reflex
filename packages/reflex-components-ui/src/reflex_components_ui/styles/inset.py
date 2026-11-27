"""The look of an inset: content that reaches the edges of its container."""

from typing import Any

from reflex_components_ui.style import ComponentStyles, unchecked

# The container, a card for one, says how far its edges are through the
# `--inset-padding-*`, `--inset-border-width` and `--inset-border-radius`
# custom properties, as it does for Radix Themes.
_SIDES = ("top", "right", "bottom", "left")
_RADIUS = "var(--inset-border-radius-calc)"


def _side(*sides: str, corners: str = "") -> Any:
    """Make the margins and the corners of an inset that reaches some sides.

    Args:
        *sides: The sides the inset reaches.
        corners: The side whose two corners follow the container, ``all`` for
            every corner, or nothing for square corners.

    Returns:
        A negative margin on each of those sides, and the radius of each
        corner.
    """
    style: dict[str, Any] = {
        f"margin_{side}": (
            f"calc(0px - var(--inset-padding-{side}-calc))" if side in sides else "0px"
        )
        for side in _SIDES
    }
    for vertical in ("top", "bottom"):
        for horizontal in ("left", "right"):
            style[f"border_{vertical}_{horizontal}_radius"] = (
                _RADIUS if corners in ("all", vertical, horizontal) else "0px"
            )
    return style


def _clip(border: bool) -> Any:
    """Make the edges an inset reaches to: of the border, or inside it.

    Args:
        border: Whether the border of the container is covered too.

    Returns:
        The distances the margins and the corners are worked out from.
    """
    width = "var(--inset-border-width, 0px)"
    radius = "var(--inset-border-radius, 0px)"
    style = {
        "--inset-border-radius-calc": radius if border else f"calc({radius} - {width})",
    }
    for side in _SIDES:
        padding = f"var(--inset-padding-{side}, 0px)"
        style[f"--inset-padding-{side}-calc"] = (
            f"calc({padding} + {width})" if border else padding
        )
    return style


INSET: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "overflow": "hidden",
    },
    "variants": {
        "clip": {
            "border-box": _clip(border=False),
            "padding-box": _clip(border=True),
        },
        "side": {
            "top": _side("left", "top", "right", corners="top"),
            "bottom": _side("left", "bottom", "right", corners="bottom"),
            "left": _side("top", "left", "bottom", corners="left"),
            "right": _side("top", "right", "bottom", corners="right"),
            "x": _side("left", "right"),
            "y": _side("top", "bottom"),
            "all": _side(*_SIDES, corners="all"),
        },
        # The padding props take two values: none, or the padding of the
        # container, which the inset then has itself.
        **{
            prop: {
                "0": unchecked({f"padding_{side}": "0" for side in sides}),
                "current": unchecked({
                    f"padding_{side}": f"var(--inset-padding-{side})" for side in sides
                }),
            }
            for prop, sides in (
                ("p", _SIDES),
                ("px", ("left", "right")),
                ("py", ("top", "bottom")),
                ("pt", ("top",)),
                ("pr", ("right",)),
                ("pb", ("bottom",)),
                ("pl", ("left",)),
            )
        },
    },
    "defaults": {"clip": "border-box", "side": "all"},
}
