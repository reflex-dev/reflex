"""Integration tests for channels multiplexed onto the event websocket.

Exercises the parts only a browser can prove: the client opens its channel
over the app's own socket, binary attachments survive the round trip in both
directions, and each one lands aligned enough to read as a typed array.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ChannelApp():
    """App serving an echo channel driven from the browser."""
    import reflex as rx

    PROBE_SETUP = """
    if (typeof window !== "undefined") {
      const probeChannel = getChannel("probe");
      window.__probe = { received: [], errors: [], connected: false, connects: 0 };
      probeChannel.on("connect", () => {
        window.__probe.connected = true;
        window.__probe.connects += 1;
      });
      probeChannel.on("disconnect", () => {
        window.__probe.connected = false;
      });
      // Drop the socket the way the transport's own watchdog does on a dead
      // connection, so the test exercises the supported reconnect path.
      window.__probe.drop = () => probeChannel._transport._dropConnection("test");
      // Drop and emit in the same tick: the socket is CLOSING but the channel
      // still reports connected, so the frame queues on the transport rather
      // than on the channel.
      window.__probe.dropThenEmit = (n) => {
        probeChannel._transport._dropConnection("test");
        probeChannel.emit("push", { n }, [new Uint8Array([1, 2, 3, 4])]);
      };
      // Emit while down, then mutate what was passed: the queued message must
      // still carry the values it was emitted with.
      window.__probe.pushThenMutate = (n) => {
        const meta = { n };
        const bytes = new Uint8Array([1, 2, 3, 4]);
        probeChannel.emit("push", meta, [bytes]);
        meta.n = -1;
        bytes.fill(9);
      };
      probeChannel.on("error", (error) => {
        window.__probe.errors.push(error);
      });
      probeChannel.on("echo", (data, buffers) => {
        window.__probe.received.push({
          data,
          bytes: Array.from(buffers[0]),
          aligned: buffers[0].byteOffset % 8 === 0,
        });
      });
      window.__probe.push = (n) =>
        probeChannel.emit("push", { n }, [new Uint8Array([1, 2, 3, 4])]);
      window.__probe.broadcast = () => probeChannel.emit("broadcast", null);
    }
    """

    class EchoChannel(rx.channels.Channel):
        name = "probe"
        accepts_binary = True

        async def on_open(self, session):
            session.join("all")

        async def on_message(self, session, event, data, buffers):
            if event == "push":
                await session.send(
                    "echo",
                    {"n": data["n"], "sizes": [len(buffer) for buffer in buffers]},
                    [bytes(reversed(buffers[0]))],
                )
            elif event == "broadcast":
                await self.send_to_room(
                    "all", "echo", {"n": -1, "sizes": []}, [b"\x09\x08\x07"]
                )

    class ChannelProbe(rx.Fragment):
        def add_imports(self):
            return {"$/utils/state": ["getChannel"]}

        def add_custom_code(self):
            return [PROBE_SETUP]

    @rx.page("/")
    def index():
        return rx.box(ChannelProbe.create(), rx.text("ready", id="ready"))

    app = rx.App()
    app.register_channel(EchoChannel())


@pytest.fixture(scope="module")
def channel_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the ChannelApp.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("channel_app"),
        app_source=ChannelApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def _connected_probe(channel_app: AppHarness, page: Page) -> None:
    """Load the page and wait for the channel to open.

    Args:
        channel_app: Running AppHarness instance.
        page: Playwright page fixture.
    """
    assert channel_app.frontend_url is not None
    page.goto(channel_app.frontend_url)
    expect(page.locator("#ready")).to_have_text("ready")
    # A cold frontend build reloads the page once the dev server finishes
    # optimizing its dependencies, which resets the probe; let that settle
    # before the test starts counting on its state.
    page.wait_for_load_state("networkidle")
    page.wait_for_function("window.__probe?.connected === true")


def test_binary_message_round_trip(channel_app: AppHarness, page: Page):
    """A binary attachment survives the round trip and arrives aligned.

    Args:
        channel_app: Running AppHarness instance.
        page: Playwright page fixture.
    """
    _connected_probe(channel_app, page)

    page.evaluate("window.__probe.push(7)")
    page.wait_for_function("window.__probe.received.length > 0")

    received = page.evaluate("window.__probe.received[0]")
    assert received["data"] == {"n": 7, "sizes": [4]}
    assert received["bytes"] == [4, 3, 2, 1]
    assert received["aligned"]
    assert page.evaluate("window.__probe.errors") == []


def test_room_broadcast_reaches_the_client(channel_app: AppHarness, page: Page):
    """A server-side room fan-out reaches a subscribed browser.

    Args:
        channel_app: Running AppHarness instance.
        page: Playwright page fixture.
    """
    _connected_probe(channel_app, page)

    page.evaluate("window.__probe.broadcast()")
    page.wait_for_function("window.__probe.received.length > 0")

    received = page.evaluate("window.__probe.received[0]")
    assert received["data"] == {"n": -1, "sizes": []}
    assert received["bytes"] == [9, 8, 7]


def test_channel_reopens_and_flushes_after_a_reconnect(
    channel_app: AppHarness, page: Page
):
    """A dropped socket reopens the channel and delivers what was queued.

    Args:
        channel_app: Running AppHarness instance.
        page: Playwright page fixture.
    """
    _connected_probe(channel_app, page)
    connects = page.evaluate("window.__probe.connects")

    page.evaluate("window.__probe.drop()")
    page.wait_for_function("window.__probe.connected === false")
    # Emitted while the socket is down: queued, not lost, and not rewritten by
    # what the caller did with the payload afterwards.
    page.evaluate("window.__probe.pushThenMutate(9)")
    # Reconnects are retried with backoff, which outlasts the default wait on
    # a machine busy building the frontend.
    page.wait_for_function(f"window.__probe.connects > {connects}", timeout=30_000)
    page.wait_for_function("window.__probe.received.length > 0", timeout=30_000)

    received = page.evaluate("window.__probe.received[0]")
    assert received["data"] == {"n": 9, "sizes": [4]}
    assert received["bytes"] == [4, 3, 2, 1]


def test_frame_queued_on_the_transport_survives_the_reconnect(
    channel_app: AppHarness, page: Page
):
    """A frame emitted as the socket drops is delivered once it is back.

    Such a frame waits on the transport's own queue, so the channel has to be
    reopened before that queue is flushed -- otherwise it reaches the backend
    ahead of its `_open` and is answered with `channel_not_open`.

    Args:
        channel_app: Running AppHarness instance.
        page: Playwright page fixture.
    """
    _connected_probe(channel_app, page)
    connects = page.evaluate("window.__probe.connects")

    page.evaluate("window.__probe.dropThenEmit(5)")
    page.wait_for_function(f"window.__probe.connects > {connects}", timeout=30_000)
    page.wait_for_function("window.__probe.received.length > 0", timeout=30_000)

    received = page.evaluate("window.__probe.received[0]")
    assert received["data"] == {"n": 5, "sizes": [4]}
    assert page.evaluate("window.__probe.errors") == []
