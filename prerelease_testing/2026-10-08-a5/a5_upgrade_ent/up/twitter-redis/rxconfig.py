import reflex as rx
import os as _qa_os

_qa_ev = _qa_os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard (a5_upgrade_ent)
    assert f"/scratchpad/envs/{_qa_ev}/" in rx.__file__, rx.__file__

config = rx.Config(
    app_name="twitter",
    db_url="sqlite:///reflex.db",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="light",
                has_background=True,
                radius="large",
                accent_color="teal",
            ),
        ),
    ],
)
