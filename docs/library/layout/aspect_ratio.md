---
components:
  - rx.aspect_ratio
---

```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
```

# Aspect Ratio

Displays content with a desired ratio.

## Basic Example

Setting the `ratio` prop will adjust the width or height
of the content such that the `width` divided by the `height` equals the `ratio`.
For responsive scaling, set the `width` or `height` of the content to `"100%"`.

```python demo
rx.grid(
    rx.aspect_ratio(
        rx.box(
            "Widescreen 16:9",
            background_color="papayawhip",
            width="100%",
            height="100%",
        ),
        ratio=16 / 9,
    ),
    rx.aspect_ratio(
        rx.box(
            "Letterbox 4:3",
            background_color="orange",
            width="100%",
            height="100%",
        ),
        ratio=4 / 3,
    ),
    rx.aspect_ratio(
        rx.box(
            "Square 1:1",
            background_color="green",
            width="100%",
            height="100%",
        ),
        ratio=1,
    ),
    rx.aspect_ratio(
        rx.box(
            "Portrait 5:7",
            background_color="lime",
            width="100%",
            height="100%",
        ),
        ratio=5 / 7,
    ),
    spacing="2",
    width="25%",
)
```

```md alert warning
# Never set `height` or `width` directly on an `aspect_ratio` component or its contents.

Instead, wrap the `aspect_ratio` in a `box` that constrains either the width or the height, then set the content width and height to `"100%"`.
```

```python demo
rx.flex(
    *[
        rx.box(
            rx.aspect_ratio(
                rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="100%", height="100%"),
                ratio=ratio,
            ),
            width="20%",
        )
        for ratio in [16 / 9, 3 / 2, 2 / 3, 1]
    ],
    justify="between",
    width="100%",
)
```
