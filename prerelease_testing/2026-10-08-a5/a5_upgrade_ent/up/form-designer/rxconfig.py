import reflex as rx
import os as _qa_os

_qa_ev = _qa_os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard (a5_upgrade_ent)
    assert f"/scratchpad/envs/{_qa_ev}/" in rx.__file__, rx.__file__

config = rx.Config(
    app_name="form_designer",
    db_url="sqlite:///reflex.db",
    plugins=[
        rx.plugins.sitemap.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(theme=rx.theme(accent_color="blue")),
    ],
)
