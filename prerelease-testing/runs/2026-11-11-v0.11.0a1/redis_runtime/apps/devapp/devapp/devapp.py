"""#7616 (cached vars recomputed after hot reload) + #7590 (state_auto_setters in spawned workers)."""

import os

import reflex as rx

_EXPECT = os.environ.get("EXPECT_VENV")
if _EXPECT:
    assert f"/envs/{_EXPECT}/" in rx.__file__, rx.__file__

CODE_VERSION = "V1"


class S(rx.State):
    n: int = 1
    name: str = ""
    _secret: int = 0

    @rx.var(cache=True)
    def label(self) -> str:
        return f"{CODE_VERSION}:{self.n}"

    @rx.var(cache=True)
    def label2(self) -> str:
        return f"L2[{self.label}]"

    @rx.var
    def worker_pid(self) -> str:
        return str(os.getpid())

    @rx.event
    def bump(self):
        self.n += 1
        self._secret += 1


class Child(S):
    @rx.var(cache=True)
    def child_label(self) -> str:
        return f"child-{CODE_VERSION}:{self.n}"


def index():
    return rx.vstack(
        rx.text("label=", rx.text.span(S.label, id="label")),
        rx.text("label2=", rx.text.span(S.label2, id="label2")),
        rx.text("child=", rx.text.span(Child.child_label, id="child_label")),
        rx.text("n=", rx.text.span(S.n, id="n")),
        rx.text("pid=", rx.text.span(S.worker_pid, id="pid")),
        rx.button("bump", id="bump", on_click=S.bump),
        rx.input(id="name", value=S.name, on_change=S.set_name),
        rx.text("name=", rx.text.span(S.name, id="name_out")),
    )


app = rx.App()
app.add_page(index)
