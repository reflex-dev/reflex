"""Tests for the workflow authoring value types."""

import datetime
import hmac
import time

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
    stripe_signature,
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


def _stripe_header(secret: str, body: bytes, timestamp: float) -> str:
    """Sign a body the way Stripe does.

    Args:
        secret: The signing secret.
        body: The raw request body.
        timestamp: The signing time in epoch seconds.

    Returns:
        The Stripe-Signature header value.
    """
    signed = f"{int(timestamp)}.".encode() + body
    digest = hmac.new(secret.encode(), signed, "sha256").hexdigest()
    return f"t={int(timestamp)},v1={digest}"


def test_stripe_signature_accepts_a_fresh_correctly_signed_delivery(monkeypatch):
    """The documented scheme: HMAC over timestamp-dot-body, inside tolerance."""
    monkeypatch.setenv("WH", "whsec_test")
    verify = stripe_signature(secret_env="WH", tolerance="5m")
    body = b'{"type": "invoice.paid"}'
    header = _stripe_header("whsec_test", body, time.time())
    assert verify(body, {"stripe-signature": header})


def test_stripe_signature_rejects_a_replayed_delivery(monkeypatch):
    """A signature is only as good as its window; an old one is a replay."""
    monkeypatch.setenv("WH", "whsec_test")
    verify = stripe_signature(secret_env="WH", tolerance="5m")
    body = b"{}"
    stale = _stripe_header("whsec_test", body, time.time() - 3600)
    assert not verify(body, {"stripe-signature": stale})
    future = _stripe_header("whsec_test", body, time.time() + 3600)
    assert not verify(body, {"stripe-signature": future})


def test_stripe_signature_rejects_tampering_and_garbage(monkeypatch):
    """Wrong secret, edited body, malformed header: all refused."""
    monkeypatch.setenv("WH", "whsec_test")
    verify = stripe_signature(secret_env="WH")
    body = b'{"amount": 100}'
    header = _stripe_header("whsec_other", body, time.time())
    assert not verify(body, {"stripe-signature": header})
    good = _stripe_header("whsec_test", body, time.time())
    assert not verify(b'{"amount": 999}', {"stripe-signature": good})
    assert not verify(body, {"stripe-signature": "t=abc,v1=zzz"})
    assert not verify(body, {"stripe-signature": "v1=deadbeef"})
    assert not verify(body, {})


def test_stripe_signature_accepts_any_matching_v1_during_rotation(monkeypatch):
    """Stripe sends multiple v1 digests while a secret rotates."""
    monkeypatch.setenv("WH", "whsec_new")
    verify = stripe_signature(secret_env="WH")
    body = b"{}"
    timestamp = int(time.time())
    old = hmac.new(b"whsec_old", f"{timestamp}.".encode() + body, "sha256").hexdigest()
    new = hmac.new(b"whsec_new", f"{timestamp}.".encode() + body, "sha256").hexdigest()
    assert verify(body, {"stripe-signature": f"t={timestamp},v1={old},v1={new}"})


def test_hmac_signature_no_longer_claims_stripe():
    """The raw-body helper must not present itself as a Stripe verifier.

    It cannot verify Stripe's timestamped scheme, and the docstring saying it
    covered Stripe was an invitation to ship replayable payment webhooks.
    """
    doc = hmac_signature.__doc__ or ""
    assert "deliberately **not** a Stripe verifier" in doc
    assert "stripe_signature" in doc, "the fix must point at the real verifier"


def test_durations_must_be_finite():
    """NaN compares false against every bound and infinity means never.

    Both would otherwise pass the negativity check and poison every due-time
    comparison downstream -- the third NaN bug of this class in the engine,
    after approval expiry and Stripe timestamps.
    """
    for poison in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(WorkflowDefinitionError, match=r"finite|negative"):
            parse_duration(poison)
    assert parse_duration(0) == pytest.approx(0.0)
    assert parse_duration("1.5h") == pytest.approx(5400.0)


def test_backoff_saturates_instead_of_overflowing():
    """Attempt five hundred is 'the cap', not an OverflowError in the kernel.

    delay_for_attempt runs inside the kernel's completion path, so an
    exception here breaks the worker, not the run.
    """
    policy = Retry(max_attempts=10_000, initial_delay="1s", max_delay="1h")
    assert policy.delay_for_attempt(500) == pytest.approx(3600.0)
    assert policy.delay_for_attempt(9_999) == pytest.approx(3600.0)


def test_hmac_verifier_accepts_either_secret_during_a_rotation(monkeypatch):
    """Old and new both verify while both are listed; a stranger never does."""
    monkeypatch.setenv("ROT", " new-secret , old-secret ")
    verify = hmac_signature(secret_env="ROT", header="X-Sig")
    body = b'{"id": 1}'
    for secret in ("old-secret", "new-secret"):
        digest = hmac.new(secret.encode(), body, "sha256").hexdigest()
        assert verify(body, {"x-sig": digest}), secret
    stranger = hmac.new(b"other", body, "sha256").hexdigest()
    assert not verify(body, {"x-sig": stranger})
    monkeypatch.setenv("ROT", "new-secret")
    old = hmac.new(b"old-secret", body, "sha256").hexdigest()
    assert not verify(body, {"x-sig": old}), "dropping the old secret ends the window"


def test_stripe_verifier_accepts_either_secret_during_a_rotation(monkeypatch):
    """A delivery signed with the outgoing secret verifies until it is dropped."""
    monkeypatch.setenv("WH", "whsec_new,whsec_old")
    verify = stripe_signature(secret_env="WH", tolerance="5m")
    body = b'{"type": "invoice.paid"}'
    assert verify(
        body, {"stripe-signature": _stripe_header("whsec_old", body, time.time())}
    )
    assert verify(
        body, {"stripe-signature": _stripe_header("whsec_new", body, time.time())}
    )
    assert not verify(
        body, {"stripe-signature": _stripe_header("whsec_other", body, time.time())}
    )
