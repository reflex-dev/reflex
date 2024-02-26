```python exec
import reflex as rx
from typing import Any
```

## Basics of Imports

Before deciding to extend Reflex by wrapping a component, check to see if there is a corresponding, well maintained React library. Search for it on [npm](https://www.npmjs.com/), and if it's there, you can use it in your Reflex app.

```javascript
import \{ HexColorPicker } from "react-colorful"
```

The two main things we need to know when wrapping a React component are the library and the tag.

The library is the name of the npm package, and the tag is the name of the React component. As seen in the example above, the library is `react-colorful` and the tag is `HexColorPicker`.

The corresponding Reflex component would look like this:

```python
class ColorPicker(rx.Component):
    """Color picker component."""

    library = "react-colorful"
    tag = "HexColorPicker"
```

## Import Types

If the tag is the default export from the module, you can set `is_default = True` in your component class. This is normally used when components don't have curly braces around them when importing.

We do this in the Spline example in the overview section:

```javascript
import Spline from '@splinetool/react-spline';
```

To wrap this component we would set `is_default = True` in our component class:

```python
class Spline(rx.Component):
    """Spline component."""
 
    library = "@splinetool/react-spline"
    tag = "Spline"
    scene: Var[str] = "https://prod.spline.design/Br2ec3WwuRGxEuij/scene.splinecode"
    is_default = True

    lib_dependencies: list[str] = ["@splinetool/runtime"]
```

## Library Dependencies

By default Reflex will install the library you have specified in the library property. However, sometimes you may need to install other libraries to use a component. In this case you can use the `lib_dependencies` property to specify other libraries to install.

As seen in the Spline example in the overview section, we need to import the `@splinetool/runtime` library to use the `Spline` component. We can specify this in our component class like this:

```python
class Spline(rx.Component):
    """Spline component."""

    library = "@splinetool/react-spline"
    tag = "Spline"
    scene: Var[str] = "https://prod.spline.design/Br2ec3WwuRGxEuij/scene.splinecode"
    is_default = True

    lib_dependencies: list[str] = ["@splinetool/runtime"]
```

## Aliases

If you are wrapping another components with the same tag as a component in your project you can use aliases to differentiate between them and avoid naming conflicts.

Lets check out the code below, in this case if we needed to wrap another color picker library with the same tag we use an alias to avoid a conflict.

```python
class AnotherColorPicker(rx.Component):
    library = "some-other-colorpicker"
    tag = "HexColorPicker"
    alias = "OtherHexColorPicker"
    color: rx.Var[str]

    def get_event_triggers(self) -> dict[str, Any]:
        return \{
            **super().get_event_triggers(),
            "on_change": lambda e0: [e0],
        }
```

## Dynamic Imports

Some libraries you may want to wrap may require dynamic imports. This is because they they may not be compatible with Server-Side Rendering (SSR).

To handle this in Reflex all you need to do is subclass `NoSSRComponent` when defining your component.

Often times when you see an import something like this:

```javascript
import dynamic from 'next/dynamic';

const MyLibraryComponent = dynamic(() => import('./MyLibraryComponent'), {
  ssr: false
});
```

You can wrap it in Reflex like this, here we are wrapping the `react-plotly.js` library which requires dynamic imports:

```python
from reflex.components.component import NoSSRComponent

class PlotlyLib(NoSSRComponent):
    """A component that wraps a plotly lib."""

    library = "react-plotly.js@2.6.0"

    lib_dependencies: List[str] = ["plotly.js@2.22.0"]
```

## Custom Code

Sometimes you may need to add custom code to your component. This could be anything from adding custom constants, to adding custom imports, or even adding custom functions. Custom code will be inserted _outside_ of the react component function.

```javascript
import React from "react";
// Other imports...
...

// Custom code
const customCode = "const customCode = 'customCode';";
```

To add custom code to your component you can use the `get_custom_code` method in your component class.

```python
from reflex.components.component import NoSSRComponent

class PlotlyLib(NoSSRComponent):
    """A component that wraps a plotly lib."""

    library = "react-plotly.js@2.6.0"

    lib_dependencies: List[str] = ["plotly.js@2.22.0"]

    def _get_custom_code(self) -> str:
        return "const customCode = 'customCode';"
```
