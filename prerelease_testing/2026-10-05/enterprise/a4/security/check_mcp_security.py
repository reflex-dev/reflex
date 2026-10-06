"""Probe OAuth bearer identity, session spoofing and protected MCP surfaces."""

import asyncio
import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:8152"
RESOURCE = BASE + "/_reflex/mcp"
CALLBACK = "http://localhost:9151/mcp-return"
STATE = "reflex___state____state.security_probe___security_probe____record_state"
PRIME = "security_probe___security_probe____record_state.prime"
CUSTOM = "state-resource://security_probe___security_probe____record_state/private_summary"


def content(result):
    """Decode JSON MCP content without storing credentials.

    Args:
        result: A tool or resource result.

    Returns:
        Its JSON-compatible content.
    """
    items = result.contents if hasattr(result, "contents") else result.content
    text = "\n".join(item.text for item in items if hasattr(item, "text"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def issue_token(user: str, evidence: dict) -> str:
    """Obtain a real app-issued OAuth bearer through OIDC and browser consent.

    Args:
        user: The mock subject consenting to agent access.
        evidence: Mutable redacted observation data.

    Returns:
        An app-issued bearer kept only in memory.
    """
    verifier = "security-boundary-" + "x" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    with httpx.Client(follow_redirects=True) as client:
        metadata = client.get(BASE + "/.well-known/oauth-authorization-server").json()
        response = client.post(metadata["registration_endpoint"], json={"client_name": "Security boundary probe", "redirect_uris": [CALLBACK], "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "client_secret_post", "scope": "profile:read"})
        response.raise_for_status()
        registered = response.json()
        authorization = metadata["authorization_endpoint"] + "?" + urlencode({"client_id": registered["client_id"], "redirect_uri": CALLBACK, "response_type": "code", "code_challenge": challenge, "code_challenge_method": "S256", "state": "security-probe", "resource": RESOURCE, "scope": "profile:read"})
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            context.route(CALLBACK + "**", lambda route: route.fulfill(status=200, body="Local OAuth callback"))
            page = context.new_page()
            page.goto(authorization)
            page.get_by_role("button", name="Login with Generic").click()
            page.wait_for_url(re.compile("/oauth2/authorize"))
            page.locator(f'button[name="sub"][value="{user}"]').click()
            page.wait_for_url(re.compile("/agent-consent"))
            expect(page.get_by_role("checkbox")).to_be_checked()
            page.get_by_role("button", name="Approve", exact=True).click()
            page.wait_for_url(lambda url: url.startswith(CALLBACK))
            parameters = parse_qs(urlparse(page.url).query)
            assert parameters["state"] == ["security-probe"]
            code = parameters["code"][0]
            browser.close()
        payload = {"grant_type": "authorization_code", "code": code, "redirect_uri": CALLBACK, "client_id": registered["client_id"], "client_secret": registered["client_secret"], "code_verifier": verifier, "resource": RESOURCE}
        response = client.post(metadata["token_endpoint"], data=payload)
        response.raise_for_status()
        token = response.json()["access_token"]
        replay = client.post(metadata["token_endpoint"], data=payload)
        evidence[user + "_oauth"] = {"exchange_status": response.status_code, "opaque": "." not in token, "code_replay_status": replay.status_code}
        assert replay.status_code == 400
        return token


async def read_guarded(session: ClientSession, uri: str):
    """Record an authorized value or explicit MCP denial.

    Args:
        session: The authenticated MCP transport session.
        uri: The protected resource URI.

    Returns:
        The resource content or a denial message.
    """
    try:
        return {"content": content(await session.read_resource(uri))}
    except Exception as error:
        return {"denial": type(error).__name__ + ": " + str(error)}


async def probe(alice: str, bob: str, evidence: dict) -> None:
    """Check invalid tokens, anonymous gates and cross-bearer session isolation.

    Args:
        alice: Alice's valid opaque OAuth bearer.
        bob: Bob's separate valid opaque OAuth bearer.
        evidence: Mutable redacted observations.
    """
    forged = ".".join(base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=") for value in ({"alg": "none", "typ": "JWT"}, {"sub": "alice", "scope": "profile:read", "resource": RESOURCE, "exp": 9999999999})) + "."
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "security-probe", "version": "1"}}}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for label, token in (("missing", None), ("invented", "invented-session-bearer"), ("unsigned_jwt", forged)):
            response = await client.post(RESOURCE, headers={"Authorization": "Bearer " + token} if token else {}, json=initialize)
            evidence[label] = {"status": response.status_code, "body": response.text}
            assert response.status_code == 401
        response = await client.post(BASE + "/_reflex/auth/token", json={"client_token": "chosen-by-caller", "sub": "alice"})
        response.raise_for_status()
        anonymous = response.json()["access_token"]
    for label, token in (("anonymous", anonymous), ("alice", alice), ("bob", bob)):
        headers = {"Authorization": "Bearer " + token, "X-User-Sub": "alice", "X-Client-Token": "chosen-by-caller"}
        async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
            async with streamable_http_client(RESOURCE, http_client=client) as (read, write, session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    item = {"tools": [tool.name for tool in tools.tools]}
                    if label != "bob":
                        item["prime"] = content(await session.call_tool("queue_event", {"event_name": PRIME, "payload": {}}))
                    item["protected_field"] = await read_guarded(session, f"reflex://state/vars/{STATE}/private_record")
                    item["protected_resource"] = await read_guarded(session, CUSTOM)
                    item["root_state"] = await read_guarded(session, "reflex://state/vars/reflex___state____state")
                    search = content(await session.call_tool("search_events", {"query": "logout"}))
                    item["framework_logout_search"] = search
                    evidence[label] = item
                    serialized = json.dumps(item)
                    if label != "alice":
                        assert "alice-PRIVATE-RECORD" not in serialized
                    else:
                        assert "alice-PRIVATE-RECORD" in json.dumps(item["protected_resource"])
                        identifier = session_id()
                        assert identifier
                        payload = {"jsonrpc": "2.0", "id": 80, "method": "resources/read", "params": {"uri": CUSTOM}}
                        async with httpx.AsyncClient(follow_redirects=True) as wire:
                            response = await wire.post(RESOURCE, headers={"Authorization": "Bearer " + bob, "Mcp-Session-Id": identifier, "MCP-Protocol-Version": "2025-03-26", "Accept": "application/json, text/event-stream"}, json=payload)
                            evidence["bob_bearer_alice_transport_session"] = {"status": response.status_code, "body": response.text}
                            assert "alice-PRIVATE-RECORD" not in response.text
                            invalid = await wire.post(RESOURCE, headers={"Authorization": "Bearer invented", "Mcp-Session-Id": identifier}, json=initialize)
                            evidence["invalid_bearer_alice_transport_session"] = {"status": invalid.status_code, "body": invalid.text}
                            assert invalid.status_code == 401
                    (ROOT / "logs/mcp-security.json").write_text(json.dumps(evidence, indent=2))


def main() -> None:
    """Run real OAuth and MCP boundary checks with credentials kept in memory."""
    evidence = {}
    alice = issue_token("alice", evidence)
    bob = issue_token("bob", evidence)
    (ROOT / "logs/mcp-security.json").write_text(json.dumps(evidence, indent=2))
    asyncio.run(probe(alice, bob, evidence))
    evidence["completed"] = True
    (ROOT / "logs/mcp-security.json").write_text(json.dumps(evidence, indent=2))
    print("OAuth bearer, anonymous protection and transport-session identity checks passed")


if __name__ == "__main__":
    main()
