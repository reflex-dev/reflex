"""Signed browser sessions and the client tokens bound to them."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from functools import cached_property
from typing import ClassVar

from reflex_base import constants
from reflex_base.environment import environment
from reflex_base.utils import console
from reflex_base.utils.exceptions import SessionAuthorizationError

logger = logging.getLogger(__name__)

_SESSION_KEY_PURPOSE = b"reflex-session"
_SID = re.compile(r"[0-9a-f]{32}\Z")
_CLIENT_TOKEN = re.compile(r"([0-9a-f]{32})\.([0-9a-f]{32})\Z")
_BASE64URL = re.compile(r"[A-Za-z0-9_-]+\Z")
_AUTH_CACHE_SIZE = 128
# Seconds that a credential sent over a socket stays exchangeable for a cookie.
_EXCHANGE_TTL = 60


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


def is_client_token(value: str) -> bool:
    """Check whether a value has the format of a session-bound client token.

    Args:
        value: The value to check.

    Returns:
        Whether the value is a nonce with an authentication tag.
    """
    return _CLIENT_TOKEN.fullmatch(value) is not None


def ensure_secret_key() -> str:
    """Get REFLEX_SECRET_KEY, generating a temporary key when it is not set.

    The generated key is set in the process environment, so processes started
    after this call, such as backend workers and reloads, share it.

    Returns:
        The comma-separated secret key ring.

    Raises:
        ValueError: If a configured key is shorter than 32 bytes.
    """
    if (configured := environment.REFLEX_SECRET_KEY.get()) is not None:
        if any(len(key.strip().encode()) < 32 for key in configured.split(",")):
            msg = "REFLEX_SECRET_KEY keys must each be at least 32 bytes"
            raise ValueError(msg)
        return configured
    key = secrets.token_hex(32)
    environment.REFLEX_SECRET_KEY.set(key)
    if environment.REFLEX_ENV_MODE.get() == constants.Env.PROD:
        logger.warning(
            "REFLEX_SECRET_KEY is not set. Reflex generated a temporary key.\n"
            "ALL BROWSER SESSIONS RESET ON EVERY RESTART, and servers that do "
            "not share this key reject each other's sessions.\n"
            "Set REFLEX_SECRET_KEY to a random value of at least 32 bytes, for "
            "example the output of: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    else:
        logger.warning(
            "REFLEX_SECRET_KEY is not set; browser sessions reset when "
            "`reflex run` restarts."
        )
    return key


def _load_secrets() -> tuple[bytes, ...]:
    """Derive the session signing keys from the secret key ring.

    Returns:
        Keys in signing preference order.

    Raises:
        ValueError: If a configured key is shorter than 32 bytes.
    """
    return tuple(
        hmac.digest(key.strip().encode(), _SESSION_KEY_PURPOSE, "sha256")
        for key in ensure_secret_key().split(",")
    )


@dataclass(frozen=True)
class SessionToken:
    """A verified browser session, distinct from an application's user identity.

    Attributes:
        id: A non-secret hash suitable for correlation in logs.
        issued_at: Unix timestamp when this session credential was issued.
        expires_at: Unix timestamp when this session credential expires.
        created_at: Unix timestamp when the session was first issued. Renewal keeps it.
        SYSTEM: Sentinel for trusted operations without a browser session.
    """

    issued_at: int
    expires_at: int
    created_at: int
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


SessionToken.SYSTEM = SessionToken(issued_at=0, expires_at=0, created_at=0, _sid="")


def authorize(session: SessionToken | None, client_token: str) -> None:
    """Check that a session may access the state of a client token.

    Args:
        session: The session that requests access, or None for anonymous access.
        client_token: The client token whose state is requested.

    Raises:
        SessionAuthorizationError: If enforcement rejects the client token.
    """
    if not client_token or (session is not None and session.authorizes(client_token)):
        return
    mode = environment.REFLEX_SESSION_TOKEN_MODE.get()
    if mode == "off":
        return
    if mode == "enforce":
        msg = "The session does not authorize this client token."
        raise SessionAuthorizationError(msg)
    console.deprecate(
        feature_name="State access without an authorized session",
        reason=(
            "Pass the requesting session when accessing client state. "
            "Trusted server-side work may explicitly use SessionToken.SYSTEM. "
            "REFLEX_SESSION_TOKEN_MODE=enforce rejects this access."
        ),
        deprecation_version="0.11.1",
        removal_version="1.0",
    )


class SessionTokenManager:
    """Internal codec for browser session cookies and their client tokens."""

    def __init__(
        self,
        app_name: str,
        ttl: int = 7 * 24 * 60 * 60,  # Seven days, in seconds.
        refresh_interval: int | None = None,
        secrets: tuple[bytes, ...] | None = None,
        max_age: int = 7 * 24 * 60 * 60,  # Seven days, in seconds.
    ) -> None:
        """Configure the codec without reading secrets until first use.

        Args:
            app_name: Stable app name used to isolate its cookie and signed audience.
            ttl: Session lifetime in seconds.
            refresh_interval: Age in seconds to refresh, defaulting to half the TTL.
            secrets: Optional explicit key ring, primarily for isolated tests.
            max_age: Seconds after first issue when renewal stops and the session ends.

        Raises:
            ValueError: If a session lifetime or the refresh interval is invalid.
        """
        if max_age <= 0:
            msg = "Session maximum age must be positive"
            raise ValueError(msg)
        if ttl <= 0 or (
            refresh_interval is not None and not 0 < refresh_interval < ttl
        ):
            msg = (
                "Session TTL must be positive and refresh interval between zero and TTL"
            )
            raise ValueError(msg)
        self._audience = app_name
        self.ttl = ttl
        self.max_age = max_age
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
        return SessionToken(
            now, now + min(self.ttl, self.max_age), now, secrets.token_hex(16)
        )

    def encode(self, session: SessionToken, *, exchange: bool = False) -> str:
        """Encode a session as an HS256 JWT using the active signing key.

        An exchange credential goes to page scripts over a socket. It is valid
        for a short time and only at the session endpoint, never as a cookie.

        Args:
            session: The session to encode.
            exchange: Whether to encode a short-lived credential for exchange.

        Returns:
            A signed JWT suitable for an HttpOnly cookie, or for one exchange.
        """
        claims = {
            "v": 1,
            "aud": self._audience,
            "sid": session._sid,
            "iat": session.issued_at,
            "exp": session.expires_at,
            "oat": session.created_at,
        }
        if exchange:
            claims["use"] = "exchange"
            claims["exp"] = min(session.expires_at, int(time.time()) + _EXCHANGE_TTL)
        kid, key = next(iter(self._keys.items()))
        header = _base64url(
            json.dumps(
                {"alg": "HS256", "typ": "JWT", "kid": kid}, separators=(",", ":")
            ).encode()
        )
        payload = _base64url(json.dumps(claims, separators=(",", ":")).encode())
        message = f"{header}.{payload}"
        return f"{message}.{_base64url(hmac.digest(key, message.encode('ascii'), 'sha256'))}"

    def decode(self, token: str, *, exchange: bool = False) -> SessionToken | None:
        """Verify the signature, schema, version, and lifetime of a session JWT.

        Args:
            token: An untrusted cookie value or exchange credential.
            exchange: Whether to accept only a credential encoded for exchange.

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
                        "using different REFLEX_SECRET_KEY values."
                    )
                    self._unknown_key_warned = True
                return None
            expected = hmac.digest(key, f"{header}.{payload}".encode("ascii"), "sha256")
            if not hmac.compare_digest(expected, _decode_base64url(signature)):
                return None
            claims = json.loads(_decode_base64url(payload))
            if not isinstance(claims, dict):
                return None
            sid, issued_at, expires_at, created_at = (
                claims.get("sid"),
                claims.get("iat"),
                claims.get("exp"),
                claims.get("oat"),
            )
            if (
                type(claims.get("v")) is not int
                or claims["v"] != 1
                or claims.get("aud") != self._audience
                or claims.get("use") != ("exchange" if exchange else None)
                or not isinstance(sid, str)
                or not _SID.fullmatch(sid)
                or type(issued_at) is not int
                or type(expires_at) is not int
                or type(created_at) is not int
                or not issued_at <= int(time.time()) < expires_at
                or not created_at <= issued_at
                or expires_at > created_at + self.max_age
            ):
                return None
            return SessionToken(issued_at, expires_at, created_at, sid)
        except (ValueError, UnicodeError, binascii.Error, RecursionError):
            return None

    def refresh(self, session: SessionToken) -> SessionToken:
        """Renew a session while preserving its client-token bindings.

        Args:
            session: The verified session to renew.

        Returns:
            The session with updated issuance and expiration times.
        """
        now = int(time.time())
        return SessionToken(
            now,
            min(now + self.ttl, session.created_at + self.max_age),
            session.created_at,
            session._sid,
        )

    def client_token_for(self, session: SessionToken, client_token: str) -> str:
        """Get the client token that a tab uses with its session.

        A tab keeps the token that it presents when the session owns it. The
        compatibility modes also keep a token that the session does not own.

        Args:
            session: The session of the tab.
            client_token: The token that the tab presents, or an empty string.

        Returns:
            The presented token, or a new token bound to the session.
        """
        if client_token and (
            session.authorizes(client_token)
            or environment.REFLEX_SESSION_TOKEN_MODE.get() != "enforce"
        ):
            return client_token
        return self.create_client_token(session)

    def create_client_token(self, session: SessionToken) -> str:
        """Create a random client token cryptographically bound to a session.

        Args:
            session: The verified session that owns the new client.

        Returns:
            An underscore-free client identifier and its authentication tag.
        """
        nonce = secrets.token_hex(16)
        return f"{nonce}.{_client_signature(session._sid, nonce)}"
