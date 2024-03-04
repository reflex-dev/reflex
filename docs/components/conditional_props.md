```python exec
import reflex as rx
```

# Conditional Props

Sometimes you want to set a prop based on a condition. You can use the `rx.cond` function to do this.

```python demo exec
class PropCondState(rx.State):

    value: list[int]
    
    def set_end(self, value: int):
        self.value = value


def cond_prop():
    return rx.slider(
        default_value=[50],
        on_value_commit=PropCondState.set_end,
        color_scheme=rx.cond(PropCondState.value[0] > 50, "green", "pink"),
        width="100%",
    )
```
