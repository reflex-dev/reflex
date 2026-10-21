from collections.abc import Mapping, Sequence

import pytest
from reflex_base.vars.base import computed_var, figure_out_type

from reflex.state import State


class CustomDict(dict[str, str]):
    """A custom dict with generic arguments."""


class ChildCustomDict(CustomDict):
    """A child of CustomDict."""


class GenericDict(dict):
    """A generic dict with no generic arguments."""


class ChildGenericDict(GenericDict):
    """A child of GenericDict."""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, int),
        (1.0, float),
        ("a", str),
        ([1, 2, 3], Sequence[int]),
        ([1, 2.0, "a"], Sequence[int | float | str]),
        ({"a": 1, "b": 2}, Mapping[str, int]),
        ({"a": 1, 2: "b"}, Mapping[int | str, str | int]),
        (CustomDict(), CustomDict),
        (ChildCustomDict(), ChildCustomDict),
        (GenericDict({1: 1}), Mapping[int, int]),
        (ChildGenericDict({1: 1}), Mapping[int, int]),
    ],
)
def test_figure_out_type(value, expected):
    assert figure_out_type(value) == expected


def test_var_subclass_registration_invalidates_lookup_caches() -> None:
    """A Var subclass registered after lookups were cached takes priority.

    ``Var.to`` / ``Var.guess_type`` dispatch through cached registry lookups;
    registering a new Var subclass must drop those caches so the new (higher
    priority) entry wins for types it claims.
    """
    from reflex_base.vars.base import Var
    from reflex_base.vars.sequence import StringVar

    class FancyTestStr(str):
        """A str subtype that later gets its own Var subclass."""

    assert isinstance(Var(_js_expr="a").to(FancyTestStr), StringVar)

    class FancyTestStrVar(Var, python_types=FancyTestStr):
        """Var subclass claiming FancyTestStr."""

    assert isinstance(Var(_js_expr="a").to(FancyTestStr), FancyTestStrVar)
    assert isinstance(
        Var(_js_expr="a", _var_type=FancyTestStr).guess_type(), FancyTestStrVar
    )


def test_computed_var_replace() -> None:
    class StateTest(State):
        @computed_var(cache=True)
        def cv(self) -> int:
            return 1

    cv = StateTest.cv
    assert cv._var_type is int

    replaced = cv._replace(_var_type=float)
    assert replaced._var_type is float


def test_reset_unique_variable_names_is_deterministic():
    """Resetting the unique-name generator reproduces the same name sequence.

    Auto-memo content hashes embed these names, so a second in-process compile
    must regenerate identical ones (the RNG state and used-name set otherwise
    persist process-wide and drift).
    """
    from reflex_base.vars.base import (
        get_unique_variable_name,
        reset_unique_variable_names,
    )

    reset_unique_variable_names()
    first = [get_unique_variable_name() for _ in range(8)]
    # Without a reset, the sequence keeps advancing (and dedups against the
    # already-used set), so it differs.
    assert [get_unique_variable_name() for _ in range(8)] != first
    # After a reset it reproduces the original sequence exactly.
    reset_unique_variable_names()
    assert [get_unique_variable_name() for _ in range(8)] == first


def test_seeded_unique_variable_names_block_resumes_the_outer_sequence():
    """A seeded block draws by its seed alone and keeps its names reserved."""
    from reflex_base.vars.base import (
        USED_VARIABLES,
        get_unique_variable_name,
        reset_unique_variable_names,
        seed_unique_variable_names,
        seeded_unique_variable_names,
    )

    reset_unique_variable_names()
    outer_first = get_unique_variable_name()
    with seeded_unique_variable_names("state.one"):
        block_names = [get_unique_variable_name() for _ in range(3)]
    outer_next = get_unique_variable_name()
    # The block's names are a function of its seed, whatever ran before.
    seed_unique_variable_names("unrelated")
    get_unique_variable_name()
    with seeded_unique_variable_names("state.one"):
        assert [get_unique_variable_name() for _ in range(3)] == block_names
    # The outer sequence resumed where it stopped, with the block's names taken.
    reset_unique_variable_names()
    assert get_unique_variable_name() == outer_first
    with seeded_unique_variable_names("state.one"):
        assert set(block_names) & USED_VARIABLES == set()
        assert [get_unique_variable_name() for _ in range(3)] == block_names
    assert set(block_names) <= USED_VARIABLES
    assert get_unique_variable_name() == outer_next
    # Reserved names are never handed out again by a seeded sequence.
    seed_unique_variable_names("app", reserved=block_names)
    assert set(block_names) <= USED_VARIABLES
    assert get_unique_variable_name() not in block_names


def test_seeded_unique_variable_names_are_per_page():
    """Each page seed yields its own reproducible sequence, resumable later.

    Incremental compiles regenerate a subset of pages; a page's names must not
    depend on which other pages compiled before it (or the reused pages would
    share "unique" names with the recompiled one).
    """
    from reflex_base.vars.base import (
        get_unique_variable_name,
        restore_unique_variable_name_state,
        seed_unique_variable_names,
        unique_variable_name_state,
    )

    seed_unique_variable_names("/a")
    a_names = [get_unique_variable_name() for _ in range(4)]
    a_state = unique_variable_name_state()
    seed_unique_variable_names("/b")
    b_names = [get_unique_variable_name() for _ in range(4)]
    assert a_names != b_names
    # Re-seeding a page reproduces its sequence regardless of what ran between.
    seed_unique_variable_names("/a")
    assert [get_unique_variable_name() for _ in range(4)] == a_names
    a_continued = [get_unique_variable_name() for _ in range(2)]
    # Restoring a captured state resumes the sequence from that point without
    # repeating names already handed out.
    restore_unique_variable_name_state(a_state)
    resumed = [get_unique_variable_name() for _ in range(2)]
    assert resumed == a_continued
    assert not set(resumed) & set(a_names)
