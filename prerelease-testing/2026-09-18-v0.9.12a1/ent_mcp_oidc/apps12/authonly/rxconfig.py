import reflex_enterprise as rxe

config = rxe.Config(
    app_name="authapp",
    plugins=[rxe.AuthPlugin()],   # AuthPlugin ONLY, no MCPPlugin
)
