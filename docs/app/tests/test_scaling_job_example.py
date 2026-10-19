"""Exercise the published handlers; fake services do not establish durability."""

import asyncio
import re
import sys
from contextlib import asynccontextmanager
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
from reflex_base.event.context import EventContext
from reflex_base.registry import RegistrationContext

GUIDE = Path(__file__).resolve().parents[2] / "hosting/scaling.md"


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
    with RegistrationContext(_config=rx.Config(app_name="scaling_example_test")):
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


@pytest.mark.asyncio
@pytest.mark.parametrize("lost_response", [False, True])
async def test_retries_reuse_the_request_key_and_committed_job(example, lost_response):
    """A repeated submission, including lost acknowledgement, keeps one job."""
    async with session(example) as state:
        example.service.lose_response = lost_response
        await example.module.ReportState.sync_report.fn(state, True)
        request_key = state._request_key
        example.service.lose_response = False
        await example.module.ReportState.sync_report.fn(state, True)
        assert state._request_key == request_key
        assert len(example.service.jobs) == len(example.service.outbox) == 1
        assert state.job_id == example.service.outbox[0]
        assert state.status == "queued" and not state.error
        async with state:
            example.module.ReportState.new_report.fn(state)
        assert state._request_key != request_key
        assert not state.job_id and not state.status


@pytest.mark.asyncio
async def test_failed_accept_does_not_claim_an_accepted_job(example):
    """A failed acceptance leaves a retryable key without a job ID/status."""
    example.service.fail_accept = True
    async with session(example) as state:
        await example.module.ReportState.sync_report.fn(state, True)
        assert state._request_key and state.error
        assert not state.job_id and not state.status
        assert not example.service.jobs and not example.service.outbox


@pytest.mark.asyncio
async def test_status_read_uses_owner_and_selected_job_id(example):
    """Possessing another owner's job ID does not return its status."""
    async with session(example) as alice:
        await example.module.ReportState.sync_report.fn(alice, True)
        job_id = alice.job_id
        await example.module.ReportState.sync_report.fn(alice)
        assert example.service.calls[-1] == (
            "read",
            "alice",
            job_id,
            alice._request_key,
        )
    async with session(example, "bob") as bob:
        async with bob:
            bob.job_id = job_id
        await example.module.ReportState.sync_report.fn(bob)
        assert example.service.calls[-1] == ("read", "bob", job_id, "")
        assert not bob.job_id and not bob.status


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["submit", "read"])
@pytest.mark.parametrize("change", ["logout", "same_owner_relogin", "selection"])
async def test_stale_service_response_does_not_update_the_ui(
    example, operation, change
):
    """Responses cannot overwrite a changed authentication or selection."""
    async with session(example) as state:
        if operation == "read":
            await example.module.ReportState.sync_report.fn(state, True)
        example.service.pause = "accept" if operation == "submit" else "read"
        task = asyncio.create_task(
            example.module.ReportState.sync_report.fn(state, operation == "submit")
        )
        await asyncio.wait_for(example.service.started.wait(), 2)
        async with state:
            if change == "selection":
                example.module.ReportState.new_report.fn(state)
            else:
                auth = await state.get_state(example.auth)
                auth._session_revision += 1
                auth._owner_id = "" if change == "logout" else "alice"
                state.job_id = state.status = state.error = ""
        example.service.release.set()
        await asyncio.wait_for(task, 2)
        assert not state.job_id and not state.status and not state.error


@pytest.mark.asyncio
async def test_fresh_state_recovers_job_and_retry_key(example):
    """A new session uses an authorized durable lookup, not old UI state."""
    async with session(example) as original:
        await example.module.ReportState.sync_report.fn(original, True)
        job_id, request_key = original.job_id, original._request_key
    async with session(example) as fresh:
        assert not fresh.job_id and not fresh._request_key
        await example.module.ReportState.sync_report.fn(fresh)
        assert example.service.calls[-1] == ("read", "alice", "", "")
        assert fresh.job_id == job_id and fresh._request_key == request_key
        await example.module.ReportState.sync_report.fn(fresh, True)
        assert len(example.service.jobs) == len(example.service.outbox) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("pending_submit", [False, True])
async def test_refresh_does_not_replace_a_new_request_with_an_older_job(
    example, pending_submit
):
    """Refresh keeps a new request's key even before its acceptance returns."""
    async with session(example) as state:
        await example.module.ReportState.sync_report.fn(state, True)
        old_job = state.job_id
        async with state:
            example.module.ReportState.new_report.fn(state)
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


@pytest.mark.asyncio
async def test_signed_out_state_does_not_call_job_services(example):
    """An absent trusted identity prevents both reads and submissions."""
    async with session(example, "") as state:
        await example.module.ReportState.sync_report.fn(state, True)
        await example.module.ReportState.sync_report.fn(state)
        assert not example.service.calls
        assert not state.job_id and not state.status
