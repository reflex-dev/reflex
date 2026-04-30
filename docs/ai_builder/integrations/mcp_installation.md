# Installation

```python exec
import reflex as rx
```

```md alert warning
# The Reflex MCP integration is currently only available for enterprise customers. Please [book a demo](https://reflex.dev/pricing/) to discuss access.
```

To use the Reflex MCP integration, you'll need to configure your AI assistant or coding tool to connect to the Reflex MCP server. No additional Python packages are required on your local machine - the server is hosted and ready to use.

## Prerequisites

- An MCP-compatible AI tool (Claude Code, Claude Desktop, Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Windsurf, etc.)
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

### Codex

Add the Reflex MCP server to Codex by running:

```bash
codex mcp add reflex --url https://build.reflex.dev/mcp
```

See the [Codex MCP documentation](https://developers.openai.com/codex/mcp) for more details.

### Cursor

[Click here to install the Reflex MCP server in Cursor](cursor://anysphere.cursor-deeplink/mcp/install?name=reflex&config=eyJ1cmwiOiJodHRwczovL2J1aWxkLnJlZmxleC5kZXYvbWNwIn0=), or edit (or create) `~/.cursor/mcp.json` for a global config, or `.cursor/mcp.json` in your project root for a project-specific config:

```json
{
  "mcpServers": {
    "reflex": {
      "url": "https://build.reflex.dev/mcp"
    }
  }
}
```

Open Cursor settings under **MCP & Integrations** to verify the server is connected and complete OAuth login. See the [Cursor MCP documentation](https://cursor.com/docs/context/mcp) for more details.

### Gemini CLI

Add the Reflex MCP server to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "reflex": {
      "httpUrl": "https://build.reflex.dev/mcp"
    }
  }
}
```

See the [Gemini CLI MCP documentation](https://google-gemini.github.io/gemini-cli/docs/tools/mcp-server.html) for more details.

### GitHub Copilot

Create a `.vscode/mcp.json` file in your project root (or open **MCP: Open User Configuration** from the VS Code command palette for a global config):

```json
{
  "servers": {
    "reflex": {
      "type": "http",
      "url": "https://build.reflex.dev/mcp"
    }
  }
}
```

After saving, start the server from the inline action above the entry in `mcp.json`, then complete the OAuth login when prompted. See the [VS Code MCP documentation](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) for more details.

### OpenCode

Add the Reflex MCP server to your `opencode.json` (project) or `~/.config/opencode/opencode.json` (global):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "reflex": {
      "type": "remote",
      "url": "https://build.reflex.dev/mcp",
      "enabled": true
    }
  }
}
```

See the [OpenCode MCP documentation](https://opencode.ai/docs/mcp-servers/) for more details.

### Windsurf

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
