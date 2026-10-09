"""Does rxconfig.py reach the BACKEND worker? Read config values inside an event handler (runs in the backend process)."""

import os
import sys

import reflex as rx
from reflex_base.config import get_config


class S(rx.State):
    msg: str = ""
    extra: str = ""

    @rx.event
    def show(self):
        c = get_config()
        self.msg = (
            f"py={sys.version.split()[0]} pid={os.getpid()} auto_setters={c.state_auto_setters} "
            f"lock_exp={c.redis_lock_expiration} color_mode={c.default_color_mode} "
            f"has_set_extra={'set_extra' in type(self).event_handlers}"
        )


def index():
    return rx.vstack(rx.button("show config", id="show", on_click=S.show), rx.text(S.msg, id="msg"))


app = rx.App()
app.add_page(index)
