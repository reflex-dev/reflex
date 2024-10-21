"""A component that wraps a recharts lib."""

from typing import Dict, Literal

from reflex.components.component import Component, MemoizationLeaf, NoSSRComponent
from reflex.utils import console


class Recharts(Component):
    """A component that wraps a recharts lib."""

    library = "recharts@2.13.0"

    def render(self) -> Dict:
        """Render the tag.

        Returns:
            The rendered tag.
        """
        tag = super().render()
        if any(p.startswith("css") for p in tag["props"]):
            console.warn(
                f"CSS props do not work for {self.__class__.__name__}. Consult docs to style it with its own prop."
            )
        tag["props"] = [p for p in tag["props"] if not p.startswith("css")]
        return tag


class RechartsCharts(NoSSRComponent, MemoizationLeaf):
    """A component that wraps a recharts lib."""

    library = "recharts@2.13.0"


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
LiteralLegendType = Literal[
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
    "none",
]
LiteralLegendAlign = Literal["left", "center", "right"]
LiteralVerticalAlign = Literal["top", "middle", "bottom"]
LiteralStackOffset = Literal["expand", "none", "wiggle", "silhouette"]
LiteralBarChartStackOffset = Literal["expand", "none", "wiggle", "silhouette", "sign"]
LiteralComposedChartBaseValue = Literal["dataMin", "dataMax", "auto"]
LiteralAxisType = Literal["number", "category"]
LiteralAreaType = Literal[
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
