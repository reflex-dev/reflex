"""Config for the minimal MCP plugin test app (ent_misc cluster)."""

import reflex as rx

import reflex_enterprise as rxe


def customize(server):
    """Register a custom tool + resource on the FastMCP server (configure= hook)."""

    @server.tool()
    def ping() -> str:
        """Return pong."""
        return "pong"

    @server.resource("config://version")
    def version() -> str:
        """Version resource."""
        return "1.0.0-test"


config = rxe.Config(
    app_name="mcp_app",
    plugins=[rxe.MCPPlugin(configure=customize)],
    disable_plugins=[rx.plugins.sitemap.SitemapPlugin],
)
