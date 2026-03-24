```python exec
import reflex as rx
from pcweb.pages.docs import styling, library
```

# Styling

Reflex components can be styled using the full power of [CSS]({"https://www.w3schools.com/css/"}).

There are three main ways to add style to your app and they take precedence in the following order:

1. **Inline:** Styles applied to a single component instance.
2. **Component:** Styles applied to components of a specific type.
3. **Global:** Styles applied to all components.

```md alert success
# Style keys can be any valid CSS property name.
To be consistent with Python standards, you can specify keys in `snake_case`.
```

## Global Styles

You can pass a style dictionary to your app to apply base styles to all components.

For example, you can set the default font family and font size for your app here just once rather than having to set it on every component.

```python
style = {
    "font_family": "Comic Sans MS",
    "font_size": "16px",
}

app = rx.App(style=style)
```

## Component Styles

In your style dictionary, you can also specify default styles for specific component types or arbitrary CSS classes and IDs.

```python
style = {
    # Set the selection highlight color globally.
    "::selection": {
        "background_color": accent_color,
    },
    # Apply global css class styles.
    ".some-css-class": {
        "text_decoration": "underline",
    },
    # Apply global css id styles.
    "#special-input": \{"width": "20vw"},
    # Apply styles to specific components.
    rx.text: {
        "font_family": "Comic Sans MS",
    },
    rx.divider: {
        "margin_bottom": "1em",
        "margin_top": "0.5em",
    },
    rx.heading: {
        "font_weight": "500",
    },
    rx.code: {
        "color": "green",
    },
}

app = rx.App(style=style)
```

Using style dictionaries like this, you can easily create a consistent theme for your app.


```md alert warning
# Watch out for underscores in class names and IDs
Reflex automatically converts `snake_case` identifiers into `camelCase` format when applying styles. To ensure consistency, it is recommended to use the dash character or camelCase identifiers in your own class names and IDs. To style third-party libraries relying on underscore class names, an external stylesheet should be used. See [custom stylesheets]({styling.custom_stylesheets.path}) for how to reference external CSS files.
```

## Inline Styles

Inline styles apply to a single component instance. They are passed in as regular props to the component.

```python demo
rx.text(
    "Hello World",
    background_image="linear-gradient(271.68deg, #EE756A 0.75%, #756AEE 88.52%)",
    background_clip="text",
    font_weight="bold",
    font_size="2em",
)
```

Children components inherit inline styles unless they are overridden by their own inline styles.

```python demo
rx.box(
    rx.hstack(
        rx.button("Default Button"),
        rx.button("Red Button", color="red"),
    ),
    color="blue",
)
```

### Style Prop

Inline styles can also be set with a `style` prop. This is useful for reusing styles between multiple components.

```python exec
text_style = {
    "color": "green",
    "font_family": "Comic Sans MS",
    "font_size": "1.2em",
    "font_weight": "bold",
    "box_shadow": "rgba(240, 46, 170, 0.4) 5px 5px, rgba(240, 46, 170, 0.3) 10px 10px",
}
```

```python
text_style={text_style}
```

```python demo
rx.vstack(
    rx.text("Hello", style=text_style),
    rx.text("World", style=text_style),
)
```

```python exec
style1 = {
    "color": "green",
    "font_family": "Comic Sans MS",
    "border_radius": "10px",
    "background_color": "rgb(107,99,246)",
}
style2 = {
    "color": "white",
    "border": "5px solid #EE756A",
    "padding": "10px",
}
```

```python
style1={style1}
style2={style2}
```

```python demo
rx.box(
    "Multiple Styles",
    style=[style1, style2],
)
```

The style dictionaries are applied in the order they are passed in. This means that styles defined later will override styles defined earlier.


## Theming

As of Reflex 'v0.4.0', you can now theme your Reflex web apps. To learn more checkout the [Theme docs]({styling.theming.path}).

The `Theme` component is used to change the theme of the application. The `Theme` can be set directly in your rx.App.

```python
app = rx.App(
    theme=rx.theme(
        appearance="light", has_background=True, radius="large", accent_color="teal"
    )
)
```

Additionally you can modify the theme of your app through using the `Theme Panel` component which can be found in the [Theme Panel docs]({library.other.theme.path}).

## Special Styles

We support all of Chakra UI's [pseudo styles]({"https://v2.chakra-ui.com/docs/styled-system/style-props#pseudo"}).

Below is an example of text that changes color when you hover over it.

```python demo
rx.box(
    rx.text("Hover Me", _hover={"color": "red"}),
)
```
