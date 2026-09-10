"""Page 2: inheritance of hybrid properties and backend var defaults (#6812).

- a plain (non-state) base class defines a hybrid_property and backend-var Fields
- a reflex mixin (rx.State, mixin=True) defines another hybrid_property
- the state annotates the same names (`label: str`, `_cache: dict[str, int]`) -> must
  instantiate, keep the descriptor, and take the base's field() defaults
- a substate reuses the parent's hybrid property
- a sibling state attaches its own var function to the mixin's property without
  touching the mixin's descriptor
"""

import reflex as rx
from reflex.experimental import hybrid_property


def _make_cache() -> dict[str, int]:
    return {"hits": 0}


class HybridBase:
    """Plain python base class (not a state)."""

    _cache = rx.field(default_factory=_make_cache)
    _level = rx.field(default=7)

    @hybrid_property
    def label(self) -> str:
        return f"{self.name}!"  # pyright: ignore[reportAttributeAccessIssue]

    @label.setter
    def _set_label(self, value: str) -> None:
        self.name = value.rstrip("!")  # pyright: ignore[reportAttributeAccessIssue]


class ShoutMixin(rx.State, mixin=True):
    """Reflex mixin state defining a hybrid property."""

    @hybrid_property
    def shout(self) -> str:
        return self.name.upper()  # pyright: ignore[reportAttributeAccessIssue]


class InheritState(HybridBase, ShoutMixin, rx.State):
    name: str = "reflex"
    # annotations on names the bases provide as hybrid properties
    label: str  # pyright: ignore[reportIncompatibleVariableOverride]
    shout: str  # pyright: ignore[reportIncompatibleVariableOverride]
    # backend vars annotated here, defaults come from the base's field()
    _cache: dict[str, int]
    _level: int

    @rx.var
    def cache_hits(self) -> int:
        return self._cache["hits"]

    @rx.var
    def level(self) -> int:
        return self._level

    @rx.var
    def label_backend(self) -> str:
        return self.label

    @rx.var
    def shout_backend(self) -> str:
        return self.shout

    @rx.event
    def hit(self):
        self._cache["hits"] += 1
        self._level += 1

    @rx.event
    def set_via_label(self, value: str):
        self.label = value  # setter inherited from the plain base


class ChildState(InheritState):
    """Real substate; `label`/`shout` resolve against the inherited `name` var."""

    extra: str = "child"

    @rx.var
    def child_label_backend(self) -> str:
        return self.label + self.extra


class SiblingState(HybridBase, rx.State):
    """Attaches its own var function to the base's property (class access on a
    non-state returns the descriptor itself, so `HybridBase.label.var` works)."""

    name: str = "bee"

    @HybridBase.label.var
    def _label_var(cls) -> rx.Var[str]:
        return cls.name + "?"

    @rx.var
    def label_backend(self) -> str:
        return self.label


def inherit_page() -> rx.Component:
    return rx.vstack(
        rx.heading("inheritance"),
        rx.el.input(id="token", value=InheritState.router.session.client_token, read_only=True),
        rx.text(InheritState.label, id="label"),
        rx.text(InheritState.label_backend, id="label_backend"),
        rx.text(InheritState.shout, id="shout"),
        rx.text(InheritState.shout_backend, id="shout_backend"),
        rx.text(InheritState.cache_hits, id="cache_hits"),
        rx.text(InheritState.level, id="level"),
        rx.text(ChildState.label, id="child_label"),
        rx.text(ChildState.child_label_backend, id="child_label_backend"),
        rx.text(SiblingState.label, id="sibling_label"),
        rx.text(SiblingState.label_backend, id="sibling_label_backend"),
        rx.hstack(
            rx.button("hit", on_click=InheritState.hit, id="btn_hit"),
            rx.button("set_via_label", on_click=InheritState.set_via_label("pynecone!"), id="btn_set_label"),
        ),
        rx.link("combo", href="/combo"),
        spacing="2",
        padding="1em",
    )
