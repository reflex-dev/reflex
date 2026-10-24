"""CT-6: what each handler kind receives for empty checkbox groups / selects with and without id / name."""
import json
import os
from typing import Any, TypedDict

import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__
NEW = hasattr(rx.form, "FormData")


class TD(TypedDict, total=False):
    g_id: list[str]
    g_name: list[str]
    g_both: list[str]


class S(rx.State):
    out: dict[str, str] = {}

    @rx.event
    def h_dict(self, form_data: dict):
        self.out["dict"] = json.dumps(form_data, sort_keys=True)

    @rx.event
    def h_td(self, form_data: TD):
        self.out["td"] = json.dumps(dict(form_data), sort_keys=True) + " types=" + json.dumps({k: [type(x).__name__ for x in v] if isinstance(v, list) else type(v).__name__ for k, v in form_data.items()})

    if NEW:
        @rx.event
        def h_fd(self, form_data: rx.form.FormData[str, str]):
            self.out["fd"] = json.dumps({k: form_data.getlist(k) for k in sorted(set(form_data.keys()))})


def controls():
    return [
        rx.checkbox_group.root(rx.checkbox_group.item(value="a"), rx.checkbox_group.item(value="b"), id="g_id"),
        rx.checkbox_group.root(rx.checkbox_group.item(value="a"), rx.checkbox_group.item(value="b"), name="g_name"),
        rx.checkbox_group.root(rx.checkbox_group.item(value="a"), rx.checkbox_group.item(value="b"), id="g_both", name="g_both"),
        rx.checkbox_cards.root(rx.checkbox_cards.item("x", value="x"), id="cards_id"),
        rx.select(["o1", "o2"], id="sel_id"),
        rx.radio_group(["r1", "r2"], id="rad_id"),
        rx.el.input(id="txt_id"),
    ]


def form(handler, fid):
    return rx.form(*controls(), rx.button("submit", type="submit", id=f"submit_{fid}"), on_submit=handler, id=fid)


def index():
    forms = [form(S.h_dict, "f_dict"), form(S.h_td, "f_td")]
    if NEW:
        forms.append(form(S.h_fd, "f_fd"))
    return rx.vstack(*forms, rx.text(S.out.to_string(), id="out"))


app = rx.App()
app.add_page(index)
