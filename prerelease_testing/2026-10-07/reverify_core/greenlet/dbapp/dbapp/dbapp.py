import reflex as rx


class Item(rx.Model, table=True):
    name: str = ""


class S(rx.State):
    n: int = 0

    @rx.event
    def add(self):
        with rx.session() as s:
            s.add(Item(name="x"))
            s.commit()
            self.n = len(s.exec(Item.select()).all())


def index():
    return rx.vstack(rx.button("add", on_click=S.add, id="add"), rx.text(S.n, id="n"))


app = rx.App()
app.add_page(index)
