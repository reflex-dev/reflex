"""Inferred types for `reflex.state` that are part of the public contract."""

from typing import assert_type

import reflex as rx
from reflex.vars.sequence import ArrayVar, StringVar

# `rx.State.pid` only exists once a page at `/post/[pid]` is added, so type
# checkers cannot see it; `route_arg` returns the same var, typed, and
# `route_catch_all` the one of a `[[...splat]]` catch-all.
assert_type(rx.State.route_arg("pid"), StringVar)
assert_type(rx.State.route_catch_all(), ArrayVar[list[str]])
