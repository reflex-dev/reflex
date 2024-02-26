---
components:
    - rx.chakra.Button
    - rx.chakra.IconButton
---

```python exec
import reflex as rx
from pcweb.templates.docpage import docdemo


basic_button = """rx.chakra.button("Click Me!")
"""
button_style = """rx.chakra.button_group(
    rx.chakra.button("Example", bg="lightblue", color="black", size = 'sm'),
    rx.chakra.button("Example", bg="orange", color="white", size = 'md'),
    rx.chakra.button("Example", color_scheme="red", size = 'lg'),
    space = "1em",
)
"""
button_visual_states = """rx.chakra.button_group(
    rx.chakra.button("Example", bg="lightgreen", color="black", is_loading = True),
    rx.chakra.button("Example", bg="lightgreen", color="black", is_disabled = True),
    rx.chakra.button("Example", bg="lightgreen", color="black", is_active = True),
    space = '1em',
)
"""

button_group_example = """rx.chakra.button_group(
    rx.chakra.button(rx.chakra.icon(tag="minus"), color_scheme="red"),
    rx.chakra.button(rx.chakra.icon(tag="add"), color_scheme="green"),
    is_attached=True,
)
"""

button_state = """class ButtonState(rx.State):
    count: int = 0

    def increment(self):
        self.count += 1

    def decrement(self):
        self.count -= 1
"""
exec(button_state)
button_state_example = """rx.chakra.hstack(
    rx.chakra.button(
        "Decrement",
        bg="#fef2f2",
        color="#b91c1c",
        border_radius="lg",
        on_click=ButtonState.decrement,
    ),
    rx.chakra.heading(ButtonState.count, font_size="2em", padding_x="0.5em"),
    rx.chakra.button(
        "Increment",
        bg="#ecfdf5",
        color="#047857",
        border_radius="lg",
        on_click=ButtonState.increment,
    ),
)
"""


button_state_code = f"""
import reflex as rx

{button_state}

def index():
    return {button_state_example}

app = rx.chakra.App()
app.add_page(index)"""

button_state2 = """class ExampleButtonState(rx.State):
    text_value: str = "Random value"
"""
exec(button_state2)

button_state2_render_code = """rx.chakra.vstack(
 rx.chakra.text(ExampleButtonState.text_value),
        rx.chakra.button(
            "Change Value",
            on_click=ExampleButtonState.set_text_value("Modified value"))
    )
"""

button_state2_code = f"""
import reflex as rx

{button_state2}

def index():
    return {button_state2_render_code}

app = rx.chakra.App()
app.add_page(index)"""


button_sizes = (
"""rx.chakra.button_group(
        rx.chakra.button(
        'Example', bg='lightblue', color='black', size='sm'
        ),
        rx.chakra.button(
            'Example', bg='orange', color='white', size='md'
        ),
        rx.chakra.button('Example', color_scheme='red', size='lg'),
)
"""  
)

button_colors = (
"""rx.chakra.button_group(
        rx.chakra.button('White Alpha', color_scheme='whiteAlpha', min_width='unset'),
        rx.chakra.button('Black Alpha', color_scheme='blackAlpha', min_width='unset'),
        rx.chakra.button('Gray', color_scheme='gray', min_width='unset'),
        rx.chakra.button('Red', color_scheme='red', min_width='unset'),
        rx.chakra.button('Orange', color_scheme='orange', min_width='unset'),
        rx.chakra.button('Yellow', color_scheme='yellow', min_width='unset'),
        rx.chakra.button('Green', color_scheme='green', min_width='unset'),
        rx.chakra.button('Teal', color_scheme='teal', min_width='unset'),
        rx.chakra.button('Blue', color_scheme='blue', min_width='unset'),
        rx.chakra.button('Cyan', color_scheme='cyan', min_width='unset'),
        rx.chakra.button('Purple', color_scheme='purple', min_width='unset'),
        rx.chakra.button('Pink', color_scheme='pink', min_width='unset'),
        rx.chakra.button('LinkedIn', color_scheme='linkedin', min_width='unset'),
        rx.chakra.button('Facebook', color_scheme='facebook', min_width='unset'),
        rx.chakra.button('Messenger', color_scheme='messenger', min_width='unset'),
        rx.chakra.button('WhatsApp', color_scheme='whatsapp', min_width='unset'),
        rx.chakra.button('Twitter', color_scheme='twitter', min_width='unset'),
        rx.chakra.button('Telegram', color_scheme='telegram', min_width='unset'),
        width='100%',
)

""" 
)

button_colors_render_code = (
"""rx.chakra.button_group(
        rx.chakra.button('White Alpha', color_scheme='whiteAlpha'),
        rx.chakra.button('Black Alpha', color_scheme='blackAlpha'),
        rx.chakra.button('Gray', color_scheme='gray'),
        rx.chakra.button('Red', color_scheme='red'),
        rx.chakra.button('Orange', color_scheme='orange'),
        rx.chakra.button('Yellow', color_scheme='yellow'),
        rx.chakra.button('Green', color_scheme='green'),
        rx.chakra.button('Teal', color_scheme='teal'),
        rx.chakra.button('Blue', color_scheme='blue'),
        rx.chakra.button('Cyan', color_scheme='cyan'),
        rx.chakra.button('Purple', color_scheme='purple'),
        rx.chakra.button('Pink', color_scheme='pink'),
        rx.chakra.button('LinkedIn', color_scheme='linkedin'),
        rx.chakra.button('Facebook', color_scheme='facebook'),
        rx.chakra.button('Messenger', color_scheme='messenger'),
        rx.chakra.button('WhatsApp', color_scheme='whatsapp'),
        rx.chakra.button('Twitter', color_scheme='twitter'),
        rx.chakra.button('Telegram', color_scheme='telegram'),
)

""" 
)

button_variants = (
"""rx.chakra.button_group(
        rx.chakra.button('Ghost Button', variant='ghost'),
        rx.chakra.button('Outline Button', variant='outline'),
        rx.chakra.button('Solid Button', variant='solid'),
        rx.chakra.button('Link Button', variant='link'),
        rx.chakra.button('Unstyled Button', variant='unstyled'),
    )
"""  

)

button_disable = (
"""rx.chakra.button('Inactive button', is_disabled=True)"""  
)
  
loading_states = (
"""rx.chakra.button(
            'Random button',
            is_loading=True,
            loading_text='Loading...',
            spinner_placement='start'
    )
"""  
)

stack_buttons_vertical = (
"""rx.chakra.stack(
        rx.chakra.button('Button 1'),
        rx.chakra.button('Button 2'),
        rx.chakra.button('Button 3'),
        direction='column',
)

"""  
)

stack_buttons_horizontal = (
"""rx.chakra.stack(
        rx.chakra.button('Button 1'),
        rx.chakra.button('Button 2'),
        rx.chakra.button('Button 3'),
        direction='row',
)
"""  
)

button_group = (
"""rx.chakra.button_group(
            rx.chakra.button('Option 1'),
            rx.chakra.button('Option 2'),
            rx.chakra.button('Option 3'),
            variant='outline',
         is_attached=True,
        )
"""  

)

```

# Button

Buttons are essential elements in your application's user interface that users can click to trigger events.
This documentation will help you understand how to use button components effectively in your Reflex application.

## Basic Usage

A basic button component is created using the `rx.chakra.button` method:

```python eval
docdemo(basic_button)
```

## Button Sizing

You can change the size of a button by setting the size prop to one of the following
values: `xs`,`sm`,`md`, or `lg`.

```python eval
docdemo(button_sizes)
```

## Button colors

Customize the appearance of buttons by adjusting their color scheme through the color_scheme prop.
You have the flexibility to choose from a range of color scales provided by your design
system, such as whiteAlpha, blackAlpha, gray, red, blue, or even utilize your own custom color scale.

```python demo box
eval(button_colors)
```

```python
{button_colors_render_code.strip()}
```

## Button Variants

You can customize the visual style of your buttons using the variant prop. Here are the available button variants:

- `ghost`: A button with a transparent background and visible text.
- `outline`: A button with no background color but with a border.
- `solid`: The default button style with a solid background color.
- `link`: A button that resembles a text link.
- `unstyled`: A button with no specific styling.

```python eval
docdemo(button_variants)
```

## Disabling Buttons

Make buttons inactive by setting the `is_disabled` prop to `True`.

```python eval
docdemo(button_disable)
```

## Handling Loading States

To indicate a loading state for a button after it's clicked, you can use the following properties:

- `is_loading`: Set this property to `True` to display a loading spinner.
- `loading_text`: Optionally, you can provide loading text to display alongside the spinner.
- `spinner_placement`: You can specify the placement of the spinner element, which is 'start' by default.

```python eval
docdemo(loading_states)
```

## Handling Click Events

You can define what happens when a button is clicked using the `on_click` event argument.
For example, to change a value in your application state when a button is clicked:

```python demo box
eval(button_state2_render_code)
```

```python
{button_state2_code.strip()}
```

In the code above, The value of `text_value` is changed through the `set_text_value` event handler upon clicking the button.
Reflex provides a default setter event_handler for every base var which can be accessed by prefixing the base var with the `set_` keyword.

Here’s another example that creates two buttons to increase and decrease a count value:

```python demo box
eval(button_state_example)
```

```python
{button_state_code.strip()}
```

In this example, we have a `ButtonState` state class that maintains a count base var.
When the "Increment" button is clicked, it triggers the `ButtonState.increment` event handler, and when the "Decrement"
button is clicked, it triggers the `ButtonState.decrement` event handler.

## Special Events and Server-Side Actions

Buttons in Reflex can trigger special events and server-side actions,
allowing you to create dynamic and interactive user experiences.
You can bind these events to buttons using the `on_click` prop.
For a comprehensive list of
available special events and server-side actions, please refer to the
[Special Events Documentation](/docs/api-reference/special-events) for detailed information and usage examples.

## Grouping Buttons

In your Reflex application, you can group buttons effectively using the `Stack` component and
the `ButtonGroup` component. Each of these options offers unique capabilities to help you structure
and style your buttons.

## Using the `Stack` Component

The `Stack` component allows you to stack buttons both vertically and horizontally, providing a flexible
layout for your button arrangements.

## Stack Buttons Vertically

```python eval
docdemo(stack_buttons_vertical)
```

## Stack Buttons Horizontally

```python eval
docdemo(stack_buttons_horizontal)
```

With the `stack` component, you can easily create both vertical and horizontal button arrangements.

## Using the `rx.chakra.button_group` Component

The `ButtonGroup` component is designed specifically for grouping buttons. It allows you to:

- Set the `size` and `variant` of all buttons within it.
- Add `spacing` between the buttons.
- Flush the buttons together by removing the border radius of their children as needed.

```python eval
docdemo(button_group)
```

```md alert
# The `ButtonGroup` component stacks buttons horizontally, whereas the `Stack` component allows stacking buttons both vertically and horizontally.
```
