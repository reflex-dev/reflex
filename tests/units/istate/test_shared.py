"""Unit tests for shared state fan-out to other linked clients."""

import asyncio
import pickle
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

import reflex as rx
from reflex.istate.shared import (
    DISCONNECT_REAP_TASKS,
    STARTED_REAP_TASKS,
    SharedState,
    SharedStateBaseInternal,
    _do_update_other_tokens,
    _patch_state,
    _reap_disconnected_client,
    schedule_disconnect_reap,
)
from reflex.state import BaseState, State
from reflex.utils.token_manager import (
    LocalTokenManager,
    RedisTokenManager,
    SocketRecord,
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client.

    Returns:
        The mock Redis client.
    """
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.get_connection_kwargs = Mock(return_value={"db": 0})
    return redis


@pytest.fixture
def redis_manager(mock_redis):
    """Create a RedisTokenManager instance with mocked config.

    Returns:
        The RedisTokenManager instance.
    """
    with patch("reflex_base.config.get_config") as mock_get_config:
        mock_config = Mock()
        mock_config.redis_token_expiration = 3600
        mock_get_config.return_value = mock_config

        return RedisTokenManager(mock_redis)


def _mock_app(token_manager) -> tuple[Mock, list[str]]:
    """Create a mock app recording the tokens passed to modify_state.

    Returns:
        The mock app and the list collecting modified token idents.
    """
    modified_tokens: list[str] = []

    @asynccontextmanager
    async def modify_state(token, previous_dirty_vars=None):
        modified_tokens.append(token.ident)
        yield Mock()

    app = Mock()
    app.modify_state = modify_state
    app.event_namespace = Mock()
    app.event_namespace._token_manager = token_manager
    return app, modified_tokens


async def _run_update_other_tokens(app, affected_tokens: set[str]) -> None:
    """Run _do_update_other_tokens against a mock app and await its tasks."""
    with patch("reflex_base.registry.RegistrationContext.get") as mock_get:
        mock_get.return_value = Mock(app=app)
        tasks = _do_update_other_tokens(
            affected_tokens=affected_tokens,
            previous_dirty_vars={},
            state_type=State,
        )
    await asyncio.gather(*tasks)


async def test_update_other_tokens_local_manager():
    """With a LocalTokenManager, only locally connected tokens are updated."""
    manager = LocalTokenManager()
    manager.token_to_socket["connected"] = SocketRecord(
        instance_id=manager.instance_id, sid="sid1"
    )
    app, modified_tokens = _mock_app(manager)

    await _run_update_other_tokens(app, {"connected", "disconnected"})

    assert modified_tokens == ["connected"]


async def test_update_other_tokens_redis_cross_instance(redis_manager, mock_redis):
    """Tokens connected to another instance are resolved via redis and updated."""
    redis_manager.token_to_socket["local"] = SocketRecord(
        instance_id=redis_manager.instance_id, sid="sid1"
    )
    foreign_record = SocketRecord(instance_id="other-instance", sid="sid2")
    foreign_key = redis_manager._get_redis_key("foreign")
    mock_redis.get.side_effect = lambda key: (
        pickle.dumps(foreign_record) if key == foreign_key else None
    )
    app, modified_tokens = _mock_app(redis_manager)

    await _run_update_other_tokens(app, {"local", "foreign", "disconnected"})

    assert sorted(modified_tokens) == ["foreign", "local"]
    # The foreign socket record is cached locally for later emit_update routing.
    assert redis_manager.token_to_socket["foreign"] == foreign_record
    # Locally owned sockets are authoritative and never require a redis lookup.
    local_key = redis_manager._get_redis_key("local")
    assert local_key not in [call.args[0] for call in mock_redis.get.call_args_list]


@pytest.fixture(autouse=True)
def _clear_reap_tasks():
    """Drop the reap bookkeeping left by tests calling the reap without scheduling it."""
    yield
    DISCONNECT_REAP_TASKS.clear()
    STARTED_REAP_TASKS.clear()


def _mock_reap_app(token_manager) -> tuple[Mock, Mock, list[str]]:
    """Create a mock app with one client linked to one shared state.

    Returns:
        The mock app, the mock shared state and the list collecting the
        token idents passed to modify_state.
    """
    modified_tokens: list[str] = []

    shared = Mock(spec=SharedState)
    shared._linked_from = {"gone", "other"}
    shared._on_subscriber_disconnected = AsyncMock()

    @asynccontextmanager
    async def modify_state(token, previous_dirty_vars=None):
        modified_tokens.append(token.ident)
        shared_root = Mock()
        shared_root.get_state = AsyncMock(return_value=shared)
        yield shared_root

    root_state = Mock(spec=State)
    root_state._reflex_internal_links = {"state.shared_sub": "room-token"}

    app = Mock()
    app.modify_state = modify_state
    app.event_namespace = Mock()
    app.event_namespace._token_manager = token_manager
    app.state_manager.get_state = AsyncMock(return_value=root_state)
    app._state = Mock()
    app._state.get_class_substate = Mock(return_value=State)
    return app, shared, modified_tokens


async def test_reap_disconnected_client_unsubscribes():
    """A client that stayed disconnected is removed from its linked states."""
    app, shared, modified_tokens = _mock_reap_app(LocalTokenManager())

    await _reap_disconnected_client(app, "gone", grace=0)

    assert modified_tokens == ["room-token"]
    assert shared._linked_from == {"other"}
    shared._on_subscriber_disconnected.assert_awaited_once_with("gone")


async def test_reap_skips_reconnected_client():
    """A client that reconnected within the grace is left subscribed."""
    manager = LocalTokenManager()
    manager.token_to_socket["gone"] = SocketRecord(
        instance_id=manager.instance_id, sid="sid1"
    )
    app, shared, modified_tokens = _mock_reap_app(manager)

    await _reap_disconnected_client(app, "gone", grace=0)

    assert modified_tokens == []
    assert shared._linked_from == {"gone", "other"}
    shared._on_subscriber_disconnected.assert_not_awaited()


async def test_reap_skips_client_reconnected_before_lock():
    """A client reconnecting while the reap waits for the shared lock stays subscribed."""
    manager = LocalTokenManager()
    app, shared, modified_tokens = _mock_reap_app(manager)
    modify_state = app.modify_state

    @asynccontextmanager
    async def reconnect_then_modify_state(token):
        manager.token_to_socket["gone"] = SocketRecord(
            instance_id=manager.instance_id, sid="sid2"
        )
        async with modify_state(token) as shared_root:
            yield shared_root

    app.modify_state = reconnect_then_modify_state

    await _reap_disconnected_client(app, "gone", grace=0)

    assert modified_tokens == ["room-token"]
    assert shared._linked_from == {"gone", "other"}
    shared._on_subscriber_disconnected.assert_not_awaited()


async def test_reap_skips_unsubscribed_client():
    """A token no longer in the subscriber set does not trigger the hook."""
    app, shared, modified_tokens = _mock_reap_app(LocalTokenManager())

    await _reap_disconnected_client(app, "unknown", grace=0)

    assert modified_tokens == ["room-token"]
    assert shared._linked_from == {"gone", "other"}
    shared._on_subscriber_disconnected.assert_not_awaited()


def test_schedule_disconnect_reap_disabled(monkeypatch):
    """Grace 0 disables scheduling entirely."""
    monkeypatch.setenv("REFLEX_SHARED_STATE_DISCONNECT_GRACE", "0")
    app, _, _ = _mock_reap_app(LocalTokenManager())

    assert schedule_disconnect_reap(app, "gone") is None
    assert not DISCONNECT_REAP_TASKS


async def test_schedule_disconnect_reap_restarts_grace(monkeypatch):
    """A new disconnect for the same token cancels the pending reap."""
    monkeypatch.setenv("REFLEX_SHARED_STATE_DISCONNECT_GRACE", "60")
    app, _, modified_tokens = _mock_reap_app(LocalTokenManager())

    first = schedule_disconnect_reap(app, "gone")
    second = schedule_disconnect_reap(app, "gone")
    assert first is not None
    assert second is not None
    with pytest.raises(asyncio.CancelledError):
        await first
    assert {"gone": second} == DISCONNECT_REAP_TASKS

    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second
    assert not DISCONNECT_REAP_TASKS
    assert modified_tokens == []


async def test_schedule_disconnect_reap_lets_started_cleanup_finish(monkeypatch):
    """A new disconnect restarts the grace without cancelling a started cleanup."""
    monkeypatch.setenv("REFLEX_SHARED_STATE_DISCONNECT_GRACE", "60")
    sleep = asyncio.sleep

    async def skip_grace(delay):
        await sleep(0)

    monkeypatch.setattr(asyncio, "sleep", skip_grace)
    app, shared, _ = _mock_reap_app(LocalTokenManager())
    hook_entered = asyncio.Event()
    release_hook = asyncio.Event()

    async def slow_hook(token):
        hook_entered.set()
        await release_hook.wait()

    shared._on_subscriber_disconnected.side_effect = slow_hook

    first = schedule_disconnect_reap(app, "gone")
    await hook_entered.wait()
    second = schedule_disconnect_reap(app, "gone")
    release_hook.set()
    assert first is not None
    assert second is not None
    await first
    await second
    # Let the done callbacks release the tasks.
    await sleep(0)

    assert shared._linked_from == {"other"}
    shared._on_subscriber_disconnected.assert_awaited_once_with("gone")
    assert not DISCONNECT_REAP_TASKS
    assert not STARTED_REAP_TASKS


@pytest.mark.parametrize("blocked_link", [0, 1])
async def test_superseded_reap_leaves_unlink_to_new_grace(
    monkeypatch, blocked_link: int
):
    """A reap waiting for a shared lock unlinks nothing once a newer disconnect restarts the grace."""
    monkeypatch.setenv("REFLEX_SHARED_STATE_DISCONNECT_GRACE", "60")
    sleep = asyncio.sleep
    first_grace, second_grace = asyncio.Event(), asyncio.Event()
    graces = [first_grace, second_grace]

    async def wait_for_grace(delay):
        await graces.pop(0).wait()

    monkeypatch.setattr(asyncio, "sleep", wait_for_grace)
    app, _, _ = _mock_reap_app(LocalTokenManager())
    rooms = [Mock(spec=SharedState) for _ in range(2)]
    for room in rooms:
        room._linked_from = {"gone"}
        room._on_subscriber_disconnected = AsyncMock()
    app.state_manager.get_state.return_value._reflex_internal_links = {
        "state.shared_0": "0",
        "state.shared_1": "1",
    }
    lock_wanted = asyncio.Event()
    release_lock = asyncio.Event()

    @asynccontextmanager
    async def modify_state(token):
        if token.ident == str(blocked_link):
            lock_wanted.set()
            await release_lock.wait()
        shared_root = Mock()
        shared_root.get_state = AsyncMock(return_value=rooms[int(token.ident)])
        yield shared_root

    app.modify_state = modify_state

    first_grace.set()
    first = schedule_disconnect_reap(app, "gone")
    await lock_wanted.wait()
    # The client reconnects and drops again while the reap waits for the lock.
    second = schedule_disconnect_reap(app, "gone")
    release_lock.set()
    assert first is not None
    assert second is not None
    await asyncio.wait([first])

    for i, room in enumerate(rooms):
        assert ("gone" in room._linked_from) is (i >= blocked_link)
    rooms[blocked_link]._on_subscriber_disconnected.assert_not_awaited()
    assert {"gone": second} == DISCONNECT_REAP_TASKS

    second_grace.set()
    await second
    # Let the done callbacks release the tasks.
    await sleep(0)

    for room in rooms:
        assert not room._linked_from
        room._on_subscriber_disconnected.assert_awaited_once_with("gone")
    assert not DISCONNECT_REAP_TASKS
    assert not STARTED_REAP_TASKS


async def test_no_fan_out_without_linked_clients():
    """An event with nothing linked does not reach for the registered App.

    Defining any ``SharedState`` subclass routes every event in the process
    through ``_modify_linked_states``. Apps that never link pay that path on
    each event with no client to fan out to, so it must not do the work -- nor
    require an App to be registered -- when there is nothing to propagate.
    """
    root_state = State.get_root_state()(_reflex_internal_init=True)
    root_state._reflex_internal_links = {}
    shared_base = root_state.substates[SharedStateBaseInternal.get_name()]
    assert isinstance(shared_base, SharedStateBaseInternal)

    with patch("reflex.istate.shared._do_update_other_tokens") as do_update:
        async with shared_base._modify_linked_states():
            pass

    do_update.assert_not_called()


class PatchRoot(BaseState):
    """The root of a tree a state is patched into."""


class PatchSource(PatchRoot):
    """A state swapped for another instance while patched."""

    who: str = "private"


class PatchReader(PatchRoot):
    """A state with a computed var reading the patched state."""

    @rx.var
    async def greeting(self) -> str:
        """Read the patched state.

        Returns:
            Its value.
        """
        return (await self.get_state(PatchSource)).who


@pytest.mark.asyncio
async def test_patch_state_recomputes_readers_after_restoring():
    """Computed vars read from a patched state are recomputed once it is swapped back."""
    root = PatchRoot(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    original = root.get_substate([PatchSource.get_name()])
    reader = root.get_substate([PatchReader.get_name()])
    # The state of another client, in a tree of its own.
    linked_root = PatchRoot(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    linked = linked_root.get_substate([PatchSource.get_name()])
    linked.who = "linked"  # pyright: ignore[reportAttributeAccessIssue]

    async with _patch_state(original_state=original, linked_state=linked):
        assert await reader.greeting == "linked"  # pyright: ignore[reportAttributeAccessIssue]
    assert await reader.greeting == "private"  # pyright: ignore[reportAttributeAccessIssue]
