---
components:
  - rx.accordion.root
  - rx.accordion.item

AccordionRoot: |
  lambda **props: rx.accordion.root(
      rx.accordion.item(
          header="First Item",
          content="The first accordion item's content",
          **props,
      ),
      rx.accordion.item(
          header="Second Item",
          content="The second accordion item's content",
          **props,
      ),
      rx.accordion.item(
          header="Third item",
          content="The third accordion item's content",
          **props,
      ),
      width="300px",
      **props,
  )

AccordionItem: |
  lambda **props: rx.accordion.root(
      rx.accordion.item(
          header="Single Item",
          content="The accordion item's content",
          **props,
      ),
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
    rx.accordion.item(
        header="First Item", content="The first accordion item's content"
    ),
    rx.accordion.item(
        header="Second Item",
        content="The second accordion item's content",
    ),
    rx.accordion.item(
        header="Third item", content="The third accordion item's content"
    ),
    width="300px",
)
```

```python test
def test_accordion_opens_one_item_at_a_time(demo):
    first = demo.get_by_text("The first accordion item's content")
    second = demo.get_by_text("The second accordion item's content")
    expect(demo.get_by_role("button")).to_have_text([
        "First Item",
        "Second Item",
        "Third item",
    ])
    expect(first).to_be_hidden()
    demo.get_by_role("button", name="First Item").click()
    expect(first).to_be_visible()
    demo.get_by_role("button", name="Second Item").click()
    expect(second).to_be_visible()
    expect(first).to_be_hidden()
```

## Styling

### Type

We use the `type` prop to determine whether multiple items can be opened at once. The allowed values for this prop are
`single` and `multiple` where `single` will only open one item at a time. The default value for this prop is `single`.

```python demo
rx.accordion.root(
    rx.accordion.item(
        header="First Item", content="The first accordion item's content"
    ),
    rx.accordion.item(
        header="Second Item",
        content="The second accordion item's content",
    ),
    rx.accordion.item(
        header="Third item", content="The third accordion item's content"
    ),
    collapsible=True,
    width="300px",
    type="multiple",
)
```

```python test
def test_accordion_type_multiple(demo):
    first = demo.get_by_text("The first accordion item's content")
    second = demo.get_by_text("The second accordion item's content")
    demo.get_by_role("button", name="First Item").click()
    demo.get_by_role("button", name="Second Item").click()
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    demo.get_by_role("button", name="First Item").click()
    expect(first).to_be_hidden()
    expect(second).to_be_visible()
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
    spacing="2",
)
```

```python test
def test_accordion_default_value(demo):
    expect(demo.get_by_text("The second accordion item's content")).to_be_visible()
    expect(demo.get_by_text("The first accordion item's content")).to_be_hidden()
    expect(demo.get_by_role("button", name="Second Item")).to_have_attribute(
        "aria-expanded", "true"
    )
```

### Collapsible

We use the `collapsible` prop to allow all items to close. If set to `False`, an opened item cannot be closed.

```python demo
rx.flex(
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content"
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=True,
        width="300px",
    ),
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item", content="The second accordion item's content"
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=False,
        width="300px",
    ),
    direction="row",
    spacing="2",
)
```

```python test
def test_accordion_collapsible(demo):
    roots = demo.locator("[data-variant]:has(> .AccordionItem)")
    collapsible_content = roots.first.get_by_text("The first accordion item's content")
    roots.first.get_by_role("button", name="First Item").click()
    expect(collapsible_content).to_be_visible()
    roots.first.get_by_role("button", name="First Item").click()
    expect(collapsible_content).to_be_hidden()

    fixed_trigger = roots.nth(1).get_by_role("button", name="First Item")
    fixed_trigger.click()
    expect(
        roots.nth(1).get_by_text("The first accordion item's content")
    ).to_be_visible()
    # A non-collapsible accordion disables the trigger of its open item.
    expect(fixed_trigger).to_be_disabled()
```

### Disable

We use the `disabled` prop to prevent interaction with the accordion and all its items.

```python demo
rx.accordion.root(
    rx.accordion.item(
        header="First Item", content="The first accordion item's content"
    ),
    rx.accordion.item(
        header="Second Item", content="The second accordion item's content"
    ),
    rx.accordion.item(
        header="Third item", content="The third accordion item's content"
    ),
    collapsible=True,
    width="300px",
    disabled=True,
)
```

```python test
def test_accordion_disabled(demo):
    triggers = demo.get_by_role("button")
    expect(triggers).to_have_count(3)
    for i in range(3):
        expect(triggers.nth(i)).to_be_disabled()
```

### Orientation

We use `orientation` prop to set the orientation of the accordion to `vertical` or `horizontal`. By default, the orientation
will be set to `vertical`. Note that, the orientation prop won't change the visual orientation but the
functional orientation of the accordion. This means that for vertical orientation, the up and down arrow keys moves focus between the next or previous item,
while for horizontal orientation, the left or right arrow keys moves focus between items.

```python demo
rx.accordion.root(
    rx.accordion.item(
        header="First Item", content="The first accordion item's content"
    ),
    rx.accordion.item(
        header="Second Item",
        content="The second accordion item's content",
    ),
    rx.accordion.item(
        header="Third item", content="The third accordion item's content"
    ),
    collapsible=True,
    width="300px",
    orientation="vertical",
)
```

```python test
def test_accordion_vertical_keyboard(demo):
    demo.get_by_role("button", name="First Item").focus()
    demo.get_by_role("button", name="First Item").press("ArrowDown")
    expect(demo.get_by_role("button", name="Second Item")).to_be_focused()
```

```python demo
rx.accordion.root(
    rx.accordion.item(
        header="First Item", content="The first accordion item's content"
    ),
    rx.accordion.item(
        header="Second Item",
        content="The second accordion item's content",
    ),
    rx.accordion.item(
        header="Third item", content="The third accordion item's content"
    ),
    collapsible=True,
    width="300px",
    orientation="horizontal",
)
```

```python test
def test_accordion_horizontal_keyboard(demo):
    demo.get_by_role("button", name="First Item").focus()
    demo.get_by_role("button", name="First Item").press("ArrowRight")
    expect(demo.get_by_role("button", name="Second Item")).to_be_focused()
```

### Variant

```python demo
rx.flex(
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item",
            content="The second accordion item's content",
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=True,
        variant="classic",
    ),
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item",
            content="The second accordion item's content",
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=True,
        variant="soft",
    ),
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item",
            content="The second accordion item's content",
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=True,
        variant="outline",
    ),
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item",
            content="The second accordion item's content",
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=True,
        variant="surface",
    ),
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item",
            content="The second accordion item's content",
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=True,
        variant="ghost",
    ),
    direction="row",
    spacing="2",
)
```

```python test
def test_accordion_variants(demo):
    roots = demo.locator("[data-variant]:has(> .AccordionItem)")
    expect(roots).to_have_count(5)
    for i, variant in enumerate(["classic", "soft", "outline", "surface", "ghost"]):
        expect(roots.nth(i)).to_have_attribute("data-variant", variant)
    expect(demo.get_by_role("button", name="Third item")).to_have_count(5)
    roots.last.get_by_role("button", name="Third item").click()
    expect(roots.last.get_by_text("The third accordion item's content")).to_be_visible()
```

### Color Scheme

We use the `color_scheme` prop to assign a specific color to the accordion background, ignoring the global theme.

```python demo
rx.flex(
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item",
            content="The second accordion item's content",
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=True,
        width="300px",
        color_scheme="grass",
    ),
    rx.accordion.root(
        rx.accordion.item(
            header="First Item", content="The first accordion item's content"
        ),
        rx.accordion.item(
            header="Second Item",
            content="The second accordion item's content",
        ),
        rx.accordion.item(
            header="Third item", content="The third accordion item's content"
        ),
        collapsible=True,
        width="300px",
        color_scheme="green",
    ),
    direction="row",
    spacing="2",
)
```

```python test
def test_accordion_color_schemes(demo):
    roots = demo.locator("[data-accent-color]:has(> .AccordionItem)")
    expect(roots).to_have_count(2)
    expect(roots.first).to_have_attribute("data-accent-color", "grass")
    expect(roots.nth(1)).to_have_attribute("data-accent-color", "green")
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

```python test
def test_accordion_controlled_value(demo):
    expect(demo.get_by_role("button", name="Test button")).to_be_visible()
    demo.get_by_role("button", name="Is it unstyled?").click()
    expect(demo.get_by_text("item_2 selected")).to_be_visible()
    expect(demo.get_by_text("It's unstyled by default", exact=False)).to_be_visible()
    expect(demo.get_by_role("button", name="Test button")).to_be_hidden()
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

```python test
def test_accordion_item_values(demo):
    third = demo.get_by_text("The third accordion item's content")
    expect(third).to_be_hidden()
    demo.get_by_role("button", name="Third item").click()
    expect(third).to_be_visible()
    demo.get_by_role("button", name="Third item").click()
    expect(third).to_be_hidden()
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
        header="Second Item",
        content="The second accordion item's content",
    ),
    rx.accordion.item(
        header="Third item", content="The third accordion item's content"
    ),
    collapsible=True,
    width="300px",
    color_scheme="blue",
)
```

```python test
def test_accordion_item_disabled(demo):
    expect(demo.get_by_role("button", name="First Item")).to_be_disabled()
    demo.get_by_role("button", name="Second Item").click()
    expect(demo.get_by_text("The second accordion item's content")).to_be_visible()
```
