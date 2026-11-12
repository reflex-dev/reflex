```python exec
import reflex as rx
```

# Grid

A simple responsive grid layout. We specify the number of columns to the `grid_template_columns` property as a list. The grid will automatically adjust the number of columns based on the screen size.

For details, see the [responsive docs page](/docs/styling/responsive/).

## Cards

```python demo
rx.grid(
    rx.foreach(
        rx.Var.range(12),
        lambda i: rx.card(f"Card {i + 1}", height="10vh"),
    ),
    gap="1rem",
    grid_template_columns=[
        "1fr",
        "repeat(2, 1fr)",
        "repeat(2, 1fr)",
        "repeat(3, 1fr)",
        "repeat(4, 1fr)",
    ],
    width="100%",
)
```

```python test
def test_grid_of_twelve_cards(demo):
    expect(demo.get_by_text(re.compile(r"^Card \d+$"))).to_have_text([
        f"Card {i}" for i in range(1, 13)
    ])
```

## Inset cards

```python demo
rx.grid(
    rx.foreach(
        rx.Var.range(12),
        lambda i: rx.card(
            rx.inset(
                rx.image(
                    src="https://web.reflex-assets.dev/other/reflex_banner.png",
                    alt="Reflex banner image",
                    width="100%",
                    height="auto",
                ),
                side="top",
                pb="current",
            ),
            rx.text(
                f"Card {i + 1}",
            ),
        ),
    ),
    gap="1rem",
    grid_template_columns=[
        "1fr",
        "repeat(2, 1fr)",
        "repeat(2, 1fr)",
        "repeat(3, 1fr)",
        "repeat(4, 1fr)",
    ],
    width="100%",
)
```

```python test
def test_grid_of_image_cards(demo):
    expect(demo.get_by_role("img", name="Reflex banner image")).to_have_count(12)
    expect(demo.get_by_role("paragraph")).to_have_text([
        f"Card {i}" for i in range(1, 13)
    ])
```
