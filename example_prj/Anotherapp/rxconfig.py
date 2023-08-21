import reflex as rx

class AnotherappConfig(rx.Config):
    pass

config = AnotherappConfig(
    app_name="Anotherapp",
    db_url="sqlite:///reflex.db",
    env=rx.Env.DEV,
    frontend_packages=[
        "@mui/material"
    ]
)

from typing import Set


class Button(rx.Component):
    library = "@mui/material"
    tag = "Button"
    variant: rx.Var[str]

    def get_triggers(self) -> Set[str]:
        return super().get_triggers() | {"on_click"}