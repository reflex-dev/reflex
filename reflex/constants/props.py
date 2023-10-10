# General
LAYOUT = ["horizontal", "vertical"]

# RECHARTS
ANIMATION_EASING = ["ease", "ease-in", "ease-out", "ease-in-out", "linear"]
IF_OVERFLOW = ["discard", "hidden", "visible", "extendDomain"]
SHAPE = ["square", "circle", "cross", "diamond", "star", "triangle", "wye"]
LINE_TYPE = ["joint", "fitting"]
ORIENTATION = ["top", "bottom", "left", "right", "middle"]
ORIENTATION_LEFT_RIGHT_MIDDLE = ORIENTATION[1:]
ORIENTATION_TOP_BOTTOM = ORIENTATION[:1]
ORIENTATION_TOP_BOTTOM_LEFT_RIGHT = ORIENTATION_LEFT_RIGHT_MIDDLE[:-1]
SCALE = [
    "auto",
    "linear",
    "pow",
    "sqrt",
    "log",
    "identity",
    "time",
    "band",
    "point",
    "ordinal",
    "quantile",
    "quantize",
    "utc",
    "sequential",
    "threshold",
]

POLAR_RAIUS_TYPE = ["number", "category"]
GRID_TYPE = ["polygon", "circle"]
POSITION = [
    "left",
    "right",
    "bottom",
    "inside",
    "outside",
    "insideLeft",
    "insideRight",
    "insideTop",
    "insideBottom",
    "insideTopLeft",
    "insideBottomLeft",
    "insideTopRight",
    "insideBottomRight",
    "insideStart",
    "insideEnd",
    "end",
    "center",
]
ICON_TYPE = [
    "line",
    "plainline",
    "square",
    "rect",
    "circle",
    "cross",
    "diamond",
    "star",
    "triangle",
    "wye",
]
LEGEND_TYPE = [*ICON_TYPE, "none"]
LEGEND_ALIGN = ["left", "center", "right"]
VERTICAL_ALIGN = ["top", "middle", "bottom"]
STACK_OFFSET = ["expand", "none", "wiggle", "silhouette"]
BAR_CHART_STACK_OFFSET = [*STACK_OFFSET, "sign"]
COMPOSED_CHART_BASE_VALUE = ["dataMin", "dataMax", "auto"]
AXIS_TYPE = ["number", "category"]
AREA_TYPE = [
    "basis",
    "basisClosed",
    "basisOpen",
    "bumpX",
    "bumpY",
    "bump",
    "linear",
    "linearClosed",
    "natural",
    "monotoneX",
    "monotoneY",
    "monotone",
    "step",
    "stepBefore",
    "stepAfter",
]
DIRECTION = ["x", "y", "both"]
INTERVAL = ["preserveStart", "preserveEnd", "preserveStartEnd"]

# CHAKRA
VARIANT = ["solid", "subtle", "outline"]
DIVIDER_VARIANT = ["solid", "dashed"]
THEME = ["light", "dark"]
TAG_COLOR_SCHEME = [
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
TABS_ALIGN = ["center", "end", "start"]
TABS_VARIANT = [
    "line",
    "enclosed",
    "enclosed-colored",
    "soft-rounded",
    "solid-rounded",
    "unstyled",
]
COLOR_SCHEME = [
    *TAG_COLOR_SCHEME,
    "whiteAlpha",
    "blackAlpha",
    "linkedin",
    "facebook",
    "messenger",
    "whatsapp",
    "twitter",
    "telegram",
]
STATUS = ["success", "info", "warning", "error"]
ALERT_VARIANT = ["subtle", "left-accent", "top-accent", "solid"]
BUTTON_VARIANT = ["outline", "solid", "link", "unstyled"]
SPINNER_PLACEMENT = ["start", "end"]
LANGUAGE = [
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
INPUT_VARIANT = ["outline", "filled", "flushed", "unstyled"]
NUMBER_INPUT_MODE = [
    "text",
    "search",
    "none",
    "tel",
    "url",
    "email",
    "numeric",
    "decimal",
]
CHAKRA_DIRECTION = ["ltr", "rtl"]
CARD_VARIANT = ["outline", "filled", "elevated", "unstyled"]
STACK_DIRECTION = ["row", "column"]
IMAGE_LOADING = ["eager", "lazy"]
TAG_SIZE = ["sm", "md", "lg"]
SPINNER_SIZE = [*TAG_SIZE, "xs"]
AVATAR_SIZES = [*TAG_SIZE, "xs", "2xl", "full", "2xs"]
# Applies to AlertDialog and Modal
ALERT_DIALOG_SIZES = [*AVATAR_SIZES[:-1], "3xl", "4xl", "5xl", "6xl"]
DRAWER_SIZE = [*SPINNER_SIZE, "xl", "full"]

MENU_STRATEGY = ["fixed", "absolute"]
MENU_OPTION = ["checkbox", "radio"]
