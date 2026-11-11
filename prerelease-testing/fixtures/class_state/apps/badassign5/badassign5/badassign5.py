"""0.9.12-style configuration of an INHERITED var through a substate; BADASSIGN_FIX=1 applies the fix the a5 error names."""
import os

import reflex as rx


class Base(rx.State):
    count: int = 0


class Child(Base):
    label: str = "child"

    @rx.event
    def bump(self):
        self.count += 1


if os.environ.get("BADASSIGN_FIX") == "1":
    Base.__fields__["count"].set_default(5)  # what the a5 TypeError suggests
else:
    Child.count = 5  # 0.9.12 idiom; TypeError on 0.10


def index():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(Child.count, id="count"),
        rx.text(Base.count, id="bcount"),
        rx.button("bump", on_click=Child.bump, id="bump"),
    )


app = rx.App()
app.add_page(index)
