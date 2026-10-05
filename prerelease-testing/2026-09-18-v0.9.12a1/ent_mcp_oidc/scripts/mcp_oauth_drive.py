"""Drive the reflex-enterprise MCP OAuth 2.1 flow with the real MCP SDK client.

The app runs ``rxe.AuthPlugin() + rxe.MCPPlugin()``, so the MCP endpoint is an
OAuth 2.1 resource server. This script is a real MCP client: it uses
``mcp.client.auth.OAuthClientProvider`` (RFC 9728 discovery + RFC 7591 dynamic
client registration + PKCE authorization code) and a real Chromium to perform
the human half — OIDC login at the fake IdP, then Approve on the app's consent
page. Afterwards it opens an MCP session with the granted token and checks that
the agent acts *as the logged-in user* (``auth=True`` handlers and protected
computed vars, which an anonymous session is refused).

Run this with the driver venv's python (playwright) after
``uv pip install mcp httpx`` into it, or with any venv that has both.

Usage: python mcp_oauth_drive.py <frontend_port> <backend_port> <callback_port> <label> <outdir>
"""

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from playwright.async_api import async_playwright
from pydantic import AnyUrl

FPORT, BPORT, CBPORT = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
LABEL, OUTDIR = sys.argv[4], sys.argv[5]
FRONT = f"http://localhost:{FPORT}"
BACK = f"http://localhost:{BPORT}"
MCP_URL = f"{BACK}/_reflex/mcp"

OUT = {"label": LABEL, "steps": []}
_code_holder: dict[str, str] = {}
_code_event = threading.Event()


def step(name, **kw):
    """Record and print one step."""
    OUT["steps"].append({"step": name, **kw})
    print(f"[{name}] " + json.dumps(kw, default=str)[:600], flush=True)


class _CallbackHandler(BaseHTTPRequestHandler):
    """Catch the OAuth redirect the browser is sent to."""

    def do_GET(self):  # noqa: N802
        """Record code/state and answer the browser."""
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        # the browser also asks for /favicon.ico on this origin: ignore it
        if parsed.path.startswith("/callback") and (q.get("code") or q.get("error")):
            _code_holder.update(
                code=(q.get("code") or [""])[0],
                state=(q.get("state") or [""])[0],
                error=(q.get("error") or [""])[0],
                raw=self.path,
            )
            _code_event.set()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>callback received</h1>")

    def log_message(self, *a):  # noqa: D102
        pass


class MemStorage:
    """In-memory OAuth token/client storage."""

    def __init__(self):
        self.tokens: OAuthToken | None = None
        self.client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self):
        """Return stored tokens."""
        return self.tokens

    async def set_tokens(self, tokens):
        """Store tokens."""
        self.tokens = tokens

    async def get_client_info(self):
        """Return the registered client."""
        return self.client_info

    async def set_client_info(self, client_info):
        """Store the registered client."""
        self.client_info = client_info


async def human_consent(auth_url: str):
    """Drive Chromium through IdP login and the app's consent page."""
    step("authorization_url", url=auth_url[:400])
    async with async_playwright() as p:
        br = await p.chromium.launch(
            executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"]
        )
        ctx = await br.new_context(viewport={"width": 1200, "height": 900})
        page = await ctx.new_page()
        console = []
        page.on("console", lambda m: console.append(f"{m.type}:{m.text[:150]}"))
        await page.goto(auth_url, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        step("after_authorize_nav", url=page.url[:200],
             text=(await page.locator("body").inner_text())[:300])
        await page.screenshot(path=f"{OUTDIR}/{LABEL}_30_consent_or_login.png",
                              full_page=True)

        # The consent page is auth-guarded: sign in first if it bounced us to
        # the AuthPlugin login page (the fake IdP auto-approves).
        login_btn = page.get_by_role("button", name="Login with")
        if await login_btn.count():
            step("login_required", url=page.url[:200])
            await login_btn.first.click()
            await page.wait_for_timeout(6000)
            step("after_idp_login", url=page.url[:250],
                 text=(await page.locator("body").inner_text())[:300])

        # wait for the consent page to appear.
        for _ in range(20):
            body = await page.locator("body").inner_text()
            if "Authorize MCP access" in body:
                break
            await page.wait_for_timeout(1000)
        body = await page.locator("body").inner_text()
        step("consent_page", visible="Authorize MCP access" in body,
             url=page.url[:200], text=body[:500])
        await page.screenshot(path=f"{OUTDIR}/{LABEL}_31_consent.png", full_page=True)

        approve = page.get_by_role("button", name="Approve")
        if await approve.count():
            await approve.first.click()
            await page.wait_for_timeout(4000)
        step("after_approve", url=page.url[:250],
             text=(await page.locator("body").inner_text())[:200],
             console_errors=[c for c in console if c.startswith("error")][:5])
        await page.screenshot(path=f"{OUTDIR}/{LABEL}_32_after_approve.png",
                              full_page=True)
        await br.close()


async def wait_for_code() -> tuple[str, str | None]:
    """Block until the callback receiver has the code."""
    for _ in range(120):
        if _code_event.is_set():
            break
        await asyncio.sleep(0.5)
    step("callback_received", **{k: v[:80] for k, v in _code_holder.items()})
    return _code_holder.get("code", ""), _code_holder.get("state") or None


async def main():
    """Run the OAuth MCP client end to end."""
    srv = HTTPServer(("127.0.0.1", CBPORT), _CallbackHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as hc:
        for path in (
            f"/.well-known/oauth-protected-resource/_reflex/mcp",
            "/.well-known/oauth-authorization-server",
        ):
            r = await hc.get(BACK + path)
            step("metadata", path=path, status=r.status_code,
                 body=r.text[:400] if r.status_code == 200 else r.text[:150])
        r = await hc.post(
            MCP_URL + "/",
            headers={"Accept": "application/json, text/event-stream",
                     "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "probe", "version": "1"}}},
        )
        step("unauthenticated_mcp", status=r.status_code,
             www_authenticate=r.headers.get("www-authenticate", ""), body=r.text[:200])

    storage = MemStorage()
    provider = OAuthClientProvider(
        server_url=MCP_URL,
        client_metadata=OAuthClientMetadata(
            redirect_uris=[AnyUrl(f"http://localhost:{CBPORT}/callback")],
            client_name="prerelease-test-agent",
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="client_secret_post",
        ),
        storage=storage,
        redirect_handler=human_consent,
        callback_handler=wait_for_code,
    )

    async with streamablehttp_client(MCP_URL, auth=provider, timeout=120) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            step("initialize", server=init.serverInfo.name,
                 instructions=(init.instructions or "")[:300])
            ci = storage.client_info
            step("registered_client",
                 client_id=(ci.client_id if ci else None),
                 has_secret=bool(ci and ci.client_secret))
            tok = storage.tokens
            step("granted_token", token_type=tok.token_type if tok else None,
                 scope=tok.scope if tok else None,
                 expires_in=tok.expires_in if tok else None,
                 has_refresh=bool(tok and tok.refresh_token))

            tools = await s.list_tools()
            step("tools", names=[t.name for t in tools.tools],
                 queue_event_schema=json.dumps(
                     next((t.inputSchema for t in tools.tools
                           if t.name == "queue_event"), {}))[:600])

            res = await s.list_resources()
            step("resources", uris=[str(x.uri) for x in res.resources][:10])
            tpl = await s.list_resource_templates()
            step("resource_templates",
                 uris=[t.uriTemplate for t in tpl.resourceTemplates][:10])

            # who am I? AuthUserState should carry the logged-in identity
            found = await s.call_tool("search_events", {"query": "secret"})
            step("search_events", text=str(found.content[0].text)[:500])

            # the fully-qualified state names the resource templates accept
            rr = await s.read_resource(AnyUrl("reflex://state"))
            states_blob = str(rr.contents[0].text)
            step("reflex_state", text=states_blob[:500])
            short_name = "authapp___authapp____public_state"
            state_name = json.loads(states_blob)["states"][1]
            step("state_names", short=short_name, fully_qualified=state_name)

            # auth=True handler: refused for anonymous sessions, allowed here
            call = await s.call_tool(
                "queue_event",
                {"event_name": f"{short_name}.set_secret",
                 "payload": {"value": "set-by-mcp-agent"}},
            )
            step("queue_event_auth_true", is_error=call.isError,
                 text=str(call.content[0].text)[:600])

            # protected computed var read
            for uri in (
                f"reflex://state/vars/{state_name}/secret_label",
                f"reflex://state/vars/{state_name}",
            ):
                try:
                    rr = await s.read_resource(AnyUrl(uri))
                    step("read_resource", uri=uri,
                         text=str(rr.contents[0].text)[:400])
                except Exception as e:  # noqa: BLE001
                    step("read_resource_error", uri=uri,
                         error=f"{type(e).__name__}: {e}"[:300])

            # background auth=True handler
            call = await s.call_tool(
                "queue_event", {"event_name": f"{short_name}.slow_secret"}
            )
            step("queue_event_background_auth", is_error=call.isError,
                 text=str(call.content[0].text)[:400])

    # control: an ANONYMOUS session token must be refused the same handler
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as hc:
        r = await hc.post(f"{BACK}/_reflex/auth/token")
        step("anon_token", status=r.status_code, body=r.text[:200])
        anon = r.json().get("access_token", "")
    async with streamablehttp_client(
        MCP_URL, headers={"Authorization": f"Bearer {anon}"}, timeout=60
    ) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            call = await s.call_tool(
                "queue_event",
                {"event_name": f"{short_name}.set_secret",
                 "payload": {"value": "set-by-anon"}},
            )
            step("anon_queue_event_auth_true", is_error=call.isError,
                 text=str(call.content[0].text)[:400])
            try:
                rr = await s.read_resource(
                    AnyUrl(f"reflex://state/vars/{state_name}/secret_label")
                )
                step("anon_read_protected_var", text=str(rr.contents[0].text)[:300])
            except Exception as e:  # noqa: BLE001
                step("anon_read_protected_var_refused",
                     error=f"{type(e).__name__}: {e}"[:300])

    srv.shutdown()


asyncio.run(main())
with open(f"{OUTDIR}/mcp_oauth_{LABEL}.json", "w") as fh:
    json.dump(OUT, fh, indent=1)
print("\nwrote", f"{OUTDIR}/mcp_oauth_{LABEL}.json")
