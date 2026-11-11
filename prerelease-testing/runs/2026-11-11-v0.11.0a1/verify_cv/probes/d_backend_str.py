"""Item D: server-side text conversion of a backend var accessed on the class."""
import io
import json
import logging
import pprint
import pydoc
import sys
import contextlib

import reflex as rx

venv = sys.argv[1]
assert f"/envs/{venv}/" in rx.__file__, rx.__file__


class Mix(rx.State, mixin=True):
    mcount: int = 0


class S(Mix, rx.State):
    _secret: str = "s3cr3t-default"
    _cache: dict = {}
    v: int = 0


logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="LOG %(message)s")
x = S._secret
cases = {
    "print(S._secret)": lambda: print(x, file=io.StringIO()),
    "str(S._secret)": lambda: str(x),
    "'%s' % S._secret": lambda: "%s" % x,
    "'{}'.format(S._secret)": lambda: "{}".format(x),
    "f'{S._secret}'": lambda: f"{x}",
    "f'{S._secret!r}'": lambda: f"{x!r}",
    "repr(S._secret)": lambda: repr(x),
    "json.dumps(S._secret, default=str)": lambda: json.dumps(x, default=str),
    "pprint.pformat(vars(S)['_secret'])": lambda: pprint.pformat(x),
    "str(Mix.mcount) (mixin field)": lambda: str(Mix.mcount),
    "help-style pydoc.render_doc(S)": lambda: len(pydoc.render_doc(S)),
    "str(S.get_fields()['v'])": lambda: str(S.get_fields()["v"]),
    "str(S.__dict__)": lambda: len(str(S.__dict__)),
    "debug loop: [f'{k}={getattr(S,k)}' for backend vars]": lambda: [str(getattr(S, k)) for k in S.backend_vars],
}
for name, fn in cases.items():
    try:
        r = fn()
        print(f"[ok]   {name}: {str(r)[:70]!r}")
    except Exception as e:
        print(f"[RAISE] {name}: {type(e).__name__}: {str(e)[:110]}")

buf = io.StringIO()
with contextlib.redirect_stderr(buf):
    logging.info("%s", x)
    logging.info(x)
print("[logging.info('%s', S._secret) / logging.info(S._secret)] stderr:", "Logging error" in buf.getvalue() and "--- Logging error --- (swallowed, app continues)" or "clean")
