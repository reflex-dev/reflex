"""Tests for the workflow definition compiler."""

import importlib.util
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import (
    Retry,
    TransientWorkflowError,
    WorkflowConfig,
    hmac_signature,
    manual,
    schedule,
    webhook,
)

import reflex as rx
from reflex.workflow.definition import compile_workflow


def _load_module(source: str) -> dict:
    """Import workflow source from a real file so its body can be parsed.

    The compiler reads handler source to reject bodies that break the
    durability boundary, which needs an importable file rather than an exec'd
    string.

    Args:
        source: The module source to write and import.

    Returns:
        The imported module's namespace.
    """
    name = f"wf_probe_{uuid.uuid4().hex}"
    path = Path(tempfile.gettempdir()) / f"{name}.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return vars(module)


def _billing_workflow():
    class BillingDefinition(rx.State):
        __workflow__ = WorkflowConfig(
            id="billing.definition", run_timeout="30d", default_queue="integrations"
        )
        payment_id: str = ""
        amount: int = 0

        @rx.event(id="payment_received", durable=True, trigger=manual(), effect="none")
        def payment_received(self, payment_id: str):
            self.payment_id = payment_id
            return BillingDefinition.fulfill

        @rx.event(
            durable=True,
            retry=Retry(max_attempts=5),
            timeout="30s",
            effect="idempotent_write",
            on_failure="report",
        )
        async def fulfill(self):
            pass

        @rx.event(durable=True, effect="none")
        def report(self):
            pass

    return BillingDefinition


def test_compile_happy_path(forked_registration_context):
    definition = compile_workflow(_billing_workflow())
    assert definition.workflow_id == "billing.definition"
    assert set(definition.handlers) == {"payment_received", "fulfill", "report"}
    assert definition.roots == ("payment_received",)
    assert definition.run_timeout == pytest.approx(30 * 86400.0)
    fulfill = definition.handlers["fulfill"]
    assert fulfill.timeout == pytest.approx(30.0)
    assert fulfill.on_failure == "report"
    assert fulfill.queue == "integrations"
    assert fulfill.is_async
    assert [field.name for field in definition.fields] == ["payment_id", "amount"]


def test_digest_stable_and_sensitive(forked_registration_context):
    first = compile_workflow(_billing_workflow())
    second = compile_workflow(_billing_workflow())
    assert first.digest == second.digest

    class OtherPolicy(rx.State):
        __workflow__ = WorkflowConfig(id="billing.definition2")

        @rx.event(id="payment_received", durable=True, trigger=manual(), effect="none")
        def payment_received(self):
            pass

    assert compile_workflow(OtherPolicy).digest != first.digest


def test_explicit_retry_retries_ordinary_failures(forked_registration_context):
    """Retry(max_attempts=5) must mean five attempts, not one."""
    definition = compile_workflow(_billing_workflow())
    retry = definition.handlers["fulfill"].retry
    assert retry.max_attempts == 5
    assert retry.is_retryable(ConnectionError("provider down"))
    assert retry.is_retryable(TransientWorkflowError("explicit"))


def test_non_idempotent_write_never_retries(forked_registration_context):
    """An uncertain write is never retried, whatever the exception."""

    class UnsafeWrite(rx.State):
        __workflow__ = WorkflowConfig(id="billing.unsafe_write")

        @rx.event(durable=True, trigger=manual(), effect="non_idempotent_write")
        def wire(self):
            pass

    retry = compile_workflow(UnsafeWrite).handlers["wire"].retry
    assert retry.max_attempts == 1
    assert not retry.is_retryable(ConnectionError("dropped"))


def test_explicit_retry_on_preserved(forked_registration_context):
    class ExplicitRetryOn(rx.State):
        __workflow__ = WorkflowConfig(id="billing.explicit_retry")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="read",
            retry=Retry(max_attempts=2, retry_on=(ConnectionError,)),
        )
        def fetch(self):
            pass

    retry = compile_workflow(ExplicitRetryOn).handlers["fetch"].retry
    assert retry.retry_on == (ConnectionError,)


def test_code_bugs_are_not_retried(forked_registration_context):
    """A retry re-runs the handler against the same state, so a bug re-fails.

    Retrying a TypeError spends the whole budget proving the code is still
    wrong, and delays an operator seeing it by the length of the backoff.
    """

    class Buggy(rx.State):
        __workflow__ = WorkflowConfig(id="billing.buggy")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="read",
            retry=Retry(max_attempts=5),
        )
        def work(self):
            pass

    retry = compile_workflow(Buggy).handlers["work"].retry
    assert not retry.is_retryable(TypeError("not callable"))
    assert not retry.is_retryable(AttributeError("no such attribute"))
    assert not retry.is_retryable(NameError("undefined"))
    # A dependency returning a body without the field you wanted is bad luck,
    # not a bug, and the next attempt may well get it right.
    assert retry.is_retryable(KeyError("items"))
    assert retry.is_retryable(ValueError("bad json"))
    assert retry.is_retryable(ConnectionError("dropped"))


def test_a_handler_may_ask_for_a_bug_class_to_be_retried(forked_registration_context):
    """The exclusion is a default, not a rule the engine imposes."""

    class Insists(rx.State):
        __workflow__ = WorkflowConfig(id="billing.insists")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="read",
            retry=Retry(max_attempts=3, retry_on=(TypeError,)),
        )
        def work(self):
            pass

    retry = compile_workflow(Insists).handlers["work"].retry
    assert retry.is_retryable(TypeError("this one is transient, honestly"))
    assert not retry.is_retryable(AttributeError("still a bug"))


def test_missing_workflow_config(forked_registration_context):
    class NoConfig(rx.State):
        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="__workflow__"):
        compile_workflow(NoConfig)


def test_wrong_config_type(forked_registration_context):
    class BadConfig(rx.State):
        __workflow__ = {"id": "a.b"}

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match=r"rx\.WorkflowConfig"):
        compile_workflow(BadConfig)


def test_not_a_state_class():
    with pytest.raises(WorkflowDefinitionError, match=r"rx\.State subclass"):
        compile_workflow(object)  # pyright: ignore[reportArgumentType]


def test_non_durable_public_handler_rejected(forked_registration_context):
    class MixedHandlers(rx.State):
        __workflow__ = WorkflowConfig(id="billing.mixed_handlers")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

        @rx.event
        def session_click(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="session_click"):
        compile_workflow(MixedHandlers)


def test_duplicate_handler_ids_rejected(forked_registration_context):
    class DuplicateIds(rx.State):
        __workflow__ = WorkflowConfig(id="billing.duplicate_ids")

        @rx.event(id="same", durable=True, trigger=manual(), effect="none")
        def first(self):
            pass

        @rx.event(id="same", durable=True, effect="none")
        def second(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="duplicate handler id"):
        compile_workflow(DuplicateIds)


def test_unresolved_hook_rejected(forked_registration_context):
    class UnresolvedHook(rx.State):
        __workflow__ = WorkflowConfig(id="billing.unresolved_hook")

        @rx.event(durable=True, trigger=manual(), effect="none", on_failure="missing")
        def go(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="on_failure"):
        compile_workflow(UnresolvedHook)


def test_self_hook_rejected(forked_registration_context):
    class SelfHook(rx.State):
        __workflow__ = WorkflowConfig(id="billing.self_hook")

        @rx.event(durable=True, trigger=manual(), effect="none", on_failure="go")
        def go(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="itself"):
        compile_workflow(SelfHook)


def test_hook_with_payload_rejected(forked_registration_context):
    class HookWithArgs(rx.State):
        __workflow__ = WorkflowConfig(id="billing.hook_args")

        @rx.event(durable=True, trigger=manual(), effect="none", on_failure="cleanup")
        def go(self):
            pass

        @rx.event(durable=True, effect="none")
        def cleanup(self, reason: str):
            pass

    with pytest.raises(WorkflowDefinitionError, match="payload arguments"):
        compile_workflow(HookWithArgs)


def test_no_root_rejected(forked_registration_context):
    class NoRoot(rx.State):
        __workflow__ = WorkflowConfig(id="billing.no_root")

        @rx.event(durable=True, effect="none")
        def internal_only(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="trigger"):
        compile_workflow(NoRoot)


def test_webhook_root_compiles(forked_registration_context):
    class WebhookRoot(rx.State):
        __workflow__ = WorkflowConfig(id="billing.webhook_root")

        @rx.event(
            durable=True,
            trigger=webhook(
                "stripe.payment_succeeded",
                verify=hmac_signature(secret_env="SECRET", header="X-Signature"),
                dedupe_by="id",
            ),
            effect="none",
        )
        def on_payment(self):
            pass

    definition = compile_workflow(WebhookRoot)
    assert definition.roots == ("on_payment",)


def test_mixed_scopes_rejected(forked_registration_context):
    class MixedScopes(rx.State):
        __workflow__ = WorkflowConfig(
            id="billing.mixed_scopes",
            allow_mixed_scopes=True,
            mixed_scope_reason="migration",
        )

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="mixed-scope"):
        compile_workflow(MixedScopes)


def test_backend_vars_rejected(forked_registration_context):
    class BackendVars(rx.State):
        __workflow__ = WorkflowConfig(id="billing.backend_vars")
        _secret_session: str = ""

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="backend-only"):
        compile_workflow(BackendVars)


def test_nested_substate_rejected(forked_registration_context):
    class ParentWorkflowState(rx.State):
        pass

    class NestedWorkflow(ParentWorkflowState):
        __workflow__ = WorkflowConfig(id="billing.nested")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="directly"):
        compile_workflow(NestedWorkflow)


def test_class_with_substates_rejected(forked_registration_context):
    class SubstateHaver(rx.State):
        __workflow__ = WorkflowConfig(id="billing.substate_haver")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    class ChildOfWorkflow(SubstateHaver):
        pass

    with pytest.raises(WorkflowDefinitionError, match="substates"):
        compile_workflow(SubstateHaver)


def test_direct_handler_call_is_rejected(forked_registration_context):
    """Calling a durable handler inline silently loses its durability."""
    source = """
import reflex as rx
from reflex_base.workflow import WorkflowConfig, manual


class InlineCallFlow(rx.State):
    __workflow__ = WorkflowConfig(id="billing.inline_call")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self):
        self.charge()

    @rx.event(durable=True, effect="idempotent_write")
    def charge(self):
        pass
"""
    namespace = _load_module(source)
    with pytest.raises(WorkflowDefinitionError, match="calls 'charge' directly"):
        compile_workflow(namespace["InlineCallFlow"])


def test_literal_return_is_rejected(forked_registration_context):
    """A durable handler returns a transition, not a value."""
    source = """
import reflex as rx
from reflex_base.workflow import WorkflowConfig, manual


class LiteralReturnFlow(rx.State):
    __workflow__ = WorkflowConfig(id="billing.literal_return")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self):
        return "done"
"""
    namespace = _load_module(source)
    with pytest.raises(WorkflowDefinitionError, match="returns 'done'"):
        compile_workflow(namespace["LiteralReturnFlow"])


def test_valid_transitions_compile(forked_registration_context):
    """The shapes the guards steer users toward all compile."""
    source = """
import reflex as rx
from reflex_base.workflow import WorkflowConfig, after, complete, manual


class TransitionsFlow(rx.State):
    __workflow__ = WorkflowConfig(id="billing.transitions")
    n: int = 0

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self):
        self.n += 1
        return TransitionsFlow.charge

    @rx.event(durable=True, effect="idempotent_write")
    def charge(self):
        return after("1h", TransitionsFlow.finish)

    @rx.event(durable=True, effect="none")
    def finish(self):
        return complete(result={"n": self.n})
"""
    namespace = _load_module(source)
    definition = compile_workflow(namespace["TransitionsFlow"])
    assert set(definition.handlers) == {"begin", "charge", "finish"}


def test_a_workflow_id_must_be_a_dotted_name(forked_registration_context):
    """The id is a durable identity, so its shape is fixed at compile time.

    Runs carry it forever and operators search by it; discovering a typo or an
    empty string after runs exist means either living with it or migrating
    rows.
    """
    with pytest.raises(WorkflowDefinitionError, match="lowercase dotted"):

        class Empty(rx.State):
            __workflow__ = WorkflowConfig(id="")

            @rx.event(durable=True, trigger=manual(), effect="none")
            def go(self):
                """Go."""

        compile_workflow(Empty)


def test_an_invalid_cron_is_rejected_at_compile_time(forked_registration_context):
    """A schedule that cannot be parsed must fail now, not at the first sweep.

    A cron typo that surfaces at runtime is a job that silently never runs.
    """
    with pytest.raises(WorkflowDefinitionError, match="cron"):

        class Bad(rx.State):
            __workflow__ = WorkflowConfig(id="defn.badcron")

            @rx.event(durable=True, trigger=schedule("not a cron"), effect="none")
            def go(self):
                """Go."""

        compile_workflow(Bad)


def test_a_webhook_without_a_verifier_is_rejected(forked_registration_context):
    """An unverified public endpoint that starts runs is not a default.

    Anyone who learns the URL could start work; the compiler makes that a
    deliberate choice rather than an oversight.
    """
    with pytest.raises(WorkflowDefinitionError, match="no verifier"):

        class Open(rx.State):
            __workflow__ = WorkflowConfig(id="defn.openhook")

            @rx.event(durable=True, trigger=webhook("topic"), effect="none")
            def go(self, payload: dict):
                """Go.

                Args:
                    payload: The delivered body.
                """

        compile_workflow(Open)
