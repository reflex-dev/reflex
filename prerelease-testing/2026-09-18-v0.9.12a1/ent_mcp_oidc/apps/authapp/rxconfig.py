import reflex_enterprise as rxe

config = rxe.Config(
    app_name="authapp",
    plugins=[rxe.AuthPlugin(), rxe.MCPPlugin()],
)
