# Overview

```md alert warning
# The Reflex MCP integration is currently only available for enterprise customers. Please [book a demo](https://reflex.dev/pricing/) to discuss access.
```

The Reflex [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server lets compatible coding assistants search current Reflex framework and component documentation.

The hosted server is available at:

```text
https://build.reflex.dev/mcp
```

## Available tool

The server currently exposes one read-only tool:

- `search_docs(query)` searches the Reflex documentation index and returns the relevant documentation sections and their source paths.

Use it for questions about Reflex APIs, components, configuration, and development workflows. Review the returned source before applying a change that depends on version-specific behavior.

See [Installation](/docs/ai/integrations/mcp-installation/) for supported clients and authentication steps.

## Enterprise Use

For an on-premises deployment of the Reflex MCP server, [contact the Reflex team](https://reflex.dev/pricing/).
