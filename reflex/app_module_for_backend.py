"""Shims the real reflex app module for running backend server (uvicorn or gunicorn).
Only the app attribute is explicitly exposed.
"""
from concurrent.futures import ThreadPoolExecutor

from reflex import constants
from reflex.utils.exec import is_prod_mode
from reflex.utils.prerequisites import get_app, get_compiled_app

if "app" != constants.CompileVars.APP:
    raise AssertionError("unexpected variable name for 'app'")

app_module = get_app(reload=False)
app = getattr(app_module, constants.CompileVars.APP)
_executor = ThreadPoolExecutor(max_workers=1)


def _done(executor: ThreadPoolExecutor):
    def _cb(f):
        # Do not leak file handles from the executor itself
        executor.shutdown(wait=False)
        # Force background compile errors to print eagerly
        print("compile done", f.result(), executor)

    return _cb


compile_future = _executor.submit(app.compile_)
compile_future.add_done_callback(_done(_executor))

# Wait for the compile to finish in prod mode to ensure all optional endpoints are mounted.
if is_prod_mode():
    compile_future.result()

# ensure only "app" is exposed.
del app_module
del compile_future
del _done
del _executor
del get_app
del get_compiled_app
del is_prod_mode
del constants
del ThreadPoolExecutor
