"""Inferred types for `reflex.state` that are part of the public contract."""

from typing import assert_type

import reflex as rx
from reflex.vars.sequence import ArrayVar, StringVar

# `rx.State.pid` only exists once a page at `/post/[pid]` is added, so type
# checkers cannot see it; `route_arg` returns the same var, typed. The catch-all
# of a route is always named `splat` and holds the remaining segments.
assert_type(rx.State.route_arg("pid"), StringVar)
assert_type(rx.State.route_arg("splat"), ArrayVar[list[str]])
