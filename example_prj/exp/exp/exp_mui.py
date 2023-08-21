"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx


from typing import Set


class Button(rx.Component):
    library = "@mui/material/Button"
    tag = "Button"
    variant: rx.Var[str]
    is_default = True

    def _get_imports(self):
        merged_imports = super()._get_imports()
        imp = {
            "react": {
                rx.vars.ImportVar(tag="*",alias="React",is_default=True),
            }
        }
        return merged_imports | imp
    # def get_triggers(self) -> Set[str]:
    #     return super().get_triggers() | {"on_click"}

class State(rx.State):
    """The app state."""
    my_var: str = ""

button = Button.create

def index() -> rx.Component:
    return rx.box(
        button(
            "A button here"
        )
    )

# Add state and page to the app.
app = rx.App()
app.add_page(index)
app.compile()
