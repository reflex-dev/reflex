import reflex as rx

config = rx.Config(
    app_name="comp_app",
    # Explicit RadixThemesPlugin: #6776 says deprecated App(theme=...) must
    # still apply its theme when the plugin is explicitly configured.
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(),
    ],
)
