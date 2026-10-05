import sys, reflex as rx
print("reflex from:", rx.__file__)
try:
    class S(rx.State):
        n: int = 0
        def get_delta(self):
            return super().get_delta()
    print("PLAIN get_delta override: ALLOWED")
except Exception as e:
    print("PLAIN get_delta override:", type(e).__name__, e)
try:
    class S2(rx.State):
        n: int = 0
        def _get_delta(self):
            return None
    print("_get_delta: ALLOWED")
except Exception as e:
    print("_get_delta:", type(e).__name__, e)
try:
    class Mix:
        def get_delta(self):
            return super().get_delta()
    class S3(Mix, rx.State):
        n: int = 0
    print("mixin base get_delta: ALLOWED")
except Exception as e:
    print("mixin base get_delta:", type(e).__name__, e)
try:
    class S4(rx.State):
        n: int = 0
    S4.get_delta = lambda self: rx.State.get_delta(self)
    print("post-hoc assignment: ALLOWED")
except Exception as e:
    print("post-hoc assignment:", type(e).__name__, e)
