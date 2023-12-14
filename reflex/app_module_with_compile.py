"""Shims the real reflex app module, and performs app.compile_() - so reflex users don't need to do it."""

from reflex.config import get_config

config = get_config()

app_module = f"{config.app_name}.{config.app_name}"

exec(f"from {app_module} import *")

try:
    app.compile_()  # noqa: F821 # type: ignore
except NameError:
    print("app not found in {app_module} - not compiling")
