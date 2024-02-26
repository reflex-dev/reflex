---
components:
    - rx.chakra.Skeleton
    - rx.chakra.SkeletonCircle
    - rx.chakra.SkeletonText
---

```python exec
import reflex as rx
```

# Skeleton

Skeleton is used to display the loading state of some components.

```python demo
rx.chakra.stack(
    rx.chakra.skeleton(height="10px", speed=1.5),
    rx.chakra.skeleton(height="15px", speed=1.5),
    rx.chakra.skeleton(height="20px", speed=1.5),
    width="50%",
)
```

Along with the basic skeleton box there are also a skeleton circle and text for ease of use.

```python demo
rx.chakra.stack(
    rx.chakra.skeleton_circle(size="30px"),
    rx.chakra.skeleton_text(no_of_lines=8),
    width="50%",
)
```

Another feature of skeleton is the ability to animate colors.
We provide the args start_color and end_color to animate the color of the skeleton component(s).

```python demo
rx.chakra.stack(
    rx.chakra.skeleton_text(
        no_of_lines=5, start_color="pink.500", end_color="orange.500"
    ),
    width="50%",
)
```

You can prevent the skeleton from loading by using the `is_loaded` prop.

```python demo
rx.chakra.vstack(
    rx.chakra.skeleton(rx.chakra.text("Text is already loaded."), is_loaded=True),
    rx.chakra.skeleton(rx.chakra.text("Text is already loaded."), is_loaded=False),
)
```
