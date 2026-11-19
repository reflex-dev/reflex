# Overview

```md alert warning
# The Reflex MCP integration is currently only available for enterprise customers. Please [book a demo](https://reflex.dev/pricing/) to discuss access.
```

The Reflex [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server lets compatible coding assistants search current Reflex framework and component documentation.

The hosted server is available at:

```text
https://build.reflex.dev/mcp
```

## Documentation tools

Check your server's `tools/list` response for the tools available in its deployed version. Releases with the knowledge tools provide two read-only documentation operations:

- `search_reflex_knowledge(queries)` accepts up to five short keyword queries and returns candidate keys, summaries, and source labels from the bundled documentation and curated knowledge.
- `get_reflex_knowledge(keys)` fetches the full text for the exact keys returned by search. Fetch the relevant entries before relying on a summary; the server reports unknown keys separately.

For example, search with `{"queries": ["horizontal scaling", "durable jobs", "Redis Sentinel"]}`, then pass the relevant returned key to `get_reflex_knowledge`. The [scaling guide](/docs/hosting/scaling/) explains version compatibility, regional session state, and recovery assumptions. Split more than five topics into separate search calls.

Older deployments may expose `search_docs` instead. Follow the tool schema advertised by the connected server. The knowledge tools use a packaged documentation snapshot, so a website update alone does not refresh the server's corpus; the server release must also update its locked documentation bundle.

Use it for questions about Reflex APIs, components, configuration, and development workflows. Review the returned source before applying a change that depends on version-specific behavior.

See [Installation](/docs/ai/integrations/mcp-installation/) for supported clients and authentication steps.

## Enterprise Use

For an on-premises deployment of the Reflex MCP server, [contact the Reflex team](https://reflex.dev/pricing/).
