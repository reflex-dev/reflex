"""Benchmarks for the ``StateManager`` get/set/modify code paths.

Every manager is wired to an in-process backing store so the numbers describe
the work Reflex does -- formatting tokens, walking the state tree,
(de)serializing states and bookkeeping locks -- rather than how fast the disk
or the network underneath it happens to be on a given runner:

* ``StateManagerMemory`` has no external store to begin with.
* ``StateManagerDisk`` writes into a tmpfs directory where the platform has
  one, so ``write_bytes`` lands in the page cache instead of on a device.
  Write debouncing is turned off so every ``set_state`` really serializes
  instead of parking the state in the background write queue.
* ``StateManagerRedis`` talks to the in-process ``mock_redis`` fake, which
  serves the command surface the manager uses -- pipelines, set commands,
  keyspace notifications -- out of plain dicts.

Lock and lease expirations are pushed far beyond any run, because the
instrumented runner is much slower than wall clock and a lock or opportunistic
lease breaking mid-run would silently change which code path is measured.

Each measured call drives its operation ``ITERATIONS`` times, because entering
the event loop costs a few microseconds no matter what happens inside it.
Unbatched, that entry is over 80% of what a cached ``get_state`` appears to
cost, enough to bury a real regression; batched, it is a fixed fifth of the
cheapest benchmark here and a rounding error on the rest.
"""

import asyncio
import shutil
import tempfile
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_asyncio
from pytest_codspeed import BenchmarkFixture
from reflex_base.environment import environment
from reflex_base.state.token import BaseStateToken

from reflex.istate.manager import StateManager
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from reflex.state import BaseState
from tests.units.mock_redis import mock_redis

from .support.states import (
    PerformanceState,
    get_performance_state,
    isolated_performance_registry,
)

AsyncOperation = Callable[[], Coroutine[Any, Any, Any]]
AsyncOperationBenchmark = Callable[[AsyncOperation], None]

# Far beyond any run, so nothing expires mid-measurement. Pinned rather than
# left to the config defaults so tuning those cannot move these numbers.
TOKEN_EXPIRATION_S = 60 * 60
LOCK_EXPIRATION_MS = TOKEN_EXPIRATION_S * 1000
OPLOCK_HOLD_TIME_MS = LOCK_EXPIRATION_MS - 1

TOKEN_IDENT = "state-manager-benchmark"

# Size of the list/dict payload carried by the data substate.
PAYLOAD_SIZE = 64

# Sentinel written during seeding and read back to prove the store round-trips.
SEEDED_VALUE = 7

# How many times one measured call repeats its operation, to amortize the cost
# of entering the event loop over enough real work to see past it.
ITERATIONS = 50


class ManagerBenchmarkState(BaseState):
    """Root state for the state manager benchmarks.

    Subclasses ``BaseState`` directly rather than ``rx.State`` so the tree is
    unaffected by the states other benchmark modules register.
    """

    counter: int = 0
    title: str = "benchmark"


class SettingsSubState(ManagerBenchmarkState):
    """A substate of scalars, standing in for cheap-to-serialize app state."""

    theme: str = "dark"
    density: int = 3


class DataSubState(ManagerBenchmarkState):
    """A substate carrying a payload, so pickling has real work to do."""

    revision: int = 0
    rows: list[int] = list(range(PAYLOAD_SIZE))
    labels: dict[str, int] = {f"label_{i}": i for i in range(PAYLOAD_SIZE)}


class DetailSubState(DataSubState):
    """A nested substate, so the tree is deeper than a single level."""

    selected: int = 0


TOKEN = BaseStateToken(ident=TOKEN_IDENT, cls=ManagerBenchmarkState)
DATA_SUBSTATE_NAME = DataSubState.get_name()


def _states_directory() -> Path:
    """Create a RAM-backed directory for the disk state manager, if possible.

    Returns:
        A fresh directory on tmpfs where the platform has one, else in the
        regular temp directory.
    """
    shm = Path("/dev/shm")
    base = shm if shm.is_dir() else Path(tempfile.gettempdir())
    return Path(tempfile.mkdtemp(prefix="reflex-benchmark-states-", dir=base))


def _make_memory_manager() -> StateManagerMemory:
    """Create the in-memory state manager.

    Returns:
        The state manager.
    """
    return StateManagerMemory(token_expiration=TOKEN_EXPIRATION_S)


def _make_disk_manager() -> StateManagerDisk:
    """Create a disk state manager rooted at the configured states directory.

    Debouncing is disabled so ``set_state`` serializes and writes inline rather
    than parking the state in the background write queue.

    Returns:
        The state manager.
    """
    return StateManagerDisk(
        token_expiration=TOKEN_EXPIRATION_S, _write_debounce_seconds=0
    )


def _make_redis_manager() -> StateManagerRedis:
    """Create a redis state manager over the in-process redis fake.

    Returns:
        The state manager.
    """
    manager = StateManagerRedis(
        redis=mock_redis(),
        token_expiration=TOKEN_EXPIRATION_S,
        lock_expiration=LOCK_EXPIRATION_MS,
        oplock_hold_time_ms=OPLOCK_HOLD_TIME_MS,
    )
    manager._oplock_enabled = False
    return manager


def _make_redis_oplock_manager() -> StateManagerRedis:
    """Create a redis state manager with opportunistic locking enabled.

    Returns:
        The state manager.
    """
    manager = _make_redis_manager()
    manager._oplock_enabled = True
    return manager


MANAGER_FACTORIES: dict[str, Callable[[], StateManager]] = {
    "memory": _make_memory_manager,
    "disk": _make_disk_manager,
    "redis": _make_redis_manager,
    "redis_oplock": _make_redis_oplock_manager,
}

ALL_MANAGERS = list(MANAGER_FACTORIES)

# Opportunistic locking only branches inside ``modify_state``; ``get_state``
# and ``set_state`` run the same code with it on or off, so the oplock
# variant is only measured where it diverges.
GET_SET_MANAGERS = ["memory", "disk", "redis"]

# Managers that keep the state tree in process memory, so the load-from-store
# path is only reachable after evicting it. The redis manager is left out: it
# reloads on every ``get_state`` anyway, and evicting an opportunistic lease's
# cached state out from under it would leave the manager waiting on a lock it
# holds itself.
CACHING_MANAGERS = ["memory", "disk"]


@pytest_asyncio.fixture
async def state_manager(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
):
    """Create a state manager holding a populated benchmark token.

    Args:
        request: The fixture request carrying the manager name to build.
        monkeypatch: The pytest monkeypatch fixture.

    Yields:
        The state manager under benchmark.
    """
    states_directory = _states_directory()
    monkeypatch.setenv(environment.REFLEX_STATES_WORKDIR.name, str(states_directory))
    try:
        manager = MANAGER_FACTORIES[request.param]()
        try:
            state = cast(ManagerBenchmarkState, await manager.get_state(TOKEN))
            state.counter = SEEDED_VALUE
            cast(
                DataSubState, state.substates[DATA_SUBSTATE_NAME]
            ).revision = SEEDED_VALUE
            await manager.set_state(TOKEN, state)

            # Guard against benchmarking reads against a store that never got
            # written: the substate has to come back carrying what seeding put
            # in it. The disk manager's process-local copy is evicted first so
            # the read deserializes from the store instead of returning the
            # cached tree; the memory manager has no store besides that cache,
            # so it is read as-is.
            if isinstance(manager, StateManagerDisk):
                manager.states.clear()
            seeded = cast(ManagerBenchmarkState, await manager.get_state(TOKEN))
            assert seeded.counter == SEEDED_VALUE
            assert (
                cast(DataSubState, seeded.substates[DATA_SUBSTATE_NAME]).revision
                == SEEDED_VALUE
            )

            # One modify cycle leaves the opportunistic locking manager in the
            # steady state it is meant to be measured in: lease held and state
            # cached.
            await _modify_state(manager)

            yield manager
        finally:
            await manager.close()
    finally:
        shutil.rmtree(states_directory, ignore_errors=True)


@pytest_asyncio.fixture
async def benchmark_state(state_manager: StateManager) -> BaseState:
    """Fetch a state tree to hand back to ``set_state`` on every iteration.

    Args:
        state_manager: The state manager to read the tree from.

    Returns:
        The root state.
    """
    return await state_manager.get_state(TOKEN)


@pytest_asyncio.fixture
async def benchmark_op(benchmark: BenchmarkFixture) -> AsyncOperationBenchmark:  # noqa: RUF029
    """Provide a way to benchmark an async state manager operation.

    The benchmark body has to be synchronous, so it borrows the loop
    pytest-asyncio already set up rather than standing up a fresh one per
    iteration, and batches ``ITERATIONS`` calls per entry into it.

    Args:
        benchmark: The codspeed benchmark fixture.

    Returns:
        A callable that warms up, then benchmarks, the given operation.
    """
    loop = asyncio.get_running_loop()

    async def repeat(operation: AsyncOperation) -> None:
        for _ in range(ITERATIONS):
            await operation()

    def measure(operation: AsyncOperation) -> None:
        loop.run_until_complete(repeat(operation))
        benchmark(lambda: loop.run_until_complete(repeat(operation)))

    return measure


def _touch(state: BaseState) -> None:
    """Dirty a var on the root state and on the payload-carrying substate.

    Mirrors an event handler writing state: the manager then has to walk the
    whole tree and serialize the states that actually changed.

    ``BaseStateToken`` is typed as holding a plain ``BaseState``, so the
    concrete var types are unknown here. This runs inside the measured region,
    so the types are waived rather than re-narrowed with a ``cast`` call.

    Args:
        state: The root state to dirty.
    """
    state.counter += 1  # pyright: ignore[reportAttributeAccessIssue]
    state.substates[DATA_SUBSTATE_NAME].revision += 1  # pyright: ignore[reportAttributeAccessIssue]


async def _get_state(manager: StateManager) -> None:
    """Read the state tree back out of the manager.

    Args:
        manager: The state manager to read from.
    """
    await manager.get_state(TOKEN)


async def _get_state_uncached(manager: StateManagerMemory | StateManagerDisk) -> None:
    """Read the state tree after evicting the manager's process-local copy.

    Args:
        manager: The state manager to read from.
    """
    manager.states.clear()
    await manager.get_state(TOKEN)


async def _set_state(manager: StateManager, state: BaseState) -> None:
    """Dirty the tree and write it back through the manager.

    Args:
        manager: The state manager to write to.
        state: The root state to write.
    """
    _touch(state)
    await manager.set_state(TOKEN, state)


async def _modify_state(manager: StateManager) -> None:
    """Take the lock, dirty the tree and release it, as event processing does.

    Args:
        manager: The state manager to modify state through.
    """
    async with manager.modify_state(TOKEN) as state:
        _touch(state)


@pytest.mark.parametrize("state_manager", GET_SET_MANAGERS, indirect=True)
def test_get_state(state_manager: StateManager, benchmark_op: AsyncOperationBenchmark):
    """Benchmark ``StateManager.get_state`` in steady state.

    Args:
        state_manager: The parametrized state manager.
        benchmark_op: The async operation benchmark runner.
    """
    benchmark_op(lambda: _get_state(state_manager))


@pytest.mark.parametrize("state_manager", CACHING_MANAGERS, indirect=True)
def test_get_state_uncached(
    state_manager: StateManagerMemory | StateManagerDisk,
    benchmark_op: AsyncOperationBenchmark,
):
    """Benchmark ``StateManager.get_state`` when it has to rebuild the tree.

    The disk manager reloads and unpickles the tree; the memory manager has no
    store to reload from, so it builds a fresh one, as it does for a new
    session.

    Args:
        state_manager: The parametrized state manager.
        benchmark_op: The async operation benchmark runner.
    """
    benchmark_op(lambda: _get_state_uncached(state_manager))


@pytest.mark.parametrize("state_manager", GET_SET_MANAGERS, indirect=True)
def test_set_state(
    state_manager: StateManager,
    benchmark_state: BaseState,
    benchmark_op: AsyncOperationBenchmark,
):
    """Benchmark ``StateManager.set_state``.

    Args:
        state_manager: The parametrized state manager.
        benchmark_state: The state tree to write.
        benchmark_op: The async operation benchmark runner.
    """
    benchmark_op(lambda: _set_state(state_manager, benchmark_state))


@pytest.mark.parametrize("state_manager", ALL_MANAGERS, indirect=True)
def test_modify_state(
    state_manager: StateManager, benchmark_op: AsyncOperationBenchmark
):
    """Benchmark ``StateManager.modify_state``.

    Args:
        state_manager: The parametrized state manager.
        benchmark_op: The async operation benchmark runner.
    """
    benchmark_op(lambda: _modify_state(state_manager))


def test_state_manager_memory_cold_get(benchmark: BenchmarkFixture):
    """Benchmark state construction for an uncached token.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    manager = StateManagerMemory()
    loop = asyncio.new_event_loop()
    iteration = 0

    def setup():
        """Return a unique token for one cold measurement."""
        nonlocal iteration
        iteration += 1
        token = BaseStateToken(ident=f"cold-{iteration}", cls=PerformanceState)
        return ((token,), {})

    def get_state(token: BaseStateToken) -> PerformanceState:
        """Fetch a state through the async manager API.

        Returns:
            Managed state.
        """
        return get_performance_state(loop.run_until_complete(manager.get_state(token)))

    def teardown(token: BaseStateToken) -> None:
        """Purge the measured state."""
        manager._purge_token(token)  # pyright: ignore [reportPrivateUsage]

    # Isolate the registry so the measured cold construction instantiates only
    # PerformanceState's subtree, not every state in the collected session.
    with isolated_performance_registry():
        try:
            benchmark.pedantic(get_state, setup=setup, teardown=teardown)
        finally:
            loop.run_until_complete(manager.close())
            loop.close()


def test_state_manager_memory_warm_get(benchmark: BenchmarkFixture):
    """Benchmark state lookup for a cached token.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    manager = StateManagerMemory()
    loop = asyncio.new_event_loop()
    token = BaseStateToken(ident="warm", cls=PerformanceState)
    loop.run_until_complete(manager.get_state(token))

    try:
        state = benchmark(
            lambda: get_performance_state(
                loop.run_until_complete(manager.get_state(token))
            )
        )
        assert isinstance(state, PerformanceState)
    finally:
        loop.run_until_complete(manager.close())
        loop.close()


def test_state_manager_memory_modify(benchmark: BenchmarkFixture):
    """Benchmark lock acquisition, mutation, and release for one token.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    manager = StateManagerMemory()
    loop = asyncio.new_event_loop()
    token = BaseStateToken(ident="modify", cls=PerformanceState)

    async def modify() -> int:
        """Increment one state under the manager lock.

        Returns:
            Updated counter.
        """
        async with manager.modify_state_with_links(token) as root_state:
            state = get_performance_state(root_state)
            state.counter += 1
            return state.counter

    try:
        assert benchmark(lambda: loop.run_until_complete(modify())) > 0
    finally:
        loop.run_until_complete(manager.close())
        loop.close()


def test_state_manager_memory_read_only_modify(benchmark: BenchmarkFixture):
    """Benchmark a read-only lock context that should not produce a write.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    manager = StateManagerMemory()
    loop = asyncio.new_event_loop()
    token = BaseStateToken(ident="read-only", cls=PerformanceState)

    async def read_only() -> int:
        """Read one field under the manager lock.

        Returns:
            Current counter.
        """
        async with manager.modify_state_with_links(token) as root_state:
            state = get_performance_state(root_state)
            return state.counter

    try:
        assert benchmark(lambda: loop.run_until_complete(read_only())) == 0
    finally:
        loop.run_until_complete(manager.close())
        loop.close()
