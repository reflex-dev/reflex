"""Exercise the published handlers; fake services do not establish durability."""

import asyncio
import re
import sys
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import reflex as rx
from reflex.compiler.compiler import compile_page
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import BaseStateToken
from reflex.istate.proxy import StateProxy
from reflex.istate.shared import SharedState, SharedStateBaseInternal
from reflex_base.event.context import EventContext
from reflex_base.registry import RegistrationContext

GUIDE = Path(__file__).resolve().parents[2] / "hosting/scaling.md"


def run_async(test):
    """Run an async case with core pytest, preserving fixture/parameter discovery."""

    @wraps(test)
    def run(*args, **kwargs):
        """Execute one case in its own event loop."""
        return asyncio.run(test(*args, **kwargs))

    return run


class ReportServiceError(Exception):
    """The adapter could not confirm the requested operation."""


class ReportService:
    """A deterministic adapter double, never a production job store."""

    def __init__(self):
        self.jobs = {}
        self.outbox = []
        self.calls = []
        self.fail_accept = False
        self.lose_response = False
        self.pause = ""
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def boundary(self, operation):
        """Assert service I/O happens after releasing the real state lock."""
        manager = EventContext.get().state_manager
        assert isinstance(manager, StateManagerMemory)
        assert not any(lock.locked() for lock in manager._states_locks.values())
        if self.pause == operation:
            self.started.set()
            await self.release.wait()

    async def accept_report(self, owner, request_key, report):
        """Emulate the documented owner-scoped acceptance contract."""
        await self.boundary("accept")
        self.calls.append(("accept", owner, request_key, report))
        if self.fail_accept:
            raise ReportServiceError
        key = (owner, request_key)
        if key in self.jobs:
            if self.jobs[key].report != report:
                raise ReportServiceError
        else:
            self.jobs[key] = SimpleNamespace(
                id=uuid4().hex, request_key=request_key, report=report, status="queued"
            )
            self.outbox.append(self.jobs[key].id)
        if self.lose_response:
            raise ReportServiceError
        return self.jobs[key]

    async def read_report(self, owner, job_id, request_key=""):
        """Return only the owner's selected or latest job."""
        await self.boundary("read")
        self.calls.append(("read", owner, job_id, request_key))
        owned = [job for (who, _), job in self.jobs.items() if who == owner]
        if job_id:
            return next((job for job in owned if job.id == job_id), None)
        if request_key:
            return self.jobs.get((owner, request_key))
        return owned[-1] if owned else None


@pytest.fixture
def example(monkeypatch):
    """Import exactly the code a reader copies, with app-owned adapters."""
    source = GUIDE.read_text()
    blocks = re.findall(r"^```python\n(.*?)^```", source, re.MULTILINE | re.DOTALL)
    matches = [block for block in blocks if "class ReportState(rx.State):" in block]
    assert len(matches) == 1
    with RegistrationContext.get().fork() as context:
        context._set_config(rx.Config(app_name="scaling_example_test"))
        if SharedStateBaseInternal.get_full_name() not in context.base_states:
            RegistrationContext.register_base_state(SharedStateBaseInternal)
        auth = ModuleType("report_app.auth")
        monkeypatch.setitem(sys.modules, auth.__name__, auth)
        exec(
            "import reflex as rx\n"
            "class AuthState(rx.State):\n"
            "    _owner_id: str = ''\n"
            "    _session_revision: int = 0\n",
            auth.__dict__,
        )
        service = ReportService()
        adapter = ModuleType("report_app.reports")
        adapter.__dict__.update(
            accept_report=service.accept_report,
            read_report=service.read_report,
            ReportServiceError=ReportServiceError,
        )
        monkeypatch.setitem(sys.modules, adapter.__name__, adapter)
        module = ModuleType(f"scaling_report_example_{uuid4().hex}")
        monkeypatch.setitem(sys.modules, module.__name__, module)
        exec(matches[0], module.__dict__)
        assert issubclass(module.ReportState, rx.State)
        assert module.ReportState.event_handlers["sync_report"].is_background
        yield SimpleNamespace(module=module, service=service, auth=auth.AuthState)


def test_report_panel_compiles_frontend_event_and_state_bindings(example):
    """Compile the copied UI itself, including real event arguments and Vars."""
    _, code = compile_page("report-example", example.module.report_panel())
    assert "export default" in code
    assert "sync_report" in code and "new_report" in code
    assert "job_id" in code and "status" in code


@asynccontextmanager
async def session(example, owner="alice"):
    """Use real Reflex state, StateProxy and state-manager lock semantics."""
    manager = StateManagerMemory()
    token = uuid4().hex
    try:
        with EventContext(token=token, state_manager=manager, enqueue_impl=AsyncMock()):
            cls = example.module.ReportState
            root = await manager.get_state(BaseStateToken(ident=token, cls=cls))
            state = root.get_substate(cls.get_full_name().split("."))
            proxy = StateProxy(state)
            async with proxy:
                auth = await proxy.get_state(example.auth)
                auth._owner_id = owner
            yield proxy
    finally:
        await manager.close()


async def start_report(example, state):
    """Follow the explicit New report, then Submit UI flow."""
    async with state:
        await example.module.ReportState.new_report.fn(state)
    await example.module.ReportState.sync_report.fn(state, True)


@run_async
async def test_session_survives_shared_state_in_another_context(example):
    """A prior shared-state demo must not break this isolated app's state locks."""
    with RegistrationContext.get().fork():

        class PriorSharedState(SharedState):
            """Model a shared-state demo evaluated in a separate app context."""

            value: int = 0

    async with session(example) as state:
        await start_report(example, state)
        assert state.job_id and state.status == "queued"


@run_async
@pytest.mark.parametrize("next_owner", ["alice", "bob"])
@pytest.mark.parametrize("lost_response", [False, True])
async def test_direct_submit_after_login_recovers_without_accepting_a_new_job(
    example, next_owner, lost_response
):
    """Submit after an authentication change recovers even a lost acceptance."""
    async with session(example) as state:
        example.service.lose_response = lost_response
        await start_report(example, state)
        expected = example.service.jobs[("alice", state._request_key)]
        if next_owner == "bob":
            async with session(example, "bob") as other:
                await start_report(example, other)
                expected = example.service.jobs[("bob", other._request_key)]
        example.service.lose_response = False
        before = len(example.service.outbox)
        async with state:
            auth = await state.get_state(example.auth)
            auth._owner_id = next_owner
            auth._session_revision += 2
            state.job_id = state.status = state.error = ""
        await example.module.ReportState.sync_report.fn(state, True)
        assert example.service.calls[-1] == ("read", next_owner, "", "")
        assert (
            state.job_id == expected.id and state._request_key == expected.request_key
        )
        assert len(example.service.jobs) == len(example.service.outbox) == before
        await example.module.ReportState.sync_report.fn(state, True)
        assert len(example.service.jobs) == len(example.service.outbox) == before


@run_async
@pytest.mark.parametrize("existing_report", [False, True])
async def test_fresh_state_submit_requires_explicit_new_or_recovers_existing(
    example, existing_report
):
    """Without a selected key, Submit never starts an unrequested new report."""
    expected = None
    if existing_report:
        async with session(example) as previous:
            await start_report(example, previous)
            expected = example.service.jobs[("alice", previous._request_key)]
    before = len(example.service.outbox)
    async with session(example) as state:
        await example.module.ReportState.sync_report.fn(state, True)
        assert example.service.calls[-1] == ("read", "alice", "", "")
        assert len(example.service.jobs) == len(example.service.outbox) == before
        if expected:
            assert state.job_id == expected.id
            assert state._request_key == expected.request_key and not state.error
        else:
            assert not state.job_id and not state._request_key
            assert state.error == "Choose New report to start a report."
        await example.module.ReportState.sync_report.fn(state, True)
        assert len(example.service.jobs) == len(example.service.outbox) == before
        await start_report(example, state)
        assert len(example.service.jobs) == len(example.service.outbox) == before + 1


@run_async
@pytest.mark.parametrize("lost_response", [False, True])
async def test_retries_reuse_the_request_key_and_committed_job(example, lost_response):
    """A repeated submission, including lost acknowledgement, keeps one job."""
    async with session(example) as state:
        example.service.lose_response = lost_response
        await start_report(example, state)
        request_key = state._request_key
        example.service.lose_response = False
        await example.module.ReportState.sync_report.fn(state, True)
        assert state._request_key == request_key
        assert len(example.service.jobs) == len(example.service.outbox) == 1
        assert state.job_id == example.service.outbox[0]
        assert state.status == "queued" and not state.error
        async with state:
            await example.module.ReportState.new_report.fn(state)
        assert state._request_key != request_key
        assert not state.job_id and not state.status


@run_async
async def test_failed_accept_does_not_claim_an_accepted_job(example):
    """A failed acceptance leaves a retryable key without a job ID/status."""
    example.service.fail_accept = True
    async with session(example) as state:
        await start_report(example, state)
        assert state._request_key and state.error
        assert not state.job_id and not state.status
        assert not example.service.jobs and not example.service.outbox


@run_async
async def test_status_read_uses_owner_and_selected_job_id(example):
    """Possessing another owner's job ID does not return its status."""
    async with session(example) as alice:
        await start_report(example, alice)
        job_id = alice.job_id
        await example.module.ReportState.sync_report.fn(alice)
        assert example.service.calls[-1] == (
            "read",
            "alice",
            job_id,
            alice._request_key,
        )
    async with session(example, "bob") as bob:
        await example.module.ReportState.sync_report.fn(bob)
        async with bob:
            bob.job_id = job_id
        await example.module.ReportState.sync_report.fn(bob)
        assert example.service.calls[-1] == ("read", "bob", job_id, "")
        assert not bob.job_id and not bob.status


@run_async
@pytest.mark.parametrize("operation", ["submit", "read"])
@pytest.mark.parametrize("change", ["logout", "same_owner_relogin", "selection"])
async def test_stale_service_response_does_not_update_the_ui(
    example, operation, change
):
    """Responses cannot overwrite a changed authentication or selection."""
    async with session(example) as state:
        async with state:
            await example.module.ReportState.new_report.fn(state)
        if operation == "read":
            await example.module.ReportState.sync_report.fn(state, True)
        example.service.pause = "accept" if operation == "submit" else "read"
        task = asyncio.create_task(
            example.module.ReportState.sync_report.fn(state, operation == "submit")
        )
        await asyncio.wait_for(example.service.started.wait(), 2)
        async with state:
            if change == "selection":
                await example.module.ReportState.new_report.fn(state)
            else:
                auth = await state.get_state(example.auth)
                auth._session_revision += 1
                auth._owner_id = "" if change == "logout" else "alice"
                state.job_id = state.status = state.error = ""
        example.service.release.set()
        await asyncio.wait_for(task, 2)
        assert not state.job_id and not state.status and not state.error


@run_async
async def test_fresh_state_recovers_job_and_retry_key(example):
    """A new session uses an authorized durable lookup, not old UI state."""
    async with session(example) as original:
        await start_report(example, original)
        job_id, request_key = original.job_id, original._request_key
    async with session(example) as fresh:
        assert not fresh.job_id and not fresh._request_key
        await example.module.ReportState.sync_report.fn(fresh)
        assert example.service.calls[-1] == ("read", "alice", "", "")
        assert fresh.job_id == job_id and fresh._request_key == request_key
        await example.module.ReportState.sync_report.fn(fresh, True)
        assert len(example.service.jobs) == len(example.service.outbox) == 1


@run_async
@pytest.mark.parametrize("next_owner", ["alice", "bob"])
@pytest.mark.parametrize("clear_ui", [False, True])
async def test_authentication_change_recovers_without_previous_session_selectors(
    example, next_owner, clear_ui
):
    """An account switch or relogin cannot reuse the old report selection."""
    async with session(example) as state:
        await start_report(example, state)
        async with session(example, next_owner) as other:
            await start_report(example, other)
            latest_id, latest_key = other.job_id, other._request_key
        async with state:
            auth = await state.get_state(example.auth)
            auth._owner_id = next_owner
            auth._session_revision += 2  # Logout and login between report events.
            state.error = "Previous session error"
            if clear_ui:
                state.job_id = state.status = state.error = ""
        example.service.pause = "read"
        task = asyncio.create_task(example.module.ReportState.sync_report.fn(state))
        await asyncio.wait_for(example.service.started.wait(), 2)
        assert not state.job_id and not state.status and not state.error
        assert not state._request_key
        example.service.release.set()
        await asyncio.wait_for(task, 2)
        assert example.service.calls[-1] == ("read", next_owner, "", "")
        assert state.job_id == latest_id and state._request_key == latest_key
        assert state.status == "queued" and not state.error
        await example.module.ReportState.sync_report.fn(state, True)
        assert len(example.service.jobs) == len(example.service.outbox) == 2


@run_async
@pytest.mark.parametrize("account_change", [False, True])
async def test_new_report_binds_identity_before_first_refresh(example, account_change):
    """An explicit new selection survives initial or post-login recovery."""
    async with session(example, "bob") as previous:
        await start_report(example, previous)
        older_id = previous.job_id
    async with session(example, "alice" if account_change else "bob") as state:
        if account_change:
            await start_report(example, state)
        async with state:
            if account_change:
                auth = await state.get_state(example.auth)
                auth._owner_id = "bob"
                auth._session_revision += 2
            await example.module.ReportState.new_report.fn(state)
        new_key = state._request_key
        await example.module.ReportState.sync_report.fn(state)
        assert example.service.calls[-1] == ("read", "bob", "", new_key)
        assert state._request_key == new_key and not state.job_id
        await example.module.ReportState.sync_report.fn(state, True)
        assert state._request_key == new_key and state.job_id != older_id


@run_async
async def test_logout_clears_selection_without_calling_job_services(example):
    """Signed-out refresh removes private selectors as well as visible fields."""
    async with session(example) as state:
        await start_report(example, state)
        calls = len(example.service.calls)
        async with state:
            auth = await state.get_state(example.auth)
            auth._owner_id = ""
            auth._session_revision += 1
            state.error = "Previous session error"
        await example.module.ReportState.sync_report.fn(state)
        assert not state.job_id and not state.status and not state.error
        assert not state._request_key
        assert len(example.service.calls) == calls


@run_async
@pytest.mark.parametrize("pending_submit", [False, True])
async def test_refresh_does_not_replace_a_new_request_with_an_older_job(
    example, pending_submit
):
    """Refresh keeps a new request's key even before its acceptance returns."""
    async with session(example) as state:
        await start_report(example, state)
        old_job = state.job_id
        async with state:
            await example.module.ReportState.new_report.fn(state)
        new_key = state._request_key
        task = None
        if pending_submit:
            example.service.pause = "accept"
            task = asyncio.create_task(
                example.module.ReportState.sync_report.fn(state, True)
            )
            await asyncio.wait_for(example.service.started.wait(), 2)
        await example.module.ReportState.sync_report.fn(state)
        assert state._request_key == new_key
        assert not state.job_id and not state.status
        if task is not None:
            example.service.release.set()
            await asyncio.wait_for(task, 2)
            assert not state.job_id
        example.service.pause = ""
        await example.module.ReportState.sync_report.fn(state, True)
        assert state._request_key == new_key and state.job_id != old_job
        assert len(example.service.jobs) == len(example.service.outbox) == 2


@run_async
async def test_signed_out_state_does_not_call_job_services(example):
    """An absent trusted identity prevents both reads and submissions."""
    async with session(example, "") as state:
        await example.module.ReportState.sync_report.fn(state, True)
        await example.module.ReportState.sync_report.fn(state)
        assert not example.service.calls
        assert not state.job_id and not state.status
