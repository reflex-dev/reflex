"""Tests for workflow registration on the App and session-tree detachment."""

import asyncio
from typing import Any

import pytest
from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.state import State
from reflex.workflow.records import RunStatus
from reflex.workflow.store import MemoryRunStore


def _make_classes():
    class SessionCounter(rx.State):
        count: int = 0

        @rx.event
        def increment(self):
            self.count += 1

    class DetachedWorkflow(rx.State):
        __workflow__ = WorkflowConfig(id="app.detached")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            self.status = "done"

    return SessionCounter, DetachedWorkflow


def test_a_workflow_class_is_never_in_the_session_tree(forked_registration_context):
    """Detaching happens at class creation, so forgetting to register is safe.

    A durable handler must never be dispatchable from a browser. Tying that to
    app.add_workflow() would mean an omitted registration left the handlers
    exposed, which is exactly the line a code generator drops.
    """
    session_cls, workflow_cls = _make_classes()
    assert workflow_cls not in State.get_substates()

    app = rx.App()
    app.add_workflow(workflow_cls)

    assert workflow_cls not in State.get_substates()
    assert session_cls in State.get_substates()
    # Durable handlers are no longer reachable through the event registry.
    ctx = RegistrationContext.get()
    assert not any(
        workflow_cls in registered.states for registered in ctx.event_handlers.values()
    )
    assert app._workflow_runtime is not None
    assert [d.workflow_id for d in app._workflow_runtime.definitions] == [
        "app.detached"
    ]


def test_session_state_unaffected_by_detach(forked_registration_context):
    session_cls, workflow_cls = _make_classes()
    app = rx.App()
    app.add_workflow(workflow_cls)

    root = State(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    assert workflow_cls.get_name() not in root.substates
    session: Any = root.substates[session_cls.get_name()]
    session.increment()
    assert session.count == 1
    assert session.get_delta()


def test_add_workflow_idempotent_per_class(forked_registration_context):
    _, workflow_cls = _make_classes()
    app = rx.App()
    app.add_workflow(workflow_cls)
    app.add_workflow(workflow_cls)
    assert app._workflow_runtime is not None
    assert len(app._workflow_runtime.definitions) == 1


def test_add_workflow_rejects_duplicate_ids(forked_registration_context):
    class FirstOwner(rx.State):
        __workflow__ = WorkflowConfig(id="app.duplicate")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    class SecondOwner(rx.State):
        __workflow__ = WorkflowConfig(id="app.duplicate")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    app = rx.App()
    app.add_workflow(FirstOwner)
    with pytest.raises(WorkflowDefinitionError, match="already registered"):
        app.add_workflow(SecondOwner)


def test_add_workflow_rejects_plain_state(forked_registration_context):
    class NotAWorkflow(rx.State):
        pass

    app = rx.App()
    with pytest.raises(WorkflowDefinitionError, match="__workflow__"):
        app.add_workflow(NotAWorkflow)


async def test_runtime_lifespan_serves_default_namespace(forked_registration_context):
    _, workflow_cls = _make_classes()
    app = rx.App(workflow_store=MemoryRunStore())
    app.add_workflow(workflow_cls)
    assert app._workflow_runtime is not None

    async with app._workflow_runtime.running():
        result = await rx.workflows.start(workflow_cls.begin())
        assert result.disposition == "started"
        assert result.run_id is not None
        # The background worker processes the run without manual pumping.
        snapshot = None
        for _ in range(200):
            snapshot = await rx.workflows.get_run(result.run_id)
            assert snapshot is not None
            if snapshot.status is RunStatus.COMPLETED:
                break
            await asyncio.sleep(0.01)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "done"}
    # After shutdown the default runtime is cleared.
    with pytest.raises(Exception, match="No workflow runtime"):
        await rx.workflows.start(workflow_cls.begin())
