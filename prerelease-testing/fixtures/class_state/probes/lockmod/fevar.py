import threading

import reflex as rx


class Holder:
    def __init__(self):
        self.lock = threading.Lock()


class FeState(rx.State):
    holder: Holder = Holder()  # frontend var of a non-serializable type
