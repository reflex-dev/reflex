"""hybrid_property / dataclass proxy / forward-ref test app for reflex 0.9.11a1."""

import sys

import reflex as rx

from .combo_state import combo_page
from .core_state import core_page
from .dc_state import dc_page
from .fwd_state import fwd_page
from .inherit_state import inherit_page

app = rx.App()
app.add_page(core_page, route="/", title="core")
app.add_page(inherit_page, route="/inherit", title="inherit")
app.add_page(combo_page, route="/combo", title="combo")
app.add_page(dc_page, route="/dc", title="dc")
app.add_page(fwd_page, route="/fwd", title="fwd")

if sys.version_info >= (3, 14):
    from .fwd_lazy_state import lazy_page

    app.add_page(lazy_page, route="/lazy", title="lazy")
