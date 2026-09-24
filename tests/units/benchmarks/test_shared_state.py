"""Regression tests for shared-state benchmark isolation and task cleanup."""

import asyncio
import subprocess
import sys
import textwrap

import pytest

from reflex.istate.shared import UPDATE_OTHER_CLIENT_TASKS
from tests.benchmarks.test_shared_state import _drain_fanout


def test_shared_benchmarks_preserve_other_states():
    """Collection and execution preserve ordinary state registrations and app."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
                import asyncio

                from reflex.app import App
                from reflex.state import State
                from reflex_base.registry import RegistrationContext

                class CounterState(State):
                    '''An ordinary counter with no optional dependencies.'''

                    counter: int = 0

                    def increment(self):
                        '''Increment the counter.'''
                        self.counter += 1

                context = RegistrationContext.get()
                original_app = App()
                states = context.base_states.copy()
                handlers = context.event_handlers.copy()
                substates = {key: value.copy() for key, value in context.base_state_substates.items() if value}
                dirty_substates = State._always_dirty_substates.copy()

                def assert_isolated():
                    '''Check that shared scenarios preserve the ordinary event path.'''
                    assert RegistrationContext.get() is context
                    assert context.app is original_app
                    assert context.base_states == states
                    assert context.event_handlers == handlers
                    assert {key: value for key, value in context.base_state_substates.items() if value} == substates
                    assert State.backend_vars['_reflex_internal_links'] is None
                    assert State._always_dirty_substates == dirty_substates

                from tests.benchmarks import test_shared_state as shared
                assert_isolated()

                async def exercise():
                    '''Run every shared scenario before modifying the ordinary counter.'''
                    for scenario in shared.SCENARIOS.values():
                        async with shared._shared_state_app(scenario, lambda *_: None) as harness:
                            await harness.counter_events()
                            await harness.modify_state()
                        assert_isolated()
                    root = State.get_root_state()(_reflex_internal_init=True)
                    counter = root.get_substate(CounterState.get_full_name().split('.'))
                    counter.increment()
                    assert counter.counter == 1
                    assert root._reflex_internal_links is None
                    assert_isolated()

                asyncio.run(exercise())
            """),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def test_drain_fanout_times_out():
    """A stalled update fails promptly and does not leak into the next scenario."""
    stalled = asyncio.create_task(asyncio.Event().wait())
    UPDATE_OTHER_CLIENT_TASKS.add(stalled)
    stalled.add_done_callback(UPDATE_OTHER_CLIENT_TASKS.discard)
    try:
        with pytest.raises(asyncio.TimeoutError):
            await _drain_fanout(timeout=0.01)
        assert stalled.cancelled()
        assert not UPDATE_OTHER_CLIENT_TASKS
    finally:
        stalled.cancel()
        await asyncio.gather(stalled, return_exceptions=True)
