import reflex as rx

from agent_files import AgentFilesPlugin

LLMS_TXT_PATH = "/llms.txt"


def _llms_txt_directive() -> rx.Component:
    """Return the agent-facing docs index directive."""
    return rx.el.blockquote(
        rx.el.span("For AI agents: the complete documentation index is at "),
        rx.el.a("llms.txt", href=LLMS_TXT_PATH),
        rx.el.span(
            ". Markdown versions are available by appending .md or sending "
            "Accept: text/markdown."
        ),
        class_name="sr-only",
    )


config = rx.Config(
    app_name="reflex_docs",
    frontend_path="/docs",
    frontend_packages=[
        "tailwindcss-animated",
    ],
    telemetry_enabled=False,
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                _llms_txt_directive(),
                has_background=True,
                radius="large",
                accent_color="violet",
            ),
        ),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.SitemapPlugin(trailing_slash="always"),
        AgentFilesPlugin(),
    ],
)
