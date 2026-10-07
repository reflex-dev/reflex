"""N-005 minimal app: which class-level default assignments keep a str-annotated browser-storage var persisted?"""

import reflex as rx

KEYS = ["a_plain", "b_facplain", "c_facls", "d_lsval", "e_ctrl", "f_ck_plain", "g_ck_lsval"]


class St(rx.State):
    a_plain: str = rx.LocalStorage("d", name="k_plain")
    b_facplain: str = rx.LocalStorage("d", name="k_facplain")
    c_facls: str = rx.LocalStorage("d", name="k_facls")
    d_lsval: str = rx.LocalStorage("d", name="k_lsval")
    e_ctrl: str = rx.LocalStorage("d", name="k_ctrl")
    f_ck_plain: str = rx.Cookie("d", name="k_ck_plain")
    g_ck_lsval: str = rx.Cookie("d", name="k_ck_val")

    @rx.event
    def change(self):
        for k in KEYS:
            setattr(self, k, f"changed-{k}")


St.a_plain = "assigned"  # plain value
St.b_facplain = lambda: "assigned"  # zero-arg factory returning a plain str
St.c_facls = lambda: rx.LocalStorage("assigned", name="k_facls")  # factory returning storage (changelog case)
St.d_lsval = rx.LocalStorage("assigned", name="k_lsval")  # storage value
St.f_ck_plain = "assigned"
St.g_ck_lsval = rx.Cookie("assigned", name="k_ck_val")


class LsCS(rx.ComponentState):
    """docs/state_structure/component_state.md EditableText pattern (cls.text = initial_value) on a storage var."""

    value: str = rx.LocalStorage("cs-default", name="k_cs")

    @rx.event
    def change(self):
        self.value = "changed-cs"

    @classmethod
    def get_component(cls, **props):
        initial_value = props.pop("initial_value", None)
        if initial_value is not None:
            cls.value = initial_value
        return rx.hstack(rx.text(cls.value, id="cs_value"), rx.button("cs change", on_click=cls.change, id="cs_change"))


def index():
    return rx.vstack(
        *[rx.text(getattr(St, k), id=k) for k in KEYS],
        rx.button("change", on_click=St.change, id="change"),
        LsCS.create(initial_value="cs-initial"),
    )


app = rx.App()
app.add_page(index)
