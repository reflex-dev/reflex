"""#7673 bugfix control: bind a proxied dict, then a proxied list, to event handlers.

usage (neutral cwd): EXPECT_VENV=$SB/envs/prev $SB/envs/prev/bin/python -I proxied_args.py
"""
import os

import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
from importlib.metadata import version

print("reflex", version("reflex"))


class P(rx.State):
    data: dict[str, int] = {"a": 1}
    rows: list[dict[str, int]] = [{"x": 1}]
    names: list[str] = ["n"]

    @rx.event
    def takes_dict(self, d: dict[str, int]): ...

    @rx.event
    def takes_list(self, rows: list[dict[str, int]]): ...

    @rx.event
    def takes_names(self, names: list[str]): ...


s = P(_reflex_internal_init=True)
for label, call in [
    ("dict then list", lambda: (P.takes_dict(s.data), P.takes_list(s.rows))),
    ("list then dict", lambda: (P.takes_list(s.rows), P.takes_dict(s.data))),
    ("list[str] then dict then list[dict]", lambda: (P.takes_names(s.names), P.takes_dict(s.data), P.takes_list(s.rows))),
]:
    try:
        specs = call()
        print(f"- {label}: ok ({type(s.data).__name__}, {type(s.rows).__name__}) -> {len(specs)} specs")
    except Exception as ex:
        print(f"- {label}: RAISES {type(ex).__name__}: {str(ex)[:200]}")
