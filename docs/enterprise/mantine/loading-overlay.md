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
    return (
        rx.container(
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
        ),
        rx.button("Toggle Loading", on_click=LoadingOverlayState.toggle_loading),
    )
```

```python test
def test_toggle_loading_overlay(demo):
    overlay = demo.locator(".mantine-LoadingOverlay-root")
    expect(demo.get_by_text("Loading Overlay Example")).to_be_visible()
    expect(overlay).to_have_count(0)
    demo.get_by_role("button", name="Toggle Loading").click()
    expect(overlay).to_be_visible()
    demo.get_by_role("button", name="Toggle Loading").click()
    expect(overlay).to_have_count(0)
```
