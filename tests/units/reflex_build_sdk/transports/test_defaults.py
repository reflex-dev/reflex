from __future__ import annotations

import subprocess
import sys

import pytest
from reflex_build_sdk import transports
from reflex_build_sdk.transports import (
    AiohttpTransport,
    AsyncHttpx2Transport,
    AsyncHttpxTransport,
    AsyncTransport,
    Httpx2Transport,
    HttpxTransport,
    Transport,
    _defaults,
)
from reflex_build_sdk.transports._defaults import (
    async_default_transport,
    default_transport,
)


def _without(monkeypatch: pytest.MonkeyPatch, *missing: str) -> None:
    real_find_spec = _defaults.find_spec
    monkeypatch.setattr(
        _defaults,
        "find_spec",
        lambda name: None if name in missing else real_find_spec(name),
    )


@pytest.mark.parametrize(
    ("missing", "expected"),
    [
        ((), Httpx2Transport),
        (("httpx2",), HttpxTransport),
    ],
)
def test_default_transport(
    monkeypatch: pytest.MonkeyPatch,
    missing: tuple[str, ...],
    expected: type[Transport],
):
    _without(monkeypatch, *missing)
    transport = default_transport()
    assert type(transport) is expected
    transport.close()


def test_default_transport_needs_an_http_library(monkeypatch: pytest.MonkeyPatch):
    _without(monkeypatch, "httpx2", "httpx")
    with pytest.raises(ImportError, match=r"reflex-build-sdk\[httpx2\]"):
        default_transport()


@pytest.mark.parametrize(
    ("missing", "expected"),
    [
        ((), AiohttpTransport),
        (("aiohttp",), AsyncHttpx2Transport),
        (("aiohttp", "httpx2"), AsyncHttpxTransport),
    ],
)
async def test_async_default_transport(
    monkeypatch: pytest.MonkeyPatch,
    missing: tuple[str, ...],
    expected: type[AsyncTransport],
):
    _without(monkeypatch, *missing)
    transport = async_default_transport()
    assert type(transport) is expected
    await transport.aclose()


def test_async_default_transport_needs_an_http_library(
    monkeypatch: pytest.MonkeyPatch,
):
    _without(monkeypatch, "aiohttp", "httpx2", "httpx")
    with pytest.raises(ImportError, match=r"reflex-build-sdk\[aiohttp\]"):
        async_default_transport()


def test_transports_rejects_unknown_attributes():
    with pytest.raises(AttributeError, match="Nope"):
        transports.Nope  # pyright: ignore[reportAttributeAccessIssue]


def test_sdk_imports_without_http_libraries():
    # A None entry in sys.modules makes importing that module raise ImportError.
    code = """
import sys
sys.modules["aiohttp"] = sys.modules["httpx"] = sys.modules["httpx2"] = None
from reflex_build_sdk import AsyncReflexBuild, ReflexBuild
from reflex_build_sdk.transports import AiohttpTransport
for client in (AsyncReflexBuild, ReflexBuild):
    try:
        client(token="t")
    except ImportError as ex:
        print(ex)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.splitlines() == [
        (
            "AsyncReflexBuild needs an HTTP library to send requests: install "
            "reflex-build-sdk[aiohttp], or pass a transport."
        ),
        (
            "ReflexBuild needs an HTTP library to send requests: install "
            "reflex-build-sdk[httpx2], or pass a transport."
        ),
    ]
