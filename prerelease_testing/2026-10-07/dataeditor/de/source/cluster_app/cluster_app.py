"""Published-package data editor browser reproduction."""
import reflex as rx
from .common import REFLEX_VERSION
from .p_dataeditor import BigState, de_big_page, de_filter_page, de_foreach_page, de_multi_page, de_page
print("CLUSTER_APP", REFLEX_VERSION, rx.__file__, flush=True)
app = rx.App()
app.add_page(de_page, route="/")
app.add_page(de_page, route="/de")
app.add_page(de_multi_page, route="/de-multi")
app.add_page(de_filter_page, route="/de-filter")
app.add_page(de_big_page, route="/de-big", on_load=BigState.load)
app.add_page(de_foreach_page, route="/de-foreach")
