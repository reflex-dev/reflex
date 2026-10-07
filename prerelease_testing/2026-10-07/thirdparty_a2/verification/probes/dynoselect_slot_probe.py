"""Replicate reflex-dynoselect's exact class-level assignment (component.State._raw_options = <list[Option]>) using the real Option type."""
import os, warnings
warnings.simplefilter("ignore")
import reflex as rx
assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version
print("reflex", version("reflex"))
from reflex_dynoselect.options import Option  # real dict subclass used by the package


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


class Dyno(rx.State):
    _raw_options: list[dict[str, str]] = []  # declaration copied from reflex_dynoselect/dynoselect.py:330


opts = [Option(label="A", value="a"), Option(label="B", value="b")]
try:
    Dyno._raw_options = opts
    print("  assignment ok; instance reads", [dict(o) for o in inst(Dyno)._raw_options])
except Exception as e:  # noqa: BLE001
    print("  assignment RAISES", type(e).__name__, str(e)[:120])
