A style can play an animation: `keyframes({...})` from `reflex_components_ui.style` is the value of `animation_name`, in a style table or in the `style` of an element, and compiles to a class name like any other style.

```python
from reflex_components_ui.style import keyframes

rx.ui.box(
    animation_name=keyframes({"from": {"opacity": 1}, "to": {"opacity": 0.25}}),
    animation_duration="800ms",
    animation_iteration_count="infinite",
)
```
