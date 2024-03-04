---
components:
    - rx.chakra.Spinner
---

```python exec
import reflex as rx
```

# Spinner

Spinners provide a visual cue that an event is either processing, awaiting a course of change or a result.

```python demo
rx.chakra.hstack(
    rx.chakra.spinner(color="red", size="xs"),
    rx.chakra.spinner(color="orange", size="sm"),
    rx.chakra.spinner(color="green", size="md"),
    rx.chakra.spinner(color="blue", size="lg"),
    rx.chakra.spinner(color="purple", size="xl"),
)
```

Along with the color you can style further with props such as speed, empty color, and thickness.

```python demo
rx.chakra.hstack(
    rx.chakra.spinner(color="lightgreen", thickness=1, speed="1s", size="xl"),
    rx.chakra.spinner(color="lightgreen", thickness=5, speed="1.5s", size="xl"),
    rx.chakra.spinner(
        color="lightgreen",
        thickness=10,
        speed="2s",
        empty_color="red",
        size="xl",
    ),
)
```
