# reflex-sdk

Python client for the [Reflex Cloud](https://build.reflex.dev) API, with synchronous and asynchronous interfaces.

```python
from reflex_sdk import ReflexCloud

with ReflexCloud() as client:
    me = client.auth.me()
    print(me.email, me.tier)
```

```python
from reflex_sdk import AsyncReflexCloud

async with AsyncReflexCloud() as client:
    me = await client.auth.me()
```

## Authentication

The client uses the first access token it finds:

1. The `token` argument.
2. The `REFLEX_ACCESS_TOKEN` environment variable.
3. The token saved by `reflex login`.

Create a token for CI with `client.auth.tokens.create("ci", expires_in_days=30)`.

## Errors

Every exception derives from `reflex_sdk.ReflexCloudError`. Error responses raise a subclass of `APIStatusError` matching the status code (`AuthenticationError`, `NotFoundError`, ...), carrying `status_code`, the server's `detail`, and the `request_id` to quote to support. Failed requests are retried up to `max_retries` times when repeating them cannot apply them twice: requests that never reached the server or were turned away with 408 or 429, and `GET`, `HEAD`, `OPTIONS` and `PUT` requests that timed out, lost their connection, or got a 500, 502, 503 or 504 response.

## Transports

`AsyncReflexCloud` sends requests with [aiohttp](https://docs.aiohttp.org) and `ReflexCloud` with [httpx](https://www.python-httpx.org). Pass a transport from `reflex_sdk.transports` to configure the HTTP client, e.g. for proxies, or to use httpx asynchronously:

```python
import aiohttp
import httpx
from reflex_sdk import AsyncReflexCloud, ReflexCloud
from reflex_sdk.transports import AiohttpTransport, AsyncHttpxTransport, HttpxTransport

async with aiohttp.ClientSession(proxy="http://proxy:8080") as session:
    async with AsyncReflexCloud(transport=AiohttpTransport(session)) as client:
        ...

client = AsyncReflexCloud(transport=AsyncHttpxTransport())
client = ReflexCloud(transport=HttpxTransport(httpx.Client(proxy="http://proxy:8080")))
```

To use another HTTP library, implement the `Transport` or `AsyncTransport` protocol.

