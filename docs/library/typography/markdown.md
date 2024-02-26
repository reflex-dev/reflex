---
components:
    - rx.markdown
---

```python exec
import reflex as rx
```

# Markdown

The `rx.markdown` component can be used to render markdown text.
It is based on [Github Flavored Markdown](https://github.github.com/gfm/).

```python demo
rx.vstack(
    rx.markdown("# Hello World!"),
    rx.markdown("## Hello World!"),
    rx.markdown("### Hello World!"),
    rx.markdown("Support us on [Github](https://github.com/reflex-dev/reflex)."),
    rx.markdown("Use `reflex deploy` to deploy your app with **a single command**."),
)
```

## Math Equations

You can render math equations using LaTeX.
For inline equations, surround the equation with `$`:

```python demo
rx.markdown("Pythagorean theorem: $a^2 + b^2 = c^2$.")
```

## Syntax Highlighting

You can render code blocks with syntax highlighting using the \`\`\`\{language} syntax:

```python demo  
rx.markdown(
r"""
\```python
import reflex as rx
from .pages import index

app = rx.App()
app.add_page(index)
\```
"""
)
```

## Tables

You can render tables using the `|` syntax:

```python demo
rx.markdown(
    """
| Syntax      | Description |
| ----------- | ----------- |
| Header      | Title       |
| Paragraph   | Text        |
"""
)
```

## Component Map

You can specify which components to use for rendering markdown elements using the
`component_map` prop.

Each key in the `component_map` prop is a markdown element, and the value is
a function that takes the text of the element as input and returns a Reflex component.

```md alert
The `codeblock` and `a` tags are special cases. In addition to the `text`, they also receive a `props` argument containing additional props for the component.
```

```python demo exec
component_map = {
    "h1": lambda text: rx.chakra.heading(text, size="lg", margin_y="1em"),
    "h2": lambda text: rx.chakra.heading(text, size="md", margin_y="1em"),
    "h3": lambda text: rx.chakra.heading(text, size="sm", margin_y="1em"),
    "p": lambda text: rx.text(text, color="green", margin_y="1em"),
    "code": lambda text: rx.code(text, color="purple"),
    "codeblock": lambda text, **props: rx.code_block(text, **props, theme="dark", margin_y="1em"),
    "a": lambda text, **props: rx.link(text, **props, color="blue", _hover={"color": "red"}),
}

def index():
    return rx.box(
        rx.markdown(
r"""
# Hello World!

## This is a Subheader

### And Another Subheader

Here is some `code`:

\```python
import reflex as rx

component = rx.text("Hello World!")
\```

And then some more text here, followed by a link to [Reflex](https://reflex.dev).
""",
    component_map=component_map,
)
    )
```
