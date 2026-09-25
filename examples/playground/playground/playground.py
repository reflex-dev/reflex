"""The playground app: a small multi-page Reflex app, also the benchmark fixture."""

import reflex as rx

from playground.pages.board import board
from playground.pages.counter import counter
from playground.pages.index import index
from playground.pages.item import item

app = rx.App(stylesheets=["/playground.css"])
app.add_page(index, title="Reflex playground")
app.add_page(counter, route="/counter", title="Counter")
app.add_page(board, route="/board", title="Board")
app.add_page(item, route="/item/[item_id]", title="Item")
