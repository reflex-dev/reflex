"""Element with custom_attrs (raw HTML attributes)."""

import reflex as rx


ROUTE = "/custom_attrs"
IDENT = "CustomAttrs"


def build():
    return rx.box(
        "content",
        custom_attrs={"data-testid": "my-box", "aria-label": "main"},
    )
