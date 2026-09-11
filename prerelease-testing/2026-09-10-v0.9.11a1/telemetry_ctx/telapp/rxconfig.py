import os
import sys
import threading

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_imports.log"), "a") as _f:
    _f.write(
        f"import thread={threading.current_thread().name} pid={os.getpid()} "
        f"syspath_len={len(sys.path)}\n"
    )

import reflex as rx

config = rx.Config(app_name="telapp")
