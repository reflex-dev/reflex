---
components:
  - rx.clipboard
---

```python exec
import reflex as rx
from pcweb.pages.docs import styling
```

# Clipboard

_New in 0.5.6_

The Clipboard component can be used to respond to paste events with complex data.

If the Clipboard component is included in a page without children,
`rx.clipboard()`, then it will attach to the document's `paste` event handler
and will be triggered when data is pasted anywhere into the page.

```python demo exec
class ClipboardPasteState(rx.State):
    @rx.event
    def on_paste(self, data: list[tuple[str, str]]):
        for mime_type, item in data:
            yield rx.toast(f"Pasted {mime_type} data: {item}")


def clipboard_example():
    return rx.fragment(
        rx.clipboard(on_paste=ClipboardPasteState.on_paste),
        "Paste Content Here",
    )
```

The `data` argument passed to the `on_paste` method is a list of tuples, where
each tuple contains the MIME type of the pasted data and the data itself. Binary
data will be base64 encoded as a data URI, and can be decoded using python's
`urlopen` or used directly as the `src` prop of an image.

## Scoped Paste Events

If you want to limit the scope of the paste event to a specific element, wrap
the `rx.clipboard` component around the elements that should trigger the paste
event.

To avoid having outer paste handlers also trigger the event, you can use the
event action `.stop_propagation` to prevent the paste from bubbling up through
the DOM.

If you need to also prevent the default action of pasting the data into a text
box, you can also attach the `.prevent_default` action.

```python demo exec
class ClipboardPasteImageState(rx.State):
    last_image_uri: str = ""

    def on_paste(self, data: list[tuple[str, str]]):
        for mime_type, item in data:
            if mime_type.startswith("image/"):
                self.last_image_uri = item
                break
        else:
            return rx.toast("Did not find an image in the pasted data")


def clipboard_image_example():
    return rx.vstack(
        rx.clipboard(
            rx.input(placeholder="Paste Image (stop propagation)"),
            on_paste=ClipboardPasteImageState.on_paste.stop_propagation
        ),
        rx.clipboard(
            rx.input(placeholder="Paste Image (prevent default)"),
            on_paste=ClipboardPasteImageState.on_paste.prevent_default
        ),
        rx.image(src=ClipboardPasteImageState.last_image_uri),
    )
```
