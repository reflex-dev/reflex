import reflex as rx
import os as _qa_os

_qa_ev = _qa_os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard
    assert f"/envs/{_qa_ev}/" in rx.__file__, rx.__file__


class UploadConfig(rx.Config):
    pass


config = UploadConfig(
    app_name="upload",
    env=rx.Env.DEV,
    plugins=[rx.plugins.RadixThemesPlugin()],
)
