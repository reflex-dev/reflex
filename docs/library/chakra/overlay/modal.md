---
components:
    - rx.chakra.Modal
    - rx.chakra.ModalOverlay
    - rx.chakra.ModalContent
    - rx.chakra.ModalHeader
    - rx.chakra.ModalBody
    - rx.chakra.ModalFooter
---

```python exec
import reflex as rx
```

# Modal

A modal dialog is a window overlaid on either the primary window or another dialog window.
Content behind a modal dialog is inert, meaning that users cannot interact with it.

```python demo exec
class ModalState(rx.State):
    show: bool = False

    def change(self):
        self.show = not (self.show)


def modal_example():
    return rx.chakra.vstack(
    rx.chakra.button("Confirm", on_click=ModalState.change),
    rx.chakra.modal(
        rx.chakra.modal_overlay(
            rx.chakra.modal_content(
                rx.chakra.modal_header("Confirm"),
                rx.chakra.modal_body("Do you want to confirm example?"),
                rx.chakra.modal_footer(rx.chakra.button("Close", on_click=ModalState.change)),
            )
        ),
        is_open=ModalState.show,
    ),
)
```
