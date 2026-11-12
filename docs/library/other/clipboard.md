---
components:
  - rx.clipboard
---

```python exec
import reflex as rx
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

```python test
def test_clipboard_page_paste_shows_toast(page, demo):
    expect(demo.get_by_text("Paste Content Here")).to_be_visible()
    page.evaluate(
        """() => {
            const data = new DataTransfer();
            data.setData("text/plain", "hello reflex");
            document.body.dispatchEvent(
                new ClipboardEvent("paste", {clipboardData: data, bubbles: true})
            );
        }"""
    )
    expect(page.get_by_text("Pasted text/plain data: hello reflex")).to_be_visible()
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
            on_paste=ClipboardPasteImageState.on_paste.stop_propagation,
        ),
        rx.clipboard(
            rx.input(placeholder="Paste Image (prevent default)"),
            on_paste=ClipboardPasteImageState.on_paste.prevent_default,
        ),
        rx.image(
            src=ClipboardPasteImageState.last_image_uri,
            alt="Image pasted from clipboard",
        ),
    )
```

```python test
def test_clipboard_scoped_image_paste(page, demo):
    paste = """(el, file) => {
        const data = new DataTransfer();
        if (file) {
            data.items.add(new File([new Uint8Array([1, 2, 3])], "a.png", {type: "image/png"}));
        } else {
            data.setData("text/plain", "not an image");
        }
        const event = new ClipboardEvent("paste", {clipboardData: data, bubbles: true, cancelable: true});
        el.dispatchEvent(event);
        return event.defaultPrevented;
    }"""
    text_input = demo.get_by_placeholder("Paste Image (prevent default)")
    assert text_input.evaluate(paste, False) is True
    expect(page.get_by_text("Did not find an image in the pasted data")).to_be_visible()
    demo.get_by_placeholder("Paste Image (stop propagation)").evaluate(paste, True)
    expect(
        demo.get_by_role("img", name="Image pasted from clipboard")
    ).to_have_attribute("src", "data:image/png;base64,AQID")
```
