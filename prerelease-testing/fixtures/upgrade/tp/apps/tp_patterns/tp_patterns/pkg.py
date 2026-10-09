"""Stand-in for a third-party package: base states, mixins and helpers a package would ship."""

from __future__ import annotations

import asyncio

import reflex as rx


class PkgCounterMixin(rx.State, mixin=True):
    """A package-provided mixin contributing a var, a backend var, a computed var and handlers."""

    count: int = 0
    _hits: int = 0

    @rx.var
    def doubled(self) -> int:
        return self.count * 2

    @rx.var
    def hits_view(self) -> str:
        return f"hits={self._hits}"

    @rx.event
    def incr(self):
        self.count += 1
        self._hits += 1

    @rx.event(background=True)
    async def slow_incr(self):
        await asyncio.sleep(0.3)
        async with self:
            self.count += 10
            self._hits += 1


class PkgBaseState(rx.State):
    """A package-provided base state that user apps subclass."""

    items: list[str] = []
    note: str = ""
    _secret: str = "pkg-secret"

    @rx.var
    def n_items(self) -> int:
        return len(self.items)

    @rx.event
    def add(self, item: str):
        self.items.append(f"{item}:{self._decorate()}")

    def _decorate(self) -> str:
        return "base"

    @rx.event
    def clear(self):
        self.items = []


class PkgOtherState(rx.State):
    """A separate package state that a package handler reaches with get_state."""

    remote: str = "untouched"
    _remote_hits: int = 0


def backend_var_names(cls) -> list[str]:
    """What a package does to discover backend vars (the replacement for backend_vars)."""
    names = []
    for name, f in cls.get_fields().items():
        if name.startswith("_") and not name.startswith("__"):
            names.append(name)
    return sorted(names)


def own_backend_var_names(cls) -> list[str]:
    """Backend vars declared by cls itself, the way a 0.10-aware package would do it."""
    out = []
    for name, f in cls.get_fields().items():
        owner = getattr(f, "_owner", None)
        backend = getattr(f, "_backend", name.startswith("_"))
        if backend and (owner is None or owner is cls) and not name.startswith("_reflex"):
            out.append(name)
    return sorted(out)
