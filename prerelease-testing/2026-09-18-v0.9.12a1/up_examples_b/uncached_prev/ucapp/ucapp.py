import reflex as rx


class S(rx.State):
    tick: int = 0

    @rx.var(cache=False)
    def steady(self) -> str:
        return "constant"

    @rx.var(cache=False)
    def changing(self) -> int:
        return self.tick * 2

    @rx.event
    def bump(self):
        self.tick += 1


def index():
    return rx.vstack(
        rx.button("bump", on_click=S.bump, id="bump"),
        rx.text(S.tick), rx.text(S.steady), rx.text(S.changing),
    )


app = rx.App()
app.add_page(index)


class DynState(rx.State):
    @rx.var
    def item_id(self) -> str:
        return self.router.url.path


@rx.page(route="/item/[iid]")
def item_page():
    return rx.vstack(rx.heading("item page"), rx.text(DynState.item_id))


@rx.page(route="/item/")
def item_index():
    return rx.text("item index")


class RouterDepState(rx.State):
    @rx.var(deps=["router"], cache=True)
    def legacy_router_dep(self) -> str:
        return self.router.url.path


@rx.page(route="/routerdep")
def routerdep_page():
    return rx.text(RouterDepState.legacy_router_dep, id="rd")
