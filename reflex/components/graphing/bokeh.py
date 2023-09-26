"""Component for displaying a Bokeh graph."""

from typing import Any
import uuid

from reflex.components.component import NoSSRComponent
from reflex.utils.serializers import serializer
from reflex.vars import Var

try:
    from bokeh.plotting import figure
except ImportError:
    figure = Any


class Bokeh(NoSSRComponent):
    """Display a Bokeh chart.
    This component takes a Bokeh figure as input and renders it within a Box layout component.
    """
    library = "/utils/components/bokeh"
    tag = "BokehFigure"
    is_default = True

    lib_dependencies: list[str] = [
        "@bokeh/bokehjs",
        "@bokeh/numbro",
        "@bokeh/slickgrid",
        "choices.js",
        "flatbush",
        "flatpickr",
        "hammerjs",
        "mathjax-full",
        "nouislider",
        "proj4",
        "regl",
        "sprintf-js",
        "timezone",
        "underscore.template",
    ]

    fig: Var[figure]

    @classmethod
    def create(cls, fig: figure, **props):  # type: ignore
        """Create a Bokeh component.

        Args:
            fig: The Bokeh figure to display.
            **props: The props to pass to the component.

        Returns:
            The Bokeh component.
        """
        if not isinstance(fig, Var):
            sfig = serialize_bokeh_chart(fig)
            return super().create(
                id=sfig["target_id"],
                fig=fig,
            )
        else:
            return super().create(
                id=fig.to(dict[str, str])["target_id"],
                fig=fig,
            )


try:
    from bokeh.embed import json_item
    from bokeh.plotting import figure

    @serializer
    def serialize_bokeh_chart(fig: figure) -> str:
        """Serialize the Bokeh figure to HTML.
        Args:
            fig (figure): The Bokeh figure to serialize.
        Returns:
            str: The serialized Bokeh figure as HTML.
        """
        return json_item(fig, str(uuid.uuid4()))

except ImportError:
    pass