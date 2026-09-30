"""Tests for signed session credentials and client bindings."""

import base64
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest
from reflex_base.config import Config
from reflex_base.environment import environment
from reflex_base.session import (
    _AUTH_CACHE_SIZE,
    SessionToken,
    SessionTokenManager,
    _load_secrets,
)
from reflex_base.utils.exceptions import EnvironmentVarValueError

SECRET = b"a" * 32
OTHER_SECRET = b"b" * 32


@pytest.fixture
def manager(monkeypatch):
    """Create an isolated codec with a fixed clock.

    Returns:
        A codec with a 100-second session lifetime.
    """
    monkeypatch.setattr("reflex_base.session.time.time", lambda: 1000)
    return SessionTokenManager("test", ttl=100, secrets=(SECRET,))


def _signed_token(header, claims, secret=SECRET):
    """Construct independently signed inputs to exercise strict decoding.

    Returns:
        A signed JWT containing the supplied header and claims.
    """
    segments = [
        base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=")
        for value in (header, claims)
    ]
    message = b".".join(segments)
    signature = base64.urlsafe_b64encode(hmac.digest(secret, message, "sha256")).rstrip(
        b"="
    )
    return (message + b"." + signature).decode()


def test_round_trip_and_public_session(manager):
    """Round-trip immutable sessions without exposing private identifiers or keys.

    Args:
        manager: The session codec fixture.
    """
    session = manager.create()
    encoded = manager.encode(session)
    decoded = manager.decode(encoded)
    assert decoded == session
    assert session.issued_at == 1000
    assert session.expires_at == 1100
    assert session.id == hashlib.sha256(session._sid.encode()).hexdigest()
    assert len(session._sid) == 32
    assert session._sid not in repr(session)
    assert SECRET.decode() not in repr(session)
    with pytest.raises(FrozenInstanceError):
        session.issued_at = 0
    assert manager.create().id != session.id
    header = json.loads(base64.urlsafe_b64decode(encoded.split(".")[0] + "=="))
    assert header == {
        "alg": "HS256",
        "typ": "JWT",
        "kid": hashlib.sha256(SECRET).hexdigest()[:16],
    }


@pytest.mark.parametrize(
    "token", ["", "x", "x.y", "x.y.z.w", "x.y.z", "!.e30.AA", "e30.é.AA", "a" * 4097]
)
def test_decode_malformed(manager, token):
    """Reject malformed session credentials.

    Args:
        manager: The session codec fixture.
        token: The malformed credential.
    """
    assert manager.decode(token) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("v", 2),
        ("v", True),
        ("v", None),
        ("sid", ""),
        ("sid", "g" * 32),
        ("sid", 123),
        ("sid", "a" * 31),
        ("iat", 1001),
        ("iat", "1000"),
        ("iat", True),
        ("iat", None),
        ("exp", 1000),
        ("exp", 999),
        ("exp", "1100"),
        ("exp", True),
    ],
)
def test_decode_rejects_invalid_claims(manager, field, value):
    """Reject signed credentials with invalid claim values.

    Args:
        manager: The session codec fixture.
        field: The claim to replace.
        value: The invalid claim value.
    """
    claims = {"v": 1, "sid": "a" * 32, "iat": 1000, "exp": 1100}
    claims[field] = value
    header = {"alg": "HS256", "kid": next(iter(manager._keys))}
    assert manager.decode(_signed_token(header, claims)) is None


@pytest.mark.parametrize(
    "header",
    [
        {"alg": "none"},
        {"alg": "HS384"},
        {"alg": "HS256", "kid": "unknown"},
        {"alg": "HS256", "kid": []},
        [],
        None,
    ],
)
def test_decode_rejects_wrong_algorithm_or_key(manager, header):
    """Reject unsupported algorithms, unknown keys, and malformed headers.

    Args:
        manager: The session codec fixture.
        header: The invalid JWT header.
    """
    claims = {"v": 1, "sid": "a" * 32, "iat": 1000, "exp": 1100}
    assert manager.decode(_signed_token(header, claims)) is None


def test_decode_rejects_bad_signature_and_nonobject_claims(manager):
    """Reject incorrect signatures and claims that are not objects.

    Args:
        manager: The session codec fixture.
    """
    header = {"alg": "HS256", "kid": next(iter(manager._keys))}
    claims = {"v": 1, "sid": "a" * 32, "iat": 1000, "exp": 1100}
    assert manager.decode(_signed_token(header, claims, OTHER_SECRET)) is None
    assert manager.decode(_signed_token(header, [])) is None


def test_refresh_keeps_existing_client_bindings(manager, monkeypatch):
    """Refresh at the configured age without changing client token ownership.

    Args:
        manager: The session codec fixture.
        monkeypatch: The clock override fixture.
    """
    session = manager.create()
    client_token = manager.create_client_token(session)
    monkeypatch.setattr("reflex_base.session.time.time", lambda: 1049)
    assert not manager.should_refresh(session)
    monkeypatch.setattr("reflex_base.session.time.time", lambda: 1050)
    assert manager.should_refresh(session)
    refreshed = manager.refresh(session)
    assert refreshed.id == session.id
    assert refreshed.issued_at == 1050
    assert refreshed.expires_at == 1150
    assert refreshed.authorizes(client_token)
    monkeypatch.setattr("reflex_base.session.time.time", lambda: 1100)
    assert manager.decode(manager.encode(session)) is None
    assert manager.decode(manager.encode(refreshed)) == refreshed


def test_client_token_binding_and_format(manager):
    """Verify client token formatting, session ownership, and trusted access.

    Args:
        manager: The session codec fixture.
    """
    session, other_session = manager.create(), manager.create()
    token = manager.create_client_token(session)
    nonce, signature = token.split(".")
    assert len(nonce) == len(signature) == 32
    assert "_" not in token
    assert session.authorizes(token)
    assert not other_session.authorizes(token)
    assert not session.authorizes(nonce + "." + "0" * 32)
    assert SessionToken.SYSTEM.authorizes("trusted-internal-token")


@pytest.mark.parametrize(
    "token",
    ["", "abc", "legacy_uuid", "a" * 32 + "." + "b" * 31, "é" * 65, "a" * 10_000],
)
def test_invalid_client_tokens_are_not_cached(manager, token):
    """Keep invalid client tokens out of the authorization cache.

    Args:
        manager: The session codec fixture.
        token: The invalid client token.
    """
    session = manager.create()
    assert not session.authorizes(token)
    assert not session._authorized


def test_authorization_cache_is_bounded_and_skips_hmac(manager):
    """Bound successful authorization caching and reuse verified signatures.

    Args:
        manager: The session codec fixture.
    """
    session = manager.create()
    token = manager.create_client_token(session)
    assert session.authorizes(token)
    with patch(
        "reflex_base.session._client_signature", side_effect=AssertionError("cached")
    ):
        assert session.authorizes(token)
    for _ in range(_AUTH_CACHE_SIZE + 1):
        assert session.authorizes(manager.create_client_token(session))
    assert len(session._authorized) <= _AUTH_CACHE_SIZE
    assert session.authorizes(token)


def test_key_rotation(manager):
    """Rotate signing keys while retaining verified client token bindings.

    Args:
        manager: The session codec fixture using the original key.
    """
    session = manager.create()
    old_cookie = manager.encode(session)
    old_client = manager.create_client_token(session)
    rotated = SessionTokenManager("test", secrets=(OTHER_SECRET, SECRET))
    rotated_session = rotated.decode(old_cookie)
    assert rotated_session is not None
    assert rotated_session.authorizes(old_client)
    assert rotated_session.authorizes(rotated.create_client_token(rotated_session))
    new_cookie = rotated.encode(rotated_session)
    assert manager.decode(new_cookie) is None
    new_only = SessionTokenManager("test", secrets=(OTHER_SECRET,))
    assert new_only.decode(old_cookie) is None
    renewed = new_only.decode(new_cookie)
    assert renewed is not None
    assert renewed.authorizes(old_client)


def test_secrets_load_lazily_and_cookies_are_app_specific(monkeypatch):
    """Isolate cookie names by app without eagerly reading signing secrets.

    Args:
        monkeypatch: The test environment fixture.
    """
    with patch(
        "reflex_base.session._load_secrets",
        side_effect=AssertionError("eager secret read"),
    ):
        first = SessionTokenManager("first")
        second = SessionTokenManager("second")
        assert first.cookie_name != second.cookie_name
        assert first.cookie_name == SessionTokenManager("first").cookie_name


def test_unknown_signing_key_warns_once(manager, caplog):
    """Different instance secrets produce one diagnostic without credentials.

    Args:
        manager: The session codec fixture.
        caplog: The captured log records.
    """
    other = SessionTokenManager("test", secrets=(OTHER_SECRET,))
    credential = other.encode(other.create())
    for _ in range(2):
        assert manager.decode(credential) is None
    assert caplog.text.count("Backend instances may be") == 1
    assert credential not in caplog.text
    assert OTHER_SECRET.decode() not in caplog.text


def test_environment_key_ring_does_not_write_files(tmp_path, monkeypatch):
    """Use configured signing keys without creating a persisted secret.

    Args:
        tmp_path: The isolated working directory.
        monkeypatch: The environment override fixture.
    """
    monkeypatch.setenv("REFLEX_SESSION_SECRET", "a" * 32 + ", " + "b" * 32)
    monkeypatch.setenv("REFLEX_WEB_WORKDIR", str(tmp_path / ".web"))
    assert _load_secrets() == (SECRET, OTHER_SECRET)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("value", ["short", "a" * 32 + ",", "," + "b" * 32])
def test_invalid_secret_never_discloses_its_value(monkeypatch, value):
    """Reject invalid configured secrets without including them in errors.

    Args:
        monkeypatch: The environment override fixture.
        value: The invalid signing key configuration.
    """
    monkeypatch.setenv("REFLEX_SESSION_SECRET", value)
    with pytest.raises(ValueError, match="at least 32 bytes") as error:
        _load_secrets()
    assert value not in str(error.value)


def test_persisted_secret_is_atomic_private_and_reused(tmp_path, monkeypatch):
    """Concurrent initialization shares one secret with private file permissions.

    Args:
        tmp_path: The isolated working directory.
        monkeypatch: The environment override fixture.
    """
    monkeypatch.delenv("REFLEX_SESSION_SECRET", raising=False)
    monkeypatch.setenv("REFLEX_WEB_WORKDIR", str(tmp_path / ".web"))
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: _load_secrets(), range(64)))
    assert len(set(results)) == 1
    assert len(results[0][0]) == 32
    assert _load_secrets() == results[0]
    path = tmp_path / ".web" / "backend" / "session_secret"
    assert path.stat().st_mode & 0o777 == 0o600
    assert list(path.parent.iterdir()) == [path]


def test_production_fallback_warning_does_not_contain_secret(
    tmp_path, monkeypatch, caplog
):
    """Warn about production fallback keys without disclosing their contents.

    Args:
        tmp_path: The isolated working directory.
        monkeypatch: The environment override fixture.
        caplog: The captured log records.
    """
    monkeypatch.delenv("REFLEX_SESSION_SECRET", raising=False)
    monkeypatch.setenv("REFLEX_WEB_WORKDIR", str(tmp_path / ".web"))
    monkeypatch.setenv("REFLEX_ENV_MODE", "prod")
    key = _load_secrets()[0]
    assert "Set REFLEX_SESSION_SECRET" in caplog.text
    assert key.hex() not in caplog.text


@pytest.mark.parametrize("value", ["not-hex", "aa", "é"])
def test_invalid_persisted_secret_is_not_replaced(tmp_path, monkeypatch, value):
    """Reject an invalid persisted secret without replacing its contents.

    Args:
        tmp_path: The isolated working directory.
        monkeypatch: The environment override fixture.
        value: The invalid persisted key contents.
    """
    monkeypatch.delenv("REFLEX_SESSION_SECRET", raising=False)
    monkeypatch.setenv("REFLEX_WEB_WORKDIR", str(tmp_path))
    path = tmp_path / "backend" / "session_secret"
    path.parent.mkdir()
    path.write_text(value)
    with pytest.raises(ValueError, match="Invalid persisted"):
        _load_secrets()
    assert path.read_text() == value


@pytest.mark.parametrize(
    ("ttl", "refresh_interval"),
    [(0, None), (-1, None), (100, 0), (100, 100), (100, -1)],
)
def test_invalid_lifetimes(ttl, refresh_interval):
    """Reject session lifetimes and refresh intervals outside their valid ranges.

    Args:
        ttl: The requested session lifetime.
        refresh_interval: The requested refresh interval.
    """
    with pytest.raises(ValueError, match="Session TTL"):
        SessionTokenManager("app", ttl=ttl, refresh_interval=refresh_interval)


def test_config_defaults_and_secret_is_not_config(monkeypatch):
    """Expose session timing configuration while keeping signing secrets separate.

    Args:
        monkeypatch: The environment override fixture.
    """
    monkeypatch.setenv("REFLEX_SESSION_SECRET", SECRET.decode())
    config = Config(app_name="test")
    assert config.session_token_ttl == 604800
    assert config.session_token_refresh_interval is None
    assert "session_secret" not in config.class_fields()
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_TTL", "100")
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_REFRESH_INTERVAL", "25")
    config = Config(app_name="test")
    assert config.session_token_ttl == 100
    assert config.session_token_refresh_interval == 25


@pytest.mark.parametrize("mode", ["off", "warn", "enforce"])
def test_session_rollout_mode(monkeypatch, mode):
    """Default to warnings and accept only supported rollout modes.

    Args:
        monkeypatch: The environment override fixture.
        mode: The supported rollout mode to select.
    """
    monkeypatch.delenv("REFLEX_SESSION_TOKEN_MODE", raising=False)
    assert environment.REFLEX_SESSION_TOKEN_MODE.get() == "warn"
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_MODE", mode)
    assert environment.REFLEX_SESSION_TOKEN_MODE.get() == mode
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_MODE", "invalid")
    with pytest.raises(EnvironmentVarValueError):
        environment.REFLEX_SESSION_TOKEN_MODE.get()
