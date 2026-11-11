"""verify_cm: independent probes for compile_memo issues 2 (unkeyed foreach lifecycle payloads),
3 (on_mount in rx.cond inside @rx.memo) and 4 (lucide grid icons via Var tag)."""

import reflex as rx

ITEMS = ["alpha", "beta", "gamma"]


class S(rx.State):
    items: list[str] = ITEMS
    events: list[str] = []
    flag: bool = True
    icon_name: str = "grid_2x_2"

    @rx.event
    def ev(self, name: str):
        self.events.append(name)

    @rx.event
    def clear(self):
        self.events = []

    @rx.event
    def reset_items(self):
        self.items = list(ITEMS)

    @rx.event
    def remove_first(self):
        self.items.pop(0)

    @rx.event
    def toggle(self):
        self.flag = not self.flag

    @rx.event
    def set_icon(self, name: str):
        self.icon_name = name


def controls():
    return rx.hstack(
        rx.button("remove first", on_click=S.remove_first, id="rm-first"),
        rx.button("reset", on_click=S.reset_items, id="reset"),
        rx.button("clear", on_click=S.clear, id="clear"),
        rx.button("toggle", on_click=S.toggle, id="toggle"),
        rx.text("flag=", S.flag.to_string(), id="flag"),
    )


def ev_log():
    return rx.text(S.events.join(","), id="events")


def row(item, key: bool):
    kw = {"key": item} if key else {}
    return rx.text(item, on_mount=S.ev("m:" + item), on_unmount=S.ev("u:" + item), class_name="row", **kw)


def nokey():
    return rx.vstack(rx.heading("nokey", id="page"), controls(), rx.foreach(S.items, lambda it: row(it, False)), ev_log())


def withkey():
    return rx.vstack(rx.heading("withkey", id="page"), controls(), rx.foreach(S.items, lambda it: row(it, True)), ev_log())


@rx.memo
def memo_cond(show: rx.Var[bool], label: rx.Var[str]) -> rx.Component:
    return rx.box(
        rx.cond(show, rx.text("shown-", label, class_name="shown", on_mount=S.ev("m:" + label), on_unmount=S.ev("u:" + label))),
    )


def memocond():
    return rx.vstack(
        rx.heading("memocond", id="page"),
        controls(),
        memo_cond(show=S.flag, label="x"),
        memo_cond(show=~S.flag, label="y"),
        ev_log(),
    )


def pagecond():
    # control: the same cond, written directly in the page (no @rx.memo)
    def c(show, label):
        return rx.box(rx.cond(show, rx.text("shown-" + label, class_name="shown", on_mount=S.ev("m:" + label), on_unmount=S.ev("u:" + label))))

    return rx.vstack(rx.heading("pagecond", id="page"), controls(), c(S.flag, "x"), c(~S.flag, "y"), ev_log())


def icons():
    return rx.vstack(
        rx.heading("icons", id="page"),
        rx.box(rx.icon(S.icon_name), id="icn-var"),
        rx.box(rx.icon("grid_2x_2"), id="icn-static"),
        rx.hstack(rx.foreach(["grid_2x_2", "grid_3x_3", "calendar_1", "arrow_up_0_1"], lambda n: rx.box(rx.icon(n), class_name="icn-loop", data_name=n))),
        rx.button("g3", on_click=S.set_icon("grid_3x_3"), id="g3"),
        rx.text(S.icon_name, id="icn-name"),
    )


app = rx.App()
app.add_page(nokey, route="/nokey")
app.add_page(withkey, route="/withkey")
app.add_page(memocond, route="/memocond")
app.add_page(pagecond, route="/pagecond")
app.add_page(icons, route="/icons")
app.add_page(lambda: rx.text("home", id="page"), route="/")
