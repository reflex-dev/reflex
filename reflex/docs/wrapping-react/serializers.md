---
title: Serializers
---

# Serializers

Vars can be any type that can be serialized to JSON. This includes primitive types like strings, numbers, and booleans, as well as more complex types like lists, dictionaries, and dataframes.

In case you need to serialize a more complex type, you can use the `serializer` decorator to convert the type to a primitive type that can be stored in the state. Just define a method that takes the complex type as an argument and returns a primitive type. We use type annotations to determine the type that you want to serialize.

For example, the Plotly component serializes a plotly figure into a JSON string that can be stored in the state.

```python
import json
import reflex as rx
from plotly.graph_objects import Figure
from plotly.io import to_json

# Use the serializer decorator to convert the figure to a JSON string.
# Specify the type of the argument as an annotation.
@rx.serializer
def serialize_figure(figure: Figure) -> list:
    # Use Plotly's to_json method to convert the figure to a JSON string.
    return json.loads(to_json(figure))["data"]
```

We can then define a var of this type as a prop in our component.

```python
import reflex as rx
from plotly.graph_objects import Figure

class Plotly(rx.Component):
    """Display a plotly graph."""
    library = "react-plotly.js@2.6.0"
    lib_dependencies: List[str] = ["plotly.js@2.22.0"]

    tag = "Plot"

    is_default = True

    # Since a serialize is defined now, we can use the Figure type directly.
    data: rx.Var[Figure]
```
