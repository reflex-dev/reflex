---
components:
  - rx.code_block
---

```python exec
import reflex as rx
```

# Code Block

The Code Block component can be used to display code easily within a website.
Put in a multiline string with the correct spacing and specify and language to show the desired code.

```python demo
rx.code_block(
    """def fib(n):
    if n <= 1:
        return n
    else:
        return(fib(n-1) + fib(n-2))""",
    language="python",
    show_line_numbers=True,
)
```

```python test
def test_code_block_with_line_numbers(demo):
    code = demo.locator("pre code")
    expect(code).to_have_class("language-python")
    expect(code.locator(".linenumber")).to_have_text(["1", "2", "3", "4", "5"])
    expect(code).to_have_text(
        "1def fib(n):\n2    if n <= 1:\n3        return n\n4    else:\n5        return(fib(n-1) + fib(n-2))"
    )
```

## Themes

The `theme` prop must be set to a `Theme` value accessed from the `rx.code_block.themes` namespace; strings are not accepted. By default, the code block uses `one_light` in light mode and `one_dark` in dark mode.

```python demo
rx.code_block(
    """print("Hello, world!")""",
    language="python",
    theme=rx.code_block.themes.dracula,
)
```

```python test
def test_code_block_dracula_theme(demo):
    pre = demo.locator("pre")
    expect(pre).to_have_text('print("Hello, world!")')
    # Dracula's background color.
    expect(pre).to_have_css("background-color", "rgb(40, 42, 54)")
```

To pick a theme that responds to the global color mode, pass `rx.color_mode_cond` with the desired light and dark variants:

```python demo
rx.code_block(
    """print("Hello, world!")""",
    language="python",
    theme=rx.color_mode_cond(
        light=rx.code_block.themes.one_light,
        dark=rx.code_block.themes.one_dark,
    ),
)
```

```python test
def test_code_block_color_mode_theme(demo):
    pre = demo.locator("pre")
    expect(pre).to_have_text('print("Hello, world!")')
    # one_light's background color.
    expect(pre).to_have_css("background-color", "rgb(250, 250, 250)")
```
