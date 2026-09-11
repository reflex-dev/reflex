"""Pure-reflex minimal repro: hook-bearing components used directly inside rx.foreach."""

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__


class HookChip(rx.el.Div):
    """A plain <div> whose add_hooks() line references its own prop var."""

    label: rx.Var[str]

    def add_hooks(self) -> list[str]:
        """Emit a hook that references the label prop.

        Returns:
            The hook lines.
        """
        return [f"const chip_label = {self.label!s};"]


class S(rx.State):
    """Holds the list to iterate over."""

    items: list[str] = ["a", "b"]
    log: str = ""

    @rx.event
    def note(self, value: str):
        """Record a value.

        Args:
            value: the value to record.
        """
        self.log = value


def chip_body(iid: rx.Var[str]) -> rx.Component:
    return HookChip.create(rx.text(iid), label=iid, custom_attrs={"data-chip": "1"})


@rx.memo
def memo_chip(iid: rx.Var[str]) -> rx.Component:
    """Same body wrapped in rx.memo."""
    return chip_body(iid)


@rx.page(route="/", title="raw literal foreach")
def index() -> rx.Component:
    return rx.vstack(
        rx.text("raw-literal", id="hdr"),
        rx.foreach(rx.Var.create(["a", "b"]), chip_body),
        id="raw",
    )


@rx.page(route="/state", title="raw state foreach")
def state_page() -> rx.Component:
    return rx.vstack(
        rx.text("raw-state", id="hdr"),
        rx.foreach(S.items, chip_body),
        id="rawstate",
    )


@rx.page(route="/memo", title="memo foreach")
def memo_page() -> rx.Component:
    return rx.vstack(
        rx.text("memo", id="hdr"),
        rx.foreach(rx.Var.create(["a", "b"]), lambda iid: memo_chip(iid=iid)),
        id="memo",
    )


@rx.page(route="/plain", title="no foreach control")
def plain_page() -> rx.Component:
    return rx.vstack(
        rx.text("plain", id="hdr"),
        chip_body(rx.Var.create("a")),
        id="plain",
    )


@rx.page(route="/upload", title="rx.upload in foreach")
def upload_page() -> rx.Component:
    return rx.vstack(
        rx.text("upload", id="hdr"),
        rx.foreach(
            S.items,
            lambda iid: rx.upload(
                rx.text(iid), id=iid, custom_attrs={"data-chip": "1"}
            ),
        ),
        id="upl",
    )


@rx.page(route="/form", title="rx.form on_submit in foreach")
def form_page() -> rx.Component:
    return rx.vstack(
        rx.text("form", id="hdr"),
        rx.foreach(
            S.items,
            lambda iid: rx.form(
                rx.el.input(name="v"),
                rx.el.button("go", type="submit"),
                on_submit=lambda _d: S.note(iid),
                custom_attrs={"data-chip": "1"},
            ),
        ),
        id="frm",
    )


@rx.page(route="/click", title="on_click with loop var in foreach")
def click_page() -> rx.Component:
    return rx.vstack(
        rx.text("click", id="hdr"),
        rx.text(S.log, id="log"),
        rx.foreach(
            S.items,
            lambda iid: rx.button(
                iid, on_click=S.note(iid), custom_attrs={"data-chip": "1"}
            ),
        ),
        id="clk",
    )


app = rx.App()
