"""An API route added to the backend through ``api_transformer``, as raw ASGI middleware."""

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import reflex as rx

from playground.models import Product

STATS_PATH = "/api/playground/stats"

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def product_stats() -> dict[str, int]:
    """Count the products and their stock.

    Returns:
        ``products`` and ``stock``.
    """
    with rx.session() as session:
        connection = session.connection()
        products, stock = connection.exec_driver_sql(
            f"SELECT COUNT(*), COALESCE(SUM(stock), 0) FROM {Product.__tablename__}"
        ).one()
    return {"products": products, "stock": stock}


def add_stats_route(app: ASGIApp) -> ASGIApp:
    """Answer ``GET /api/playground/stats`` with the catalog's counts; pass anything else on.

    Args:
        app: The backend's ASGI app.

    Returns:
        The wrapped app.
    """

    async def with_stats(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != STATS_PATH:
            await app(scope, receive, send)
            return
        body = json.dumps(product_stats()).encode()
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    return with_stats
