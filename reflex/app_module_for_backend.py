"""Shims the real reflex app module for running backend server (uvicorn or gunicorn).
Only the app attribute is explicitly exposed.
"""

from concurrent.futures import ThreadPoolExecutor

from reflex import constants
from reflex.utils.exec import is_prod_mode
from reflex.utils.prerequisites import get_and_validate_app

if constants.CompileVars.APP != "app":
    raise AssertionError("unexpected variable name for 'app'")

app, app_module = get_and_validate_app(reload=False)
# For py3.9 compatibility when redis is used, we MUST add any decorator pages
# before compiling the app in a thread to avoid event loop error (REF-2172).
app._apply_decorated_pages()
compile_future = ThreadPoolExecutor(max_workers=1).submit(app._compile)
compile_future.add_done_callback(
    # Force background compile errors to print eagerly
    lambda f: f.result()
)
# Wait for the compile to finish in prod mode to ensure all optional endpoints are mounted.
if is_prod_mode():
    compile_future.result()

# ensure only "app" is exposed.
del app_module
del compile_future
del get_and_validate_app
del is_prod_mode
del constants
del ThreadPoolExecutor
