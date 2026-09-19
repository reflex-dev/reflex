"""#7117 local package specifier test app."""

import reflex as rx

assert "/home/user/reflex" not in rx.__file__, rx.__file__


class HelloDir(rx.Component):
    """Wraps the local directory package."""

    library = "@masenf/hello-react@../hello-react"
    tag = "Hello"

    label: rx.Var[str]


class HelloTgz(rx.Component):
    """Wraps the local tarball package."""

    library = "@masenf/hello-react-tgz@../hello-react/masenf-hello-react-0.1.0.tgz"
    tag = "Hello"
    alias = "HelloFromTgz"

    label: rx.Var[str]


class S(rx.State):
    """State."""

    n: int = 0
    names: list[str] = ["a", "b"]

    @rx.event
    def inc(self):
        """Increment."""
        self.n += 1


def index() -> rx.Component:
    """Index."""
    return rx.vstack(
        rx.heading("hrapp", id="heading"),
        HelloDir.create(rx.text(S.n, id="dir-n"), label="from-dir", id="hd"),
        rx.button("inc", on_click=S.inc, id="inc"),
        rx.cond(S.n > 1, rx.text("many", id="cnd"), rx.text("few", id="cnd")),
        rx.foreach(S.names, lambda x: HelloDir.create(label=x, class_name="fe")),
        HelloTgz.create(rx.text("tgz-child", id="tgz-child"), label="from-tgz", id="ht"),
    )


app = rx.App()
app.add_page(index, route="/")
