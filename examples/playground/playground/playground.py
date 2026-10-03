"""The playground app: a multi-page Reflex app covering the framework, also the benchmark fixture."""

import reflex as rx

from playground.api import add_stats_route
from playground.models import seed_database
from playground.pages.about import about, not_found
from playground.pages.board import board
from playground.pages.charts import charts
from playground.pages.content import content
from playground.pages.counter import counter
from playground.pages.data import analytics_page, product_page, table_page
from playground.pages.events import events
from playground.pages.forms import forms
from playground.pages.grids import grids
from playground.pages.index import index
from playground.pages.item import item
from playground.pages.room import room
from playground.pages.settings import settings
from playground.pages.storage import storage
from playground.pages.tasks import tasks
from playground.pages.upload import upload
from playground.pages.widgets import widgets
from playground.states.analytics import AnalyticsState
from playground.states.data import DataState
from playground.states.editor import ProductEditState
from playground.states.room import RoomState

app = rx.App(stylesheets=["/playground.css"], api_transformer=add_stats_route)
# Reflex 0.9 takes the theme from RadixThemesPlugin (rxconfig.py).
if not hasattr(rx.plugins, "RadixThemesPlugin"):
    app.theme = rx.theme(accent_color="violet")
app.register_lifespan_task(seed_database)

app.add_page(index, title="Reflex playground")
app.add_page(counter, route="/counter", title="Counter")
app.add_page(board, route="/board", title="Board")
app.add_page(item, route="/item/[item_id]", title="Item")
app.add_page(events, route="/events", title="Events")
app.add_page(tasks, route="/tasks", title="Tasks")
app.add_page(table_page, route="/data", title="Products", on_load=DataState.load)
app.add_page(
    product_page,
    route="/data/product/[product_id]",
    title="Product",
    on_load=ProductEditState.load_product,
)
app.add_page(
    product_page,
    route="/data/new",
    title="New product",
    on_load=ProductEditState.new_product,
)
app.add_page(
    analytics_page,
    route="/data/analytics",
    title="Analytics",
    on_load=AnalyticsState.load,
)
app.add_page(forms, route="/forms", title="Forms")
app.add_page(upload, route="/upload", title="Upload")
app.add_page(storage, route="/storage", title="Storage")
app.add_page(charts, route="/charts", title="Charts")
app.add_page(grids, route="/grids", title="Grids")
app.add_page(content, route="/content", title="Content")
app.add_page(widgets, route="/widgets", title="Widgets")
app.add_page(room, route="/room/[room_id]", title="Room", on_load=RoomState.enter)
app.add_page(settings, route="/settings", title="Settings")
app.add_page(about, route="/about", title="About")
app.add_page(not_found, route="404", title="Not found")
