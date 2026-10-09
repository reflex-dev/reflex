import threading

import reflex as rx


class CacheState(rx.State):
    _lock: threading.Lock = threading.Lock()  # user meant a ClassVar
    hits: int = 0

    @rx.event
    def hit(self):
        self.hits += 1


def index():
    return rx.box(rx.text(CacheState.hits), rx.button("hit", on_click=CacheState.hit))


app = rx.App()
app.add_page(index)
