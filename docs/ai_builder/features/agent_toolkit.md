# Agent Toolkit

The **Agent Toolkit** brings together the current Reflex documentation, the hosted Reflex MCP server, and Reflex Agent Skills so local coding assistants can work with the same guidance as Reflex Build.

Agent Toolkit configures assistants that run outside Reflex Build. For web search, Python execution, and image generation used by the Builder agent inside an app, see [Agent Tools](/docs/ai/features/agent-tools/).

```python exec
import reflex as rx
```

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/agent_toolkit.webp",
    alt="Agent Toolkit MCP and coding assistant setup options",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

Open **Agent Toolkit** in the project sidebar to find setup instructions for supported coding assistants.

```md alert info
# Enterprise access
The hosted Reflex MCP server currently requires an Enterprise organization. [Contact the Reflex team](https://reflex.dev/pricing/) if the MCP connection is unavailable for your organization.
```

## MCP

Connect an MCP-compatible assistant to:

```text
https://build.reflex.dev/mcp
```

The page provides client-specific instructions for Claude Code, Claude Desktop, Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, and Windsurf. Authentication opens in your browser when the client first connects.

See [MCP installation](/docs/ai/integrations/mcp-installation/) for the commands and configuration for each client.

## Reflex Agent Skills

Skills add reusable Reflex-specific workflows to a local coding assistant. The Agent Toolkit shows the recommended installation method for supported tools and a manual `AGENTS.md` option.

Use MCP for current structured documentation and component context. Use Skills for repeatable setup, development, validation, and debugging behavior. They can be used together.

For the complete onboarding workflow, see the [Agent Toolkit guide](/docs/ai/integrations/agent-toolkit/).
