"""a3_class_state extra e2e: storage options kept by #7495 plain-value class assignment, in the browser.

- sync: LocalStorage(sync=True) assigned a plain value -> must still sync across tabs
- ck: Cookie(max_age, same_site='strict') assigned a plain value -> browser cookie keeps its attributes
- ann: var annotated rx.LocalStorage assigned a plain value (a2: TypeError at import; a3: accepted)
- ss: SessionStorage assigned a plain value
- opt: Optional[str] LocalStorage assigned None (outside the documented str guarantee)
"""
from typing import Optional

import reflex as rx

OUTCOMES: dict[str, str] = {}


class St(rx.State):
    sync: str = rx.LocalStorage("d", name="k_sync", sync=True)
    ck: str = rx.Cookie("d", name="k_ck_opt", max_age=3600, same_site="strict")
    ann: rx.LocalStorage = rx.LocalStorage("d", name="k_ann")
    ss: str = rx.SessionStorage("d", name="k_ss")
    opt: Optional[str] = rx.LocalStorage("d", name="k_opt")

    @rx.event
    def change(self, tag: str):
        self.sync = f"{tag}-sync"
        self.ck = f"{tag}-ck"
        self.ann = f"{tag}-ann"
        self.ss = f"{tag}-ss"
        self.opt = f"{tag}-opt"

    @rx.event
    def set_sync(self, v: str):
        self.sync = v


for _name, _value in (("sync", "assigned"), ("ck", "assigned"), ("ann", "assigned"), ("ss", "assigned"), ("opt", None)):
    try:
        setattr(St, _name, _value)
        OUTCOMES[_name] = "ok"
    except Exception as e:  # noqa: BLE001
        OUTCOMES[_name] = f"{type(e).__name__}"
OUTCOMES["client_storage"] = ",".join(n for n in ("sync", "ck", "ann", "ss", "opt") if St._is_client_storage(n))


def index():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(str(OUTCOMES), id="outcomes"),
        *[rx.text(getattr(St, n), id=f"v_{n}") for n in ("sync", "ck", "ann", "ss", "opt")],
        rx.button("change A", on_click=St.change("A"), id="change_a"),
        rx.button("sync from here", on_click=St.set_sync("from-tab2"), id="set_sync"),
    )


app = rx.App()
app.add_page(index)
