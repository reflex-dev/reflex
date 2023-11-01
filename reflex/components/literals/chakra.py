from typing import Literal

LiteralColorScheme = Literal[
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "teal",
    "blue",
    "cyan",
    "purple",
    "pink",
    "whiteAlpha",
    "blackAlpha",
    "linkedin",
    "facebook",
    "messenger",
    "whatsapp",
    "twitter",
    "telegram",
]

LiteralVariant = Literal["solid", "subtle", "outline"]
LiteralDividerVariant = Literal["solid", "dashed"]

LiteralTagColorScheme = Literal[
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "teal",
    "blue",
    "cyan",
    "purple",
    "pink",
]
LiteralTagAlign = Literal["center", "end", "start"]
LiteralTabsVariant = Literal[
    "line",
    "enclosed",
    "enclosed-colored",
    "soft-rounded",
    "solid-rounded",
    "unstyled",
]

LiteralStatus = Literal["success", "info", "warning", "error"]
LiteralAlertVariant = Literal["subtle", "left-accent", "top-accent", "solid"]
LiteralButtonVariant = Literal["ghost", "outline", "solid", "link", "unstyled"]
LiteralSpinnerPlacement = Literal["start", "end"]
LiteralLanguage = Literal[
    "en",
    "da",
    "de",
    "es",
    "fr",
    "ja",
    "ko",
    "pt_br",
    "ru",
    "zh_cn",
    "ro",
    "pl",
    "ckb",
    "lv",
    "se",
    "ua",
    "he",
    "it",
]

LiteralInputVariant = Literal["outline", "filled", "flushed", "unstyled"]
LiteralInputNumberMode = [
    "text",
    "search",
    "none",
    "tel",
    "url",
    "email",
    "numeric",
    "decimal",
]
LiteralChakraDirection = Literal["ltr", "rtl"]
LiteralCardVariant = Literal["outline", "filled", "elevated", "unstyled"]
LiteralStackDirection = Literal["row", "column"]
LiteralImageLoading = Literal["eager", "lazy"]
LiteralTagSize = Literal["sm", "md", "lg"]
LiteralSpinnerSize = Literal[Literal[LiteralTagSize], "xs", "xl"]
LiteralAvatarSize = Literal[Literal[LiteralTagSize], "xl", "xs", "2xl", "full", "2xs"]
LiteralButtonSize = Literal["sm", "md", "lg", "xs"]
# Applies to AlertDialog and Modal
LiteralAlertDialogSize = Literal[
    "sm", "md", "lg", "xs", "2xl", "full", "3xl", "4xl", "5xl", "6xl"
]
LiteralDrawerSize = Literal[Literal[LiteralSpinnerSize], "xl", "full"]

LiteralMenuStrategy = Literal["fixed", "absolute"]
LiteralMenuOption = Literal["checkbox", "radio"]
LiteralPopOverTrigger = Literal["click", "hover"]

LiteralHeadingSize = Literal["lg", "md", "sm", "xs", "xl", "2xl", "3xl", "4xl"]
