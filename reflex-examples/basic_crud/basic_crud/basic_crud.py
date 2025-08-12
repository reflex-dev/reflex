"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import asyncio
import json

from fastapi import FastAPI
import httpx
from sqlmodel import select

import reflex as rx

from .api import product_router
from .model import Product

DEFAULT_BODY = """{
    "code":"",
    "label":"",
    "image":"/favicon.ico",
    "quantity":0,
    "category":"",
    "seller":"",
    "sender":""
}"""

URL_OPTIONS = {
    "GET": "products",
    "POST": "products",
    "PUT": "products/{pr_id}",
    "DELETE": "products/{pr_id}",
}


class State(rx.State):
    """The app state."""

    products: list[Product]
    _db_updated: bool = False

    def load_product(self):
        with rx.session() as session:
            self.products = session.exec(select(Product)).all()
        yield State.reload_product

    @rx.event(background=True)
    async def reload_product(self):
        while True:
            await asyncio.sleep(2)
            if self.db_updated:
                async with self:
                    with rx.session() as session:
                        self.products = session.exec(select(Product)).all()
                    self._db_updated = False

    @rx.var
    def db_updated(self) -> bool:
        return self._db_updated

    @rx.var
    def total(self) -> int:
        return len(self.products)


class QueryState(State):
    body: str = DEFAULT_BODY
    response_code: str = ""
    response: str = ""
    method: str = "GET"
    url_query: str = URL_OPTIONS["GET"]
    query_options = list(URL_OPTIONS.keys())

    def update_method(self, value):
        if self.url_query == "":
            self.url_query = URL_OPTIONS[value]
        self.method = value

    @rx.var
    def need_body(self) -> bool:
        return False

    @rx.var
    def f_response(self) -> str:
        return f"""```json\n{self.response}\n```"""

    def clear_query(self):
        self.url_query = URL_OPTIONS["GET"]
        self.method = "GET"
        self.body = DEFAULT_BODY

    async def send_query(self):
        # Get the backend port from Reflex config
        backend_port = rx.config.get_config().backend_port
        url = f"http://localhost:{backend_port}/{self.url_query}"
        async with httpx.AsyncClient() as client:
            match self.method:
                case "GET":
                    res = await client.get(url)
                case "POST":
                    res = await client.post(url, data=self.body)
                case "PUT":
                    res = await client.put(url, data=self.body)
                case "DELETE":
                    res = await client.delete(url)
                case _:
                    res = None
        self.response_code = str(res.status_code)
        if res.is_success:
            self.response = json.dumps(res.json(), indent=2)
            self._db_updated = True
        else:
            self.response = res.content.decode()


def data_display():
    return rx.vstack(
        rx.heading(State.total, " products found"),
        rx.foreach(State.products, render_product),
        rx.spacer(),
        width="30vw",
        height="100%",
    )


def render_product(product: Product):
    return rx.hstack(
        rx.image(src=product.image, height="100%", width="3vw"),
        rx.text(f"({product.code}) {product.label}", width="10vw"),
        rx.vstack(
            rx.text("Stock:", product.quantity),
            rx.text("Category:", product.category),
            spacing="0",
            width="7vw",
        ),
        rx.vstack(
            rx.text("Seller:", product.seller),
            rx.text("Sender:", product.sender),
            spacing="0",
            width="7vw",
        ),
        rx.spacer(),
        border="solid black 1px",
        spacing="5",
        width="100%",
    )


def query_form():
    return rx.vstack(
        rx.hstack(
            rx.text("Query:"),
            rx.select(
                ["GET", "POST", "PUT", "DELETE"],
                on_change=QueryState.update_method,
            ),
            rx.input(
                value=QueryState.url_query,
                on_change=QueryState.set_url_query,
                width="30vw",
            ),
        ),
        rx.text("Body:"),
        rx.text_area(
            value=QueryState.body,
            height="20vh",
            width="20vh",
            on_change=QueryState.set_body,
        ),
        rx.hstack(
            rx.button("Clear", on_click=QueryState.clear_query),
            rx.button("Send", on_click=QueryState.send_query),
        ),
        rx.divider(orientation="horizontal", border="solid black 1px", width="100%"),
        rx.hstack(
            rx.text("Status: ", QueryState.response_code), rx.spacer(), width="100%"
        ),
        rx.container(
            rx.markdown(
                QueryState.f_response,
                language="json",
                height="30vh",
            )
        ),
        width="100%",
    )


def index() -> rx.Component:
    return rx.hstack(
        rx.spacer(),
        data_display(),
        rx.spacer(),
        rx.divider(orientation="vertical", border="solid black 1px"),
        query_form(),
        rx.spacer(),
        height="100vh",
        width="100vw",
        spacing="0",
    )


fastapi = FastAPI()
fastapi.include_router(product_router)

app = rx.App(api_transformer=fastapi)
app.add_page(index, on_load=State.load_product)
