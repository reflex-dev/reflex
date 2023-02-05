
from pynecone import data

# Test data.
x_num = [1, 2, 3, 4, 5]
x_str = ["Cats", "Dogs", "Birds", "Fish", "Reptiles"]
y = [1, 2, 3, 4, 10]
y1 = [5, 12, 4, 6, 1]
y2 = [
    [1, 5, 7, 4, 10, 14],
    [1, 2, 3, 4, 10],
    [1, 2, 3, 4, 5],
    [1, 7, 3, 14, 10],
    [1, 2, 6, 4, 10],
]
amount = [1, 5, 3, 14, 1]


def test_line():
    output = data(graph="line", x=x_num, y=y)
    expected = [
        {"x": 1, "y": 1},
        {"x": 2, "y": 2},
        {"x": 3, "y": 3},
        {"x": 4, "y": 4},
        {"x": 5, "y": 10},
    ]
    assert output == expected


def test_scatter():
    output = data(graph="scatter", x=x_num, y=y)
    expected = [
        {"x": 1, "y": 1},
        {"x": 2, "y": 2},
        {"x": 3, "y": 3},
        {"x": 4, "y": 4},
        {"x": 5, "y": 10},
    ]
    assert output == expected


def test_area():
    output = data(graph="area", x=x_num, y=y)
    expected = [
        {"x": 1, "y": 1},
        {"x": 2, "y": 2},
        {"x": 3, "y": 3},
        {"x": 4, "y": 4},
        {"x": 5, "y": 10},
    ]
    assert output == expected


def test_bar():
    output = data(graph="bar", x=x_str, y=y)
    expected = [
        {"x": "Cats", "y": 1},
        {"x": "Dogs", "y": 2},
        {"x": "Birds", "y": 3},
        {"x": "Fish", "y": 4},
        {"x": "Reptiles", "y": 10},
    ]
    assert output == expected


def test_box_plot():
    output = data(graph="box_plot", x=x_num, y=y2)
    expected = [
        {"x": 1, "y": [1, 5, 7, 4, 10, 14]},
        {"x": 2, "y": [1, 2, 3, 4, 10]},
        {"x": 3, "y": [1, 2, 3, 4, 5]},
        {"x": 4, "y": [1, 7, 3, 14, 10]},
        {"x": 5, "y": [1, 2, 6, 4, 10]},
    ]
    output_specified = data(
        graph="box_plot", x=x_num, min_=y1, max_=y1, median=y1, q1=y1, q3=y1
    )
    expected_specified = [
        {"x": 1, "min": 5, "max": 5, "median": 5, "q1": 5, "q3": 5},
        {"x": 2, "min": 12, "max": 12, "median": 12, "q1": 12, "q3": 12},
        {"x": 3, "min": 4, "max": 4, "median": 4, "q1": 4, "q3": 4},
        {"x": 4, "min": 6, "max": 6, "median": 6, "q1": 6, "q3": 6},
        {"x": 5, "min": 1, "max": 1, "median": 1, "q1": 1, "q3": 1},
    ]
    assert output == expected
    assert output_specified == expected_specified


def test_histogram():
    output = data(graph="histogram", x=x_num)
    output2 = data(graph="histogram", x=y1)
    expected = [{"x": 1}, {"x": 2}, {"x": 3}, {"x": 4}, {"x": 5}]
    expected2 = [{"x": 5}, {"x": 12}, {"x": 4}, {"x": 6}, {"x": 1}]
    assert output == expected
    assert output2 == expected2


def test_pie():
    output = data(graph="pie", x=x_str, y=amount)
    expected = [
        {"x": "Cats", "y": 1},
        {"x": "Dogs", "y": 5},
        {"x": "Birds", "y": 3},
        {"x": "Fish", "y": 14},
        {"x": "Reptiles", "y": 1},
    ]
    output_labels = data(graph="pie", x=x_str, y=amount, label=x_str)
    expected_labels = [
        {"x": "Cats", "y": 1, "label": "Cats"},
        {"x": "Dogs", "y": 5, "label": "Dogs"},
        {"x": "Birds", "y": 3, "label": "Birds"},
        {"x": "Fish", "y": 14, "label": "Fish"},
        {"x": "Reptiles", "y": 1, "label": "Reptiles"},
    ]
    assert output == expected
    assert output_labels == expected_labels


def test_voronoi():
    output = data(graph="voronoi", x=x_num, y=y)
    expected = [
        {"x": 1, "y": 1},
        {"x": 2, "y": 2},
        {"x": 3, "y": 3},
        {"x": 4, "y": 4},
        {"x": 5, "y": 10},
    ]
    assert output == expected


def test_candlestick():
    output = data(graph="candlestick", x=x_num, open=y1, high=y1, low=y1, close=y1)
    expected = [
        {"x": 1, "open": 5, "high": 5, "low": 5, "close": 5},
        {"x": 2, "open": 12, "high": 12, "low": 12, "close": 12},
        {"x": 3, "open": 4, "high": 4, "low": 4, "close": 4},
        {"x": 4, "open": 6, "high": 6, "low": 6, "close": 6},
        {"x": 5, "open": 1, "high": 1, "low": 1, "close": 1},
    ]

    assert output == expected


def test_errorbar():
    output = data(graph="error_bar", x=x_num, y=y1, error_y=y1, error_x=y1)
    expected = [
        {"x": 1, "y": 5, "errorY": 5, "errorX": 5},
        {"x": 2, "y": 12, "errorY": 12, "errorX": 12},
        {"x": 3, "y": 4, "errorY": 4, "errorX": 4},
        {"x": 4, "y": 6, "errorY": 6, "errorX": 6},
        {"x": 5, "y": 1, "errorY": 1, "errorX": 1},
    ]
    assert output == expected
