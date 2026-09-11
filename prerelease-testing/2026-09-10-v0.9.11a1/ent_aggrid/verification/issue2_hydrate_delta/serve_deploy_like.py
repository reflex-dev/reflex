"""Emulate a containerized deployment: backend process that never compiles.

This is exactly what `reflex run --env prod` does when uvicorn+gunicorn are installed
(reflex/utils/exec.py:783 spawns the prod backend with __REFLEX_SKIP_COMPILE=true), and
what a Dockerfile that runs `reflex export` in one step and serves the ASGI app in another
does. The frontend build in .web/build is reused as-is.
"""

import os
import sys

os.environ["__REFLEX_SKIP_COMPILE"] = "true"
os.environ["__REFLEX_MOUNT_FRONTEND_COMPILED_APP"] = "true"
os.environ["REFLEX_ENV_MODE"] = "prod"
os.environ["CI"] = "1"
os.environ["APP_HARNESS_FLAG"] = "1"
os.environ["REFLEX_TELEMETRY_ENABLED"] = "false"

import reflex  # noqa: E402

print("VERIFY reflex from:", reflex.__file__, flush=True)

from granian.constants import Interfaces  # noqa: E402
from granian.server import Server as Granian  # noqa: E402

from reflex.utils.exec import get_app_instance_from_file  # noqa: E402

target = get_app_instance_from_file()
print("ASGI target:", target, flush=True)
Granian(
    target=target,
    factory=True,
    address="0.0.0.0",
    port=int(sys.argv[1]),
    interface=Interfaces.ASGI,
    workers=1,
).serve()
