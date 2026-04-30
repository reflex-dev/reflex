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

### Claude Code

Add the Reflex MCP server to Claude Code by running:

```bash
claude mcp add --transport http reflex https://build.reflex.dev/mcp
```

Then authenticate by running the `/mcp` command inside Claude Code and following the login steps in your browser. Authentication tokens are stored securely and refreshed automatically. See the [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp) for more details.

### Claude Desktop

Claude Desktop pulls remote MCP servers from your Claude account's connectors. Go to [claude.ai](https://claude.ai) → **Settings** → **Connectors** → **Add custom connector**, enter `https://build.reflex.dev/mcp` as the URL, and complete the OAuth login. The connector will then be available in Claude Desktop after you sign in. See the [custom connectors guide](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) for details and plan availability.

### Windsurf/Cascade

Edit (or create) `~/.codeium/windsurf/mcp_config.json` and add the Reflex server:

```json
{
  "mcpServers": {
    "reflex": {
      "serverUrl": "https://build.reflex.dev/mcp"
    }
  }
}
```

After saving, open Cascade and click the refresh icon in the MCP toolbar to load the new server. See the [Windsurf MCP documentation](https://docs.windsurf.com/windsurf/cascade/mcp) for more details.

### Codex

Add this to your `~/.codex/config.toml` file:

```toml
[mcp_servers.reflex]
url = "https://build.reflex.dev/mcp"
```

See the [Codex MCP documentation](https://developers.openai.com/codex/mcp) for additional options such as `bearer_token_env_var` and `http_headers`.
