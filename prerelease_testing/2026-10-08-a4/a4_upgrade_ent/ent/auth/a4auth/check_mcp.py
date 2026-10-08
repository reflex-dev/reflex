"""Exercise the anonymous MCP plugin through the published SDK transport."""

import asyncio
import json
from pathlib import Path

import reflex  # ENT_AUTH_VENV_GUARD

assert "/scratchpad/envs/ent_auth2-drv/" in reflex.__file__, reflex.__file__

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:8626"  # ent_auth cluster port (10-05 used 8132)


def text_value(result) -> object:
    """Decode text content from one MCP result.

    Args:
        result: A tool or resource read result.

    Returns:
        The decoded JSON content when possible, otherwise the text.
    """
    text = (
        "\n".join(c.text for c in result.contents if hasattr(c, "text"))
        if hasattr(result, "contents")
        else "\n".join(c.text for c in result.content if hasattr(c, "text"))
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def main() -> None:
    """Check missing tokens, mutations, reads, isolation, and redaction."""
    evidence = {}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for name, headers in [
            ("missing_bearer", {}),
            ("fabricated_bearer", {"Authorization": "Bearer test-invented-token"}),
        ]:
            response = await client.post(
                BASE + "/_reflex/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                },
            )
            evidence[name] = {"status": response.status_code, "body": response.text}
            (ROOT / "logs/mcp-anonymous.json").write_text(
                json.dumps(evidence, indent=2)
            )
            assert response.status_code == 401
        token_a = (await client.post(BASE + "/_reflex/auth/token")).json()[
            "access_token"
        ]
        token_b = (await client.post(BASE + "/_reflex/auth/token")).json()[
            "access_token"
        ]
    for label, token in [("A", token_a), ("B", token_b)]:
        async with httpx.AsyncClient(
            headers={"Authorization": "Bearer " + token}
        ) as client:
            async with streamable_http_client(
                BASE + "/_reflex/mcp", http_client=client
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    tools = await session.list_tools()
                    search = text_value(
                        await session.call_tool("search_events", {"query": "bump"})
                    )
                    evidence[label] = {
                        "instructions": init.instructions,
                        "tools": [t.name for t in tools.tools],
                        "search": search,
                    }
                    (ROOT / "logs/mcp-anonymous.json").write_text(
                        json.dumps(evidence, indent=2)
                    )
                    events = search if isinstance(search, list) else search["results"]
                    event_name = next(
                        e["name"] for e in events if e["name"].endswith(".bump")
                    )
                    state_name = (
                        "reflex___state____state." + event_name.rsplit(".", 1)[0]
                    )
                    if label == "A":
                        mutation = text_value(
                            await session.call_tool(
                                "queue_event",
                                {"event_name": event_name, "payload": {"amount": 4}},
                            )
                        )
                        evidence[label]["mutation"] = mutation
                    count = text_value(
                        await session.read_resource(
                            f"reflex://state/vars/{state_name}/count"
                        )
                    )
                    doubled = text_value(
                        await session.read_resource(
                            f"reflex://state/vars/{state_name}/doubled"
                        )
                    )
                    evidence[label].update(count=count, doubled=doubled)
                    (ROOT / "logs/mcp-anonymous.json").write_text(
                        json.dumps(evidence, indent=2)
                    )
                    assert count["value"] == (4 if label == "A" else 0), count
                    assert doubled["value"] == (8 if label == "A" else 0), doubled
                    whole = text_value(
                        await session.read_resource(
                            "reflex://state/vars/reflex___state____state"
                        )
                    )
                    evidence[label]["root_state"] = whole
                    templates = await session.list_resource_templates()
                    evidence[label]["resource_templates"] = [
                        str(t.uriTemplate) for t in templates.resourceTemplates
                    ]
                    summary = text_value(
                        await session.read_resource(
                            "state-resource://components___components____agent_state/summary/local-label"
                        )
                    )
                    evidence[label]["summary"] = summary
                    assert summary["count"] == (4 if label == "A" else 0), summary
                    assert summary["label"] == "local-label", summary
                    assert '"client_token": ""' in json.dumps(whole), whole
                    assert '"session_id": ""' in json.dumps(whole), whole
    (ROOT / "logs/mcp-anonymous.json").write_text(json.dumps(evidence, indent=2))
    print(
        "Anonymous MCP token rejection, events, computed reads, redaction and session isolation passed"
    )


if __name__ == "__main__":
    asyncio.run(main())
