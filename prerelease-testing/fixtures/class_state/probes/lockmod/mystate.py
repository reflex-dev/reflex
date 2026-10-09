import threading

import reflex as rx


class CacheState(rx.State):
    _lock: threading.Lock = threading.Lock()  # user meant a ClassVar
    hits: int = 0
