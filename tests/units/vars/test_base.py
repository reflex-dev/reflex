import datetime
import uuid
from collections.abc import Mapping, Sequence

import pytest
from pytest_mock import MockerFixture
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


@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize(
    ("wall_clock_delta", "monotonic_delta", "expected_value"),
    [
        (datetime.timedelta(hours=-1), 11, 2),
        (datetime.timedelta(hours=1), 1, 1),
    ],
)
@pytest.mark.asyncio
async def test_computed_var_interval_uses_monotonic_time(
    mocker: MockerFixture,
    is_async: bool,
    wall_clock_delta: datetime.timedelta,
    monotonic_delta: int,
    expected_value: int,
) -> None:
    """Test interval expiry is unaffected by wall-clock changes.

    Args:
        mocker: Pytest mock fixture.
        is_async: Whether to access the asynchronous computed var.
        wall_clock_delta: The wall-clock change after the initial access.
        monotonic_delta: The elapsed monotonic time after the initial access.
        expected_value: The expected computed value after the clocks advance.
    """
    call_count = 0

    class StateTest(State):
        @computed_var(cache=True, interval=10)
        def cv(self) -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        @computed_var(cache=True, interval=10)
        async def async_cv(self) -> int:
            nonlocal call_count
            call_count += 1
            return call_count

    monotonic_time = 100
    mocker.patch(
        "reflex_base.vars.base.time.monotonic", side_effect=lambda: monotonic_time
    )
    initial_wall_time = datetime.datetime(2026, 1, 1)
    datetime_mock = mocker.patch("reflex_base.vars.base.datetime.datetime")
    datetime_mock.now.return_value = initial_wall_time

    state = StateTest()
    if is_async:
        assert await state.async_cv == 1
    else:
        assert state.cv == 1

    monotonic_time += monotonic_delta
    datetime_mock.now.return_value = initial_wall_time + wall_clock_delta

    if is_async:
        assert await state.async_cv == expected_value
    else:
        assert state.cv == expected_value
    assert call_count == expected_value


def test_computed_var_interval_persists_legacy_datetime() -> None:
    """Test the persisted last-updated attribute remains a datetime.

    Older workers compute ``datetime.datetime.now() - last_updated`` directly
    on the deserialized attribute, so the value stored under the legacy
    attribute must stay a plain datetime for rolling deployments.
    """

    class StateTest(State):
        @computed_var(cache=True, interval=10)
        def cv(self) -> int:
            return 1

    state = StateTest()
    assert state.cv == 1

    computed = StateTest.computed_vars["cv"]
    last_updated = getattr(state, computed._last_updated_attr)
    assert isinstance(last_updated, datetime.datetime)
    assert datetime.datetime.now() - last_updated < datetime.timedelta(seconds=10)


@pytest.mark.parametrize(
    ("wall_clock_delta", "expected_value"),
    [
        (datetime.timedelta(seconds=1), 1),
        (datetime.timedelta(hours=1), 2),
    ],
)
def test_computed_var_interval_wall_clock_fallback(
    wall_clock_delta: datetime.timedelta,
    expected_value: int,
) -> None:
    """Test state from another process falls back to wall-clock expiry.

    Args:
        wall_clock_delta: The wall-clock time elapsed since the last update.
        expected_value: The expected computed value after the fallback check.
    """
    call_count = 0

    class StateTest(State):
        @computed_var(cache=True, interval=10)
        def cv(self) -> int:
            nonlocal call_count
            call_count += 1
            return call_count

    state = StateTest()
    assert state.cv == 1

    computed = StateTest.computed_vars["cv"]
    # Simulate deserialization in a different process: the monotonic reading
    # carries a foreign clock id, so only the wall-clock datetime is usable.
    setattr(state, computed._last_updated_monotonic_attr, (uuid.uuid4(), 100.0))
    setattr(
        state,
        computed._last_updated_attr,
        datetime.datetime.now() - wall_clock_delta,
    )

    assert state.cv == expected_value


def test_computed_var_interval_cached_across_instances(
    mocker: MockerFixture,
) -> None:
    """Test a fresh value stays cached when first read by another instance.

    Sequential requests landing on different workers (e.g. the REST/MCP event
    handler API behind a load balancer) see a foreign clock id; that must not
    force recomputation while the value is fresh by wall clock.
    """
    call_count = 0

    class StateTest(State):
        @computed_var(cache=True, interval=60)
        def cv(self) -> int:
            nonlocal call_count
            call_count += 1
            return call_count

    state = StateTest()
    assert state.cv == 1

    # Simulate the state being loaded by a different worker process, which
    # has its own module-level clock id.
    mocker.patch("reflex_base.vars.base._MONOTONIC_CLOCK_ID", uuid.uuid4())

    assert state.cv == 1
    assert call_count == 1


@pytest.mark.parametrize(
    "persisted_timestamp",
    [None, (object(), 100), "2026-01-01"],
)
def test_computed_var_interval_expires_incompatible_timestamp(
    persisted_timestamp: object,
) -> None:
    """Test an interval cache with an incompatible timestamp is expired.

    Args:
        persisted_timestamp: A timestamp from a legacy version or another clock.
    """
    call_count = 0

    class StateTest(State):
        @computed_var(cache=True, interval=10)
        def cv(self) -> int:
            nonlocal call_count
            call_count += 1
            return call_count

    state = StateTest()
    assert state.cv == 1

    computed = StateTest.computed_vars["cv"]
    delattr(state, computed._last_updated_monotonic_attr)
    setattr(state, computed._last_updated_attr, persisted_timestamp)

    assert state.cv == 2
