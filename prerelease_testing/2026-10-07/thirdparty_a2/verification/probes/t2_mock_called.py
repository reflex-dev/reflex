"""T-2 side effects with test doubles: does assigning a Mock to a State var CALL the mock?"""
import os
from typing import Optional
from unittest import mock
import reflex as rx
assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version
print("reflex", version("reflex"))


class Client:
    pass


class FakeClient:  # duck-typed double, not a Client subclass
    pass


class Svc(rx.State):
    _client: Optional[Client] = None  # properly typed slot
    _untyped = None  # unannotated placeholder
    _n: int = 0


def t(label, fn):
    try:
        r = fn()
        print(f"  {label:<78} -> {r!r}"[:210])
    except Exception as e:  # noqa: BLE001
        print(f"  {label:<78} -> RAISES {type(e).__name__}: {str(e)[:100]}")


m1 = mock.MagicMock(name="plain_mock")
t("setattr(Svc,'_client', MagicMock())  [typed Optional[Client] slot]", lambda: setattr(Svc, "_client", m1))
print("     plain MagicMock .called after the assignment attempt:", m1.called, "call_count:", m1.call_count)

m2 = mock.MagicMock(name="untyped_mock")
t("setattr(Svc,'_untyped', MagicMock())  [unannotated None placeholder]", lambda: setattr(Svc, "_untyped", m2))
print("     MagicMock .called:", m2.called, "call_count:", m2.call_count)

m3 = mock.MagicMock(name="spec_mock", spec=Client)
t("setattr(Svc,'_client', MagicMock(spec=Client))", lambda: setattr(Svc, "_client", m3))
print("     spec'd MagicMock .called:", m3.called)
Svc._client = None  # reset the slot to its original value (works: Optional[Client] accepts None)

t("setattr(Svc,'_client', FakeClient())  [duck-typed double]", lambda: setattr(Svc, "_client", FakeClient()))

m4 = mock.MagicMock(name="int_returning", return_value=7)
t("setattr(Svc,'_n', MagicMock(return_value=7))  [int slot; mock acts as factory]", lambda: setattr(Svc, "_n", m4))
print("     int-returning mock .called:", m4.called, "call_count:", m4.call_count)
def _read():
    try:
        i = Svc(_reflex_internal_init=True)
    except TypeError:
        i = Svc()
    return i._n
t("fresh Svc()._n  (each new instance calls the mock again?)", _read)
print("     mock call_count after one more instance:", m4.call_count)

p = mock.patch.object(Svc, "_n", mock.MagicMock(return_value=8))
t("mock.patch.object(Svc,'_n', MagicMock(return_value=8)).start()", lambda: p.start())
t("  ... then .stop()", lambda: p.stop())
