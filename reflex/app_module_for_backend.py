"""Shims the real reflex app module for running backend server (uvicorn or gunicorn).
Only the app attribute is explicitly exposed.
"""

import time
from concurrent.futures import ThreadPoolExecutor

from reflex import constants
from reflex.utils import telemetry
from reflex.utils.exec import is_prod_mode
from reflex.utils.prerequisites import get_app

if constants.CompileVars.APP != "app":
    raise AssertionError("unexpected variable name for 'app'")

app_module = get_app(reload=False)
app = getattr(app_module, constants.CompileVars.APP)
# For py3.8 and py3.9 compatibility when redis is used, we MUST add any decorator pages
# before compiling the app in a thread to avoid event loop error (REF-2172).
app._apply_decorated_pages()
start_time = time.perf_counter()


compile_future = ThreadPoolExecutor(max_workers=1).submit(app._compile)
compile_future.add_done_callback(lambda f: telemetry.compile_callback(f, start_time))

# Wait for the compile to finish in prod mode to ensure all optional endpoints are mounted.
if is_prod_mode():
    compile_future.result()

# ensure only "app" is exposed.
del app_module
del compile_future
del get_app
del is_prod_mode
del constants
del ThreadPoolExecutor
