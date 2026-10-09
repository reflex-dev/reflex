"""Tests specific to redis state manager."""

import asyncio
import contextlib
import enum
import os
import time
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from types import ModuleType
from typing import Any, cast

import pytest
import pytest_asyncio
from reflex_base.utils.exceptions import EnvironmentVarValueError, LockExpiredError

from reflex.istate.manager.redis import (
    _RELEASE_LOCK_SCRIPT,
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


class SubState2(RedisTestState):
    """A test substate for redis state manager tests."""


class RedisAppObjectState(BaseState):
    """A root state holding an instance of an app-defined class."""

    _value: Any = None


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
    """Test that immediate cancellation of the lease releases oplock.

    The lease may be cancelled before its task ever ran, which still has to
    flush the state and release the lock.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        event_log: The redis event log.
    """
    token = str(uuid.uuid4())
    state_token = BaseStateToken(ident=token, cls=root_state)

    state_manager_redis._debug_enabled = True
    state_manager_redis._oplock_enabled = True
    # The canceller below spins until a lease exists, so fail fast if the
    # subscription a lease requires is unavailable.
    await _subscribed(state_manager_redis)

    async def canceller() -> asyncio.Task:
        while (lease_task := state_manager_redis._local_leases.get(token)) is None:  # noqa: ASYNC110
            await asyncio.sleep(0)
        lease_task.cancel()
        return lease_task

    task = asyncio.create_task(canceller())

    async with state_manager_redis.modify_state(state_token) as new_state:
        assert isinstance(new_state, root_state)
        new_state.count += 1

    lease_task = await task
    await asyncio.wait({lease_task})
    await asyncio.gather(*state_manager_redis._lease_cleanups)

    assert await state_manager_redis._get_local_lease(token) is None
    assert (
        await state_manager_redis.redis.get(state_manager_redis._lock_key(state_token))
        is None
    )
    final_state = await state_manager_redis.get_state(state_token)
    assert isinstance(final_state, root_state)
    assert final_state.count == 1


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


@pytest.mark.asyncio
async def test_oplock_cancel_after_lock_acquired_releases_lock(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    monkeypatch: pytest.MonkeyPatch,
):
    """Cancelling a modify between taking the lock and leasing it releases the lock.

    A superseded event is cancelled at whatever await it is in, and a lock left
    behind keeps every other event of the token waiting until it expires.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        monkeypatch: Pytest monkeypatch fixture.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    state_manager_redis._oplock_enabled = True
    await _subscribed(state_manager_redis)

    lock_acquired = asyncio.Event()

    async def block_after_acquiring(lock_key: bytes) -> int:
        lock_acquired.set()
        await asyncio.Event().wait()
        return 0

    monkeypatch.setattr(
        state_manager_redis, "_n_lock_contenders", block_after_acquiring
    )

    async def modify():
        async with state_manager_redis.modify_state(token):
            pass

    task = asyncio.create_task(modify())
    await lock_acquired.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert (
        await state_manager_redis.redis.get(state_manager_redis._lock_key(token))
        is None
    )


@pytest.mark.asyncio
async def test_cancel_while_acquiring_lock_releases_it(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    monkeypatch: pytest.MonkeyPatch,
):
    """A lock set in redis whose reply never reached the cancelled caller is released.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        monkeypatch: Pytest monkeypatch fixture.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    lock_set = asyncio.Event()
    redis_set = state_manager_redis.redis.set

    async def set_then_hang(*args: Any, **kwargs: Any) -> Any:
        result = await redis_set(*args, **kwargs)
        if kwargs.get("nx"):
            lock_set.set()
            await asyncio.Event().wait()
        return result

    monkeypatch.setattr(state_manager_redis.redis, "set", set_then_hang)

    async def modify():
        async with state_manager_redis.modify_state(token):
            pass

    task = asyncio.create_task(modify())
    await lock_set.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert (
        await state_manager_redis.redis.get(state_manager_redis._lock_key(token))
        is None
    )


@pytest.mark.asyncio
async def test_cancel_while_releasing_lock_releases_it(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    monkeypatch: pytest.MonkeyPatch,
):
    """A release cut short by a cancellation still deletes the lock.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        monkeypatch: Pytest monkeypatch fixture.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    releasing = asyncio.Event()
    # redis-py types EVAL replies as str; the lock release replies with bytes.
    redis_eval = cast("Callable[..., Awaitable[Any]]", state_manager_redis.redis.eval)

    async def first_release_hangs(script: str, *args: Any) -> Any:
        if script == _RELEASE_LOCK_SCRIPT and not releasing.is_set():
            releasing.set()
            await asyncio.Event().wait()
        return await redis_eval(script, *args)

    monkeypatch.setattr(state_manager_redis.redis, "eval", first_release_hangs)

    async def hold_lock():
        async with state_manager_redis._lock(token):
            pass

    task = asyncio.create_task(hold_lock())
    await releasing.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert (
        await state_manager_redis.redis.get(state_manager_redis._lock_key(token))
        is None
    )


@pytest.mark.asyncio
async def test_lock_release_after_expiration_keeps_the_next_owner(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
):
    """Releasing a lock that already expired must not delete its next owner's lock.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    lock_key = state_manager_redis._lock_key(token)

    async with state_manager_redis._lock(token):
        # The lock expires and another holder takes it.
        await state_manager_redis.redis.delete(lock_key)
        await state_manager_redis.redis.set(
            lock_key, b"next-owner", px=state_manager_redis.lock_expiration
        )

    assert await state_manager_redis.redis.get(lock_key) == b"next-owner"


@pytest.mark.asyncio
async def test_oplock_lease_keeps_its_lock_for_queued_uses(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    short_lock_expiration: int,
):
    """A lease keeps its lock while the uses queued ahead of its flush run.

    Each use stays within the lock expiration, but together they outlast it, so
    without renewal the flush would find the lock expired and drop their changes.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        short_lock_expiration: The lock expiration time in milliseconds.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    state_manager_redis._oplock_enabled = True
    state_manager_redis.oplock_hold_time_ms = short_lock_expiration // 2
    await _subscribed(state_manager_redis)

    async with state_manager_redis.modify_state(token):
        lease_task = await state_manager_redis._get_local_lease(token.lock_key)
        assert lease_task is not None

    async def use():
        async with state_manager_redis.modify_state(token) as state:
            assert isinstance(state, root_state)
            state.count += 1
            await asyncio.sleep(short_lock_expiration * 0.6 / 1000)

    # Both queue up on the cached state before the lease breaks.
    await asyncio.gather(use(), use())
    await lease_task

    final_state = await state_manager_redis.get_state(token)
    assert isinstance(final_state, root_state)
    assert final_state.count == 2


@pytest.mark.asyncio
async def test_oplock_lease_lets_a_use_past_the_lock_expiration_expire(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    short_lock_expiration: int,
):
    """A use of the cached state longer than the lock expiration loses the lock.

    Its lease ends in LockExpiredError without writing, as a handler holding
    the lock itself would.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        short_lock_expiration: The lock expiration time in milliseconds.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    state_manager_redis._oplock_enabled = True
    state_manager_redis.oplock_hold_time_ms = short_lock_expiration // 2
    await _subscribed(state_manager_redis)

    async with state_manager_redis.modify_state(token) as state:
        assert isinstance(state, root_state)
        state.count += 1
        lease_task = await state_manager_redis._get_local_lease(token.lock_key)
        assert lease_task is not None
        await asyncio.sleep(short_lock_expiration * 1.25 / 1000)

    with pytest.raises(LockExpiredError):
        await lease_task
    final_state = await state_manager_redis.get_state(token)
    assert isinstance(final_state, root_state)
    assert final_state.count == 0


@pytest.mark.asyncio
async def test_oplock_lease_renewal_leaves_another_holders_lock_alone(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    short_lock_expiration: int,
):
    """A lease whose lock another holder took never extends that holder's lock.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        short_lock_expiration: The lock expiration time in milliseconds.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    lock_key = state_manager_redis._lock_key(token)
    state_manager_redis._oplock_enabled = True
    state_manager_redis.oplock_hold_time_ms = short_lock_expiration // 2
    await _subscribed(state_manager_redis)

    async with state_manager_redis.modify_state(token):
        lease_task = await state_manager_redis._get_local_lease(token.lock_key)
        assert lease_task is not None

    async with state_manager_redis.modify_state(token):
        # The lease's lock expires and another holder takes it, for less time
        # than this use keeps the cached state past the lease break.
        await state_manager_redis.redis.delete(lock_key)
        await state_manager_redis.redis.set(
            lock_key, b"other", px=short_lock_expiration * 6 // 10
        )
        await asyncio.sleep(short_lock_expiration * 0.9 / 1000)
        assert await state_manager_redis.redis.get(lock_key) is None

    with pytest.raises(LockExpiredError):
        await lease_task


@pytest.mark.asyncio
async def test_oplock_lease_reports_a_failed_renewal(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    short_lock_expiration: int,
    monkeypatch: pytest.MonkeyPatch,
):
    """A lock renewal that fails ends the lease with its error.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        short_lock_expiration: The lock expiration time in milliseconds.
        monkeypatch: Pytest monkeypatch fixture.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    state_manager_redis._oplock_enabled = True
    state_manager_redis.oplock_hold_time_ms = short_lock_expiration // 2
    await _subscribed(state_manager_redis)

    async with state_manager_redis.modify_state(token):
        lease_task = await state_manager_redis._get_local_lease(token.lock_key)
        assert lease_task is not None

    class RenewalError(Exception):
        """Raised by the failing renewal."""

    async def failing_renewal(lock_key: bytes, lock_id: bytes, px: int) -> bool:  # noqa: RUF029
        raise RenewalError

    monkeypatch.setattr(state_manager_redis, "_extend_lock", failing_renewal)
    # In use past the lease break, so the flush renews the lock while it waits.
    async with state_manager_redis.modify_state(token):
        await asyncio.sleep(short_lock_expiration * 0.75 / 1000)
    with pytest.raises(RenewalError):
        await lease_task


@pytest.mark.asyncio
async def test_oplock_waiter_woken_when_the_cached_holder_raises(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    monkeypatch: pytest.MonkeyPatch,
):
    """A local waiter joins the lease when the event ahead of it raises.

    The waiter queued on the redis lock before the lease existed, so only the
    holder can tell it about the lease; otherwise it sits out the whole lease.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        monkeypatch: Pytest monkeypatch fixture.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    state_manager_redis._oplock_enabled = True
    state_manager_redis.oplock_hold_time_ms = 2000
    await _subscribed(state_manager_redis)

    holder_locked = asyncio.Event()
    waiter_queued = asyncio.Event()

    async def lease_despite_the_waiter(lock_key: bytes) -> int:
        # Another local waiter's SREM can empty the shared waiters set, so the
        # holder leases although this one is still queued.
        if not holder_locked.is_set():
            holder_locked.set()
            await waiter_queued.wait()
        return 0

    monkeypatch.setattr(
        state_manager_redis, "_n_lock_contenders", lease_despite_the_waiter
    )

    class HandlerError(Exception):
        """Raised by the event holding the cached state."""

    async def failing_holder():
        async with state_manager_redis.modify_state(token):
            raise HandlerError

    async def waiter() -> float:
        started = time.monotonic()
        async with state_manager_redis.modify_state(token):
            return time.monotonic() - started

    holder = asyncio.create_task(failing_holder())
    await holder_locked.wait()
    waiting = asyncio.create_task(waiter())
    lock_key = state_manager_redis._lock_key(token)
    while not state_manager_redis._n_lock_waiters(lock_key):  # noqa: ASYNC110
        await asyncio.sleep(0)
    # Its contention notice arrives before the lease exists, so it breaks nothing.
    await asyncio.sleep(0.1)
    waiter_queued.set()

    with pytest.raises(HandlerError):
        await holder
    # Woken well before its next re-check of the lock.
    assert await waiting < state_manager_redis.lock_expiration / 10_000 / 2


@pytest.mark.asyncio
async def test_cancelled_waiter_passes_its_wakeup_on(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    monkeypatch: pytest.MonkeyPatch,
):
    """A waiter cancelled after its wakeup hands the wakeup to the next waiter.

    Otherwise the next waiter, queued after the release was announced, waits
    until its wait times out.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        monkeypatch: Pytest monkeypatch fixture.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    lock_key = state_manager_redis._lock_key(token)
    state_manager_redis._oplock_enabled = False
    await _subscribed(state_manager_redis)

    first_retry = asyncio.Event()
    try_get_lock = state_manager_redis._try_get_lock

    async def first_waiter_stalls_on_retry(key: bytes, lock_id: bytes) -> bool | None:
        if lock_id.startswith(b"first:") and state_manager_redis._n_lock_waiters(key):
            first_retry.set()
            await asyncio.Event().wait()
        return await try_get_lock(key, lock_id)

    monkeypatch.setattr(
        state_manager_redis, "_try_get_lock", first_waiter_stalls_on_retry
    )

    async def take_lock(event_name: str) -> float:
        started = time.monotonic()
        async with state_manager_redis._lock(token, event_name=event_name):
            return time.monotonic() - started

    release_holder = asyncio.Event()

    async def holder():
        async with state_manager_redis._lock(token, event_name="holder"):
            await release_holder.wait()

    holding = asyncio.create_task(holder())
    while await state_manager_redis.redis.get(lock_key) is None:  # noqa: ASYNC110
        await asyncio.sleep(0)
    first = asyncio.create_task(take_lock("first"))
    while not state_manager_redis._n_lock_waiters(lock_key):  # noqa: ASYNC110
        await asyncio.sleep(0)

    release_holder.set()
    await holding
    await first_retry.wait()
    # The release is announced before the second waiter queues.
    await asyncio.sleep(0.1)
    second = asyncio.create_task(take_lock("second"))
    while state_manager_redis._n_lock_waiters(lock_key) < 2:  # noqa: ASYNC110
        await asyncio.sleep(0)

    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    # Woken well before its next re-check of the lock.
    assert await second < state_manager_redis.lock_expiration / 10_000 / 2


@pytest.mark.asyncio
async def test_waiter_rechecks_a_lock_released_without_notice(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
    monkeypatch: pytest.MonkeyPatch,
):
    """A waiter whose release notification got lost still takes the free lock.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
        monkeypatch: Pytest monkeypatch fixture.
    """
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    lock_key = state_manager_redis._lock_key(token)
    state_manager_redis.lock_expiration = 2000
    await _subscribed(state_manager_redis)
    # Neither the release's own notice nor its keyspace event reach the waiter.
    monkeypatch.setattr(state_manager_redis, "_notify_next_waiter", lambda key: None)

    release_holder = asyncio.Event()

    async def holder():
        async with state_manager_redis._lock(token):
            await release_holder.wait()

    async def waiter() -> float:
        started = time.monotonic()
        async with state_manager_redis._lock(token):
            return time.monotonic() - started

    holding = asyncio.create_task(holder())
    while await state_manager_redis.redis.get(lock_key) is None:  # noqa: ASYNC110
        await asyncio.sleep(0)
    waiting = asyncio.create_task(waiter())
    while not state_manager_redis._n_lock_waiters(lock_key):  # noqa: ASYNC110
        await asyncio.sleep(0)
    release_holder.set()
    await holding

    assert await waiting < state_manager_redis.lock_expiration / 1000 / 2


@pytest.mark.asyncio
async def test_waiter_woken_when_the_holder_lock_expired(
    state_manager_redis: StateManagerRedis,
    root_state: type[RedisTestState],
):
    """A holder whose lock expired under it still wakes the next waiter.

    Args:
        state_manager_redis: The StateManagerRedis to test.
        root_state: The root state class.
    """
    internals = getattr(state_manager_redis.redis, "_internals", {})
    if "keys" not in internals:
        pytest.skip("Expiring a lock without its keyspace event needs the mock redis.")
    token = BaseStateToken(ident=str(uuid.uuid4()), cls=root_state)
    lock_key = state_manager_redis._lock_key(token)
    await _subscribed(state_manager_redis)

    waiter_queued = asyncio.Event()

    async def holder():
        async with state_manager_redis._lock(token):
            await waiter_queued.wait()
            # The lock expires, and its expired event was already handled.
            internals["keys"].pop(lock_key)
            internals["expire_times"].pop(lock_key, None)
            msg = "the lock expired"
            raise LockExpiredError(msg)

    async def waiter() -> float:
        started = time.monotonic()
        async with state_manager_redis._lock(token):
            return time.monotonic() - started

    holding = asyncio.create_task(holder())
    while await state_manager_redis.redis.get(lock_key) is None:  # noqa: ASYNC110
        await asyncio.sleep(0)
    waiting = asyncio.create_task(waiter())
    while not state_manager_redis._n_lock_waiters(lock_key):  # noqa: ASYNC110
        await asyncio.sleep(0)
    waiter_queued.set()
    with pytest.raises(LockExpiredError):
        await holding

    # Woken well before its next re-check of the lock.
    assert await waiting < state_manager_redis.lock_expiration / 10_000 / 2


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
