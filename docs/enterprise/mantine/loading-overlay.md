---
title: Loading Overlay
---

# Loading Overlay component
`rxe.mantine.loading_overlay` is a component that displays a loading overlay on top of its children. It is useful for indicating that a process is ongoing and prevents user interaction with the underlying content.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class LoadingOverlayState(rx.State):
    loading: bool = False

    @rx.event
    def toggle_loading(self):
        self.loading = not self.loading

def loading_overlay_example():
    return rx.container(
        rxe.mantine.loading_overlay(
            rx.text(
                "Loading Overlay Example",
                height="200px",
                width="100px",
            ),
            overlay_props={"radius": "sm", "blur": 2},
            visible=LoadingOverlayState.loading,
            z_index=1000,
        ),
    ),rx.button("Toggle Loading", on_click=LoadingOverlayState.toggle_loading),
```
