---
components:
    - rx.chakra.CircularProgress
    - rx.chakra.CircularProgressLabel
---

```python exec
import reflex as rx
```

# CircularProgress

The CircularProgress component is used to indicate the progress for determinate and indeterminate processes.
Determinate progress: fills the circular track with color, as the indicator moves from 0 to 360 degrees.
Indeterminate progress: grows and shrinks the indicator while moving along the circular track.

```python demo
rx.chakra.hstack(
    rx.chakra.circular_progress(value=0),
    rx.chakra.circular_progress(value=25),
    rx.chakra.circular_progress(rx.chakra.circular_progress_label(50), value=50),
    rx.chakra.circular_progress(value=75),
    rx.chakra.circular_progress(value=100),
    rx.chakra.circular_progress(is_indeterminate=True),
)
```
