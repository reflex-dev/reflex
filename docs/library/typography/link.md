---
components:
    - rx.link
---

```python exec
import reflex as rx
from pcweb.pages.docs import api_reference
```

# Link

Links are accessible elements used primarily for navigation. Use the `href` prop to specify the location for the link to navigate to.

```python demo
rx.link("Reflex Home Page.", href="https://reflex.dev/")
```

You can also provide local links to other pages in your project without writing the full url.

```python demo
rx.link("Example", href="/docs/library",)
```


The `link` component can be used to wrap other components to make them link to other pages.

```python demo
rx.link(rx.button("Example"), href="https://reflex.dev/")
```

You can also create anchors to link to specific parts of a page using the `id` prop.

```python demo
rx.box("Example", id="example")
```

To reference an anchor, you can use the `href` prop of the `link` component. The `href` should be in the format of the page you want to link to followed by a # and the id of the anchor.

```python demo
rx.link("Example", href="/docs/library/typography/link#example")
```

```md alert info
# Redirecting the user using State 
It is also possible to redirect the user to a new path within the application, using `rx.redirect()`. Check out the docs [here]({api_reference.special_events.path}).
```

# Style

## Size

Use the `size` prop to control the size of the link. The prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog.", size="1"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="2"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="3"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="4"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="5"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="6"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="7"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="8"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="9"),
    direction="column",
    spacing="3",
)
```

## Weight

Use the `weight` prop to set the text weight.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog.", weight="light"),
    rx.link("The quick brown fox jumps over the lazy dog.", weight="regular"),
    rx.link("The quick brown fox jumps over the lazy dog.", weight="medium"),
    rx.link("The quick brown fox jumps over the lazy dog.", weight="bold"),
    direction="column",
    spacing="3",
)
```

## Trim

Use the `trim` prop to trim the leading space at the start, end, or both sides of the rendered text.

```python demo
rx.flex(
    rx.link("Without Trim",
        trim="normal",
        style={"background": "var(--gray-a2)",
                "border_top": "1px dashed var(--gray-a7)",
                "border_bottom": "1px dashed var(--gray-a7)",}
    ),
    rx.link("With Trim",
        trim="both",
        style={"background": "var(--gray-a2)",
                "border_top": "1px dashed var(--gray-a7)",
                "border_bottom": "1px dashed var(--gray-a7)",}
    ),
    direction="column",
    spacing="3",
)
```

## Underline

Use the `underline` prop to manage the visibility of the underline affordance. It defaults to `auto`.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog.", underline="auto"),
    rx.link("The quick brown fox jumps over the lazy dog.", underline="hover"),
    rx.link("The quick brown fox jumps over the lazy dog.", underline="always"),
    direction="column",
    spacing="3",
)
```

## Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog.", color_scheme="indigo"),
    rx.link("The quick brown fox jumps over the lazy dog.", color_scheme="cyan"),
    rx.link("The quick brown fox jumps over the lazy dog.", color_scheme="crimson"),
    rx.link("The quick brown fox jumps over the lazy dog.", color_scheme="orange"),
    direction="column",
)
```

## High Contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog."),
    rx.link("The quick brown fox jumps over the lazy dog.", high_contrast=True),
    direction="column",
)
```
