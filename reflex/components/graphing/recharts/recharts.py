"""A component that wraps a recharts lib."""
from typing import Literal

from reflex.components.component import Component, NoSSRComponent
from reflex.constants import MemoizationDisposition, MemoizationMode


class Recharts(Component):
    """A component that wraps a recharts lib."""

    library = "recharts@2.8.0"


class RechartsMemoizationLeafMixin(Component):
    """A mixin for Recharts components that must not memoize their children separately.

    This includes all chart types and ResponsiveContainer itself.
    """

    _memoization_mode = MemoizationMode(recursive=False)

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a Recharts chart container component (mixin).

        Args:
            *children: The children components.
            **props: The props of the component.

        Returns:
            A Recharts component.
        """
        comp = super().create(*children, **props)
        if comp.get_hooks():
            # If any of the children depend on state, then this instance needs to memoize.
            comp._memoization_mode = cls._memoization_mode.copy(
                update={"disposition": MemoizationDisposition.ALWAYS},
            )
        return comp


class RechartsCharts(NoSSRComponent, RechartsMemoizationLeafMixin):
    """A component that wraps a recharts lib."""

    library = "recharts@2.8.0"


LiteralAnimationEasing = Literal["ease", "ease-in", "ease-out", "ease-in-out", "linear"]
LiteralIfOverflow = Literal["discard", "hidden", "visible", "extendDomain"]
LiteralShape = Literal[
    "square", "circle", "cross", "diamond", "star", "triangle", "wye"
]
LiteralLineType = Literal["joint", "fitting"]
LiteralOrientation = Literal["top", "bottom", "left", "right", "middle"]
LiteralOrientationLeftRightMiddle = Literal["left", "right", "middle"]
LiteralOrientationTopBottom = Literal["top", "bottom"]
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
LiteralLegendType = [
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
LiteralDirection = Literal["x", "y", "both"]
LiteralInterval = Literal["preserveStart", "preserveEnd", "preserveStartEnd"]
LiteralSyncMethod = Literal["index", "value"]
