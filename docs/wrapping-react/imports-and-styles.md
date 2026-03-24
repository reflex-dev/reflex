
# Styles and Imports

When wrapping a React component, you may need to define styles and imports that are specific to the component. This is done by defining the `add_styles` and `add_imports` methods in your component class.

### Imports

Sometimes, the component you are wrapping will need to import other components or libraries. This is done by defining the `add_imports` method in your component class.
That method should return a dictionary of imports, where the keys are the names of the packages to import and the values are the names of the components or libraries to import.

Values can be either a string or a list of strings. If the import needs to be aliased, you can use the `ImportVar` object to specify the alias and whether the import should be installed as a dependency.

```python
from reflex.utils.imports import ImportVar

class ComponentWithImports(MyBaseComponent):
    def add_imports(self):
        """Add imports to the component."""
        return {
            # If you only have one import, you can use a string.
            "my-package1": "my-import1",
            # If you have multiple imports, you can pass a list.
            "my-package2": ["my-import2"],
            # If you need to control the import in a more detailed way, you can use an ImportVar object.
            "my-package3": ImportVar(tag="my-import3", alias="my-alias", install=False, is_default=False),
            # To import a CSS file, pass the full path to the file, and use an empty string as the key.
            "": "my-package-with-css/styles.css",
        }
```

```md alert info
# The tag and library of the component will be automatically added to the imports. They do not need to be added again in `add_imports`.
```

### Styles

Styles are any CSS styles that need to be included in the component. The style will be added inline to the component, so you can use any CSS styles that are valid in React.

```python
class StyledComponent(MyBaseComponent):
    """MyComponent."""

    def add_style(self) -> dict[str, Any] | None:
        """Add styles to the component."""

        return rx.Style({
            "backgroundColor": "red",
            "color": "white",
            "padding": "10px",
        })
```
