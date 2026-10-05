"""Check descriptor edge cases against the isolated published alpha wheels."""

import json
import os
import pickle
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

import reflex as rx
from reflex_base.plugins.compiler import CompileContext, PageContext
from reflex_base.utils.exceptions import SetUndefinedStateVarError, StateValueError


class Owner(rx.State):
    """Declare frontend/backend fields that subclasses may independently shadow."""

    value: int = 2
    items: list[int] = [1]
    _private: list[int] = []

    @rx.var
    def computed(self) -> int:
        """Return a parent-owned computed value.

        Returns:
            Twice the parent value.
        """
        return self.value * 2

    @rx.event
    def increment(self):
        """Increment the declaring state's value."""
        self.value += 1


class Shadow(Owner):
    """Redeclare frontend, backend, and computed vars with independent values."""

    value: int = 10
    _private: list[int] = [9]

    @rx.var
    def computed(self) -> int:
        """Return a child-owned computed value.

        Returns:
            Three times the child value.
        """
        return self.value * 3


class FieldToComputed(Owner):
    """Replace an inherited base var with a computed var."""

    @rx.var
    def value(self) -> int:
        """Return an independent child value.

        Returns:
            The independent value.
        """
        return 99


class ComputedToField(Owner):
    """Replace an inherited computed var with a stored var."""

    computed: int = 55


class AbstractMixin(ABC, rx.State, mixin=True):
    """Mix ABC machinery into a reusable state class."""

    @abstractmethod
    def _value(self) -> int:
        """Require the concrete state's backend implementation.

        Returns:
            The implementation's value.
        """
        raise NotImplementedError


class Concrete(AbstractMixin, rx.State):
    """Supply the abstract state's backend implementation."""

    def _value(self) -> int:
        """Return the concrete implementation's value.

        Returns:
            The concrete value.
        """
        return 42


def raises(expected: type[Exception], callback: Callable, match: str = "") -> None:
    """Assert an exception from a standalone script without a pytest dependency.

    Args:
        expected: The expected exception type.
        callback: The call expected to fail.
        match: A required substring in its message.
    """
    caught = None
    try:
        callback()
    except expected as error:
        caught = str(error)
    assert caught is not None
    assert match in caught


def declare_reserved() -> None:
    """Declare a state member whose name remains reserved."""

    class Reserved(rx.State):
        _abc_impl: str = "invalid"


def main() -> None:
    """Assert field ownership, abstract mixins, pickle round trips and typo guards."""
    checks = []
    root = rx.State(_reflex_internal_init=True)
    owner = root.get_substate(Owner.get_full_name().split("."))
    shadow = root.get_substate(Shadow.get_full_name().split("."))
    swapped = root.get_substate(FieldToComputed.get_full_name().split("."))
    stored = root.get_substate(ComputedToField.get_full_name().split("."))
    concrete = root.get_substate(Concrete.get_full_name().split("."))
    assert (owner.value, shadow.value, swapped.value, stored.computed) == (
        2,
        10,
        99,
        55,
    )
    assert (owner.computed, shadow.computed) == (4, 30)
    shadow.value = 11
    assert (owner.value, shadow.value, owner.computed, shadow.computed) == (
        2,
        11,
        4,
        33,
    )
    shadow.increment()
    assert (owner.value, shadow.value, owner.computed, shadow.computed) == (
        3,
        11,
        6,
        33,
    )
    assert Shadow.get_fields()["value"]._owner is Shadow
    assert Shadow.get_fields()["items"]._owner is Owner
    assert Shadow.get_fields()["_private"]._owner is Shadow
    shadow.items.append(2)
    shadow._private.append(8)
    assert list(owner.items) == [1, 2]
    assert list(owner._private) == []
    assert list(shadow._private) == [9, 8]
    checks.append(
        "Independent base/backend/computed shadows; base-to-computed and computed-to-base shadows; inherited handler binds owner; inherited mutable value reaches owner"
    )
    assert concrete._value() == 42
    raises(TypeError, lambda: AbstractMixin(_reflex_internal_init=True), "abstract")
    raises(StateValueError, declare_reserved, "reserved")
    checks.append(
        "ABC state mixin composes; abstract methods remain enforced; explicit reserved _abc_impl is rejected"
    )
    loaded_owner = pickle.loads(pickle.dumps(owner))
    loaded_shadow = pickle.loads(pickle.dumps(shadow))
    loaded_shadow.parent_state = loaded_owner
    assert (loaded_owner.value, loaded_shadow.value) == (3, 11)
    assert list(loaded_owner.items) == [1, 2]
    assert list(loaded_shadow._private) == [9, 8]
    loaded_shadow.items.append(3)
    assert list(loaded_owner.items) == [1, 2, 3]
    assert list(owner.items) == [1, 2]
    checks.append(
        "Published-alpha per-state pickle round trips retain independent values; restoring the parent link reconnects inherited mutable ownership"
    )
    for context in (PageContext, CompileContext):
        raises(LookupError, context.get)
    checks.append(
        "PageContext.get and CompileContext.get raise LookupError without an active context"
    )
    mode = os.environ.get("REFLEX_ENV_MODE", "dev")
    try:
        owner.undeclared_probe = 1
    except SetUndefinedStateVarError:
        assert mode != "prod"
        checks.append("Development undeclared-attribute guard rejects a typo")
    else:
        assert mode == "prod"
        assert owner.undeclared_probe == 1
        checks.append("Production permits undeclared attributes as documented")
    result = {"mode": mode, "status": "pass", "checks": checks, "source": rx.__file__}
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
