"""Component for displaying a plotly graph."""

from typing import Any, Dict, Union, List, Optional

from pynecone.components.component import Component
from pynecone.components.tags import Tag
from pynecone.var import Var


def format_line(x: List, y: List) -> List:
    """Format line data."""
    data = []
    if len(x) != len(y):
        raise ValueError("x and y must be the same length")

    for i in range(len(x)):
        data.append({"x": x[i], "y": y[i]})

    return data


def format_scatter(x: List, y: List, amount: Optional[List] = None) -> List:
    """Format a scatter."""
    data = []
    if x is None or y is None:
        raise ValueError("x and y must be provided")

    if len(x) != len(y):
        raise ValueError("x and y must be the same length")

    if amount is None:
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i]})
    else:
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i], "amount": amount[i]})

    return data


def format_area(x: List, y: List, y0: Optional[List] = None) -> List:
    """Format an area."""
    data = []
    if y0 is None:
        if len(x) != len(y):
            raise ValueError("x and y must be the same length")
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i]})
    else:
        if len(x) != len(y) or len(x) != len(y0):
            raise ValueError("x, y, and y0 must be the same length")
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i], "y0": y0[i]})
    return data


def format_bar(x: List, y: List, y0: Optional[List] = None) -> List:
    """Format an bar."""
    data = []
    if y0 is None:
        if len(x) != len(y):
            raise ValueError("x and y must be the same length")
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i]})
    else:
        if len(x) != len(y) or len(x) != len(y0):
            raise ValueError("x, y, and y0 must be the same length")
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i], "y0": y0[i]})

    print(data)
    return data


def format_box_plot(
    x: List,
    y: Optional[List[Any]] = None,
    min_: Optional[List[Any]] = None,
    max_: Optional[List[Any]] = None,
    median: Optional[List[Any]] = None,
    q1: Optional[List[Any]] = None,
    q3: Optional[List[Any]] = None,
) -> List:
    """Format a box plot."""
    data = []
    if x is None:
        raise ValueError("x must be specified")

    if y is not None:
        if len(x) != len(y):
            raise ValueError("x and y must be the same length")
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i]})

    else:
        if min_ is None or max_ is None or median is None or q1 is None or q3 is None:
            raise ValueError(
                "min, max, median, q1, and q3 must be specified if y is not provided"
            )
        elif (
            len(x) != len(min_)
            or len(x) != len(max_)
            or len(x) != len(median)
            or len(x) != len(q1)
            or len(x) != len(q3)
        ):
            raise ValueError(
                "x, min, max, median, q1, and q3 must be the same length and specified if y is not provided"
            )
        for i in range(len(x)):
            row = {}
            if x is not None:
                row["x"] = x[i]
            if min_ is not None:
                row["min"] = min_[i]
            if max_ is not None:
                row["max"] = max_[i]
            if median is not None:
                row["median"] = median[i]
            if q1 is not None:
                row["q1"] = q1[i]
            if q3 is not None:
                row["q3"] = q3[i]
            data.append(row)
    return data


def format_histogram(x: List) -> List:
    """Format a histogram."""
    data = []
    if x is None:
        raise ValueError("x must be specified")

    for i in range(len(x)):
        data.append({"x": x[i]})

    return data


def format_pie(x: List, y: List, label: Optional[List] = None) -> List:
    """Format a pie chart."""
    data = []
    if x is None:
        raise ValueError("x must be specified")

    if label is None:
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i]})
    else:
        for i in range(len(x)):
            data.append({"x": x[i], "y": y[i], "label": label[i]})

    return data


def format_voronoi(x: List, y: List) -> List:
    """Format a voronoi chart."""
    data = []
    if x is None:
        raise ValueError("x must be specified")

    if len(x) != len(y):
        raise ValueError("x and y must be the same length")

    for i in range(len(x)):
        data.append({"x": x[i], "y": y[i]})

    return data


def format_candlestick(x: List, open: List, close: List, high: List, low: List) -> List:
    """Format a candlestick chart."""
    data = []
    if x is None:
        raise ValueError("x must be specified")

    if (
        len(x) != len(open)
        or len(x) != len(close)
        or len(x) != len(high)
        or len(x) != len(low)
    ):
        raise ValueError("x, open, close, high, and low must be the same length")

    for i in range(len(x)):
        data.append(
            {
                "x": x[i],
                "open": open[i],
                "close": close[i],
                "high": high[i],
                "low": low[i],
            }
        )

    return data


def format_error_bar(x: List, y: List, error_x: List, error_y: List) -> List:
    """Format an error bar."""
    data = []
    if x is None:
        raise ValueError("x must be specified")

    if len(x) != len(y):
        raise ValueError("x and y must be the same length")

    if len(x) != len(error_x) or len(x) != len(error_y):
        raise ValueError("x, y, error_x, and error_y must be the same length")
    else:
        for i in range(len(x)):
            data.append(
                {"x": x[i], "y": y[i], "error_x": error_x[i], "error_y": error_y[i]}
            )

    return data


def data(graph: str, x: List, y: Optional[List] = None, **kwargs) -> List:
    """Create a pynecone data object."""
    if graph == "box_plot":
        return format_box_plot(x, y, **kwargs)
    elif graph == "bar":
        return format_bar(x, y)  # type: ignore
    elif graph == "line":
        return format_line(x, y)  # type: ignore
    elif graph == "scatter":
        return format_scatter(x, y, **kwargs)  # type: ignore
    elif graph == "area":
        return format_area(x, y, **kwargs)  # type: ignore
    elif graph == "histogram":
        return format_histogram(x)
    elif graph == "pie":
        return format_pie(x, y, **kwargs)  # type: ignore
    elif graph == "voronoi":
        return format_voronoi(x, y)  # type: ignore
    elif graph == "candlestick":
        return format_candlestick(x, **kwargs)
    elif graph == "error_bar":
        return format_error_bar(x, y, **kwargs)  # type: ignore
    else:
        raise ValueError("Invalid graph type")


class Victory(Component):
    """A component that wraps a plotly lib."""

    library = "victory"

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


class Chart(Victory):
    """Display a victory graph."""

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
    corner_radius: Var[float | int]


class Area(Victory):
    """Display a victory area."""

    tag = "VictoryArea"

    # Interpolation for the line: Polar line charts may use the following interpolation options: "basis", "cardinal", "catmullRom", "linear" and Cartesian line charts may use the following interpolation options: "basis", "bundle", "cardinal", "catmullRom", "linear", "monotoneX", "monotoneY", "natural", "step", "stepAfter", "stepBefore"
    interpolation: Var[str]


class Pie(Victory):
    """Display a victory pie."""

    tag = "VictoryPie"

    # Defines a color scale to be applied to each slice. Takes in an array of colors. Default color scemes are: "grayscale", "qualitative", "heatmap", "warm", "cool", "red", "green", "blue".
    color_scale: Var[str]

    # Specifies the corner radius of the slices rendered in the pie chart.
    corner_radius: Var[float | int]

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
    corner_radius: Var[float | int]


class ErrorBar(Victory):
    """Display a victory errorbar."""

    tag = "VictoryErrorBar"

    # Sets the border width of the error bars.
    borderWidth: Var[float]


class Group(Victory):
    """Display a victory group."""

    tag = "VictoryGroup"

    # Optional prop that defines a color scale to be applied to the children of the group. Takes in an array of colors. Default color scemes are: "grayscale", "qualitative", "heatmap", "warm", "cool", "red", "green", "blue".
    color_scale: Var[List]

    # Optional prop that defines a single color to be applied to the children of the group. Overrides color_scale.
    color: Var[str]

    # Determines the number of pixels each element in a group should be offset from its original position on the independent axis.
    offset: Var[float]


class Stack(Victory):
    """Display a victory stack."""

    tag = "VictoryStack"

    # Prop is used for grouping stacks of bars.
    categories: Var[int]

    # Optional prop that defines a color scale to be applied to the children of the group. Takes in an array of colors. Default color scemes are: "grayscale", "qualitative", "heatmap", "warm", "cool", "red", "green", "blue".
    color_scale: Var[List]


class Voronoi(Victory):
    """Display a victory Voronoi."""

    tag = "VictoryVoronoi"


class Polar(Victory):
    """Display a victory polar."""

    tag = "VictoryPolarAxis"

    # Specifies whether the axis corresponds to the dependent variable
    dependent_axis: Var[bool]
