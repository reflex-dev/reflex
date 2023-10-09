"""Victory graphing components."""

from typing import Any, Dict, List, Optional, Union

from reflex.components.component import Component
from reflex.style import Style
from reflex.utils import console
from reflex.vars import Var


def format_xy(x: List, y: List) -> List:
    """Format x and y data.

    Args:
        x: The x values.
        y: The y values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x and y are not the same length.
    """
    if len(x) != len(y):
        raise ValueError("x and y must be the same length")
    return [{"x": x[i], "y": y[i]} for i in range(len(x))]


def format_line(x: List, y: List) -> List:
    """Format line data.

    Args:
        x: The x values.
        y: The y values.

    Returns:
        The formatted data.
    """
    return format_xy(x, y)


def format_scatter(x: List, y: List, amount: Optional[List] = None) -> List:
    """Format scatter data.

    Args:
        x: The x values.
        y: The y values.
        amount: The amount of each point.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x and y are not the same length.
    """
    if x is None or y is None:
        raise ValueError("x and y must be provided")

    if amount is None:
        return format_xy(x, y)

    return [{"x": x[i], "y": y[i], "amount": amount[i]} for i in range(len(x))]


def format_area(x: List, y: List, y0: Optional[List] = None) -> List:
    """Format area data.

    Args:
        x: The x values.
        y: The y values.
        y0: The y0 values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x and y are not the same length.
    """
    if y0 is None:
        return format_xy(x, y)
    if len(x) != len(y) or len(x) != len(y0):
        raise ValueError("x, y, and y0 must be the same length")
    return [{"x": x[i], "y": y[i], "y0": y0[i]} for i in range(len(x))]


def format_bar(x: List, y: List, y0: Optional[List] = None) -> List:
    """Format bar data.

    Args:
        x: The x values.
        y: The y values.
        y0: The y0 values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x and y are not the same length.
    """
    if y0 is None:
        return format_xy(x, y)
    if len(x) != len(y) or len(x) != len(y0):
        raise ValueError("x, y, and y0 must be the same length")
    return [{"x": x[i], "y": y[i], "y0": y0[i]} for i in range(len(x))]


def format_box_plot(
    x: List,
    y: Optional[List[Any]] = None,
    min_: Optional[List[Any]] = None,
    max_: Optional[List[Any]] = None,
    median: Optional[List[Any]] = None,
    q1: Optional[List[Any]] = None,
    q3: Optional[List[Any]] = None,
) -> List:
    """Format box plot data.

    Args:
        x: The x values.
        y: The y values.
        min_: The minimum values.
        max_: The maximum values.
        median: The median values.
        q1: The q1 values.
        q3: The q3 values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x is not provided.
        ValueError: If y is provided and x, y are not the same length.
        ValueError: If y is not provided and min, max, median, q1, and q3 are not provided.
        ValueError: If y is not provided and x, min, max, median, q1, and q3 are not the same length.
    """
    if x is None:
        raise ValueError("x must be specified")

    if y is not None:
        return format_xy(x, y)

    if min_ is None or max_ is None or median is None or q1 is None or q3 is None:
        raise ValueError(
            "min, max, median, q1, and q3 must be specified if y is not provided"
        )
    if (
        len(x) != len(min_)
        or len(x) != len(max_)
        or len(x) != len(median)
        or len(x) != len(q1)
        or len(x) != len(q3)
    ):
        raise ValueError(
            "x, min, max, median, q1, and q3 must be the same length and specified if y is not provided"
        )
    return [
        {
            "x": x[i],
            "min": min_[i],
            "max": max_[i],
            "median": median[i],
            "q1": q1[i],
            "q3": q3[i],
        }
        for i in range(len(x))
    ]


def format_histogram(x: List) -> List:
    """Format histogram data.

    Args:
        x: The x values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x is not provided.
    """
    if x is None:
        raise ValueError("x must be specified")

    return [{"x": x[i]} for i in range(len(x))]


def format_pie(x: List, y: List, label: Optional[List] = None) -> List:
    """Format pie data.

    Args:
        x: The x values.
        y: The y values.
        label: The label values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x is not provided.
        ValueError: If x and y are not the same length.
        ValueError: If x, y, and label are not the same length.
    """
    if x is None:
        raise ValueError("x must be specified")

    if label is None:
        return format_xy(x, y)
    if len(x) != len(y) or len(x) != len(label):
        raise ValueError("x, y, and label must be the same length")
    return [{"x": x[i], "y": y[i], "label": label[i]} for i in range(len(x))]


def format_voronoi(x: List, y: List) -> List:
    """Format voronoi data.

    Args:
        x: The x values.
        y: The y values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x or y is not provided.
        ValueError: If x and y are not the same length.
    """
    if x is None or y is None:
        raise ValueError("x and y must be specified")

    return format_xy(x, y)


def format_candlestick(x: List, open: List, close: List, high: List, low: List) -> List:
    """Format candlestick data.

    Args:
        x: The x values.
        open: The open values.
        close: The close values.
        high: The high values.
        low: The low values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x is not provided.
        ValueError: If x, open, close, high, and low are not the same length.
    """
    if x is None:
        raise ValueError("x must be specified")

    if (
        len(x) != len(open)
        or len(x) != len(close)
        or len(x) != len(high)
        or len(x) != len(low)
    ):
        raise ValueError("x, open, close, high, and low must be the same length")

    return [
        {"x": x[i], "open": open[i], "close": close[i], "high": high[i], "low": low[i]}
        for i in range(len(x))
    ]


def format_error_bar(x: List, y: List, error_x: List, error_y: List) -> List:
    """Format error bar data.

    Args:
        x: The x values.
        y: The y values.
        error_x: The error_x values.
        error_y: The error_y values.

    Returns:
        The formatted data.

    Raises:
        ValueError: If x is not provided.
        ValueError: If x, y, error_x, and error_y are not the same length.
    """
    if x is None:
        raise ValueError("x must be specified")

    if len(x) != len(error_x) or len(x) != len(error_y):
        raise ValueError("x, y, error_x, and error_y must be the same length")
    else:
        return [
            {"x": x[i], "y": y[i], "errorX": error_x[i], "errorY": error_y[i]}
            for i in range(len(x))
        ]


def data(graph: str, x: List, y: Optional[List] = None, **kwargs) -> List:
    """Format data.

    Args:
        graph: The graph type.
        x: The x values.
        y: The y values.
        kwargs: The keyword arguments.

    Returns:
        The formatted data.

    Raises:
        ValueError: If graph is not provided.
        ValueError: If graph is not supported.
    """
    console.deprecate(
        "Victory Chart",
        "Use the Recharts library instead under rx.recharts",
        "0.2.9",
        "0.3.0",
    )

    if graph == "area":
        return format_area(x, y, **kwargs)  # type: ignore
    elif graph == "bar":
        return format_bar(x, y)  # type: ignore
    elif graph == "box_plot":
        return format_box_plot(x, y, **kwargs)
    elif graph == "candlestick":
        return format_candlestick(x, **kwargs)
    elif graph == "error_bar":
        return format_error_bar(x, y, **kwargs)  # type: ignore
    elif graph == "histogram":
        return format_histogram(x)
    elif graph == "line":
        return format_line(x, y)  # type: ignore
    elif graph == "pie":
        return format_pie(x, y, **kwargs)  # type: ignore
    elif graph == "scatter":
        return format_scatter(x, y, **kwargs)  # type: ignore
    elif graph == "voronoi":
        return format_voronoi(x, y)  # type: ignore
    else:
        raise ValueError("Invalid graph type")


class Victory(Component):
    """A component that wraps a victory lib."""

    library = "victory@^36.6.8"

    # The data to display.
    data: Var[List[Dict]]

    # The height of the chart.
    height: Var[str]

    # The width of the chart.
    width: Var[str]

    # Max domain for the chart.
    max_domain: Var[Dict]

    # Min domain for the chart.
    min_domain: Var[Dict]

    # Whether the chart is polar.
    polar: Var[bool]

    # Scale for the chart: "linear", "time", "log", "sqrt"
    scale: Var[Dict]

    # Labels for the chart.
    labels: Var[List]

    # Display the chart horizontally.
    horizontal: Var[bool]

    # Whether the chart is standalone.
    standalone: Var[bool]

    # The sort order for the chart: "ascending", "descending"
    sort_order: Var[str]

    # The padding for the chart.
    padding: Var[Dict]

    # Domain padding for the chart.
    domain_padding: Var[Dict]

    # A custom style for the code block.
    custom_style: Var[Dict[str, str]]

    @classmethod
    def create(cls, *children, **props):
        """Create a chart component.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The chart component.
        """
        console.deprecate(
            "Victory Chart",
            "Use the Recharts library instead under rx.recharts",
            "0.2.9",
            "0.3.0",
        )

        # This component handles style in a special prop.
        custom_style = props.pop("style", {})

        # Transfer style props to the custom style prop.
        for key, value in props.items():
            if key not in cls.get_fields():
                custom_style[key] = value

        # Create the component.
        return super().create(
            *children,
            **props,
            custom_style=Style(custom_style),
        )

    def _add_style(self, style):
        self.custom_style = self.custom_style or {}
        self.custom_style.update(style)  # type: ignore

    def _render(self):
        out = super()._render()
        return out.add_props(style=self.custom_style).remove_props("custom_style")


class Chart(Victory):
    """Wrapper component that renders a given set of children on a set of Cartesian or polar axes."""

    tag = "VictoryChart"

    # Start angle for the chart.
    start_angle: Var[int]

    # End angle for the chart.
    end_angle: Var[int]

    # The padding for the chart.
    domain_padding: Var[Dict]


class Line(Victory):
    """Display a victory line."""

    tag = "VictoryLine"

    # Interpolation for the line: Polar line charts may use the following interpolation options: "basis", "cardinal", "catmullRom", "linear" and Cartesian line charts may use the following interpolation options: "basis", "bundle", "cardinal", "catmullRom", "linear", "monotoneX", "monotoneY", "natural", "step", "stepAfter", "stepBefore"
    interpolation: Var[str]


class Bar(Victory):
    """Display a victory bar."""

    tag = "VictoryBar"

    # The alignment prop specifies how bars should be aligned relative to their data points. This prop may be given as "start", "middle" or "end". When this prop is not specified, bars will have "middle" alignment relative to their data points.
    alignment: Var[str]

    # Determines the relative width of bars to the available space. This prop should be given as a number between 0 and 1. When this prop is not specified, bars will have a default ratio of 0.75.
    bar_ratio: Var[float]

    # Specify the width of each bar.
    bar_width: Var[int]

    # Specifies a radius to apply to each bar.
    corner_radius: Var[float]


class Area(Victory):
    """Display a victory area."""

    tag = "VictoryArea"

    # Interpolation for the line: Polar line charts may use the following interpolation options: "basis", "cardinal", "catmullRom", "linear" and Cartesian line charts may use the following interpolation options: "basis", "bundle", "cardinal", "catmullRom", "linear", "monotoneX", "monotoneY", "natural", "step", "stepAfter", "stepBefore"
    interpolation: Var[str]


class Pie(Victory):
    """Display a victory pie."""

    tag = "VictoryPie"

    # Defines a color scale to be applied to each slice. Takes in an array of colors. Default color scale are: "grayscale", "qualitative", "heatmap", "warm", "cool", "red", "green", "blue".
    color_scale: Var[Union[str, List[str]]]

    # Specifies the corner radius of the slices rendered in the pie chart.
    corner_radius: Var[float]

    # Specifies the angular placement of each label relative to the angle of its corresponding slice. Options are : "parallel", "perpendicular", "vertical".
    label_placement: Var[str]

    # Specifies the position of each label relative to its corresponding slice. Options are : "startAngle", "endAngle", "centroid".
    label_position: Var[str]

    # Defines the radius of the arc that will be used for positioning each slice label. This prop should be given as a number between 0 and 1. If this prop is not set, the label radius will default to the radius of the pie + label padding.
    label_radius: Var[float]

    # Defines the amount of separation between adjacent data slices in number of degrees.
    pad_angle: Var[float]

    # Specifies the radius of the pie. When this prop is not given, it will be calculated based on the width, height, and padding props.
    radius: Var[float]

    # Specifies the inner radius of the pie. When this prop is not given, it will default to 0.
    inner_radius: Var[float]

    # Specifies the start angle of the first slice in number of degrees. Default is 0.
    start_angle: Var[float]

    # Specifies the end angle of the last slice in number of degrees. Default is 360.
    end_angle: Var[float]


class Candlestick(Victory):
    """Display a victory candlestick."""

    tag = "VictoryCandlestick"

    # Candle colors are significant in candlestick charts, with colors indicating whether a market closed higher than it opened (positive), or closed lower than it opened (negative). The candleColors prop should be given as an object with color strings specified for positive and negative.
    candle_colors: Var[Dict]

    # Specifies an approximate ratio between candle widths and spaces between candles.
    candle_ratio: Var[float]

    # Specify the width of each candle.
    candle_width: Var[float]

    # Defines the labels that will correspond to the close value for each candle.
    close_labels: Var[List]


class Scatter(Victory):
    """Display a victory scatter."""

    tag = "VictoryScatter"

    # Indicates which property of the data object should be used to scale data points in a bubble chart.
    bubble_property: Var[str]

    # Sets a lower limit for scaling data points in a bubble chart.
    min_bubble_size: Var[float]

    # Sets an upper limit for scaling data points in a bubble chart.
    max_bubble_size: Var[float]


class BoxPlot(Victory):
    """Display a victory boxplot."""

    tag = "VictoryBoxPlot"

    # Specifies how wide each box should be.
    box_width: Var[float]


class Histogram(Victory):
    """Display a victory histogram."""

    tag = "VictoryHistogram"

    # Specify how the data will be binned.
    bins: Var[List]

    # Specifies the amount of space between each bin.
    bin_spacing: Var[float]

    # Specifies a radius to apply to each bar.
    corner_radius: Var[float]


class ErrorBar(Victory):
    """Display a victory errorbar."""

    tag = "VictoryErrorBar"

    # Sets the border width of the error bars.
    border_width: Var[float]


class ChartGroup(Victory):
    """Display a victory group."""

    tag = "VictoryGroup"

    # Optional prop that defines a color scale to be applied to the children of the group. Takes in an array of colors. Default color scale are: "grayscale", "qualitative", "heatmap", "warm", "cool", "red", "green", "blue".
    color_scale: Var[Union[str, List[str]]]

    # Optional prop that defines a single color to be applied to the children of the group. Overrides color_scale.
    color: Var[str]

    # Determines the number of pixels each element in a group should be offset from its original position on the independent axis.
    offset: Var[float]


class ChartStack(Victory):
    """Display a victory stack."""

    tag = "VictoryStack"

    # Prop is used for grouping stacks of bars.
    categories: Var[int]

    # Optional prop that defines a color scale to be applied to the children of the group. Takes in an array of colors. Default color scale are: "grayscale", "qualitative", "heatmap", "warm", "cool", "red", "green", "blue".
    color_scale: Var[Union[str, List[str]]]


class Voronoi(Victory):
    """Display a victory Voronoi."""

    tag = "VictoryVoronoi"


class Polar(Victory):
    """Display a victory polar."""

    tag = "VictoryPolarAxis"

    # Specifies whether the axis corresponds to the dependent variable
    dependent_axis: Var[bool]
