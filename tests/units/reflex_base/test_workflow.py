"""Tests for the workflow authoring value types."""

import datetime

import pytest
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import (
    After,
    Retry,
    TransientWorkflowError,
    WorkflowConfig,
    after,
    build_durable_config,
    default_retry_for_effect,
    hmac_signature,
    manual,
    parse_duration,
    schedule,
    webhook,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30s", 30.0),
        ("500ms", 0.5),
        ("2.5h", 9000.0),
        ("1m", 60.0),
        ("30d", 30 * 86400.0),
        (15, 15.0),
        (0.25, 0.25),
        (datetime.timedelta(minutes=2), 120.0),
        (" 10 s ", 10.0),
    ],
)
def test_parse_duration(value, expected):
    assert parse_duration(value) == expected


@pytest.mark.parametrize(
    "value",
    ["30", "s", "-5s", "5 hours", None, object(), True],
)
def test_parse_duration_invalid(value):
    with pytest.raises(WorkflowDefinitionError):
        parse_duration(value)


def test_parse_duration_negative_timedelta():
    with pytest.raises(WorkflowDefinitionError, match="negative"):
        parse_duration(datetime.timedelta(seconds=-1))


def test_retry_defaults_valid():
    retry = Retry()
    assert retry.max_attempts == 3
    assert retry.delay_for_attempt(1) == pytest.approx(1.0)
    assert retry.delay_for_attempt(2) == pytest.approx(2.0)
    assert retry.delay_for_attempt(100) == pytest.approx(60.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"multiplier": 0.5},
        {"jitter": "half"},
        {"initial_delay": "1m", "max_delay": "1s"},
        {"retry_on": (ValueError,), "do_not_retry_on": (Exception,)},
    ],
)
def test_retry_invalid(kwargs):
    with pytest.raises(WorkflowDefinitionError):
        Retry(**kwargs)


def test_retry_is_retryable_respects_deny_list():
    retry = Retry(
        retry_on=(TransientWorkflowError,),
        do_not_retry_on=(ValueError,),
    )
    assert retry.is_retryable(TransientWorkflowError("x"))
    assert not retry.is_retryable(ValueError("x"))
    assert not retry.is_retryable(RuntimeError("x"))


def test_default_retry_for_effect():
    for effect in ("none", "read", "idempotent_write"):
        retry = default_retry_for_effect(effect)
        assert retry.max_attempts == 3
        # Ordinary failures retry; that is the point of a durable step.
        assert retry.is_retryable(ConnectionError("flaky"))
        assert retry.is_retryable(TransientWorkflowError("explicit"))
    non_idempotent = default_retry_for_effect("non_idempotent_write")
    assert non_idempotent.max_attempts == 1
    assert non_idempotent.retry_on == ()
    assert not non_idempotent.is_retryable(ConnectionError("flaky"))


def test_workflow_config_valid():
    config = WorkflowConfig(id="billing.payment_received", run_timeout="30d")
    assert config.max_steps == 10_000
    assert config.run_timeout is not None
    assert parse_duration(config.run_timeout) == pytest.approx(30 * 86400.0)


@pytest.mark.parametrize(
    "workflow_id",
    ["", "Billing", "billing..sync", ".billing", "billing.", "1billing", "a-b"],
)
def test_workflow_config_invalid_id(workflow_id):
    with pytest.raises(WorkflowDefinitionError, match=r"WorkflowConfig\.id"):
        WorkflowConfig(id=workflow_id)


def test_workflow_config_mixed_scope_acknowledgement():
    with pytest.raises(WorkflowDefinitionError, match="mixed_scope_reason"):
        WorkflowConfig(id="a.b", allow_mixed_scopes=True)
    with pytest.raises(WorkflowDefinitionError, match="allow_mixed_scopes"):
        WorkflowConfig(id="a.b", mixed_scope_reason="why")
    config = WorkflowConfig(
        id="a.b", allow_mixed_scopes=True, mixed_scope_reason="migration"
    )
    assert config.allow_mixed_scopes


def test_workflow_config_invalid_max_steps():
    with pytest.raises(WorkflowDefinitionError, match="max_steps"):
        WorkflowConfig(id="a.b", max_steps=0)


def test_triggers():
    assert manual().kind == "manual"
    verifier = hmac_signature(secret_env="SECRET", header="X-Signature")
    hook = webhook("stripe.payment_succeeded", verify=verifier, dedupe_by="id")
    assert hook.kind == "webhook"
    assert hook.topic == "stripe.payment_succeeded"
    assert hook.dedupe_by == "id"
    cron = schedule("0 9 * * 1")
    assert cron.kind == "schedule"
    with pytest.raises(WorkflowDefinitionError, match="topic"):
        webhook("", verify=verifier)
    with pytest.raises(WorkflowDefinitionError, match="cron"):
        schedule("hourly")


def test_after_validates_delay_eagerly():
    assert isinstance(after("2d", object()), After)
    with pytest.raises(WorkflowDefinitionError):
        after("2 fortnights", object())


def _build(**overrides):
    kwargs = {
        "durable": False,
        "id": None,
        "trigger": None,
        "retry": None,
        "timeout": None,
        "effect": None,
        "queue": None,
        "on_failure": None,
        "on_timeout": None,
        "singleton": None,
        "rate_limit": None,
        "throttle": None,
        "debounce": None,
        "background": None,
        "has_browser_actions": False,
    }
    kwargs.update(overrides)
    return build_durable_config(**kwargs)


def test_build_durable_config_session_handler_passthrough():
    assert _build() is None


def test_build_durable_config_options_require_durable():
    with pytest.raises(WorkflowDefinitionError, match="requires durable=True"):
        _build(retry=Retry())


def test_build_durable_config_requires_effect():
    with pytest.raises(WorkflowDefinitionError, match="effect"):
        _build(durable=True)
    with pytest.raises(WorkflowDefinitionError, match="effect"):
        _build(durable=True, effect="write")


def test_build_durable_config_background_exclusive():
    with pytest.raises(WorkflowDefinitionError, match="mutually exclusive"):
        _build(durable=True, effect="none", background=True)


def test_build_durable_config_browser_actions_rejected():
    with pytest.raises(WorkflowDefinitionError, match="browser event actions"):
        _build(durable=True, effect="none", has_browser_actions=True)


def test_build_durable_config_non_idempotent_single_attempt():
    with pytest.raises(WorkflowDefinitionError, match="one business attempt"):
        _build(
            durable=True,
            effect="non_idempotent_write",
            retry=Retry(max_attempts=2),
        )
    config = _build(
        durable=True,
        effect="non_idempotent_write",
        retry=Retry(max_attempts=1),
    )
    assert config is not None


def test_build_durable_config_invalid_id():
    with pytest.raises(WorkflowDefinitionError, match="id"):
        _build(durable=True, effect="none", id="Not-Valid")


def test_build_durable_config_invalid_trigger():
    with pytest.raises(WorkflowDefinitionError, match="trigger"):
        _build(durable=True, effect="none", trigger="manual")


def test_build_durable_config_hooks_normalized():
    def cleanup(self):
        pass

    config = _build(
        durable=True, effect="none", on_failure=cleanup, on_timeout="report"
    )
    assert config is not None
    assert config.on_failure == "cleanup"
    assert config.on_timeout == "report"
    with pytest.raises(WorkflowDefinitionError, match="on_failure"):
        _build(durable=True, effect="none", on_failure="")


def test_build_durable_config_parses_timeout():
    config = _build(durable=True, effect="read", timeout="45s")
    assert config is not None
    assert config.timeout == pytest.approx(45.0)


def test_webhook_requires_authentication():
    """An unverified webhook endpoint would let anyone start runs."""
    with pytest.raises(WorkflowDefinitionError, match="no verifier"):
        webhook("stripe.paid")
    with pytest.raises(WorkflowDefinitionError, match="unverified_reason"):
        webhook("stripe.paid", allow_unverified=True)
    public = webhook(
        "internal.ping", allow_unverified=True, unverified_reason="internal network"
    )
    assert public.allow_unverified
    with pytest.raises(WorkflowDefinitionError, match="keep the verifier"):
        webhook(
            "stripe.paid",
            verify=hmac_signature(secret_env="S", header="H"),
            allow_unverified=True,
            unverified_reason="mixed",
        )
