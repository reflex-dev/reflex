"""Shims the real reflex app module for running backend server (uvicorn or gunicorn).
Only the app attribute is explicitly exposed.
"""
from reflex import constants
from reflex.utils.prerequisites import get_app

if "app" != constants.CompileVars.APP:
    raise AssertionError("unexpected variable name for 'app'")
app = getattr(get_app(), constants.CompileVars.APP)

# ensure only "app" is exposed.
del get_app
del constants
