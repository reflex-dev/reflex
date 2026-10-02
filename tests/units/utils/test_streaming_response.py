from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from reflex_base.utils.streaming_response import DisconnectAwareStreamingResponse
from starlette.requests import ClientDisconnect


@pytest.mark.asyncio
async def test_send_oserror_raises_client_disconnect_and_closes_body():
    """A send-side disconnect still raises ClientDisconnect and closes the stream."""
    body_closed = asyncio.Event()
    disconnect_notified = asyncio.Event()
    on_finish = AsyncMock()

    async def body():
        try:
            yield b"payload"
            await asyncio.Event().wait()
        finally:
            body_closed.set()

    async def receive() -> dict[str, Any]:
        await asyncio.Event().wait()
        msg = "receive should not return"
        raise AssertionError(msg)

    async def send(message):
        await asyncio.sleep(0)
        if message["type"] == "http.response.body":
            err = "client disconnected"
            raise OSError(err)

    response = DisconnectAwareStreamingResponse(
        body(),
        media_type="application/x-ndjson",
        on_finish=on_finish,
        on_disconnect=disconnect_notified.set,
    )

    with pytest.raises(ClientDisconnect):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)

    await asyncio.wait_for(body_closed.wait(), timeout=1)
    assert disconnect_notified.is_set()
    on_finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_2_4_disconnect_cancels_stream_and_runs_finish():
    """Pre-2.4 ASGI disconnect cancels the body stream and cleanup runs once."""
    body_started = asyncio.Event()
    on_finish = AsyncMock()

    # Unlike the 2.4+ path, anyio task-group cancellation does not call
    # aclose() on the body async generator, so we don't track body_closed here.
    async def body():
        body_started.set()
        yield b"payload"
        await asyncio.Event().wait()

    async def receive():
        await body_started.wait()
        return {"type": "http.disconnect"}

    async def send(_message):
        await asyncio.sleep(0)

    response = DisconnectAwareStreamingResponse(
        body(),
        media_type="application/x-ndjson",
        on_finish=on_finish,
    )

    await asyncio.wait_for(
        response({"type": "http", "asgi": {"spec_version": "2.1"}}, receive, send),
        timeout=1,
    )

    on_finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_malformed_spec_version_falls_back_without_crashing():
    """Malformed ASGI spec versions fall back to Starlette's legacy path."""
    on_finish = AsyncMock()
    sent = []

    async def receive() -> dict[str, Any]:
        await asyncio.Event().wait()
        msg = "receive should not return"
        raise AssertionError(msg)

    async def send(message):
        await asyncio.sleep(0)
        sent.append(message)

    response = DisconnectAwareStreamingResponse(
        [b"payload"],
        media_type="application/x-ndjson",
        on_finish=on_finish,
    )

    await asyncio.wait_for(
        response(
            {"type": "http", "asgi": {"spec_version": "2.4-beta"}},
            receive,
            send,
        ),
        timeout=1,
    )

    assert [message["type"] for message in sent] == [
        "http.response.start",
        "http.response.body",
        "http.response.body",
    ]
    on_finish.assert_awaited_once()
