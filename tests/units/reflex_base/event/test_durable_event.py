"""Tests for the durable options of the ``@rx.event`` decorator."""

import pytest
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import Retry, get_durable_config, manual

import reflex as rx


def test_durable_marker_attached(forked_registration_context):
    class MarkerWorkflow(rx.State):
        @rx.event(
            id="begin",
            durable=True,
            trigger=manual(),
            retry=Retry(max_attempts=2),
            timeout="10s",
            effect="read",
            queue="integrations",
        )
        async def begin(self):
            pass

    config = get_durable_config(MarkerWorkflow.event_handlers["begin"].fn)
    assert config is not None
    assert config.id == "begin"
    assert config.effect == "read"
    assert config.timeout == pytest.approx(10.0)
    assert config.queue == "integrations"
    assert config.retry is not None
    assert config.retry.max_attempts == 2


def test_bare_event_has_no_marker(forked_registration_context):
    class PlainState(rx.State):
        @rx.event
        def tick(self):
            pass

    assert get_durable_config(PlainState.event_handlers["tick"].fn) is None


def test_durable_options_without_durable_raise():
    with pytest.raises(WorkflowDefinitionError, match="requires durable=True"):

        @rx.event(effect="none")
        def handler(self):
            pass


def test_durable_background_mutually_exclusive():
    with pytest.raises(WorkflowDefinitionError, match="mutually exclusive"):

        @rx.event(durable=True, effect="none", background=True)
        def handler(self):
            pass


def test_durable_browser_actions_rejected():
    with pytest.raises(WorkflowDefinitionError, match="browser event actions"):

        @rx.event(durable=True, effect="none", throttle=100)
        def handler(self):
            pass


def test_durable_generator_rejected():
    with pytest.raises(WorkflowDefinitionError, match="generators"):

        @rx.event(durable=True, effect="none")
        def handler(self):
            yield


def test_durable_async_generator_rejected():
    with pytest.raises(WorkflowDefinitionError, match="generators"):

        @rx.event(durable=True, effect="none")
        async def handler(self):  # noqa: RUF029
            yield


def test_durable_hook_accepts_function_reference(forked_registration_context):
    class HookWorkflow(rx.State):
        @rx.event(durable=True, effect="none")
        def cleanup(self):
            pass

        @rx.event(durable=True, effect="read", on_failure=cleanup)
        def risky(self):
            pass

    config = get_durable_config(HookWorkflow.event_handlers["risky"].fn)
    assert config is not None
    assert config.on_failure == "cleanup"
