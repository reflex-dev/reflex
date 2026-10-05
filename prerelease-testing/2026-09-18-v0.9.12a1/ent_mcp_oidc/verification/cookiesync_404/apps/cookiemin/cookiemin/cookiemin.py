"""Minimal repro: HTTPCookie.sync() route registration in dev mode.

No OIDC, no AuthPlugin -- just an HTTPCookie and the compile-time sync() event.
"""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.auth.cookie import HTTPCookie


class CookieState(rx.State):
    _pref: str = HTTPCookie("default", name="minpref", secure=False)
    note: str = "idle"

    @rx.event
    def set_pref(self):
        """Set the cookie server-side (this calls HTTPCookie.sync() at RUNTIME)."""
        type(self)._pref.set(self, "set-by-backend")  # pyright: ignore[reportAttributeAccessIssue]
        self.note = "cookie set server-side"


def index() -> rx.Component:
    return rx.vstack(
        rx.text(CookieState.note, id="note"),
        # Compile-time construction of the sync event spec.
        rx.button("Cookie Sync", on_click=HTTPCookie.sync(), id="sync"),
        rx.button("Set Cookie", on_click=CookieState.set_pref, id="setcookie"),
    )


app = rxe.App()
app.add_page(index)
