"""Literals used by radix components."""
from typing import Literal

# base
LiteralAlign = Literal["start", "center", "end", "baseline", "stretch"]
LiteralJustify = Literal["start", "center", "end", "between"]
LiteralSize = Literal["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
LiteralVariant = Literal["solid", "soft", "outline", "ghost"]
LiteralAccentColor = Literal[
    "tomato",
    "red",
    "ruby",
    "crimson",
    "pink",
    "plum",
    "purple",
    "violet",
    "iris",
    "indigo",
    "blue",
    "cyan",
    "teal",
    "jade",
    "green",
    "grass",
    "brown",
    "orange",
    "sky",
    "mint",
    "lime",
    "yellow",
    "amber",
    "gold",
    "bronze",
    "gray",
]
LiteralAppearance = Literal["inherit", "light", "dark"]
LiteralGrayColor = Literal["gray", "mauve", "slate", "sage", "olive", "sand", "auto"]
LiteralPanelBackground = Literal["solid", "transparent"]
LiteralRadius = Literal["none", "small", "medium", "large", "full"]
LiteralScaling = Literal["90%", "95%", "100%", "105%", "110%"]


# components
LiteralButtonSize = Literal["1", "2", "3", "4"]
LiteralSwitchSize = Literal["1", "2", "3", "4"]
LiteralTextFieldSize = Literal["1", "2", "3"]
LiteralTextFieldVariant = Literal["classic", "surface", "soft"]

# layout
LiteralBoolNumber = Literal["0", "1"]
LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]
LiteralFlexDisplay = Literal["none", "inline-flex", "flex"]
LiteralFlexWrap = Literal["nowrap", "wrap", "wrap-reverse"]
LiteralGridDisplay = Literal["none", "inline-grid", "grid"]
LiteralGridFlow = Literal["row", "column", "dense", "row-dense", "column-dense"]
LiteralContainerSize = Literal["1", "2", "3", "4"]
LiteralSectionSize = Literal["1", "2", "3"]

# typography
LiteralTextWeight = Literal["light", "regular", "medium", "bold"]
LiteralTextAlign = Literal["left", "center", "right"]
LiteralTextSize = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]
LiteralTextTrim = Literal["normal", "start", "end", "both"]
LiteralLinkUnderline = Literal["auto", "hover", "always"]
