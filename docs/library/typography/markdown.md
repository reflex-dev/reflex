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

````python demo
rx.markdown(
r"""
```python
import reflex as rx
from .pages import index

app = rx.App()
app.add_page(index)
```
"""
)
````

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

## Plugins

Plugins can be used to extend the functionality of the markdown renderer.

By default Reflex uses the following plugins:
- `remark-gfm` for Github Flavored Markdown support (`use_gfm`).
- `remark-math` and `rehype-katex` for math equation support (`use_math`, `use_katex`).
- `rehype-unwrap-images` to remove paragraph tags around images (`use_unwrap_images`).
- `rehype-raw` to render raw HTML in markdown (`use_raw`). NOTE: in a future release this will be disabled by default for security reasons.

These default plugins can be disabled by passing `use_[plugin_name]=False` to the `rx.markdown` component. For example, to disable raw HTML rendering, use `rx.markdown(..., use_raw=False)`.

## Arbitrary Plugins

You can also add arbitrary remark or rehype plugins using the `remark_plugins`
and `rehype_plugins` props in conjunction with the `rx.markdown.plugin` helper.

`rx.markdown.plugin` takes two arguments:

1. The npm package name and version of the plugin (e.g. `remark-emoji@5.0.2`).
2. The named export to use from the plugin (e.g. `remarkEmoji`).

### Remark Plugin Example

For example, to add support for emojis using the `remark-emoji` plugin:

```python demo
rx.markdown(
    "Hello :smile:! :rocket: :tada:",
    remark_plugins=[
        rx.markdown.plugin("remark-emoji@5.0.2", "remarkEmoji"),
    ],
)
```

### Rehype Plugin Example

To make `rehype-raw` safer for untrusted HTML input we can use `rehype-sanitize`, which defaults to a safe schema similar to that used by Github.

```python demo
rx.markdown(
    """Here is some **bold** text and a <script>alert("XSS Attack!")</script>.""",
    use_raw=True,
    rehype_plugins=[
        rx.markdown.plugin("rehype-sanitize@5.0.1", "rehypeSanitize"),
    ],
)
```

### Plugin Options

Both `remark_plugins` and `rehype_plugins` accept a heterogeneous list of `plugin`
or tuple of `(plugin, options)` in case the plugin requires some kind of special
configuration.

For example, `rehype-slug` is a simple plugin that adds ID attributes to the
headings, but the `rehype-autolink-headings` plugin accepts options to specify
how to render the links to those anchors.

```python demo
rx.markdown(
    """
# Heading 1
## Heading 2
""",
    rehype_plugins=[
        rx.markdown.plugin("rehype-slug@6.0.0", "rehypeSlug"),
        (
            rx.markdown.plugin("rehype-autolink-headings@7.1.0", "rehypeAutolinkHeadings"),
            {
                "behavior": "wrap",
                "properties": {
                    "className": ["heading-link"],
                },
            },
        ),
    ],
)
```

## Component Map

You can specify which components to use for rendering markdown elements using the
`component_map` prop.

Each key in the `component_map` prop is a markdown element, and the value is
a function that takes the text of the element as input and returns a Reflex component.

```md alert
The `pre` and `a` tags are special cases. In addition to the `text`, they also receive a `props` argument containing additional props for the component.
```

````python demo exec
component_map = {
    "h1": lambda text: rx.heading(text, size="5", margin_y="1em"),
    "h2": lambda text: rx.heading(text, size="3", margin_y="1em"),
    "h3": lambda text: rx.heading(text, size="1", margin_y="1em"),
    "p": lambda text: rx.text(text, color="green", margin_y="1em"),
    "code": lambda text: rx.code(text, color="purple"),
    "pre": lambda text, **props: rx.code_block(text, **props, theme=rx.code_block.themes.dark, margin_y="1em"),
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

```python
import reflex as rx

component = rx.text("Hello World!")
```

And then some more text here,
followed by a link to
[Reflex](https://reflex.dev/).
""",
    component_map=component_map,
)
    )
````
