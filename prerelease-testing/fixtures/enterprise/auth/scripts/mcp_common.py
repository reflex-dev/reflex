"""MCP client helpers (published mcp SDK) for the ent_auth_mcp_redis cluster."""

import base64
import contextlib
import hashlib
import json
import re
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import mcp

assert ("/envs/" + __import__("os").environ.get("ENT_DRV", "ent-drv") + "/") in mcp.__file__, mcp.__file__  # reflex + reflex-enterprise[mcp] + playwright (ENT_DRV)
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

AGENT = "reflex___state____state.entauth___entauth____agent_state"


def text_value(result):
    """Decode a tool/resource result into JSON when possible."""
    if hasattr(result, "contents"):
        text = "\n".join(c.text for c in result.contents if hasattr(c, "text"))
    else:
        text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def tool_result(result):
    """Return {'is_error': bool, 'value': decoded}."""
    return {"is_error": bool(getattr(result, "isError", False)), "value": text_value(result)}


@contextlib.asynccontextmanager
async def mcp_session(url: str, token: str):
    async with httpx.AsyncClient(headers={"Authorization": "Bearer " + token}, timeout=60) as client:
        async with streamable_http_client(url, http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def call(session, name, args=None):
    return tool_result(await session.call_tool(name, args or {}))


async def read(session, uri):
    try:
        return {"is_error": False, "value": text_value(await session.read_resource(uri))}
    except Exception as exc:  # McpError
        return {"is_error": True, "value": f"{type(exc).__name__}: {exc}"}


def pkce():
    verifier = "ent-auth-mcp-redis-verifier-" + "y" * 40
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge
