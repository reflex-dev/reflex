---
components:
  - rx.accordion.root
  - rx.accordion.item

AccordionRoot: |
  lambda **props: rx.accordion.root(
      rx.accordion.item(header="First Item", content="The first accordion item's content"),
      rx.accordion.item(
          header="Second Item", content="The second accordion item's content",
      ),
      rx.accordion.item(header="Third item", content="The third accordion item's content"),
      width="300px",
      **props,
  )

AccordionItem: |
  lambda **props: rx.accordion.root(
      rx.accordion.item(header="First Item", content="The first accordion item's content", **props),
      rx.accordion.item(
          header="Second Item", content="The second accordion item's content", **props,
      ),
      rx.accordion.item(header="Third item", content="The third accordion item's content", **props),
      width="300px",
  )
---

```python exec
import reflex as rx
```

# Accordion

An accordion is a vertically stacked set of interactive headings that each reveal an associated section of content.
The accordion component is made up of `accordion`, which is the root of the component and takes in an `accordion.item`,
which contains all the contents of the collapsible section.

## Basic Example

```python demo
rx.accordion.root(
    rx.accordion.item(header="First Item", content="The first accordion item's content"),
    rx.accordion.item(
        header="Second Item", content="The second accordion item's content",
    ),
    rx.accordion.item(header="Third item", content="The third accordion item's content"),
    width="300px",
)
```

## Styling

### Type

We use the `type` prop to determine whether multiple items can be opened at once. The allowed values for this prop are
`single` and `multiple` where `single` will only open one item at a time. The default value for this prop is `single`.

```python demo
rx.accordion.root(
    rx.accordion.item(header="First Item", content="The first accordion item's content"),
    rx.accordion.item(
        header="Second Item", content="The second accordion item's content",
    ),
    rx.accordion.item(header="Third item", content="The third accordion item's content"),
    collapsible=True,
    width="300px",
    type="multiple",
)
```

### Default Value

We use the `default_value` prop to specify which item should open by default. The value for this prop should be any of the
unique values set by an `accordion.item`.

```python demo
rx.flex(
    rx.accordion.root(
        rx.accordion.item(
            header="First Item",
            content="The first accordion item's content",
            value="item_1",
        ),
        rx.accordion.item(
            header="Second Item",
            content="The second accordion item's content",
            value="item_2",
        ),
        rx.accordion.item(
            header="Third item",
            content="The third accordion item's content",
            value="item_3",
        ),
        width="300px",
        default_value="item_2",
    ),
    direction="row",
    spacing="2"
)
```

### Collapsible

We use the `collapsible` prop to allow all items to close. If set to `False`, an opened item cannot be closed.

```python demo
rx.flex(
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(header="Second Item", content="The second accordion item's content"),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=True,
        width="300px",
    ),
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(header="Second Item", content="The second accordion item's content"),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=False,
        width="300px",
    ),
    direction="row",
    spacing="2"
)
```

### Disable

We use the `disabled` prop to prevent interaction with the accordion and all its items.

```python demo
rx.accordion.root(
    rx.accordion.item(header="First Item", content="The first accordion item's content"),
    rx.accordion.item(header="Second Item", content="The second accordion item's content"),
    rx.accordion.item(header="Third item", content="The third accordion item's content"),
    collapsible=True,
    width="300px",
    disabled=True,
)
```

### Orientation

We use `orientation` prop to set the orientation of the accordion to `vertical` or `horizontal`. By default, the orientation
will be set to `vertical`. Note that, the orientation prop won't change the visual orientation but the
functional orientation of the accordion. This means that for vertical orientation, the up and down arrow keys moves focus between the next or previous item,
while for horizontal orientation, the left or right arrow keys moves focus between items.

```python demo
rx.accordion.root(
    rx.accordion.item(header="First Item", content="The first accordion item's content"),
    rx.accordion.item(
        header="Second Item", content="The second accordion item's content",
    ),
    rx.accordion.item(header="Third item", content="The third accordion item's content"),
    collapsible=True,
    width="300px",
    orientation="vertical",
)
```

```python demo
rx.accordion.root(
    rx.accordion.item(header="First Item", content="The first accordion item's content"),
    rx.accordion.item(
        header="Second Item", content="The second accordion item's content",
    ),
    rx.accordion.item(header="Third item", content="The third accordion item's content"),
    collapsible=True,
    width="300px",
    orientation="horizontal",
)
```

### Variant

```python demo
rx.flex(
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content",
        ),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=True,
        variant="classic",
    ),
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content",
        ),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=True,
        variant="soft",
    ),
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content",
        ),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=True,
        variant="outline",
    ),
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content",
        ),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=True,
        variant="surface",
    ),
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content",
        ),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=True,
        variant="ghost",
    ),
    direction="row",
    spacing="2"
)
```

### Color Scheme

We use the `color_scheme` prop to assign a specific color to the accordion background, ignoring the global theme.

```python demo
rx.flex(
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content",
        ),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=True,
        width="300px",
        color_scheme="grass",
    ),
    rx.accordion.root(
        rx.accordion.item(header="First Item", content="The first accordion item's content"),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content",
        ),
        rx.accordion.item(header="Third item", content="The third accordion item's content"),
        collapsible=True,
        width="300px",
        color_scheme="green",
    ),
    direction="row",
    spacing="2"
)
```

### Value

We use the `value` prop to specify the controlled value of the accordion item that we want to activate.
This property should be used in conjunction with the `on_value_change` event argument.

```python demo exec
class AccordionState(rx.State):
    """The app state."""
    value: str = "item_1"
    item_selected: str

    @rx.event
    def change_value(self, value):
        self.value = value
        self.item_selected = f"{value} selected"


def index() -> rx.Component:
    return rx.theme(
        rx.container(
            rx.text(AccordionState.item_selected),
            rx.flex(
                rx.accordion.root(
                    rx.accordion.item(
                        header="Is it accessible?",
                        content=rx.button("Test button"),
                        value="item_1",
                    ),
                    rx.accordion.item(
                        header="Is it unstyled?",
                        content="Yes. It's unstyled by default, giving you freedom over the look and feel.",
                        value="item_2",
                    ),
                    rx.accordion.item(
                        header="Is it finished?",
                        content="It's still in beta, but it's ready to use in production.",
                        value="item_3",
                    ),
                    collapsible=True,
                    width="300px",
                    value=AccordionState.value,
                    on_value_change=lambda value: AccordionState.change_value(value),
                ),
                direction="column",
                spacing="2",
            ),
            padding="2em",
            text_align="center",
        )
    )
```

## AccordionItem

The accordion item contains all the parts of a collapsible section.

## Styling

### Value

```python demo
rx.accordion.root(
    rx.accordion.item(
        header="First Item",
        content="The first accordion item's content",
        value="item_1",
    ),
    rx.accordion.item(
        header="Second Item",
        content="The second accordion item's content",
        value="item_2",
    ),
    rx.accordion.item(
        header="Third item",
        content="The third accordion item's content",
        value="item_3",
    ),
    collapsible=True,
    width="300px",
)
```

### Disable

```python demo
rx.accordion.root(
    rx.accordion.item(
        header="First Item",
        content="The first accordion item's content",
        disabled=True,
    ),
    rx.accordion.item(
        header="Second Item", content="The second accordion item's content",
    ),
    rx.accordion.item(header="Third item", content="The third accordion item's content"),
    collapsible=True,
    width="300px",
    color_scheme="blue",
)
```
