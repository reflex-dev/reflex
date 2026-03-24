```python exec
import reflex as rx
```

# Auto Scroll

The `rx.auto_scroll` component is a div that automatically scrolls to the bottom when new content is added. This is useful for chat interfaces, logs, or any container where new content is dynamically added and you want to ensure the most recent content is visible.

## Basic Usage

```python demo exec
import reflex as rx

class AutoScrollState(rx.State):
    messages: list[str] = ["Initial message"]
    
    def add_message(self):
        self.messages.append(f"New message #{len(self.messages) + 1}")

def auto_scroll_example():
    return rx.vstack(
        rx.auto_scroll(
            rx.foreach(
                AutoScrollState.messages,
                lambda message: rx.box(
                    message,
                    padding="0.5em",
                    border_bottom="1px solid #eee",
                    width="100%"
                )
            ),
            height="200px",
            width="300px",
            border="1px solid #ddd",
            border_radius="md",
        ),
        rx.button("Add Message", on_click=AutoScrollState.add_message),
        width="300px",
        align_items="center",
    )
```

The `auto_scroll` component automatically scrolls to show the newest content when it's added. In this example, each time you click "Add Message", a new message is added to the list and the container automatically scrolls to display it.

## When to Use Auto Scroll

- **Chat applications**: Keep the chat window scrolled to the most recent messages.
- **Log viewers**: Automatically follow new log entries as they appear.
- **Feed interfaces**: Keep the newest content visible in dynamically updating feeds.

## Props

`rx.auto_scroll` is based on the `rx.div` component and inherits all of its props. By default, it sets `overflow="auto"` to enable scrolling.

Some common props you might use with `auto_scroll`:

- `height`: Set the height of the scrollable container.
- `width`: Set the width of the scrollable container.
- `padding`: Add padding inside the container.
- `border`: Add a border around the container.
- `border_radius`: Round the corners of the container.

## How It Works

The component tracks when new content is added and maintains the scroll position in two scenarios:

1. When the user is already near the bottom of the content (within 50 pixels), it will scroll to the bottom when new content is added.
2. When the container didn't have a scrollbar before but does now (due to new content), it will automatically scroll to the bottom.

This behavior ensures that users can scroll up to view older content without being forced back to the bottom, while still automatically following new content in most cases.
