"""Colors module."""

# Customs colors from /assets/custom-colors.css
from typing import Literal

ColorType = Literal["white", "slate", "violet", "jade", "red"]
ShadeType = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]


def c_color(color: ColorType, shade: ShadeType, alpha: bool = False) -> str:
    """Create a color variable string.

    Returns:
        The component.
    """
    shade_str = str(shade).replace(".", "-")
    return f"var(--c-{color}-{shade_str}{'-a' if alpha else ''})"
