```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from pcweb.pages.docs import styling
```

# Grid

A simple responsive grid layout. We specify the number of columns to the `grid_template_columns` property as a list. The grid will automatically adjust the number of columns based on the screen size.

For details, see the [responsive docs page]({styling.responsive.path}).

## Cards

```python demo
rx.grid(
    rx.foreach(
        rx.Var.range(12),
        lambda i: rx.card(f"Card {i + 1}", height="10vh"),
    ),
	gap="1rem",
    grid_template_columns=["1fr", "repeat(2, 1fr)", "repeat(2, 1fr)", "repeat(3, 1fr)", "repeat(4, 1fr)"],
    width="100%"
)
```

## Inset cards

```python demo
rx.grid(
	rx.foreach(
		rx.Var.range(12),
		lambda i: rx.card(
			rx.inset(
				rx.image(
					src=f"{REFLEX_ASSETS_CDN}other/reflex_banner.png",
					width="100%",
					height="auto",
				),
				side="top",
				pb="current"
			),
			rx.text(
				f"Card {i + 1}",
			),
		),
	),
	gap="1rem",
	grid_template_columns=["1fr", "repeat(2, 1fr)", "repeat(2, 1fr)", "repeat(3, 1fr)", "repeat(4, 1fr)"],
	width="100%"
)
```
