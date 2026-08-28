"""MCP client driver for the minimal reflex-enterprise MCPPlugin app.

Usage: python drive_mcp.py <backend_base_url>
Gets an anonymous bearer from /_reflex/auth/token, connects the python `mcp`
streamable-HTTP client to /_reflex/mcp, lists tools/resources, calls the
custom `ping` tool, drives `search_events`/`queue_event`, and reads the
`reflex://` and `state-resource://` resources.
"""

import asyncio
import json
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

BASE = sys.argv[1].rstrip("/")

results = []


def check(name, ok, details=""):
    results.append({"name": name, "ok": bool(ok), "details": str(details)[:500]})
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} :: {str(details)[:500]}")


async def main():
    async with httpx.AsyncClient(trust_env=False) as client:
        r = await client.post(BASE + "/_reflex/auth/token")
        check(
            "token_endpoint",
            r.status_code == 200 and "access_token" in r.json(),
            f"status={r.status_code} body={r.text[:200]}",
        )
        token = r.json()["access_token"]

        # unauthenticated MCP request should be rejected
        r2 = await client.post(
            BASE + "/_reflex/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={
                "content-type": "application/json",
                "accept": "application/json, text/event-stream",
            },
            follow_redirects=True,
        )
        check(
            "mcp_requires_auth",
            r2.status_code == 401,
            f"status without bearer={r2.status_code} (after redirects)",
        )

    headers = {"Authorization": f"Bearer {token}"}
    async with streamablehttp_client(BASE + "/_reflex/mcp", headers=headers) as (
        read,
        write,
        _,
    ):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            instr = init.instructions or ""
            check(
                "mcp_initialize",
                bool(init.serverInfo),
                f"server={init.serverInfo.name} instructions[:120]={instr[:120]!r}",
            )

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            check(
                "tools_list",
                {"ping", "search_events", "queue_event"} <= set(names),
                f"tools={names}",
            )

            ping = await session.call_tool("ping", {})
            ping_text = ping.content[0].text if ping.content else ""
            check("custom_tool_ping", ping_text == "pong", f"ping -> {ping_text!r}")

            res = await session.list_resources()
            uris = sorted(str(r.uri) for r in res.resources)
            check("resources_list", len(uris) > 0, f"resources={uris}")

            tmpl = await session.list_resource_templates()
            turis = sorted(str(t.uriTemplate) for t in tmpl.resourceTemplates)
            check(
                "resource_templates_list",
                any("reflex://state/vars/" in u for u in turis),
                f"templates={turis}",
            )
            # no-arg rxe.mcp.resource methods surface as concrete resources
            summary_uri = next(
                (u for u in uris if "state-resource://" in u and "summary" in u), None
            )
            check(
                "state_resource_advertised",
                summary_uri is not None,
                f"summary_uri={summary_uri}",
            )

            ver = await session.read_resource("config://version")
            vtext = ver.contents[0].text
            check("custom_resource_version", vtext == "1.0.0-test", f"-> {vtext!r}")

            # search_events for the increment handler
            se = await session.call_tool("search_events", {"query": "increment"})
            se_text = se.content[0].text if se.content else ""
            check(
                "search_events",
                "increment" in se_text,
                f"search_events('increment')[:300] -> {se_text[:300]!r}",
            )
            # extract the full event name
            event_name = None
            try:
                data = json.loads(se_text)
                if isinstance(data, dict):
                    entries = data.get("events") or data.get("results") or [data]
                else:
                    entries = data
                for e in entries:
                    n = e.get("name") or e.get("event_name") or ""
                    if "increment" in n:
                        event_name = n
                        break
            except Exception:
                import re

                m = re.search(r"[\w.\-]*increment[\w.\-]*", se_text)
                event_name = m.group(0) if m else None
            print("EVENT NAME:", event_name)

            # resolve the fully-qualified state name from reflex://state
            state_name = None
            try:
                stl = await session.read_resource("reflex://state")
                stl_text = stl.contents[0].text
                import re

                m = re.search(r"[\w.]*counter_state[\w.]*", stl_text)
                state_name = m.group(0) if m else None
                check(
                    "read_states_meta",
                    state_name is not None,
                    f"states[:300]={stl_text[:300]!r} -> state_name={state_name}",
                )
            except Exception as e:
                check("read_states_meta", False, f"exception: {e}")

            # queue increment(amount=5)
            q = await session.call_tool(
                "queue_event",
                {"event_name": event_name, "payload": {"amount": 5}},
            )
            q_text = q.content[0].text if q.content else ""
            check(
                "queue_event_increment",
                "5" in q_text and not q.isError,
                f"delta[:300]={q_text[:300]!r}",
            )

            # queue again -> 10 (session persistence across calls)
            q2 = await session.call_tool(
                "queue_event",
                {"event_name": event_name, "payload": {"amount": 5}},
            )
            q2_text = q2.content[0].text if q2.content else ""
            check(
                "queue_event_session_persists",
                "10" in q2_text and not q2.isError,
                f"delta[:300]={q2_text[:300]!r}",
            )

            # read live state var
            try:
                sv = await session.read_resource(f"reflex://state/vars/{state_name}")
                sv_text = sv.contents[0].text
                check(
                    "read_state_vars",
                    '"count": 10' in sv_text or "'count': 10" in sv_text,
                    f"state vars[:300]={sv_text[:300]!r}",
                )
            except Exception as e:
                check("read_state_vars", False, f"exception: {e}")

            # computed var recompute
            try:
                dv = await session.read_resource(
                    f"reflex://state/vars/{state_name}/doubled"
                )
                dv_text = dv.contents[0].text
                check("read_computed_var", "20" in dv_text, f"doubled -> {dv_text!r}")
            except Exception as e:
                check("read_computed_var", False, f"exception: {e}")

            # custom state resource (URI as advertised in resources/list)
            try:
                sr = await session.read_resource(
                    summary_uri or f"state-resource://{state_name}/summary"
                )
                sr_text = sr.contents[0].text
                check(
                    "custom_state_resource",
                    "10" in sr_text and "hello" in sr_text,
                    f"summary -> {sr_text!r}",
                )
            except Exception as e:
                check("custom_state_resource", False, f"exception: {e}")

            # event metadata resource
            try:
                ev = await session.read_resource(f"reflex://event/{event_name}")
                ev_text = ev.contents[0].text
                check(
                    "read_event_meta",
                    "amount" in ev_text,
                    f"event meta[:300]={ev_text[:300]!r}",
                )
            except Exception as e:
                check("read_event_meta", False, f"exception: {e}")

    fails = [r for r in results if not r["ok"]]
    print(f"\nSUMMARY: {len(results) - len(fails)}/{len(results)} passed")
    with open(sys.argv[2] if len(sys.argv) > 2 else "mcp_results.json", "w") as f:
        json.dump(results, f, indent=2)


asyncio.run(main())
