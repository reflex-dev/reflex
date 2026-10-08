"""a3_hydration: natural trigger for sync=True LocalStorage ping-pong: an on_load handler that writes a synced
LocalStorage var (e.g. "last page seen"), with several tabs of the app loading at once (browser session restore).

/stamp   on_load sets Stamp.last = "<tab token[:6]>-<n>" (a different value per tab)
/same    on_load sets Stamp.last = "same" (every tab writes the same value)
/        no on_load (just displays the synced var)
"""

import os

import reflex as rx

assert f"/scratchpad/envs/{os.environ['RVH_VENV']}/" in rx.__file__, (os.environ.get("RVH_VENV"), rx.__file__)


class Stamp(rx.State):
    last: str = rx.LocalStorage("", name="ss_last", sync=True)
    loads: int = 0

    @rx.event
    def on_load_stamp(self):
        self.loads += 1
        self.last = f"{self.router.session.client_token[:6]}-{self.loads}"

    @rx.event
    def on_load_same(self):
        self.loads += 1
        self.last = "same"


def page():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        rx.text(Stamp.last, id="theme"),
        rx.text(Stamp.loads, id="loads"),
    )


app = rx.App()
app.add_page(page, route="/")
app.add_page(page, route="/stamp", on_load=Stamp.on_load_stamp)
app.add_page(page, route="/same", on_load=Stamp.on_load_same)
