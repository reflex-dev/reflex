"""Run local MCP OAuth discovery, consent, PKCE, tools and token rotation."""

import asyncio
import base64
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from check_mcp import text_value
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:8132"
RESOURCE = BASE + "/_reflex/mcp"
CALLBACK = "http://localhost:9131/mcp-return"


async def check_tools(token: str) -> dict:
    """Execute a protected event with an app-issued OAuth token.

    Args:
        token: Opaque access token from the local OAuth exchange.

    Returns:
        Redacted MCP response evidence.
    """
    async with httpx.AsyncClient(
        headers={"Authorization": "Bearer " + token}
    ) as client:
        async with streamable_http_client(RESOURCE, http_client=client) as (
            read,
            write,
            _,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                search = text_value(
                    await session.call_tool("search_events", {"query": "reveal"})
                )
                event = next(
                    e["name"] for e in search["results"] if e["handler"] == "reveal"
                )
                mutation = text_value(
                    await session.call_tool(
                        "queue_event", {"event_name": event, "payload": {}}
                    )
                )
                state = "reflex___state____state." + event.rsplit(".", 1)[0]
                value = text_value(
                    await session.read_resource(f"reflex://state/vars/{state}/message")
                )
                assert value["value"] == "revealed-alice", value
                root_state = text_value(
                    await session.read_resource(
                        "reflex://state/vars/reflex___state____state"
                    )
                )
                assert '"client_token": ""' in json.dumps(root_state), root_state
                assert '"session_id": ""' in json.dumps(root_state), root_state
                return {
                    "protected_event": event,
                    "message": value,
                    "delta": mutation,
                    "redacted_root_state": root_state,
                }


def main() -> None:
    """Drive local browser consent then verify the OAuth and MCP endpoints."""
    evidence = {}
    verifier = "local-prerelease-test-verifier-" + "x" * 40
    challenge = (
        base64
        .urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    with httpx.Client() as client:
        metadata = client.get(BASE + "/.well-known/oauth-authorization-server").json()
        evidence["metadata"] = metadata
        registered = client.post(
            metadata["registration_endpoint"],
            json={
                "client_name": "Local prerelease test",
                "redirect_uris": [CALLBACK],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "client_secret_post",
                "scope": "profile:read",
            },
        )
        registered.raise_for_status()
        registration = registered.json()
        evidence["registration"] = {
            k: v
            for k, v in registration.items()
            if k not in {"client_secret", "registration_access_token"}
        }
        authorization = (
            metadata["authorization_endpoint"]
            + "?"
            + urlencode({
                "client_id": registration["client_id"],
                "redirect_uri": CALLBACK,
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "local-test-state",
                "resource": RESOURCE,
                "scope": "profile:read",
            })
        )
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            context.route(
                CALLBACK + "**",
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="<p>Local OAuth callback</p>",
                ),
            )
            page = context.new_page()
            errors, console = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "console",
                lambda msg: console.append({"type": msg.type, "text": msg.text}),
            )
            page.goto(authorization)
            page.wait_for_url(re.compile("/login"))
            page.get_by_role("button", name="Login with Generic").click()
            page.wait_for_url(re.compile("/oauth2/authorize"))
            page.locator('button[name="sub"][value="alice"]').click()
            page.wait_for_url(re.compile("/agent-consent"))
            expect(
                page.get_by_text("Local prerelease test", exact=True)
            ).to_be_visible()
            expect(page.get_by_role("checkbox")).to_be_checked()
            page.screenshot(path=str(ROOT / "screenshots/mcp-oauth-consent.png"))
            page.get_by_role("button", name="Approve", exact=True).click()
            page.wait_for_url(lambda url: url.startswith(CALLBACK))
            params = parse_qs(urlparse(page.url).query)
            assert params["state"] == ["local-test-state"]
            code = params["code"][0]
            evidence["browser"] = {
                "consent_approved": True,
                "state_roundtrip": True,
                "page_errors": errors,
                "console": console,
            }
            browser.close()
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CALLBACK,
            "client_id": registration["client_id"],
            "client_secret": registration["client_secret"],
            "code_verifier": verifier,
            "resource": RESOURCE,
        }
        exchanged = client.post(metadata["token_endpoint"], data=token_data)
        exchanged.raise_for_status()
        tokens = exchanged.json()
        evidence["exchange"] = {
            "status": exchanged.status_code,
            "token_type": tokens["token_type"],
            "scope": tokens.get("scope"),
            "opaque_access_token": "." not in tokens["access_token"],
            "opaque_refresh_token": "." not in tokens["refresh_token"],
        }
        replay = client.post(metadata["token_endpoint"], data=token_data)
        evidence["authorization_code_replay"] = {
            "status": replay.status_code,
            "body": replay.json(),
        }
        assert replay.status_code == 400
        (ROOT / "logs/mcp-oauth.json").write_text(json.dumps(evidence, indent=2))
        evidence["mcp"] = asyncio.run(check_tools(tokens["access_token"]))
        refreshed = client.post(
            metadata["token_endpoint"],
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": registration["client_id"],
                "client_secret": registration["client_secret"],
                "resource": RESOURCE,
            },
        )
        refreshed.raise_for_status()
        rotated = refreshed.json()
        assert rotated["refresh_token"] != tokens["refresh_token"]
        evidence["refresh"] = {
            "status": refreshed.status_code,
            "rotated": True,
            "scope": rotated.get("scope"),
        }
        replayed_refresh = client.post(
            metadata["token_endpoint"],
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": registration["client_id"],
                "client_secret": registration["client_secret"],
                "resource": RESOURCE,
            },
        )
        evidence["refresh_replay"] = {
            "status": replayed_refresh.status_code,
            "body": replayed_refresh.json(),
        }
        assert replayed_refresh.status_code == 400
    (ROOT / "logs/mcp-oauth.json").write_text(json.dumps(evidence, indent=2))
    print(
        "MCP OAuth discovery, registration, browser consent, PKCE, protected event, code replay and refresh rotation passed"
    )


if __name__ == "__main__":
    main()
