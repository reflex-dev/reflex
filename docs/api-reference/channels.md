```python exec
import reflex as rx
```

# Channels

A channel is an application-defined message stream multiplexed onto the
websocket your app already uses for state updates. It is the supported way for
a component or a third-party package to move data that does not belong in
state — streaming chart columns, a live cursor position, an audio buffer —
without opening a second connection.

Because a channel rides the app's own socket, it inherits the connection's
origin checks, client token, reconnect handling and reverse-proxy setup.

Channels require state to be enabled (the default) and the `websocket`
transport. They are not available under `transport="socketio"` or
`transport="polling"`: there, registering a channel logs a warning and skips
it, and its browser-side handle reports a `channels_unsupported` error.

## Defining a channel

Subclass `rx.channels.Channel`, give it a name, and handle messages:

```python
import reflex as rx


class Ticks(rx.channels.Channel):
    name = "ticks"

    async def on_open(self, session):
        session.data["symbols"] = set()

    async def on_message(self, session, event, data, buffers):
        if event == "subscribe":
            session.join(data["symbol"])
            session.data["symbols"].add(data["symbol"])
        elif event == "unsubscribe":
            session.leave(data["symbol"])

    async def on_close(self, session):
        del session.data["symbols"]


app = rx.App()
app.register_channel(Ticks())
```

A package can register its channel from a plugin's `post_compile` hook instead,
which runs at backend startup with the live app. Registration never stops an
app that cannot serve channels from starting, so a package needs no check of
its own.

Every field of an inbound message is client-controlled and unvalidated. A
handler that raises is logged and the connection keeps serving, so a failing
handler never drops the app's socket.

Handlers run inline on their connection's receive loop, which keeps messages
in order and lets a slow channel push back on its client. It also means a
handler that awaits something slow stalls that connection — its state updates
wait, its heartbeat replies stop, and after `REFLEX_SOCKET_INTERVAL +
REFLEX_SOCKET_TIMEOUT` the server closes it as unresponsive. That holds for
anything the handler awaits, `asyncio.to_thread` included, so run long work in
a task of its own and answer when it finishes:

```python
import asyncio


class Rows(rx.channels.Channel):
    name = "rows"

    def __init__(self):
        super().__init__()
        # Held, so the event loop does not drop a running task.
        self._tasks = set()

    async def on_message(self, session, event, data, buffers):
        task = asyncio.create_task(self._answer(session, data["filter"]))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _answer(self, session, query_filter):
        rows = await asyncio.to_thread(expensive_query, query_filter)
        if session.open:
            await session.send("rows", {"count": len(rows)}, [rows.tobytes()])
```

## Sending to clients

`ChannelSession.send` answers one client. `Channel.send_to_room` fans out to
everyone who joined a room, and `Channel.send_to_token` addresses every
session belonging to one client token (browser tab):

```python
await session.send("tick", {"symbol": "RFX", "price": 42.0})
await self.send_to_room("RFX", "tick", {"price": 42.0})
```

Work running in a task of its own can outlive its client; `session.open`
reports whether the client is still connected before you commit to expensive
or long-lived work. Inside `on_message` itself it stays true: the connection
cannot close while its receive loop is waiting for the handler.

Rooms and sessions are local to the worker holding the connection. A client
reconnecting to another worker opens its session there, so anything that must
outlive a connection belongs in Reflex state, not in the channel.

To push from a background task or a thread, hold the serving event loop and
schedule the coroutine on it with `asyncio.run_coroutine_threadsafe`.

## Binary payloads

Messages may carry binary attachments beside their JSON metadata. They travel
as raw bytes — no base64, no JSON numbers — and arrive in the browser as
`Uint8Array` views, each aligned so it can be read as a typed array without
copying:

```python
class Frames(rx.channels.Channel):
    name = "frames"
    # Inbound attachments are refused unless the channel opts in.
    accepts_binary = True

    async def on_message(self, session, event, data, buffers):
        await session.send("frame", {"rows": len(buffers[0]) // 8}, buffers)
```

A message may carry up to 64 attachments, in either direction:
`session.send` raises and `channel.emit` throws rather than build a frame the
other end would refuse.

Size is capped in one direction only. A frame a client sends must fit
`REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE` (1 MB by default) or the backend closes
the connection, so `channel.emit` throws first and a message queued before the
channel opened is dropped with an `error` when the limit turns out to exclude
it. Raise the setting if your clients send larger payloads; Granian, the
default server, receives frames of at most 16 MiB, so Reflex caps the setting
there and you need uvicorn for anything larger. Messages the server sends are
not capped by it — mind the section below on sharing the connection.

`connect`, `disconnect` and `error` are reserved message names: the client
handle reports its own lifecycle under them. So is every name starting with
`_`, which the channel protocol uses for its own messages. Neither end puts a
reserved name on the wire: `session.send` and `channel.emit` refuse them, and a
message that arrives under one is answered with a `reserved_event` error
instead of reaching `on_message`.

## Using a channel from the frontend

`getChannel` returns a handle that survives reconnects and remounts, so a
component can register its handlers once:

```javascript
import { getChannel } from "$/utils/state";

const channel = getChannel("ticks");

channel.on("connect", () => channel.emit("subscribe", { symbol: "RFX" }));
channel.on("tick", (data, buffers) => console.log(data.price));
channel.on("error", (error) => console.error(error.code, error.message));

// Attachments are an array of ArrayBuffers or typed arrays.
channel.emit("frame", { seq: 1 }, [new Float64Array([1, 2, 3])]);
```

`channel.emit` throws on anything the backend would refuse — a name that is
not a string or is reserved, attachments that are not an array of binary
buffers — rather than cost the app its socket. Read a `Blob` with
`await blob.arrayBuffer()` before attaching it.

Messages emitted before the channel is open are queued and flushed on
`connect`. `error` reports a channel-level failure: an unknown channel name, a
backend too old to speak channels, or a transport that cannot carry them.

## Performance

On uvicorn, websocket messages are compressed with permessage-deflate by
default. That is a good trade for JSON state updates and a poor one for binary
data, which barely shrinks while costing milliseconds of event loop time per
message. Apps that stream binary over a channel should turn it off:

```bash
REFLEX_SOCKET_PER_MESSAGE_DEFLATE=false reflex run --env prod
```

Granian, the default server, does not negotiate permessage-deflate at all, so
the setting only changes uvicorn deployments.

Channel messages share one connection with state updates, so a very large
message delays the deltas queued behind it. Prefer messages bounded by what the
client actually needs — a screenful of data, not a whole dataset.
