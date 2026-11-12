---
components:
  - rx.aspect_ratio
---

```python exec
import reflex as rx
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
            color="black",
            width="100%",
            height="100%",
        ),
        ratio=16 / 9,
    ),
    rx.aspect_ratio(
        rx.box(
            "Letterbox 4:3",
            background_color="orange",
            color="black",
            width="100%",
            height="100%",
        ),
        ratio=4 / 3,
    ),
    rx.aspect_ratio(
        rx.box(
            "Square 1:1",
            background_color="green",
            color="white",
            width="100%",
            height="100%",
        ),
        ratio=1,
    ),
    rx.aspect_ratio(
        rx.box(
            "Portrait 5:7",
            background_color="lime",
            color="black",
            width="100%",
            height="100%",
        ),
        ratio=5 / 7,
    ),
    spacing="2",
    width="25%",
)
```

```python test
def test_aspect_ratio_boxes_keep_ratio(demo):
    for label, ratio in [
        ("Widescreen 16:9", 16 / 9),
        ("Letterbox 4:3", 4 / 3),
        ("Square 1:1", 1),
        ("Portrait 5:7", 5 / 7),
    ]:
        box = demo.get_by_text(label, exact=True)
        expect(box).to_be_visible()
        size = box.bounding_box()
        assert size["width"] / size["height"] == pytest.approx(ratio, rel=0.02)
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
                rx.image(
                    src="https://web.reflex-assets.dev/other/logo.jpg",
                    alt="Reflex logo",
                    width="100%",
                    height="100%",
                ),
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

```python test
def test_aspect_ratio_images_side_by_side(demo):
    images = demo.get_by_role("img", name="Reflex logo")
    expect(images).to_have_count(4)
    boxes = [images.nth(i).bounding_box() for i in range(4)]
    for box, ratio in zip(boxes, [16 / 9, 3 / 2, 2 / 3, 1]):
        assert box["width"] / box["height"] == pytest.approx(ratio, rel=0.02)
    xs = [box["x"] for box in boxes]
    assert xs == sorted(set(xs))
```
