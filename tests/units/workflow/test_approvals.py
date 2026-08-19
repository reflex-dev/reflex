"""Tests for signed approval links.

An approval link is a bearer credential sent by email, so most of these are
about what a link must *not* do: decide anything on a GET, survive an edit,
outlive its expiry, or work twice.
"""

import json
import time

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import WorkflowConfig, manual
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

import reflex as rx
from reflex.workflow.approvals import (
    APPROVAL_ROUTE,
    SECRET_ENV,
    _b64,
    approval_endpoint,
)
from reflex.workflow.context import RunContext, bind_run, unbind_run
from reflex.workflow.records import RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import MemoryRunStore

SECRET = "test-approval-secret"


class Verdict(BaseModel):
    """A typed decision payload."""

    approved: bool
    by: str


LINKS: dict[str, str] = {}


class Expense(rx.State):
    """An expense that waits for a manager's decision."""

    __workflow__ = WorkflowConfig(id="approval.expense")

    decided = rx.Signal(dict)
    amount: int = 0
    outcome: str = ""

    @rx.event(durable=True, trigger=manual(), effect="none")
    def submit(self, amount: int):
        """Send the manager two links and wait.

        Args:
            amount: The amount claimed.

        Returns:
            A wait on the decision channel.
        """
        self.amount = amount
        LINKS["approve"] = rx.approval_link(Expense.decided({"ok": True}))
        LINKS["reject"] = rx.approval_link(Expense.decided({"ok": False}))
        return rx.wait_for(
            Expense.decided,
            then=Expense.record,
            timeout="7d",
            on_timeout=Expense.lapse,
        )

    @rx.event(durable=True, effect="none")
    def lapse(self):
        """Nobody answered in time.

        Returns:
            Completion.
        """
        self.outcome = "lapsed"
        return rx.complete(result={"outcome": self.outcome})

    @rx.event(durable=True, effect="none")
    def record(self, decision: dict):
        """Record what the manager said.

        Args:
            decision: The delivered payload.

        Returns:
            Completion.
        """
        self.outcome = "approved" if decision["ok"] else "rejected"
        return rx.complete(result={"outcome": self.outcome})


@pytest.fixture
def approving(monkeypatch, forked_registration_context):
    """A started run waiting on a decision, with its links built.

    Args:
        monkeypatch: Used to set the signing secret.
        forked_registration_context: Isolates state registration.

    Returns:
        The runtime and a Starlette app serving the approval endpoint.
    """
    monkeypatch.setenv(SECRET_ENV, SECRET)
    LINKS.clear()
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Expense)
    app = Starlette(
        routes=[
            Route(APPROVAL_ROUTE, approval_endpoint(runtime), methods=["GET", "POST"])
        ]
    )
    return runtime, app


async def _start(runtime) -> str:
    """Start one expense run and let it reach its wait.

    Args:
        runtime: The runtime to start it on.

    Returns:
        The run id.
    """
    await runtime.startup(start_worker=False)
    result = await runtime.kernel.start(Expense.submit(120))
    await runtime.kernel.run_until_idle()
    assert result.run_id is not None
    return result.run_id


async def test_a_get_never_decides_anything(approving):
    """Fetching the link must not record a decision.

    Mail clients and link scanners fetch URLs before a person sees them, so a
    link that approves on GET approves itself in transit.
    """
    runtime, app = approving
    run_id = await _start(runtime)

    with TestClient(app) as client:
        response = client.get(LINKS["approve"])
    assert response.status_code == 200
    assert "Confirm" in response.text

    snapshot = await runtime.kernel.get_run(run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.WAITING
    assert snapshot.state["outcome"] == ""


async def test_a_post_records_the_decision(approving):
    """Submitting the confirmation delivers the payload the link names."""
    runtime, app = approving
    run_id = await _start(runtime)

    with TestClient(app) as client:
        response = client.post(LINKS["approve"])
    assert response.status_code == 200
    assert "recorded" in response.text.lower()

    await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.COMPLETED
    assert snapshot.result == {"outcome": "approved"}


async def test_the_reject_link_carries_its_own_payload(approving):
    """Each choice is a separate link, so the URL fixes the answer."""
    runtime, app = approving
    run_id = await _start(runtime)

    with TestClient(app) as client:
        assert client.post(LINKS["reject"]).status_code == 200

    await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(run_id)
    assert snapshot is not None
    assert snapshot.result == {"outcome": "rejected"}


async def test_a_spent_link_cannot_be_spent_again(approving):
    """Replaying a link is a no-op, not a second decision."""
    runtime, app = approving
    await _start(runtime)

    with TestClient(app) as client:
        assert client.post(LINKS["approve"]).status_code == 200
        second = client.post(LINKS["approve"])
    assert "already been used" in second.text.lower()


async def test_the_losing_link_cannot_overturn_the_decision(approving):
    """Once approved, the reject link finds nothing left to decide."""
    runtime, app = approving
    run_id = await _start(runtime)

    with TestClient(app) as client:
        assert client.post(LINKS["approve"]).status_code == 200
        await runtime.kernel.run_until_idle()
        late = client.post(LINKS["reject"])

    assert late.status_code == 409
    snapshot = await runtime.kernel.get_run(run_id)
    assert snapshot is not None
    assert snapshot.result == {"outcome": "approved"}


async def test_an_edited_token_is_refused(approving):
    """Changing any claim invalidates the signature.

    The interesting attack is not a random string: it is a valid link whose
    payload has been flipped, which is why the signature covers the claims and
    not just the run id.
    """
    runtime, app = approving
    run_id = await _start(runtime)

    encoded, signature = LINKS["reject"].rsplit("/", 1)[-1].split(".")
    claims = json.loads(
        __import__("base64").urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    )
    claims["p"] = {"ok": True}
    forged = _b64(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())

    with TestClient(app) as client:
        response = client.post(f"/_workflow/approve/{forged}.{signature}")
    assert response.status_code == 400

    snapshot = await runtime.kernel.get_run(run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.WAITING


async def test_a_token_signed_with_another_secret_is_refused(approving, monkeypatch):
    """A link minted by a different deployment does not work here."""
    runtime, app = approving
    await _start(runtime)
    stolen = LINKS["approve"]

    monkeypatch.setenv(SECRET_ENV, "a-different-secret")
    with TestClient(app) as client:
        assert client.post(stolen).status_code == 400


async def test_an_expired_token_is_refused(approving, monkeypatch):
    """A link stops working once its expiry passes."""
    runtime, app = approving
    await _start(runtime)

    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 8 * 86400)
    with TestClient(app) as client:
        response = client.post(LINKS["approve"])
    assert response.status_code == 400


async def test_a_malformed_token_is_refused(approving):
    """Garbage in the path is a clean rejection, not a traceback."""
    runtime, app = approving
    await _start(runtime)

    with TestClient(app) as client:
        for token in ("", "nonsense", "a.b.c", "!!!.###", "x" * 5000):
            assert client.post(f"/_workflow/approve/{token}").status_code in (
                400,
                404,
            )


def test_links_refuse_to_sign_without_a_secret(monkeypatch):
    """There is no default secret, and no silent fallback to one."""
    monkeypatch.delenv(SECRET_ENV, raising=False)
    token = bind_run(
        RunContext(
            run_id="r1",
            workflow_id="approval.expense",
            ordinal=0,
            handler_id="submit",
            attempt=1,
            epoch=1,
        )
    )
    try:
        with pytest.raises(WorkflowRuntimeError, match=SECRET_ENV):
            rx.approval_link(Expense.decided({"ok": True}))
    finally:
        unbind_run(token)


def test_links_refuse_to_build_outside_a_handler(monkeypatch):
    """A link addresses one run, so there has to be one."""
    monkeypatch.setenv(SECRET_ENV, SECRET)
    with pytest.raises(WorkflowRuntimeError, match="durable"):
        rx.approval_link(Expense.decided({"ok": True}))


async def test_json_callers_get_json(approving):
    """An API client can spend a link without parsing HTML."""
    runtime, app = approving
    await _start(runtime)

    with TestClient(app) as client:
        headers = {"accept": "application/json"}
        confirm = client.get(LINKS["approve"], headers=headers)
        assert confirm.json()["status"] == "confirm"
        spent = client.post(LINKS["approve"], headers=headers)
    assert spent.json()["status"] == "resolved"


async def test_base_url_prefixes_an_absolute_link(approving, monkeypatch):
    """An emailed link needs an origin, not a path."""
    runtime, _ = approving
    await runtime.startup(start_worker=False)

    token = bind_run(
        RunContext(
            run_id="r1",
            workflow_id="approval.expense",
            ordinal=0,
            handler_id="submit",
            attempt=1,
            epoch=1,
        )
    )
    try:
        link = rx.approval_link(
            Expense.decided({"ok": True}), base_url="https://app.example.com/"
        )
    finally:
        unbind_run(token)
    assert link.startswith("https://app.example.com/_workflow/approve/")


async def test_a_server_without_a_secret_says_so(approving, monkeypatch):
    """A misconfigured server must not look like an expired link.

    Reporting "expired" would send an operator looking for a data problem when
    the real one is a missing environment variable.
    """
    runtime, app = approving
    await _start(runtime)
    link = LINKS["approve"]

    monkeypatch.delenv(SECRET_ENV, raising=False)
    with TestClient(app) as client:
        response = client.post(link, headers={"accept": "application/json"})
    assert response.status_code == 500
    assert "not configured" in response.json()["error"]


class Typed(rx.State):
    """A channel declared with a model, which is the common case."""

    __workflow__ = WorkflowConfig(id="approval.typed")

    review = rx.Signal(Verdict)
    outcome: str = ""

    @rx.event(durable=True, trigger=manual(), effect="none")
    def ask(self):
        """Build a link carrying a model, then wait.

        Returns:
            A wait on the review channel.
        """
        LINKS["typed"] = rx.approval_link(
            Typed.review(Verdict(approved=True, by="ada"))
        )
        return rx.wait_for(
            Typed.review, then=Typed.decide, timeout="3d", on_timeout=Typed.lapse
        )

    @rx.event(durable=True, effect="none")
    def decide(self, verdict: Verdict):
        """Record a typed verdict.

        Args:
            verdict: The delivered decision, rebuilt as its model.

        Returns:
            Completion.
        """
        self.outcome = f"{verdict.by}:{verdict.approved}"
        return rx.complete(result={"outcome": self.outcome})

    @rx.event(durable=True, effect="none")
    def lapse(self):
        """Nobody answered."""


async def test_a_link_can_carry_a_model_payload(
    monkeypatch, forked_registration_context
):
    """A channel declared with a model must survive the round trip.

    The token crosses a network boundary as JSON, so a pydantic payload has to
    be reduced on the way out and rebuilt on the way in. Passing the model
    straight into the token fails to serialize -- and every realistic channel
    is typed, so a dict-only test would never notice.
    """
    monkeypatch.setenv(SECRET_ENV, SECRET)
    LINKS.clear()
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(Typed)
    app = Starlette(
        routes=[
            Route(APPROVAL_ROUTE, approval_endpoint(runtime), methods=["GET", "POST"])
        ]
    )
    await runtime.startup(start_worker=False)
    result = await runtime.kernel.start(Typed.ask)
    await runtime.kernel.run_until_idle()
    assert result.run_id is not None

    with TestClient(app) as client:
        assert client.post(LINKS["typed"]).status_code == 200
    await runtime.kernel.run_until_idle()

    snapshot = await runtime.kernel.get_run(result.run_id)
    assert snapshot is not None
    assert snapshot.result == {"outcome": "ada:True"}
    await runtime.shutdown()


@pytest.mark.parametrize(
    ("name", "expiry"),
    [("infinite", float("inf")), ("not-a-number", float("nan"))],
)
def test_a_token_can_never_be_immortal(monkeypatch, name, expiry):
    """An expiry that is not a finite number must not pass the check.

    NaN loses every comparison, so `nan < now` is False and the deadline
    silently never arrives; infinity does it outright. Signing means only our
    own bug could mint such a token, which is exactly why the verifier must
    not assume it never will.
    """
    import json

    from reflex.workflow.approvals import _b64, _sign, decode_token

    monkeypatch.setenv(SECRET_ENV, SECRET)
    claims = {
        "r": "run1",
        "c": "decided",
        "p": {"ok": True},
        "k": "key",
        "e": expiry,
    }
    body = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    with pytest.raises(WorkflowRuntimeError, match="not valid"):
        decode_token(f"{_b64(body)}.{_sign(body)}")


def test_a_token_missing_a_claim_is_refused(monkeypatch):
    """Every claim the delivery depends on must be present and signed."""
    import json

    from reflex.workflow.approvals import _b64, _sign, decode_token

    monkeypatch.setenv(SECRET_ENV, SECRET)
    complete = {
        "r": "run1",
        "c": "decided",
        "p": {"ok": True},
        "k": "key",
        "e": time.time() + 60,
    }
    for dropped in complete:
        claims = {key: value for key, value in complete.items() if key != dropped}
        body = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
        with pytest.raises(WorkflowRuntimeError, match="not valid"):
            decode_token(f"{_b64(body)}.{_sign(body)}")


TWO_STAGE_LINKS: dict[str, str] = {}
_NOW = [1_000_000.0]


class Lapsing(rx.State):
    """A question that lapses, then asks a different one on the same channel."""

    __workflow__ = WorkflowConfig(id="approval.lapsing")

    decided = rx.Signal(dict)

    @rx.event(durable=True, trigger=manual(), effect="none")
    def submit(self):
        """Ask, with links nobody will click.

        Returns:
            The first wait.
        """
        TWO_STAGE_LINKS["one_approve"] = rx.approval_link(Lapsing.decided({"ok": True}))
        return rx.wait_for(
            Lapsing.decided,
            then=Lapsing.first,
            timeout="7d",
            on_timeout=Lapsing.ask_again,
        )

    @rx.event(durable=True, effect="none")
    def ask_again(self):
        """Nobody answered; ask a fresh question on the same channel.

        Returns:
            The second wait.
        """
        return rx.wait_for(
            Lapsing.decided,
            then=Lapsing.second,
            timeout="7d",
            on_timeout=Lapsing.give_up,
        )

    @rx.event(durable=True, effect="none")
    def first(self, decision: dict):
        """Record a first-question answer.

        Args:
            decision: The delivered payload.

        Returns:
            Completion.
        """
        return rx.complete(result={"answered": "first", "decision": decision})

    @rx.event(durable=True, effect="none")
    def second(self, decision: dict):
        """Record a second-question answer.

        Args:
            decision: The delivered payload.

        Returns:
            Completion.
        """
        return rx.complete(result={"answered": "second", "decision": decision})

    @rx.event(durable=True, effect="none")
    def give_up(self):
        """Nobody answered either question.

        Returns:
            Failure.
        """
        return rx.fail(reason="lapsed twice")


class TwoStage(rx.State):
    """A decision that is asked twice on one channel."""

    __workflow__ = WorkflowConfig(id="approval.two_stage")

    decided = rx.Signal(dict)
    first: str = ""
    second: str = ""

    @rx.event(durable=True, trigger=manual(), effect="none")
    def submit(self):
        """Ask the first question with both choices.

        Returns:
            The first wait.
        """
        TWO_STAGE_LINKS["one_approve"] = rx.approval_link(
            TwoStage.decided({"ok": True})
        )
        TWO_STAGE_LINKS["one_reject"] = rx.approval_link(
            TwoStage.decided({"ok": False})
        )
        return rx.wait_for(
            TwoStage.decided,
            then=TwoStage.stage_one,
            timeout="7d",
            on_timeout=TwoStage.lapse,
        )

    @rx.event(durable=True, effect="none")
    def stage_one(self, decision: dict):
        """Record the first answer and ask a second question.

        Args:
            decision: The delivered payload.

        Returns:
            The second wait.
        """
        self.first = "approved" if decision["ok"] else "rejected"
        TWO_STAGE_LINKS["two_approve"] = rx.approval_link(
            TwoStage.decided({"ok": True})
        )
        return rx.wait_for(
            TwoStage.decided,
            then=TwoStage.stage_two,
            timeout="7d",
            on_timeout=TwoStage.lapse,
        )

    @rx.event(durable=True, effect="none")
    def stage_two(self, decision: dict):
        """Record the second answer.

        Args:
            decision: The delivered payload.

        Returns:
            Completion.
        """
        self.second = "approved" if decision["ok"] else "rejected"
        return rx.complete(result={"first": self.first, "second": self.second})

    @rx.event(durable=True, effect="none")
    def lapse(self):
        """Nobody answered in time.

        Returns:
            Failure.
        """
        return rx.fail(reason="lapsed")


async def test_a_losing_alternative_cannot_answer_the_next_question(
    monkeypatch, forked_registration_context
):
    """A decision's discarded choice must not decide a later question.

    Both links belong to one question. Spending approve decides it; the
    reject link is then a spent decision, not a delivery in search of a wait.
    Keying links by the payload made them distinct identities, so the reject
    sat buffered and the second wait on the same channel swallowed it -- a
    two-stage approval completing with a second answer nobody gave.

    Args:
        monkeypatch: Used to set the signing secret.
        forked_registration_context: Isolates state registration.
    """
    monkeypatch.setenv(SECRET_ENV, SECRET)
    TWO_STAGE_LINKS.clear()
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(TwoStage)
    app = Starlette(
        routes=[
            Route(APPROVAL_ROUTE, approval_endpoint(runtime), methods=["GET", "POST"])
        ]
    )
    await runtime.startup(start_worker=False)
    started = await runtime.kernel.start(TwoStage.submit())
    await runtime.kernel.run_until_idle()
    assert started.run_id is not None

    with TestClient(app) as client:
        assert client.post(TWO_STAGE_LINKS["one_approve"]).status_code == 200
        await runtime.kernel.run_until_idle()
        # The second question is now open. The first question's discarded
        # choice must not be able to answer it.
        stale = client.post(TWO_STAGE_LINKS["one_reject"])
        assert stale.status_code == 409, stale.text
        assert "no longer open" in stale.text.lower(), stale.text
        await runtime.kernel.run_until_idle()

    snapshot = await runtime.kernel.get_run(started.run_id)
    assert snapshot is not None
    assert snapshot.status is not RunStatus.COMPLETED, (
        f"the second stage was answered by the first stage's reject: {snapshot.result}"
    )

    # The second question's own link still decides it.
    with TestClient(app) as client:
        assert client.post(TWO_STAGE_LINKS["two_approve"]).status_code == 200
    await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(started.run_id)
    assert snapshot is not None
    assert snapshot.result == {"first": "approved", "second": "approved"}


async def test_a_link_from_a_timed_out_question_cannot_answer_the_next_one(
    monkeypatch, forked_registration_context
):
    """A question nobody answered is over, and its links go with it.

    Nothing was spent, so there is no spent-link record to catch this: the
    first question simply lapsed. If the run then asks something else on the
    same channel, the forgotten link from the first question must not answer
    it. The link names the step that asked; only that step's question is its
    to answer.

    Args:
        monkeypatch: Used to set the signing secret.
        forked_registration_context: Isolates state registration.
    """
    monkeypatch.setenv(SECRET_ENV, SECRET)
    TWO_STAGE_LINKS.clear()
    store = MemoryRunStore()
    runtime = WorkflowRuntime(store, clock=lambda: _NOW[0])
    runtime.register(Lapsing)
    app = Starlette(
        routes=[
            Route(APPROVAL_ROUTE, approval_endpoint(runtime), methods=["GET", "POST"])
        ]
    )
    await runtime.startup(start_worker=False)
    started = await runtime.kernel.start(Lapsing.submit())
    await runtime.kernel.run_until_idle()
    assert started.run_id is not None
    stale_link = TWO_STAGE_LINKS["one_approve"]

    # Nobody answers. The deadline arrives and the run asks a second question
    # on the same channel.
    _NOW[0] += 8 * 24 * 3600
    await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(started.run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.WAITING, "the second question is open"

    with TestClient(app) as client:
        late = client.post(stale_link)
    assert late.status_code == 409, late.text

    await runtime.kernel.run_until_idle()
    snapshot = await runtime.kernel.get_run(started.run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.WAITING, (
        f"a link from the lapsed question answered the second one: {snapshot.result}"
    )
