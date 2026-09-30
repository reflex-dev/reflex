"""Signed browser sessions and the client tokens bound to them."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass, field
from functools import cached_property
from typing import ClassVar

from reflex_base import constants
from reflex_base.environment import environment

logger = logging.getLogger(__name__)

SESSION_SECRET_FILENAME = "session_secret"
_SID = re.compile(r"[0-9a-f]{32}\Z")
_CLIENT_TOKEN = re.compile(r"([0-9a-f]{32})\.([0-9a-f]{32})\Z")
_BASE64URL = re.compile(r"[A-Za-z0-9_-]+\Z")
_AUTH_CACHE_SIZE = 128


def _base64url(value: bytes) -> str:
    """Encode bytes without base64url padding.

    Args:
        value: Bytes to encode.

    Returns:
        Encoded bytes as ASCII text.
    """
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_base64url(value: str) -> bytes:
    """Decode a JWT segment using only the base64url alphabet.

    Args:
        value: Encoded segment.

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If the segment is malformed.
    """
    if not _BASE64URL.fullmatch(value):
        msg = "Invalid session token encoding"
        raise ValueError(msg)
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _client_signature(sid: str, nonce: str) -> str:
    """Sign a client token with an unambiguous session binding.

    Args:
        sid: Private session identifier.
        nonce: Random client identifier.

    Returns:
        A 128-bit hexadecimal authentication tag.
    """
    return hmac.digest(
        bytes.fromhex(sid), f"reflex-client-token:{nonce}".encode("ascii"), "sha256"
    )[:16].hex()


def _load_secrets() -> tuple[bytes, ...]:
    """Load the configured key ring or atomically create a local signing key.

    Returns:
        Keys in signing preference order.

    Raises:
        ValueError: If configured or persisted keys are invalid.
    """
    configured = environment.REFLEX_SESSION_SECRET.get()
    if configured is not None:
        keys = tuple(key.strip().encode() for key in configured.split(","))
        if any(len(key) < 32 for key in keys):
            msg = "REFLEX_SESSION_SECRET keys must each be at least 32 bytes"
            raise ValueError(msg)
        return keys

    path = (
        environment.REFLEX_WEB_WORKDIR.get()
        / constants.Dirs.BACKEND
        / SESSION_SECRET_FILENAME
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # Link a complete 0600 file into place, so racing workers cannot read a
        # partially written key or replace the winner's key.
        with tempfile.NamedTemporaryFile(dir=path.parent) as candidate:
            candidate.write(secrets.token_hex(32).encode("ascii"))
            candidate.flush()
            with suppress(FileExistsError):
                os.link(candidate.name, path)
    try:
        key = bytes.fromhex(path.read_text(encoding="ascii"))
    except (ValueError, UnicodeError) as error:
        msg = "Invalid persisted session signing secret"
        raise ValueError(msg) from error
    if len(key) != 32:
        msg = "Invalid persisted session signing secret"
        raise ValueError(msg)
    if environment.REFLEX_ENV_MODE.get() == constants.Env.PROD:
        logger.warning(
            "Using a local session signing secret. Set REFLEX_SESSION_SECRET to "
            "share sessions across production replicas and deployments."
        )
    return (key,)


@dataclass(frozen=True)
class SessionToken:
    """A verified browser session, distinct from an application's user identity.

    Attributes:
        id: A non-secret hash suitable for correlation in logs.
        issued_at: Unix timestamp when this session credential was issued.
        expires_at: Unix timestamp when this session credential expires.
        SYSTEM: Sentinel for trusted operations without a browser session.
    """

    issued_at: int
    expires_at: int
    _sid: str = field(repr=False)
    id: str = field(init=False)
    _authorized: set[str] = field(default_factory=set, repr=False, compare=False)
    SYSTEM: ClassVar[SessionToken]

    def __post_init__(self) -> None:
        """Derive the public identifier without exposing the private session ID."""
        object.__setattr__(self, "id", hashlib.sha256(self._sid.encode()).hexdigest())

    def authorizes(self, client_token: str) -> bool:
        """Check a client's binding to this session, caching verified successes.

        Expiration is checked when decoding the session credential; a connected
        transport controls when to refresh or revalidate that credential.

        Args:
            client_token: The client token to verify.

        Returns:
            Whether this session owns the client token.
        """
        if self is SessionToken.SYSTEM or client_token in self._authorized:
            return True
        match = _CLIENT_TOKEN.fullmatch(client_token)
        if match is None:
            return False
        nonce, signature = match.groups()
        if not hmac.compare_digest(signature, _client_signature(self._sid, nonce)):
            return False
        if len(self._authorized) >= _AUTH_CACHE_SIZE:
            self._authorized.clear()
        self._authorized.add(client_token)
        return True


SessionToken.SYSTEM = SessionToken(issued_at=0, expires_at=0, _sid="")


class SessionTokenManager:
    """Internal codec for browser session cookies and their client tokens."""

    def __init__(
        self,
        app_name: str,
        ttl: int = 7 * 24 * 60 * 60,
        refresh_interval: int | None = None,
        secrets: tuple[bytes, ...] | None = None,
    ) -> None:
        """Configure the codec without reading secrets until first use.

        Args:
            app_name: Stable app name used to isolate its cookie.
            ttl: Session lifetime in seconds.
            refresh_interval: Age in seconds to refresh, defaulting to half the TTL.
            secrets: Optional explicit key ring, primarily for isolated tests.

        Raises:
            ValueError: If the session lifetime or refresh interval is invalid.
        """
        if ttl <= 0 or (
            refresh_interval is not None and not 0 < refresh_interval < ttl
        ):
            msg = (
                "Session TTL must be positive and refresh interval between zero and TTL"
            )
            raise ValueError(msg)
        self.ttl = ttl
        self.refresh_interval = (
            ttl / 2 if refresh_interval is None else refresh_interval
        )
        self.cookie_name = (
            f"reflex_session_{hashlib.sha256(app_name.encode()).hexdigest()[:12]}"
        )
        self._configured_secrets = secrets
        self._unknown_key_warned = False

    @cached_property
    def _keys(self) -> dict[str, bytes]:
        """Read the key ring once and index it by its non-secret fingerprint.

        Returns:
            Signing keys indexed by key ID, with the active signing key first.
        """
        return {
            hashlib.sha256(key).hexdigest()[:16]: key
            for key in self._configured_secrets or _load_secrets()
        }

    def create(self) -> SessionToken:
        """Create a new random session.

        Returns:
            A new session with the configured lifetime.
        """
        now = int(time.time())
        return SessionToken(now, now + self.ttl, secrets.token_hex(16))

    def encode(self, session: SessionToken) -> str:
        """Encode a session as an HS256 JWT using the active signing key.

        Args:
            session: The session to encode.

        Returns:
            A signed JWT suitable for an HttpOnly cookie.
        """
        kid, key = next(iter(self._keys.items()))
        header = _base64url(
            json.dumps(
                {"alg": "HS256", "typ": "JWT", "kid": kid}, separators=(",", ":")
            ).encode()
        )
        payload = _base64url(
            json.dumps(
                {
                    "v": 1,
                    "sid": session._sid,
                    "iat": session.issued_at,
                    "exp": session.expires_at,
                },
                separators=(",", ":"),
            ).encode()
        )
        message = f"{header}.{payload}"
        return f"{message}.{_base64url(hmac.digest(key, message.encode('ascii'), 'sha256'))}"

    def decode(self, token: str) -> SessionToken | None:
        """Verify the signature, schema, version, and lifetime of a session JWT.

        Args:
            token: An untrusted cookie value.

        Returns:
            The verified session, or None for invalid or expired credentials.
        """
        if len(token) > 4096:
            return None
        try:
            header, payload, signature = token.split(".")
            metadata = json.loads(_decode_base64url(header))
            if not isinstance(metadata, dict) or metadata.get("alg") != "HS256":
                return None
            kid = metadata.get("kid")
            if not isinstance(kid, str):
                return None
            if (key := self._keys.get(kid)) is None:
                if not self._unknown_key_warned:
                    logger.warning(
                        "Unrecognized session signing key. Backend instances may be "
                        "using different REFLEX_SESSION_SECRET values."
                    )
                    self._unknown_key_warned = True
                return None
            expected = hmac.digest(key, f"{header}.{payload}".encode("ascii"), "sha256")
            if not hmac.compare_digest(expected, _decode_base64url(signature)):
                return None
            claims = json.loads(_decode_base64url(payload))
            if not isinstance(claims, dict):
                return None
            sid, issued_at, expires_at = (
                claims.get("sid"),
                claims.get("iat"),
                claims.get("exp"),
            )
            if (
                type(claims.get("v")) is not int
                or claims["v"] != 1
                or not isinstance(sid, str)
                or not _SID.fullmatch(sid)
                or type(issued_at) is not int
                or type(expires_at) is not int
                or not issued_at <= int(time.time()) < expires_at
            ):
                return None
            return SessionToken(issued_at, expires_at, sid)
        except (ValueError, UnicodeError, binascii.Error, RecursionError):
            return None

    def should_refresh(self, session: SessionToken) -> bool:
        """Check whether a session has reached its configured refresh age.

        Args:
            session: The verified session to check.

        Returns:
            Whether to issue a refreshed cookie.
        """
        return time.time() - session.issued_at >= self.refresh_interval

    def refresh(self, session: SessionToken) -> SessionToken:
        """Renew a session while preserving its client-token bindings.

        Args:
            session: The verified session to renew.

        Returns:
            The session with updated issuance and expiration times.
        """
        now = int(time.time())
        return SessionToken(now, now + self.ttl, session._sid)

    def create_client_token(self, session: SessionToken) -> str:
        """Create a random client token cryptographically bound to a session.

        Args:
            session: The verified session that owns the new client.

        Returns:
            An underscore-free client identifier and its authentication tag.
        """
        nonce = secrets.token_hex(16)
        return f"{nonce}.{_client_signature(session._sid, nonce)}"
