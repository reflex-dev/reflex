import os
import threading

import reflex as rx

import sibling_settings  # project-local sibling module (#6933)

with open(os.path.join(os.path.dirname(__file__), "config_imports.log"), "a") as f:
    f.write(
        f"rxconfig import thread={threading.current_thread().name} "
        f"pid={os.getpid()} syspath_len={len(__import__('sys').path)}\n"
    )

config = rx.Config(app_name=sibling_settings.APP_NAME)
