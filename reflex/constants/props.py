
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

LAYOUT = ["horizontal", "vertical"]

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
    "stepBeffore",
    "stepAfter",
]

DIRECTION = ["x", "y", "both"]

INTERVAL = ["preserveStart", "preserveEnd", "preserveStartEnd"]
