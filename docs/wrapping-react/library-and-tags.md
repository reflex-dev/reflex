---
title: Library and Tags
---

```python exec
from pcweb.pages.docs import api_reference
```

# Find The Component

There are two ways to find a component to wrap:
1. Write the component yourself locally.
2. Find a well-maintained React library on [npm](https://www.npmjs.com/) that contains the component you need.

In both cases, the process of wrapping the component is the same except for the `library` field.

# Wrapping the Component

To start wrapping your React component, the first step is to create a new component in your Reflex app. This is done by creating a new class that inherits from `rx.Component` or `rx.NoSSRComponent`. 

See the [API Reference]({api_reference.component.path}) for more details on the `rx.Component` class.

This is when we will define the most important attributes of the component:
1. **library**: The name of the npm package that contains the component.
2. **tag**: The name of the component to import from the package.
3. **alias**: (Optional) The name of the alias to use for the component. This is useful if multiple component from different package have a name in common. If `alias` is not specified, `tag` will be used.
4. **lib_dependencies**: Any additional libraries needed to use the component.
5. **is_default**: (Optional) If the component is a default export from the module, set this to `True`. Default is `False`.

Optionally, you can override the default component creation behavior by implementing the `create` class method. Most components won't need this when props are straightforward conversions from Python to JavaScript. However, this is useful when you need to add custom initialization logic, transform props, or handle special cases when the component is created.

```md alert warning
# When setting the `library` attribute, it is recommended to included a pinned version of the package. Doing so, the package will only change when you intentionally update the version, avoid unexpected breaking changes.
```

```python
class MyBaseComponent(rx.Component):
    """MyBaseComponent."""

    # The name of the npm package.
    library = "my-library@x.y.z"

    # The name of the component to use from the package.
    tag = "MyComponent"

    # Any additional libraries needed to use the component.
    lib_dependencies: list[str] = ["package-deps@x.y.z"]

    # The name of the alias to use for the component.
    alias = "MyComponentAlias"

    # If the component is a default export from the module, set this to True.
    is_default = True/False

    @classmethod
    def create(cls, *children, **props):
        """Create an instance of MyBaseComponent.
        
        Args:
            *children: The children of the component.
            **props: The props of the component.
            
        Returns:
            The component instance.
        """
        # Your custom creation logic here
        return super().create(*children, **props)

```

# Wrapping a Dynamic Component 

When wrapping some libraries, you may want to use dynamic imports. This is because they may not be compatible with Server-Side Rendering (SSR).

To handle this in Reflex, subclass `NoSSRComponent` when defining your component. It works the same as `rx.Component`, but it will automatically add the correct custom code for a dynamic import.

Often times when you see an import something like this:

```javascript
import dynamic from 'next/dynamic';

const MyLibraryComponent = dynamic(() => import('./MyLibraryComponent'), {
  ssr: false
});
```

You can wrap it in Reflex like this:

```python
from reflex.components.component import NoSSRComponent

class MyLibraryComponent(NoSSRComponent):
    """A component that wraps a lib needing dynamic import."""

    library = "my-library@x.y.z"

    tag="MyLibraryComponent"
```

It may not always be clear when a library requires dynamic imports. A few things to keep in mind are if the component is very client side heavy i.e. the view and structure depends on things that are fetched at run time, or if it uses `window` or `document` objects directly it will need to be wrapped as a `NoSSRComponent`. 

Some examples are:

1. Video and Audio Players
2. Maps
3. Drawing Canvas
4. 3D Graphics
5. QR Scanners
6. Reactflow

The reason for this is that it does not make sense for your server to render these components as the server does not have access to your camera, it cannot draw on your canvas or render a video from a file. 

In addition, if in the component documentation it mentions nextJS compatibility or server side rendering compatibility, it is a good sign that it requires dynamic imports.

# Advanced - Parsing a state Var with a JS Function
When wrapping a component, you may need to parse a state var by applying a JS function to it. 

## Define the parsing function

First you need to define the parsing function by writing it in `add_custom_code`.

```python

def add_custom_code(self) -> list[str]:
    """Add custom code to the component."""
    # Define the parsing function
    return [
        """
        function myParsingFunction(inputProp) {
            // Your parsing logic here
            return parsedProp;
        }"""
    ]
```

## Apply the parsing function to your props

Then, you can apply the parsing function to your props in the `create` method. 

```python
from reflex.vars.base import Var
from reflex.vars.function import FunctionStringVar

    ...
    @classmethod
    def create(cls, *children, **props):
        """Create an instance of MyBaseComponent.
        
        Args:
            *children: The children of the component.
            **props: The props of the component.
            
        Returns:
            The component instance.
        """
        # Apply the parsing function to the props
        if (prop_to_parse := props.get("propsToParse")) is not None:
            if isinstance(prop_to_parse, Var):
                props["propsToParse"] = FunctionStringVar.create("myParsingFunction").call(prop_to_parse)
            else:
                # This is not a state Var, so you can parse the value directly in python
                parsed_prop = python_parsing_function(prop_to_parse)
                props["propsToParse"] = parsed_prop
        return super().create(*children, **props)
    ...
```