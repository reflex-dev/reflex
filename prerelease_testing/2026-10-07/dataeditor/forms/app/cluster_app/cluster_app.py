"""dataeditor_components cluster app entry point."""

import reflex as rx

from .common import REFLEX_VERSION
from .p_charts import plotly_page, recharts_page
from .p_dataeditor import BigState, de_big_page, de_filter_page, de_foreach_page, de_multi_page, de_page
from .p_forms import forms_page
from .p_match import match_page, memo_names_page
from .p_misc import code_page, download_page, home_page, radix_page
from .p_select_matrix import select_matrix
from .p_new_components import new_components

print("CLUSTER_APP reflex", REFLEX_VERSION, rx.__file__, flush=True)

app = rx.App()
app.add_page(home_page, route="/")
app.add_page(de_page, route="/de")
app.add_page(de_multi_page, route="/de-multi")
app.add_page(de_filter_page, route="/de-filter")
app.add_page(de_big_page, route="/de-big", on_load=BigState.load)
app.add_page(de_foreach_page, route="/de-foreach")
app.add_page(forms_page, route="/forms")
app.add_page(match_page, route="/match")
app.add_page(memo_names_page, route="/memo-names")
app.add_page(plotly_page, route="/plotly")
app.add_page(recharts_page, route="/recharts")
app.add_page(radix_page, route="/radix")
app.add_page(code_page, route="/code")
app.add_page(download_page, route="/download")
app.add_page(select_matrix, route="/select-matrix")
app.add_page(new_components, route="/new-components")
