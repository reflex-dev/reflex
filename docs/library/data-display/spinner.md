---
components:
  - rx.spinner
---

# Spinner

Spinner is used to display an animated loading indicator when a task is in progress.

```python exec
import reflex as rx
```

```python demo
rx.spinner()
```

```python test
def test_spinner_renders(demo):
    expect(demo.locator(".rt-Spinner")).to_have_count(1)
```

## Basic Examples

Spinner can have different sizes.

```python demo
rx.vstack(
    rx.hstack(
        rx.spinner(size="1"),
        rx.spinner(size="2"),
        rx.spinner(size="3"),
        align="center",
        gap="1em",
    )
)
```

```python test
def test_spinner_sizes(demo):
    spinners = demo.locator(".rt-Spinner")
    expect(spinners).to_have_count(3)
    for i, size in enumerate(["1", "2", "3"]):
        expect(spinners.nth(i)).to_have_class(re.compile(rf"\brt-r-size-{size}\b"))
```

## Demo with buttons

Buttons have their own loading prop that automatically composes a spinner.

```python demo
rx.button("Bookmark", loading=True)
```

```python test
def test_button_loading_spinner(demo):
    button = demo.get_by_role("button", name="Bookmark")
    expect(button).to_be_disabled()
    expect(button.locator(".rt-Spinner")).to_have_count(1)
```

## Spinner inside a button

If you have an icon inside the button, you can use the button's disabled state and wrap the icon in a standalone rx.spinner to achieve a more sophisticated design.

```python demo
rx.button(rx.spinner(loading=True), "Bookmark", disabled=True)
```

```python test
def test_spinner_inside_disabled_button(demo):
    button = demo.get_by_role("button", name="Bookmark")
    expect(button).to_be_disabled()
    expect(button).to_have_text("Bookmark")
    expect(button.locator(".rt-Spinner")).to_have_count(1)
```
