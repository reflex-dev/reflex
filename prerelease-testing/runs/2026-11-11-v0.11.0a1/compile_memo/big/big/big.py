"""Large app for python compile-time comparison: 40 pages x 150 stateful components."""
import reflex as rx


class B(rx.State):
    vals: list[int] = list(range(50))
    n: int = 0
    s: str = "x"

    @rx.event
    def inc(self, i: int):
        self.n += i


def block(p: int, i: int):
    return rx.hstack(
        rx.text(f"p{p} i{i} ", B.n + i),
        rx.button("+", on_click=B.inc(i)),
        rx.cond(B.n > i, rx.badge("big"), rx.badge("small")),
        rx.input(value=B.s, on_change=B.set_s if hasattr(B, "set_s") else None) if False else rx.text(B.s),
    )


app = rx.App()
for p in range(40):
    app.add_page(lambda p=p: rx.vstack(*[block(p, i) for i in range(150)]), route=f"/p{p}")
