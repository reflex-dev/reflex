"""Tests specific to redis state manager."""

import asyncio
import contextlib
import enum
import os
import time
import uuid
from collections import Counter
from collections.abc import AsyncGenerator
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from reflex_base.utils.exceptions import EnvironmentVarValueError, LockExpiredError

from reflex.istate.manager.redis import (
    StateManagerRedis,
    _default_lock_expiration,
    _default_oplock_hold_time_ms,
)
from reflex.istate.manager.token import BaseStateToken
from reflex.state import BaseState
from tests.units.mock_redis import mock_redis, real_redis


class RedisTestState(BaseState):
    """A test state for redis state manager tests."""

    foo: str = "bar"
    count: int = 0


class SubState1(RedisTestState):
    """A test substate for redis state manager tests."""

    child_value: str = ""


class SubState2(RedisTestState):
    """A test substate for redis state manager tests."""


class TreeRoot(BaseState):
    """The root of a state tree with a value in each state."""

    root_value: int = 0


class TreeFirst(TreeRoot):
    """A substate of the tree root."""

    first_value: int = 0


class TreeSecond(TreeRoot):
    """Another substate of the tree root."""

    second_value: int = 0


class RedisAppObjectState(BaseState):
    """A root state holding an instance of an app-defined class."""

    _value: Any = None


@pytest.mark.asyncio
async def test_get_state_reads_tree_in_one_command():
    """Read persisted and missing states together, preserving their tree positions."""
    redis = mock_redis()
    manager = StateManagerRedis(redis=redis)
    token = BaseStateToken(ident="batched-read", cls=RedisTestState)
    persisted = RedisTestState()
    persisted.foo = "persisted"
    classes = sorted(
        manager._get_required_state_classes(RedisTestState, subclasses=True),
        key=lambda cls: cls.get_full_name(),
    )
    redis.mget = AsyncMock(
        return_value=[
            persisted._serialize() if cls is RedisTestState else None for cls in classes
        ]
    )

    state = await manager.get_state(token)

    assert isinstance(state, RedisTestState)
    assert state.foo == "persisted"
    assert state.count == 0
    assert set(state.substates) == {SubState1.get_name(), SubState2.get_name()}
    assert all(child.parent_state is state for child in state.substates.values())
    redis.mget.assert_awaited_once_with([str(token.with_cls(cls)) for cls in classes])
    await manager.close()


@pytest.mark.asyncio
async def test_get_state_reuses_populated_tree_without_reading():
    """Fetching an already attached state must not contact Redis or replace it."""
    redis = mock_redis()
    manager = StateManagerRedis(redis=redis)
    token = BaseStateToken(ident="populated-read", cls=SubState1)
    state = RedisTestState()
    redis.mget = AsyncMock(return_value=[])
    redis.pipeline = Mock(side_effect=AssertionError("Unexpected Redis read"))

    child = await manager.get_state(token, top_level=False, for_state_instance=state)

    assert child is state.substates[SubState1.get_name()]
    redis.mget.assert_not_awaited()
    await manager.close()


@pytest.fixture
def root_state() -> type[RedisTestState]:

    return RedisTestState


async def _subscribed(state_manager: StateManagerRedis) -> StateManagerRedis:
    """Wait until the manager's lock updates subscription is confirmed.

    Leases are only taken once it is, so tests that expect one must wait for it.

    Args:
        state_manager: The StateManagerRedis to wait for.

    Returns:
        The same StateManagerRedis.
    """
    await state_manager._ensure_lock_task_subscribed()
    return state_manager


@pytest_asyncio.fixture(loop_scope="function")
async def state_manager_redis(
    root_state: type[RedisTestState],
) -> AsyncGenerator[StateManagerRedis]:
    """Get a StateManagerRedis with a real or mocked redis client.

    Args:
        root_state: The root state class.

    Yields:
        The StateManagerRedis.
    """
    async with real_redis() as redis:
        if redis is None:
            redis = mock_redis()
        state_manager = StateManagerRedis(redis=redis)
        # Best effort: tests that need no lease must still run on a Redis that
        # rejects CONFIG, where the subscription never confirms.
        with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
            await state_manager._ensure_lock_task_subscribed()
        test_start = time.monotonic()
        yield state_manager
        # None of the tests should have triggered a lock expiration.
        assert (time.monotonic() - test_start) * 1000 < state_manager.lock_expiration

    await state_manager.close()


@pytest.fixture
def event_log(state_manager_redis: StateManagerRedis) -> list[dict[str, Any]]:
    """Get the redis event log from the state manager.

    Args:
        state_manager_redis: The StateManagerRedis.

    Returns:
        The redis event log.
    """
    return state_manager_redis.redis._internals["event_log"]  # pyright: ignore[reportAttributeAccessIssue]


@pytest.fixture
def event_log_on_update(state_manager_redis: StateManagerRedis) -> asyncio.Event:
    """Get the event for new event records being added to the redis event log.

    Test is responsible for calling `.clear` before an operation when it needs
    to detect a new event added afterward.

    Args:
        state_manager_redis: The StateManagerRedis.

    Returns:
        The event that is set when new events are added to the redis event log.
    """
    return state_manager_redis.redis._internals["event_log_on_update"]  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.asyncio
async def test_basic_get_set(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
):
    """Test basic operations of StateManagerRedis.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
    """
    state_manager_redis._oplock_enabled = False

    token = str(uuid.uuid4())

    fresh_state = await state_manager_redis.get_state(
        BaseStateToken(ident=token, cls=root_state)
    )
    fresh_state.foo = "baz"
    fresh_state.count = 42
    await state_manager_redis.set_state(
        BaseStateToken(ident=token, cls=root_state), fresh_state
    )


async def test_modify(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
):
    """Test modifying state with StateManagerRedis.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
    """
    state_manager_redis._oplock_enabled = False

    token = str(uuid.uuid4())

    # Initial modify should set count to 1
    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=root_state)
    ) as new_state:
        new_state.count = 1

    # Subsequent modify should set count to 2
    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=root_state)
    ) as new_state:
        assert isinstance(new_state, root_state)
        assert new_state.count == 1
        new_state.count += 2

    final_state = await state_manager_redis.get_state(
        BaseStateToken(ident=token, cls=root_state)
    )
    assert isinstance(final_state, root_state)
    assert final_state.count == 3


@pytest.mark.parametrize(
    "locking_path", ["disabled", "contended", "lease_ended", "cached"]
)
async def test_modify_cancelled_persists_state(
    state_manager_redis: StateManagerRedis,
    monkeypatch: pytest.MonkeyPatch,
    locking_path: str,
):
    """Keep mutations and cancellation cleanup visible to the next handler.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        monkeypatch: The pytest monkeypatch fixture.
        locking_path: The Redis locking path to exercise.
    """
    manager = state_manager_redis
    manager._oplock_enabled = locking_path != "disabled"
    if locking_path == "contended":
        monkeypatch.setattr(manager, "_n_lock_contenders", AsyncMock(return_value=1))
    elif locking_path == "lease_ended":
        monkeypatch.setattr(
            manager, "_create_lease_break_task", AsyncMock(return_value=None)
        )
    elif locking_path == "cached":
        await _subscribed(manager)

    token = BaseStateToken(ident=str(uuid.uuid4()), cls=RedisTestState)
    started = asyncio.Event()

    async def modify():
        """Mutate state before cancellation and again during handler cleanup."""
        async with manager.modify_state(token) as state:
            state.count = 1
            state.substates[SubState1.get_name()].child_value = "child update"
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                state.foo = "cancelled"

    task = asyncio.create_task(modify())
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel("superseded")
        with pytest.raises(asyncio.CancelledError, match="superseded"):
            await task
        assert task.cancelled()

        async with manager.modify_state(token) as state:
            assert isinstance(state, RedisTestState)
            assert state.count == 1
            assert state.foo == "cancelled"
            child = state.substates[SubState1.get_name()]
            assert isinstance(child, SubState1)
            assert child.child_value == "child update"
            state.count += 1

        # Closing flushes a cached lease; a fresh read must see persisted state.
        await manager.close()
        persisted = await manager.get_state(token)
        assert isinstance(persisted, RedisTestState)
        assert persisted.count == 2
        assert persisted.foo == "cancelled"
        persisted_child = persisted.substates[SubState1.get_name()]
        assert isinstance(persisted_child, SubState1)
        assert persisted_child.child_value == "child update"
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def test_repeated_cancellation_waits_for_state_save(
    state_manager_redis: StateManagerRedis,
    monkeypatch: pytest.MonkeyPatch,
):
    """Keep the Redis lock until a repeatedly cancelled handler finishes saving.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        monkeypatch: The pytest monkeypatch fixture.
    """
    manager = state_manager_redis
    manager._oplock_enabled = False
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=RedisTestState)
    started = asyncio.Event()
    saving = asyncio.Event()
    release_save = asyncio.Event()
    original_set_state = manager.set_state

    async def save(*args, **kwargs):
        """Pause the state write while the handler is cancelled again."""
        saving.set()
        await release_save.wait()
        await original_set_state(*args, **kwargs)

    monkeypatch.setattr(manager, "set_state", save)

    async def modify():
        """Mutate state and suspend until superseded."""
        async with manager.modify_state(token) as state:
            state.count = 1
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(modify())
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel("superseded")
        await asyncio.wait_for(saving.wait(), timeout=5)
        for _ in range(2):
            task.cancel("shutdown")
            await asyncio.sleep(0)
        assert not task.done()
        assert await manager.redis.get(manager._lock_key(token)) is not None
        release_save.set()
        with pytest.raises(asyncio.CancelledError, match="superseded"):
            await task
        persisted = await manager.get_state(token)
        assert isinstance(persisted, RedisTestState)
        assert persisted.count == 1
        assert await manager.redis.get(manager._lock_key(token)) is None
    finally:
        release_save.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def test_modify_exception_does_not_persist_state(
    state_manager_redis: StateManagerRedis,
):
    """Keep the existing write-discarding behavior for non-cancellation errors.

    Args:
        state_manager_redis: The StateManagerRedis to test.
    """
    manager = state_manager_redis
    manager._oplock_enabled = False
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=RedisTestState)
    with pytest.raises(RuntimeError, match="handler failed"):
        async with manager.modify_state(token) as state:
            state.count = 1
            msg = "handler failed"
            raise RuntimeError(msg)
    persisted = await manager.get_state(token)
    assert isinstance(persisted, RedisTestState)
    assert persisted.count == 0


async def test_modify_cancelled_does_not_save_after_lock_expiry(
    state_manager_redis: StateManagerRedis,
):
    """Cancellation must not bypass the lock fence when saving state.

    Args:
        state_manager_redis: The StateManagerRedis to test.
    """
    manager = state_manager_redis
    manager._oplock_enabled = False
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=RedisTestState)
    async with manager.modify_state(token) as state:
        state.count = 1

    with pytest.raises(LockExpiredError):
        async with manager.modify_state(token) as state:
            state.count = 2
            await manager.redis.delete(manager._lock_key(token))
            raise asyncio.CancelledError
    persisted = await manager.get_state(token)
    assert isinstance(persisted, RedisTestState)
    assert persisted.count == 1


async def test_get_state_discards_unpicklable_state(
    state_manager_redis: StateManagerRedis,
    app_classes_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    """A stored state that can no longer be unpickled is replaced.

    After a deploy changes a class held in a state var, unpickling the stored
    state fails before the schema check. The tab must get a fresh state instead
    of failing on every event until the redis key expires.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        app_classes_module: The module of app classes held in the state.
        monkeypatch: The pytest monkeypatch fixture.
    """
    state_manager_redis._oplock_enabled = False
    module = app_classes_module

    token = BaseStateToken(ident=str(uuid.uuid4()), cls=RedisAppObjectState)
    async with state_manager_redis.modify_state(token) as state:
        state._value = module.Color.BLUE

    # The deploy: the stored enum member no longer exists.
    monkeypatch.setattr(
        module, "Color", enum.Enum("Color", {"RED": "red"}, module=module.__name__)
    )

    fresh_state = await state_manager_redis.get_state(token)
    assert isinstance(fresh_state, RedisAppObjectState)
    assert fresh_state._value is None


async def test_modify_oplock(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    event_log: list[dict[str, Any]],
    event_log_on_update: asyncio.Event,
):
    """Test modifying state with StateManagerRedis with optimistic locking.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
        event_log_on_update: The event for new event records being added to the redis event log.
    """
    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True

    state_manager_2 = await _subscribed(
        StateManagerRedis(redis=state_manager_redis.redis)
    )

    state_manager_2._debug_enabled = True
    state_manager_2._oplock_enabled = True

    event_log_on_update.clear()

    # Initial modify should set count to 1
    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=root_state),
    ) as new_state:
        new_state.count = 1

    # Initial state manager should be holding a lease
    lease_task_1 = state_manager_redis._local_leases.get(token)
    assert lease_task_1 is not None
    assert not lease_task_1.done()

    # The state should not be locked
    state_lock_1 = state_manager_redis._cached_states_locks.get(token)
    assert state_lock_1 is not None
    assert not state_lock_1.locked()

    await event_log_on_update.wait()
    lock_events_before = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])
    assert lock_events_before == 1

    # The second modify should NOT trigger another redis lock
    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=root_state),
    ) as new_state:
        new_state.count = 2
        assert state_lock_1.locked()

    lock_events_after = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])

    assert lock_events_before == lock_events_after

    # Contend the lock from another state manager
    event_log_on_update.clear()
    async with state_manager_2.modify_state(
        BaseStateToken(ident=token, cls=root_state),
    ) as new_state:
        new_state.count = 3
        state_lock_2 = state_manager_2._cached_states_locks.get(token)
        assert state_lock_2 is not None
        assert state_lock_2.locked()

    # The second manager should be holding the lease now
    lease_task_2 = state_manager_2._local_leases.get(token)
    assert lease_task_2 is not None
    assert not lease_task_2.done()
    assert not state_lock_2.locked()

    # Lease task 1 should be cancelled by the time we have modified the state
    assert lease_task_1.done()
    assert lease_task_1.cancelled()
    assert token not in state_manager_redis._local_leases
    assert token not in state_manager_redis._cached_states

    # There should have been another redis lock taken.
    await event_log_on_update.wait()
    lock_events_after_2 = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])
    assert lock_events_after_2 == lock_events_after + 1

    # And there should have been a lock release.
    unlock_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"del"
    ])
    assert unlock_events == 1

    # And a single token set.
    token_set_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(root_state.get_full_name().encode())
        and ev["data"] == b"set"
    ])
    assert token_set_events == 1

    # Now close the contender to release its lease.
    event_log_on_update.clear()
    await state_manager_2.close()
    await event_log_on_update.wait()

    # Both locks should have been released.
    unlock_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"del"
    ])
    assert unlock_events == 2

    # And both tokens should have been set.
    token_set_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(root_state.get_full_name().encode())
        and ev["data"] == b"set"
    ])
    assert token_set_events == 2


async def test_oplock_contention_queue(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    event_log: list[dict[str, Any]],
):
    """Test the oplock contention queue.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
    """
    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True

    state_manager_2 = await _subscribed(
        StateManagerRedis(redis=state_manager_redis.redis)
    )

    state_manager_2._debug_enabled = True
    state_manager_2._oplock_enabled = True

    modify_started = asyncio.Event()
    modify_2_started = asyncio.Event()
    modify_1_continue = asyncio.Event()
    modify_2_continue = asyncio.Event()

    async def modify_1():
        async with state_manager_redis.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            assert isinstance(new_state, root_state)
            new_state.count += 1
            modify_started.set()
            await modify_1_continue.wait()

    async def modify_2():
        await modify_started.wait()
        modify_2_started.set()
        async with state_manager_2.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            assert isinstance(new_state, root_state)
            new_state.count += 1
            await modify_2_continue.wait()

    async def modify_3():
        await modify_started.wait()
        modify_2_started.set()
        async with state_manager_2.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            assert isinstance(new_state, root_state)
            new_state.count += 1
            await modify_2_continue.wait()

    task_1 = asyncio.create_task(modify_1())
    task_2 = asyncio.create_task(modify_2())
    task_3 = asyncio.create_task(modify_3())

    await modify_2_started.wait()

    # Let modify 1 complete
    modify_1_continue.set()

    # Let modify 2 complete
    modify_2_continue.set()

    await task_1
    await task_2
    await task_3

    interim_state = await state_manager_redis.get_state(
        BaseStateToken(ident=token, cls=root_state)
    )
    assert isinstance(interim_state, root_state)
    assert interim_state.count == 1

    await state_manager_2.close()

    final_state = await state_manager_redis.get_state(
        BaseStateToken(ident=token, cls=root_state)
    )
    assert isinstance(final_state, root_state)
    assert final_state.count == 3

    # There should only be two lock acquisitions
    lock_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])
    assert lock_events == 2


async def test_oplock_contention_no_lease(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    event_log: list[dict[str, Any]],
):
    """Test the oplock contention queue, when no waiters can share.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
    """
    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True

    state_manager_2 = await _subscribed(
        StateManagerRedis(redis=state_manager_redis.redis)
    )

    state_manager_2._debug_enabled = True
    state_manager_2._oplock_enabled = True

    state_manager_3 = await _subscribed(
        StateManagerRedis(redis=state_manager_redis.redis)
    )
    state_manager_3._debug_enabled = True
    state_manager_3._oplock_enabled = True

    modify_started = asyncio.Event()
    modify_2_started = asyncio.Event()
    modify_1_continue = asyncio.Event()
    modify_2_continue = asyncio.Event()

    async def modify_1():
        async with state_manager_redis.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            assert isinstance(new_state, root_state)
            new_state.count += 1
            modify_started.set()
            await modify_1_continue.wait()

    async def modify_2():
        await modify_started.wait()
        modify_2_started.set()
        async with state_manager_2.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            assert isinstance(new_state, root_state)
            new_state.count += 1
            await modify_2_continue.wait()

    async def modify_3():
        await modify_started.wait()
        modify_2_started.set()
        async with state_manager_3.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            assert isinstance(new_state, root_state)
            new_state.count += 1
            await modify_2_continue.wait()

    task_1 = asyncio.create_task(modify_1())
    task_2 = asyncio.create_task(modify_2())
    task_3 = asyncio.create_task(modify_3())

    await modify_2_started.wait()

    # Let modify 1 complete
    modify_1_continue.set()

    # Let modify 2 complete
    modify_2_continue.set()

    await task_1
    await task_2
    await task_3

    # First task should have always gotten a lease
    assert token in state_manager_redis._cached_states_locks

    # The 2nd or 3rd modify should have _never_ got a lease due to contention
    if token not in state_manager_2._cached_states_locks:
        assert await state_manager_3._get_local_lease(token) is not None
    elif token not in state_manager_3._cached_states_locks:
        assert await state_manager_2._get_local_lease(token) is not None
    else:
        pytest.fail("One of the contending state managers should not have a lease.")

    await state_manager_2.close()
    await state_manager_3.close()

    final_state = await state_manager_2.get_state(
        BaseStateToken(ident=token, cls=root_state)
    )
    assert isinstance(final_state, root_state)
    assert final_state.count == 3

    # There should be three lock acquisitions
    lock_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])
    assert lock_events == 3


@pytest.mark.parametrize("racer_delay", [None, 0, 0.1])
@pytest.mark.asyncio
async def test_oplock_contention_racers(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    racer_delay: float | None,
):
    """Test the oplock contention queue with racers.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        racer_delay: The delay before the second racer starts.
    """
    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True

    state_manager_2 = await _subscribed(
        StateManagerRedis(redis=state_manager_redis.redis)
    )
    state_manager_2._debug_enabled = True
    state_manager_2._oplock_enabled = True
    lease_1 = None
    lease_2 = None

    async def modify_1():
        nonlocal lease_1
        async with state_manager_redis.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            lease_1 = await state_manager_redis._get_local_lease(token)
            assert isinstance(new_state, root_state)
            new_state.count += 1

    async def modify_2():
        if racer_delay is not None:
            await asyncio.sleep(racer_delay)
        nonlocal lease_2
        async with state_manager_2.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            lease_2 = await state_manager_2._get_local_lease(token)
            assert isinstance(new_state, root_state)
            new_state.count += 1

    await asyncio.gather(
        modify_1(),
        modify_2(),
    )

    if lease_1 is not None and lease_2 is not None:
        # A broken lease is only cancelled() once its final flush completes.
        await asyncio.wait({lease_1, lease_2}, return_when=asyncio.FIRST_COMPLETED)

    if lease_1 is None or lease_1.cancelled():
        assert lease_2 is not None
        assert not lease_2.cancelled()
    elif lease_2 is None or lease_2.cancelled():
        assert lease_1 is not None
        assert not lease_1.cancelled()
    else:
        pytest.fail(
            "One lease should have been cancelled, other should still be active."
        )


@pytest.mark.asyncio
async def test_oplock_lease_waits_for_lock_updates_subscriber(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that no lease is taken until redis confirms the lock updates subscription.

    A lease taken before the subscriber listens could miss the contention
    notification that breaks it, stalling other instances for the full hold time.
    Events before the confirmation must not wait for it either, since a
    subscriber that never confirms would then stall every event.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        monkeypatch: The pytest monkeypatch fixture.
    """
    state_token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    state_manager_redis._oplock_enabled = True
    redis = state_manager_redis.redis
    pubsub = redis.pubsub
    confirm = asyncio.Event()

    @contextlib.asynccontextmanager
    async def delayed_confirmation_pubsub():
        async with pubsub() as ps:
            listen = ps.listen

            async def delayed_listen():
                await confirm.wait()
                async for message in listen():
                    yield message

            ps.listen = delayed_listen
            yield ps

    # Restart the subscriber with its subscription confirmation held back.
    if (lock_task := state_manager_redis._lock_task) is not None:
        lock_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await lock_task
    monkeypatch.setattr(redis, "pubsub", delayed_confirmation_pubsub)

    async def modify() -> int:
        async with state_manager_redis.modify_state(state_token) as new_state:
            assert isinstance(new_state, root_state)
            new_state.count += 1
            return new_state.count

    # Before the confirmation, an event updates without a lease instead of
    # waiting out the subscribe timeout (2s).
    assert await asyncio.wait_for(modify(), timeout=1) == 1
    assert not state_manager_redis._lock_updates_subscribed.is_set()
    assert await state_manager_redis._get_local_lease(state_token.lock_key) is None
    assert await redis.get(state_manager_redis._lock_key(state_token)) is None

    confirm.set()
    await state_manager_redis._ensure_lock_task_subscribed()
    assert await modify() == 2
    assert await state_manager_redis._get_local_lease(state_token.lock_key) is not None


@pytest.mark.asyncio
async def test_oplock_immediate_cancel(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    event_log: list[dict[str, Any]],
):
    """Test that immediate cancellation of modify releases oplock.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
    """
    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True
    # The canceller below spins until a lease exists, so fail fast if the
    # subscription a lease requires is unavailable.
    await _subscribed(state_manager_redis)

    async def canceller():
        while (lease_task := state_manager_redis._local_leases.get(token)) is None:  # noqa: ASYNC110
            await asyncio.sleep(0)
        lease_task.cancel()

    task = asyncio.create_task(canceller())

    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=root_state),
    ) as new_state:
        assert await state_manager_redis._get_local_lease(token) is None
        assert isinstance(new_state, root_state)
        new_state.count += 1

    await task


@pytest.mark.asyncio
async def test_oplock_fetch_substate(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    event_log: list[dict[str, Any]],
):
    """Test fetching substate with oplock enabled and partial state is cached.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
    """
    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True

    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=SubState1),
    ) as new_state:
        assert SubState1.get_name() in new_state.substates
        assert SubState2.get_name() not in new_state.substates

    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=SubState2),
    ) as new_state:
        # Both substates should be fetched and cached.
        assert SubState1.get_name() in new_state.substates
        assert SubState2.get_name() in new_state.substates

    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=SubState1),
    ) as new_state:
        # Both substates should be fetched and cached now.
        assert SubState1.get_name() in new_state.substates
        assert SubState2.get_name() in new_state.substates

    # Should have still only been one lock acquisition.
    lock_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])
    assert lock_events == 1


@pytest.fixture
def short_lock_expiration(
    state_manager_redis: StateManagerRedis,
):
    """Get a StateManagerRedis with a short lock expiration for testing.

    Args:
        state_manager_redis: The base StateManagerRedis.

    Yields:
        The lock expiration time in milliseconds.
    """
    lock_expiration = 4000 if os.environ.get("CI") else 300
    original_expiration = state_manager_redis.lock_expiration
    state_manager_redis.lock_expiration = lock_expiration
    yield lock_expiration
    state_manager_redis.lock_expiration = original_expiration


@pytest.mark.asyncio
async def test_oplock_hold_oplock_after_cancel(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    event_log: list[dict[str, Any]],
    event_log_on_update: asyncio.Event,
    short_lock_expiration: int,
):
    """Test that cancelling a modify does not release the oplock prematurely.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
        event_log_on_update: The event log update event.
        short_lock_expiration: The lock expiration time in milliseconds.
    """
    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True

    modify_started = asyncio.Event()
    modify_continue = asyncio.Event()
    modify_ended = asyncio.Event()

    async def modify():
        async with state_manager_redis.modify_state(
            BaseStateToken(ident=token, cls=root_state),
        ) as new_state:
            modify_started.set()
            assert isinstance(new_state, root_state)
            new_state.count += 1
            await modify_continue.wait()
            modify_ended.set()

    task = asyncio.create_task(modify())

    await modify_started.wait()
    started = time.monotonic()
    await asyncio.sleep(short_lock_expiration / 1000 * 0.5)
    state_lock = state_manager_redis._cached_states_locks.get(token)
    assert state_lock is not None
    assert state_lock.locked()
    lease_task = await state_manager_redis._get_local_lease(token)
    assert lease_task is not None
    assert not lease_task.done()
    lease_task.cancel()
    # post-cancel wait should get another full lock_expiration.
    await asyncio.sleep(short_lock_expiration / 1000 * 0.8)
    assert not lease_task.done()
    modify_continue.set()
    await modify_ended.wait()
    ended = time.monotonic()

    # We should have successfully held the lock for longer than the lock expiration
    assert (ended - started) * 1000 > short_lock_expiration

    await task
    with pytest.raises(asyncio.CancelledError):
        await lease_task

    # Modify the state again, this should get a new lock and lease
    event_log_on_update.clear()
    async with state_manager_redis.modify_state(
        BaseStateToken(ident=token, cls=root_state),
    ) as new_state:
        assert isinstance(new_state, root_state)
        new_state.count += 1

    # There should have been two redis lock acquisitions.
    await event_log_on_update.wait()
    lock_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])
    assert lock_events == 2

    await state_manager_redis.close()

    # Both increments should be present.
    final_state = await state_manager_redis.get_state(
        BaseStateToken(ident=token, cls=root_state)
    )
    assert isinstance(final_state, root_state)
    assert final_state.count == 2


async def test_set_state_saves_tree_in_one_round_trip(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
):
    """Saving a state tree checks the lock and writes every touched state in one command.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
    """
    state_manager_redis._oplock_enabled = False
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    redis = state_manager_redis.redis
    real_eval = redis.eval
    evals: list[tuple[Any, ...]] = []

    def counting_eval(script, numkeys, *keys_and_args):
        evals.append(keys_and_args)
        return real_eval(script, numkeys, *keys_and_args)

    async with state_manager_redis.modify_state(token) as state:
        assert len(state.substates) == 2
        state.count = 1
        redis.eval = counting_eval  # pyright: ignore[reportAttributeAccessIssue]
        try:
            await state_manager_redis.set_state(
                token,
                state,
                lock_id=await redis.get(state_manager_redis._lock_key(token)),
            )
        finally:
            redis.eval = real_eval  # pyright: ignore[reportAttributeAccessIssue]

    # One command for a tree of three states, all of them touched by the load.
    assert len(evals) == 1
    assert str(token) in evals[0]
    saved = await state_manager_redis.get_state(token)
    assert isinstance(saved, root_state)
    assert saved.count == 1


async def test_set_state_discards_writes_when_lock_changes_hands(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
):
    """A save whose lock expired or was re-acquired before the write is discarded.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
    """
    from reflex_base.utils.exceptions import LockExpiredError

    state_manager_redis._oplock_enabled = False
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    lock_key = state_manager_redis._lock_key(token)

    with pytest.raises(LockExpiredError):
        async with state_manager_redis.modify_state(token) as state:
            state.count = 5
            # Another worker takes over the lock before this save lands.
            await state_manager_redis.redis.set(lock_key, b"someone-else")
    saved = await state_manager_redis.get_state(token)
    assert isinstance(saved, root_state)
    assert saved.count == 0


def test_oplock_hold_time_below_one_millisecond(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sub-millisecond hold time must not read as the unset default.

    Zero means "use half the lock expiration", so a duration that floors to
    zero milliseconds has to round up instead of falling into that branch.
    """
    monkeypatch.setenv("REFLEX_OPLOCK_HOLD_TIME", "500us")
    assert _default_oplock_hold_time_ms() == 1


def test_oplock_hold_time_unset_halves_the_lock_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unset hold time keeps deriving from the lock expiration."""
    monkeypatch.delenv("REFLEX_OPLOCK_HOLD_TIME", raising=False)
    monkeypatch.delenv("REFLEX_OPLOCK_HOLD_TIME_MS", raising=False)
    assert _default_oplock_hold_time_ms() == _default_lock_expiration() // 2


def test_oplock_hold_time_rejects_a_negative_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A negative hold time is a configuration error, not one millisecond."""
    monkeypatch.setenv("REFLEX_OPLOCK_HOLD_TIME", "-5s")
    with pytest.raises(EnvironmentVarValueError, match="must not be negative"):
        _default_oplock_hold_time_ms()


def _count_redis_calls(redis: Any, *names: str) -> Counter[str]:
    """Count the calls to some methods of a redis client.

    Args:
        redis: The redis client to instrument.
        *names: The names of the methods to count.

    Returns:
        The counter of calls per method name, updated as the client is used.
    """
    calls: Counter[str] = Counter()
    for name in names:
        method = getattr(redis, name)

        def counted(
            *args: Any, _name: str = name, _method: Any = method, **kwargs: Any
        ):
            calls[_name] += 1
            return _method(*args, **kwargs)

        setattr(redis, name, counted)
    return calls


async def _stored_tree_states(
    state_manager_redis: StateManagerRedis, token: BaseStateToken
) -> set[type[BaseState]]:
    """Get the states of a TreeRoot tree that have a payload stored in redis.

    Args:
        state_manager_redis: The StateManagerRedis to read from.
        token: The token of the tree.

    Returns:
        The classes of the stored states.
    """
    return {
        state_cls
        for state_cls in (TreeRoot, TreeFirst, TreeSecond)
        if await state_manager_redis.redis.get(token._state_key(state_cls)) is not None
    }


async def test_set_state_persists_the_touched_states_in_one_round_trip(
    state_manager_redis: StateManagerRedis,
):
    """Every touched state of a tree is written in a single pipeline.

    Args:
        state_manager_redis: The StateManagerRedis to test.
    """
    state_manager_redis._oplock_enabled = False
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=TreeRoot)
    state = await state_manager_redis.get_state(token)
    assert isinstance(state, TreeRoot)
    state.root_value = 4
    first = state.substates[TreeFirst.get_name()]
    assert isinstance(first, TreeFirst)
    first.first_value = 5

    calls = _count_redis_calls(state_manager_redis.redis, "pipeline")
    await state_manager_redis.set_state(token, state)

    assert calls == {"pipeline": 1}
    # The untouched TreeSecond is not written.
    assert await _stored_tree_states(state_manager_redis, token) == {
        TreeRoot,
        TreeFirst,
    }
    persisted = await state_manager_redis.get_state(token)
    assert isinstance(persisted, TreeRoot)
    assert persisted.root_value == 4
    persisted_first = persisted.substates[TreeFirst.get_name()]
    persisted_second = persisted.substates[TreeSecond.get_name()]
    assert isinstance(persisted_first, TreeFirst)
    assert isinstance(persisted_second, TreeSecond)
    assert persisted_first.first_value == 5
    assert persisted_second.second_value == 0


async def test_set_state_writes_nothing_when_no_state_was_touched(
    state_manager_redis: StateManagerRedis,
):
    """A tree without touched states costs no write at all.

    Args:
        state_manager_redis: The StateManagerRedis to test.
    """
    state_manager_redis._oplock_enabled = False
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=TreeRoot)
    state = await state_manager_redis.get_state(token)

    calls = _count_redis_calls(state_manager_redis.redis, "pipeline", "set")
    await state_manager_redis.set_state(token, state)

    assert not calls
    assert not await _stored_tree_states(state_manager_redis, token)


async def test_set_state_writes_the_touched_states_in_one_fenced_save(
    state_manager_redis: StateManagerRedis,
    monkeypatch: pytest.MonkeyPatch,
):
    """With the lock held, only the touched states are written, by one lock-checked command.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        monkeypatch: The pytest monkeypatch fixture.
    """
    state_manager_redis._oplock_enabled = False
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=TreeRoot)
    redis = state_manager_redis.redis
    lock_key = state_manager_redis._lock_key(token)
    state = await state_manager_redis.get_state(token)
    first = state.substates[TreeFirst.get_name()]
    assert isinstance(first, TreeFirst)
    first.first_value = 5

    lock_id = b"test-lock-id"
    await redis.set(lock_key, lock_id, px=state_manager_redis.lock_expiration)
    real_eval = redis.eval
    saved_keys: list[tuple[Any, ...]] = []

    def recording_eval(script: str, numkeys: int, *keys_and_args: Any) -> Any:
        saved_keys.append(keys_and_args[:numkeys])
        return real_eval(script, numkeys, *keys_and_args)

    monkeypatch.setattr(redis, "eval", recording_eval)
    calls = _count_redis_calls(redis, "pipeline")
    await state_manager_redis.set_state(token, state, lock_id=lock_id)

    assert not calls
    assert saved_keys == [(lock_key, token._state_key(TreeFirst))]
    assert await _stored_tree_states(state_manager_redis, token) == {TreeFirst}
    await redis.delete(lock_key)


async def test_mock_redis_eval_only_emulates_the_fenced_save_script():
    """The mock refuses any script it does not emulate, instead of mis-running it."""
    # redis-py types eval as possibly synchronous; the mock is always async.
    eval_script: Any = mock_redis().eval
    with pytest.raises(NotImplementedError):
        await eval_script("return 1", 0)
