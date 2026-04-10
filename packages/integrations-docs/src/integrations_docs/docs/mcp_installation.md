# Installation

```python exec
import reflex as rx
```

```md alert warning
# The Reflex MCP integration is currently only available for enterprise customers. Please [book a demo](https://reflex.dev/pricing/) to discuss access.
```

To use the Reflex MCP integration, you'll need to configure your AI assistant or coding tool to connect to the Reflex MCP server. No additional Python packages are required on your local machine - the server is hosted and ready to use.

## Prerequisites

- An MCP-compatible AI tool (Claude Desktop, Windsurf, Codex, etc.)
- Internet connection to access the hosted MCP server
- Valid Reflex account for OAuth 2.1 authentication

## Authentication

The Reflex MCP server uses OAuth 2.1 protocol for secure authentication. You'll need a valid Reflex account, and authentication is handled automatically through your MCP client configuration when you provide your Reflex credentials.

## IDE and Coding Assistant Integration

### Claude Desktop

Add the Reflex MCP server to your Claude Desktop configuration by editing your configuration file:

```json
{
  "mcpServers": {
    "reflex": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.reflex.dev/mcp"]
    }
  }
}
```

### Windsurf/Cascade

Create a `.vscode/mcp.json` file in your project root:

```json
{
  "mcpServers": {
    "reflex": {
      "serverType": "http",
      "url": "https://mcp.reflex.dev/mcp"
    }
  }
}
```

### Codex

Add this configuration to your `~/.codex/config.toml` file:

```toml
[mcp_servers.reflex]
command = "npx"
args = ["-y", "mcp-remote", "https://mcp.reflex.dev/mcp"]
```

Note: Codex requires MCP servers to communicate over stdio. The `mcp-remote` package bridges the connection to the HTTP-based Reflex MCP server.
