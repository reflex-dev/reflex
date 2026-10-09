"""Import probe for the SQLAlchemy 2.1 / greenlet gap. Usage: <venv>/bin/python -I greenlet_probe.py <venv-substring>"""
import sys
from importlib.metadata import PackageNotFoundError, version


def v(n):
    try:
        return version(n)
    except PackageNotFoundError:
        return "NOT INSTALLED"


import reflex as rx

assert sys.argv[1] in rx.__file__, rx.__file__
print(f"reflex {v('reflex')} sqlmodel {v('sqlmodel')} sqlalchemy {v('sqlalchemy')} greenlet {v('greenlet')}")
try:
    class M(rx.Model, table=True):
        name: str

    print("OK: rx.Model subclass created, table", M.__tablename__)
except Exception as e:  # noqa: BLE001
    print(f"FAIL: {type(e).__name__}: {str(e).splitlines()[0][:200]}")
