---
components:
  - rx.text.kbd
---

```python exec
import reflex as rx
```

# rx.text.kbd (Keyboard)

Represents keyboard input or a hotkey.

```python demo
rx.text.kbd("Shift + Tab")
```

```python test
def test_kbd_renders_hotkey(demo):
    expect(demo.locator("kbd")).to_have_text("Shift + Tab")
```

## Size

Use the `size` prop to control text size. This prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease.

```python demo
rx.flex(
    rx.text.kbd("Shift + Tab", size="1"),
    rx.text.kbd("Shift + Tab", size="2"),
    rx.text.kbd("Shift + Tab", size="3"),
    rx.text.kbd("Shift + Tab", size="4"),
    rx.text.kbd("Shift + Tab", size="5"),
    rx.text.kbd("Shift + Tab", size="6"),
    rx.text.kbd("Shift + Tab", size="7"),
    rx.text.kbd("Shift + Tab", size="8"),
    rx.text.kbd("Shift + Tab", size="9"),
    direction="column",
    spacing="3",
)
```

```python test
def test_kbd_sizes_increase(demo):
    keys = demo.locator("kbd")
    expect(keys).to_have_count(9)
    expect(keys).to_have_text(["Shift + Tab"] * 9)
    sizes = keys.evaluate_all(
        "els => els.map(e => parseFloat(getComputedStyle(e).fontSize))"
    )
    assert sizes == sorted(set(sizes))
```
