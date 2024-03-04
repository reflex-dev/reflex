```python exec
import reflex as rx
from typing import Any
from pcweb.pages.docs import state
```

## Declaring Vars

As seen in our [state section]({state.overview.path}), we can use `rx.Var` to define state variables in our Reflex apps.

When wrapping your own react components, you can use `rx.Var` to define props for your component. In the example below, we define a `color` prop for our `ColorPicker` component.

```python
class ColorPicker(rx.Component):
    library = "react-colorful"
    tag = "HexColorPicker"
    color: rx.Var[str]
```

However, vars can be more than just a sigle type. You var can be any combination of primitive types.

```python
class SomeComponent(rx.Component):

    tag = "SomeComponent"

    data: Var[List[Dict[str, Any]]]
```

Here we define a var that is a list of dictionaries. This is useful for when you want to pass in a list of data to your component.

## Serializing Vars

Sometimes you want to create a var that isn't a common primitive type. In this case, you can use the `serializer` to convert your var to a primitive type which can be stored in your state.

Here is an example of how we can serialize a plotly figure into a json which can be stored in our state.

```python
import json
from typing import Any, Dict, List

from reflex.components.component import NoSSRComponent
from reflex.utils.serializers import serializer
from reflex.vars import Var

try:
    from plotly.graph_objects import Figure
except ImportError:
    Figure = Any
    
class PlotlyLib(NoSSRComponent):
    """A component that wraps a plotly lib."""

    library = "react-plotly.js@2.6.0"

    lib_dependencies: List[str] = ["plotly.js@2.22.0"]


class Plotly(PlotlyLib):
    """Display a plotly graph."""

    tag = "Plot"

    is_default = True

    # The figure to display. This can be a plotly figure or a plotly data json.
    data: Var[Figure]

    ...


try:
    from plotly.graph_objects import Figure
    from plotly.io import to_json

    @serializer
    def serialize_figure(figure: Figure) -> list:
        """Serialize a plotly figure.

        Args:
            figure: The figure to serialize.

        Returns:
            The serialized figure.
        """
        return json.loads(str(to_json(figure)))["data"]

except ImportError:
    pass
```

## Event Triggers

As seen in our [events section](https://reflex.dev/docs/state/events/), we can use event triggers to handle events in our Reflex apps. When wrapping your own react components, you can use the `get_event_triggers` method to define event triggers for your component.

Sometimes these event trigger may take in arguments, for example, the `on_change` event trigger for the `HexColorPicker` component we saw in the [wrapping react section](https://reflex.dev/docs/wrapping-react/wrapping-react/). In this case, we can use a lambda function to pass in the event argument to the event trigger. The function associated with a trigger maps args for the javascript trigger to args that will be passed to the backend event handler function.

```python
class ColorPicker(rx.Component):
    library = "react-colorful"
    tag = "HexColorPicker"
    color: rx.Var[str]

    def get_event_triggers(self) -> dict[str, Any]:
        return \{
            **super().get_event_triggers(),
            "on_change": lambda e0: [e0],
        }
```
