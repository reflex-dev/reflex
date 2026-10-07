import os, reflex
assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__
import reflex as rx
class Cfg(rx.State):
    limit: int = 0
    _quota: int = 0
Cfg.limit = 10
Cfg._quota = 10
s = Cfg(_reflex_internal_init=True)
print(reflex.__file__.split('/envs/')[1].split('/')[0], "instance:", s.limit, s._quota)
try:
    print("field default:", Cfg.get_fields()["limit"].default_value(), Cfg.get_fields()["_quota"].default_value())
except Exception as e:
    print("field default n/a:", type(e).__name__, e)
