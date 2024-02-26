"""Shims the real reflex app module for running backend server (uvicorn or gunicorn).
Only the app attribute is explicitly exposed.
"""
from concurrent.futures import ThreadPoolExecutor

from reflex import constants
from reflex.utils.prerequisites import get_app, get_compiled_app

if "app" != constants.CompileVars.APP:
    raise AssertionError("unexpected variable name for 'app'")

app_module = get_app(reload=False)
app = getattr(app_module, constants.CompileVars.APP)
# Force background compile errors to print eagerly
ThreadPoolExecutor(max_workers=1).submit(app.compile_).add_done_callback(
    lambda f: f.result()
)

# ensure only "app" is exposed.
del app_module
del get_app
del get_compiled_app
del constants
del ThreadPoolExecutor
