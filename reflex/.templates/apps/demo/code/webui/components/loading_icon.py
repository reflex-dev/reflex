import reflex as rx


class LoadingIcon(rx.Component):
    """A custom loading icon component."""

    library = "react-loading-icons"
    tag = "SpinningCircles"
    stroke: rx.Var[str]
    stroke_opacity: rx.Var[str]
    fill: rx.Var[str]
    fill_opacity: rx.Var[str]
    stroke_width: rx.Var[str]
    speed: rx.Var[str]
    height: rx.Var[str]

    def get_event_triggers(self) -> dict:
        return {"on_change": lambda status: [status]}


loading_icon = LoadingIcon.create
