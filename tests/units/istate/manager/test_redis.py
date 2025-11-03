"""Tests specific to redis state manager."""

import asyncio
import os
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio

from reflex.istate.manager.redis import StateManagerRedis
from reflex.state import BaseState, _substate_key
from tests.units.mock_redis import mock_redis, real_redis


@pytest.fixture
def root_state() -> type[BaseState]:
    class RedisTestState(BaseState):
        foo: str = "bar"
        count: int = 0

    return RedisTestState


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def state_manager_redis(
    root_state: type[BaseState],
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
        state_manager = StateManagerRedis(state=root_state, redis=redis)
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


@pytest.mark.asyncio
async def test_basic_get_set(
    state_manager_redis: StateManagerRedis,
    root_state: type[BaseState],
):
    """Test basic operations of StateManagerRedis.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
    """
    state_manager_redis._oplock_enabled = False

    token = str(uuid.uuid4())

    fresh_state = await state_manager_redis.get_state(_substate_key(token, root_state))
    fresh_state.foo = "baz"
    fresh_state.count = 42
    await state_manager_redis.set_state(_substate_key(token, root_state), fresh_state)


async def test_modify(
    state_manager_redis: StateManagerRedis,
    root_state: type[BaseState],
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
        _substate_key(token, root_state)
    ) as new_state:
        new_state.count = 1

    # Subsequent modify should set count to 2
    async with state_manager_redis.modify_state(
        _substate_key(token, root_state)
    ) as new_state:
        assert new_state.count == 1
        new_state.count += 2

    final_state = await state_manager_redis.get_state(_substate_key(token, root_state))
    assert final_state.count == 3


async def test_modify_oplock(
    state_manager_redis: StateManagerRedis,
    root_state: type[BaseState],
    event_log: list[dict[str, Any]],
):
    """Test modifying state with StateManagerRedis with optimistic locking.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
    """
    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True

    state_manager_2 = StateManagerRedis(
        state=root_state, redis=state_manager_redis.redis
    )

    state_manager_2._debug_enabled = True
    state_manager_2._oplock_enabled = True

    # Initial modify should set count to 1
    async with state_manager_redis.modify_state(
        _substate_key(token, root_state),
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

    lock_events_before = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])
    assert lock_events_before == 1

    # The second modify should NOT trigger another redis lock
    async with state_manager_redis.modify_state(
        _substate_key(token, root_state),
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
    async with state_manager_2.modify_state(
        _substate_key(token, root_state),
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
    await state_manager_2.close()

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
    root_state: type[BaseState],
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

    state_manager_2 = StateManagerRedis(
        state=root_state, redis=state_manager_redis.redis
    )

    state_manager_2._debug_enabled = True
    state_manager_2._oplock_enabled = True

    modify_started = asyncio.Event()
    modify_2_started = asyncio.Event()
    modify_1_continue = asyncio.Event()
    modify_2_continue = asyncio.Event()

    async def modify_1():
        async with state_manager_redis.modify_state(
            _substate_key(token, root_state),
        ) as new_state:
            new_state.count += 1
            modify_started.set()
            await modify_1_continue.wait()

    async def modify_2():
        await modify_started.wait()
        modify_2_started.set()
        async with state_manager_2.modify_state(
            _substate_key(token, root_state),
        ) as new_state:
            new_state.count += 1
            await modify_2_continue.wait()

    async def modify_3():
        await modify_started.wait()
        modify_2_started.set()
        async with state_manager_2.modify_state(
            _substate_key(token, root_state),
        ) as new_state:
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
        _substate_key(token, root_state)
    )
    assert interim_state.count == 1

    await state_manager_2.close()

    final_state = await state_manager_redis.get_state(_substate_key(token, root_state))
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
    root_state: type[BaseState],
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

    state_manager_2 = StateManagerRedis(
        state=root_state, redis=state_manager_redis.redis
    )

    state_manager_2._debug_enabled = True
    state_manager_2._oplock_enabled = True

    state_manager_3 = StateManagerRedis(
        state=root_state, redis=state_manager_redis.redis
    )
    state_manager_3._debug_enabled = True
    state_manager_3._oplock_enabled = True

    modify_started = asyncio.Event()
    modify_2_started = asyncio.Event()
    modify_1_continue = asyncio.Event()
    modify_2_continue = asyncio.Event()

    async def modify_1():
        async with state_manager_redis.modify_state(
            _substate_key(token, root_state),
        ) as new_state:
            new_state.count += 1
            modify_started.set()
            await modify_1_continue.wait()

    async def modify_2():
        await modify_started.wait()
        modify_2_started.set()
        async with state_manager_2.modify_state(
            _substate_key(token, root_state),
        ) as new_state:
            new_state.count += 1
            await modify_2_continue.wait()

    async def modify_3():
        await modify_started.wait()
        modify_2_started.set()
        async with state_manager_3.modify_state(
            _substate_key(token, root_state),
        ) as new_state:
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

    final_state = await state_manager_2.get_state(_substate_key(token, root_state))
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
    root_state: type[BaseState],
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

    state_manager_2 = StateManagerRedis(
        state=root_state, redis=state_manager_redis.redis
    )
    state_manager_2._debug_enabled = True
    state_manager_2._oplock_enabled = True
    lease_1 = None
    lease_2 = None

    async def modify_1():
        nonlocal lease_1
        async with state_manager_redis.modify_state(
            _substate_key(token, root_state),
        ) as new_state:
            lease_1 = await state_manager_redis._get_local_lease(token)
            new_state.count += 1

    async def modify_2():
        if racer_delay is not None:
            await asyncio.sleep(racer_delay)
        nonlocal lease_2
        async with state_manager_2.modify_state(
            _substate_key(token, root_state),
        ) as new_state:
            lease_2 = await state_manager_2._get_local_lease(token)
            new_state.count += 1

    await asyncio.gather(
        modify_1(),
        modify_2(),
    )

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
async def test_oplock_immediate_cancel(
    state_manager_redis: StateManagerRedis,
    root_state: type[BaseState],
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

    async def canceller():
        while (lease_task := state_manager_redis._local_leases.get(token)) is None:  # noqa: ASYNC110
            await asyncio.sleep(0)
        lease_task.cancel()

    task = asyncio.create_task(canceller())

    async with state_manager_redis.modify_state(
        _substate_key(token, root_state),
    ) as new_state:
        assert await state_manager_redis._get_local_lease(token) is None
        new_state.count += 1

    await task


@pytest.mark.asyncio
async def test_oplock_fetch_substate(
    state_manager_redis: StateManagerRedis,
    root_state: type[BaseState],
    event_log: list[dict[str, Any]],
):
    """Test fetching substate with oplock enabled and partial state is cached.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
    """

    class SubState1(root_state):
        pass

    class SubState2(root_state):
        pass

    token = str(uuid.uuid4())

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True

    async with state_manager_redis.modify_state(
        _substate_key(token, SubState1),
    ) as new_state:
        assert SubState1.get_name() in new_state.substates
        assert SubState2.get_name() not in new_state.substates

    async with state_manager_redis.modify_state(
        _substate_key(token, SubState2),
    ) as new_state:
        # Both substates should be fetched and cached.
        assert SubState1.get_name() in new_state.substates
        assert SubState2.get_name() in new_state.substates

    async with state_manager_redis.modify_state(
        _substate_key(token, SubState1),
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
    root_state: type[BaseState],
    event_log: list[dict[str, Any]],
    short_lock_expiration: int,
):
    """Test that cancelling a modify does not release the oplock prematurely.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
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
            _substate_key(token, root_state),
        ) as new_state:
            modify_started.set()
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
    async with state_manager_redis.modify_state(
        _substate_key(token, root_state),
    ) as new_state:
        new_state.count += 1

    # There should have been two redis lock acquisitions.
    lock_events = len([
        ev
        for ev in event_log
        if ev["channel"].endswith(b"lock") and ev["data"] == b"set"
    ])
    assert lock_events == 2

    await state_manager_redis.close()

    # Both increments should be present.
    final_state = await state_manager_redis.get_state(_substate_key(token, root_state))
    assert final_state.count == 2
