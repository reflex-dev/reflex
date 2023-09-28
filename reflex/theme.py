import enum

from reflex import constants
from reflex.vars import BaseVar, Var


class Scale(enum.Enum):
    """The scale of the color.
    
    See https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale
    """
    APP_BACKGROUND = 1
    SUBTLE_BACKGROUND = 2
    UI_ELEMENT_BACKGROUND = 3
    HOVERED_UI_ELEMENT_BACKGROUND = 4
    ACTIVE_SELECTED_UI_ELEMENT_BACKGROUND = 5
    SUBTLE_BORDERS_AND_SEPARATORS = 6
    UI_ELEMENT_BORDER_AND_FOCUS_RINGS = 7
    HOVERED_UI_ELEMENT_BORDER = 8
    SOLID_BACKGROUNDS = 9
    HOVERED_SOLID_BACKGROUNDS = 10
    LOW_CONTRAST_TEXT = 11
    HIGH_CONTRAST_TEXT = 12


def accent_color(scale: int | Scale) -> Var:
    if isinstance(scale, Scale):
        scale = scale.value
    return BaseVar.create_safe(
        f"var(--${{{constants.THEME_CONTEXT}?.accentColor}}-{scale})",
    )


def gray_color(scale: int | Scale) -> Var:
    if isinstance(scale, Scale):
        scale = scale.value
    return BaseVar.create_safe(
        f"var(--${{{constants.THEME_CONTEXT}?.grayColor}}-{scale})",
    )

panel_background = BaseVar.create_safe(
    f"${{{constants.THEME_CONTEXT}?.panelBackground}}",
)

scaling = BaseVar.create_safe(
    f"${{{constants.THEME_CONTEXT}?.scaling}}",
)

radius = BaseVar.create_safe(
    f"${{{constants.THEME_CONTEXT}?.radius}}",
)

def size(value: int) -> dict[str, Var]:
    return dict(
        margin=f"var(--space-{value})",
        padding=f"var(--space-{value})",
        border_radius=f"max(var(--radius-{value}), var(--radius-full))",
        custom_attrs={
            "data-radius": radius,
        },
    )