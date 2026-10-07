"""Blank app + env-gated chatty stdout thread (verify_upgrade, A3-07/A3-08)."""

import os
import threading
import time

import reflex as rx

assert "/scratchpad/envs/alpha2/" in rx.__file__, rx.__file__

_RATE = float(os.environ.get("VU_CHATTY_RATE", "0"))
_SEQ_FILE = os.environ.get("VU_SEQ_FILE", "")


def _chatter():
    fd = os.open(_SEQ_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644) if _SEQ_FILE else None
    n = 0
    pad = "x" * 80
    while True:
        n += 1
        print(f"VUSEQ {n:07d} {pad}", flush=True)
        if fd is not None:
            # Last line whose print() returned (i.e. fully handed to the pipe).
            os.pwrite(fd, f"{n:07d}\n".encode(), 0)
        time.sleep(1.0 / _RATE)


async def _start_chatter():
    if _RATE > 0:
        threading.Thread(target=_chatter, daemon=True, name="vu-chatter").start()


class State(rx.State):
    """The app state."""


def index() -> rx.Component:
    return rx.container(rx.heading("blank blank_a2", id="title"))


app = rx.App()
app.add_page(index)
app.register_lifespan_task(_start_chatter)
