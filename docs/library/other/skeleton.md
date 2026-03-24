---
description: Skeleton, a loading placeholder component for content that is not yet available.
components:
    - rx.skeleton
---

```python exec
import reflex as rx
```

# Skeleton (loading placeholder)

`Skeleton` is a loading placeholder component that serves as a visual placeholder while content is loading.
It is useful for maintaining the layout's structure and providing users with a sense of progression while awaiting the final content.

```python demo
rx.vstack(
    rx.skeleton(rx.button("button-small"), height="10px"),
    rx.skeleton(rx.button("button-big"), height="20px"),
    rx.skeleton(rx.text("Text is loaded."), loading=True,),
    rx.skeleton(rx.text("Text is already loaded."), loading=False,),
),
```

When using `Skeleton` with text, wrap the text itself instead of the parent element to have a placeholder of the same size.

Use the loading prop to control whether the skeleton or its children are displayed. Skeleton preserves the dimensions of children when they are hidden and disables interactive elements.
