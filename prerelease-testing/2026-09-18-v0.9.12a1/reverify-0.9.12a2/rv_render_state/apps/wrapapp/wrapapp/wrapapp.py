"""App-wrap nesting probe for #7218 (badge must forward children).

Registers custom app wraps at priorities above, at and below the sticky badge
(priority 0), alongside the real `(-1, "DataEditorPortal")` wrap that
`rx.data_editor` registers and the sonner toaster wrap.
"""

import reflex as rx


class WrapState(rx.State):
    n: int = 0
    cols: list[dict] = [
        {"title": "A", "type": "str"},
        {"title": "B", "type": "int"},
    ]
    data: list[list] = [["x", 1], ["y", 2]]

    @rx.event
    def fire_toast(self):
        self.n += 1
        return rx.toast.info(f"toast #{self.n}")


class WrapMarker(rx.el.Div):
    """A component that registers its own app wrap at a chosen priority."""

    def add_hooks(self) -> list[str]:
        return []


def _marker(name: str, priority: int):
    class _M(rx.el.Div):
        def _get_app_wrap_components(self) -> dict[tuple[int, str], rx.Component]:
            return {
                (priority, name): rx.el.div(
                    id=f"wrap_{name}", custom_attrs={"data-wrap": name}
                )
            }

    return _M.create(id=f"host_{name}")


def index() -> rx.Component:
    return rx.vstack(
        rx.text("wrapapp", id="hello"),
        rx.button("toast", on_click=WrapState.fire_toast, id="b_toast"),
        rx.text(WrapState.n.to_string(), id="v_n"),
        _marker("hi", 5),
        _marker("zero_ish", 0),
        _marker("lo", -2),
        _marker("lo3", -3),
        rx.data_editor(
            columns=WrapState.cols,
            data=WrapState.data,
            id="grid",
        ),
    )


app = rx.App()
app.add_page(index, route="/")
