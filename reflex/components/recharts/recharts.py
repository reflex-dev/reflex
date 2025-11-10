"""A component that wraps a recharts lib."""

from typing import Any, Literal

from reflex.components.component import Component, MemoizationLeaf, NoSSRComponent


class Recharts(Component):
    """A component that wraps a recharts lib."""

    library = "recharts@3.4.1"

    def _get_style(self) -> dict:
        return {"wrapperStyle": self.style}


class RechartsCharts(NoSSRComponent, MemoizationLeaf):
    """A component that wraps a recharts lib."""

    library = "recharts@3.4.1"


LiteralAnimationEasing = Literal["ease", "ease-in", "ease-out", "ease-in-out", "linear"]
LiteralIfOverflow = Literal["discard", "hidden", "visible", "extendDomain"]
LiteralShape = Literal[
    "square", "circle", "cross", "diamond", "star", "triangle", "wye"
]
LiteralLineType = Literal["joint", "fitting"]
LiteralOrientation = Literal["top", "bottom", "left", "right", "middle"]
LiteralOrientationLeftRightMiddle = Literal["left", "right", "middle"]
LiteralOrientationTopBottom = Literal["top", "bottom"]
LiteralOrientationLeftRight = Literal["left", "right"]
LiteralOrientationTopBottomLeftRight = Literal["top", "bottom", "left", "right"]
LiteralScale = Literal[
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
LiteralTextAnchor = Literal["start", "middle", "end"]
LiteralLayout = Literal["horizontal", "vertical"]
LiteralPolarRadiusType = Literal["number", "category"]
LiteralGridType = Literal["polygon", "circle"]
LiteralPosition = Literal[
    "top",
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
LiteralIconType = Literal[
    "circle",
    "cross",
    "diamond",
    "line",
    "plainline",
    "rect",
    "square",
    "star",
    "triangle",
    "wye",
]
LiteralLegendType = Literal[
    "circle",
    "cross",
    "diamond",
    "line",
    "plainline",
    "rect",
    "square",
    "star",
    "triangle",
    "wye",
    "none",
]
LiteralLegendAlign = Literal["left", "center", "right"]
LiteralVerticalAlign = Literal["top", "middle", "bottom"]
LiteralStackOffset = Literal["expand", "none", "wiggle", "silhouette"]
LiteralBarChartStackOffset = Literal["expand", "none", "wiggle", "silhouette", "sign"]
LiteralComposedChartBaseValue = Literal["dataMin", "dataMax", "auto"]
LiteralAxisType = Literal["number", "category"]
LiteralCurveType = Literal[
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
LiteralDirection = Literal["x", "y"]
LiteralInterval = Literal["preserveStart", "preserveEnd", "preserveStartEnd"]
LiteralIntervalAxis = Literal[
    "preserveStart", "preserveEnd", "preserveStartEnd", "equidistantPreserveStart"
]
LiteralSyncMethod = Literal["index", "value"]

ACTIVE_DOT_TYPE = bool | dict[str, Any]
