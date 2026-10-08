import reflex as rx
import os as _qa_os

_qa_ev = _qa_os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard (a4_upgrade_ent)
    assert f"/scratchpad/envs/{_qa_ev}/" in rx.__file__, rx.__file__

config = rx.Config(
    app_name="github_stats",
    plugins=[rx.plugins.RadixThemesPlugin()],
)
