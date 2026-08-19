"""Signed links that let a person answer a waiting run from an email.

A run waiting on a decision is common enough that every workflow engine grows
some version of it, and the naive version is a URL carrying a run id. That is
an open door: anyone who guesses or forwards it can approve. Here a link is a
signed token that names exactly one run, one channel, and one payload, expires,
and can be spent once.

Two details are the whole security story:

*Nothing is trusted from the URL.* The token carries its own signature over
every field, so a recipient who edits the run id, the payload, or the expiry
invalidates it. The secret never leaves the server.

*A GET never decides anything.* Mail clients and link scanners fetch URLs
before a human sees them, so a link that approves on GET approves itself. The
GET renders a confirmation the person submits, and only the POST delivers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import time
from html import escape
from typing import TYPE_CHECKING, Any, Final

from reflex_base.utils import console
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import ChannelDelivery, parse_duration
from starlette.responses import HTMLResponse, JSONResponse, Response

from reflex.workflow.context import require_run
from reflex.workflow.serde import to_run_data

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from reflex_base.workflow import DurationLike
    from starlette.requests import Request

    from reflex.workflow.runtime import WorkflowRuntime

SECRET_ENV: Final = "REFLEX_WORKFLOW_APPROVAL_SECRET"
APPROVAL_ROUTE: Final = "/_workflow/approve/{token:path}"
DEFAULT_EXPIRY: Final = "7d"
MAX_TOKEN_BYTES: Final = 4096


def _secret() -> bytes:
    """Read the signing secret.

    Returns:
        The secret as bytes.

    Raises:
        WorkflowRuntimeError: If the environment does not carry one.
    """
    secret = os.environ.get(SECRET_ENV)
    if not secret:
        msg = (
            f"Approval links must be signed, so {SECRET_ENV} has to be set to a "
            "long random string. There is deliberately no default: a built-in "
            "secret would make every deployment's links forgeable."
        )
        raise WorkflowRuntimeError(msg)
    return secret.encode()


def _b64(raw: bytes) -> str:
    """Encode bytes for a URL path segment.

    Args:
        raw: The bytes to encode.

    Returns:
        Unpadded base64url text.
    """
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    """Decode a URL path segment back to bytes.

    Args:
        text: Unpadded base64url text.

    Returns:
        The decoded bytes.
    """
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: bytes) -> str:
    """Sign a token body.

    Args:
        body: The encoded claims.

    Returns:
        The signature, base64url encoded.
    """
    return _b64(hmac.new(_secret(), body, hashlib.sha256).digest())


def approval_link(
    delivery: ChannelDelivery,
    *,
    base_url: str = "",
    expires_in: DurationLike = DEFAULT_EXPIRY,
    key: str | None = None,
) -> str:
    """Build a signed link that delivers one decision to the current run.

    Call it from inside a durable handler; the run it addresses is the run the
    handler is running in. Build one link per choice and put them both in the
    message::

        approve = rx.approval_link(Expense.decided({"ok": True}))
        reject = rx.approval_link(Expense.decided({"ok": False}))

    Args:
        delivery: The channel and payload to deliver, e.g.
            ``Expense.decided({"ok": True})``.
        base_url: Origin to prefix, e.g. ``"https://app.example.com"``. Leave
            empty for a path, which is what a relative link needs.
        expires_in: How long the link stays valid.
        key: Delivery identity. Two links sharing a key are the same decision,
            so the second one spent is a no-op; distinct keys let one person
            approve after another rejected. Defaults to a key derived from the
            channel and payload, which makes a link single-use.

    Returns:
        The URL.
    """
    context = require_run("approval_link()")
    # A channel is typically declared with a model, so the payload has to be
    # reduced to plain data here rather than at delivery: the token carries it
    # across a network boundary, and only plain data survives the round trip.
    payload = to_run_data({"value": delivery.payload})["value"]
    if key is None:
        material = json.dumps(
            [context.run_id, delivery.channel, payload], sort_keys=True
        )
        key = hashlib.sha256(material.encode()).hexdigest()[:32]
    claims = {
        "r": context.run_id,
        "c": delivery.channel,
        "p": payload,
        "k": key,
        "e": time.time() + parse_duration(expires_in, param="expires_in"),
    }
    body = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    token = f"{_b64(body)}.{_sign(body)}"
    return f"{base_url.rstrip('/')}/_workflow/approve/{token}"


def decode_token(token: str) -> dict[str, Any]:
    """Verify a token and return its claims.

    Args:
        token: The token from the URL.

    Returns:
        The verified claims.

    Raises:
        WorkflowRuntimeError: If the token is malformed, unsigned, forged, or
            expired. The message is deliberately the same for every failure,
            so a caller cannot use it to probe what a valid token looks like.
    """
    invalid = "This approval link is not valid. It may have expired."
    if len(token) > MAX_TOKEN_BYTES or token.count(".") != 1:
        raise WorkflowRuntimeError(invalid)
    encoded, signature = token.split(".")
    try:
        body = _unb64(encoded)
    except Exception as exc:
        raise WorkflowRuntimeError(invalid) from exc
    if not hmac.compare_digest(signature, _sign(body)):
        raise WorkflowRuntimeError(invalid)
    try:
        claims = json.loads(body)
    except json.JSONDecodeError as exc:
        raise WorkflowRuntimeError(invalid) from exc
    if not isinstance(claims, dict) or not {"r", "c", "p", "k", "e"} <= claims.keys():
        raise WorkflowRuntimeError(invalid)
    expiry = claims["e"]
    # Finite is not pedantry: NaN fails every comparison, so `nan < now` is
    # False and a NaN expiry would make a token immortal; infinity would do it
    # outright. Signing means only our own bug could mint one, which is
    # precisely why the verifier should not depend on that being true.
    if (
        not isinstance(expiry, (int, float))
        or isinstance(expiry, bool)
        or not math.isfinite(expiry)
        or expiry < time.time()
    ):
        raise WorkflowRuntimeError(invalid)
    return claims


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
 body {{ font: 16px/1.5 system-ui, sans-serif; margin: 0; display: grid;
        place-items: center; min-height: 100vh; background: #f6f7f9;
        color: #16181d; }}
 main {{ background: #fff; padding: 2.5rem; border-radius: 12px; max-width: 26rem;
        box-shadow: 0 1px 3px rgba(0,0,0,.08); text-align: center; }}
 h1 {{ font-size: 1.25rem; margin: 0 0 .75rem; }}
 p {{ margin: 0 0 1.5rem; color: #5a6270; }}
 button {{ font: inherit; padding: .7rem 1.6rem; border: 0; border-radius: 8px;
          background: #16181d; color: #fff; cursor: pointer; }}
</style></head>
<body><main><h1>{title}</h1><p>{message}</p>{form}</main></body></html>
"""

_FORM = '<form method="post"><button type="submit">{label}</button></form>'


def _page(title: str, message: str, *, form: str = "", status: int = 200) -> Response:
    """Render one of the confirmation pages.

    Args:
        title: Heading text.
        message: Body text.
        form: Optional submit form.
        status: HTTP status code.

    Returns:
        The response.
    """
    return HTMLResponse(
        _PAGE.format(title=escape(title), message=escape(message), form=form),
        status_code=status,
    )


def _wants_json(request: Request) -> bool:
    """Whether the caller asked for JSON rather than a page.

    Args:
        request: The incoming request.

    Returns:
        True when JSON was requested explicitly.
    """
    return "application/json" in request.headers.get("accept", "")


def approval_endpoint(
    runtime: WorkflowRuntime,
) -> Callable[[Request], Coroutine[Any, Any, Response]]:
    """Build the endpoint that spends approval links.

    Args:
        runtime: The runtime owning the runs.

    Returns:
        The endpoint callable.
    """

    async def endpoint(request: Request) -> Response:
        """Confirm on GET, deliver on POST.

        Args:
            request: The incoming request.

        Returns:
            The response.
        """
        token = request.path_params.get("token", "")
        try:
            _secret()
        except WorkflowRuntimeError as err:
            # A server with no secret cannot tell a good link from a forged
            # one. Saying "expired" would send an operator hunting a data
            # problem instead of a configuration one.
            console.error(f"Approval link rejected: {err}")
            message = "Approvals are not configured on this server."
            if _wants_json(request):
                return JSONResponse({"error": message}, status_code=500)
            return _page("Not available", message, status=500)
        try:
            claims = decode_token(token)
        except WorkflowRuntimeError as err:
            if _wants_json(request):
                return JSONResponse({"error": str(err)}, status_code=400)
            return _page("Link not valid", str(err), status=400)

        if request.method == "GET":
            # A mail client or scanner may fetch this; only a person submits.
            if _wants_json(request):
                return JSONResponse({"status": "confirm", "run_id": claims["r"]})
            return _page(
                "Confirm your response",
                "Submitting this records your decision on the waiting run.",
                form=_FORM.format(label="Confirm"),
            )

        disposition = await runtime.kernel.signal(
            claims["r"],
            ChannelDelivery(channel=claims["c"], payload=claims["p"]),
            key=claims["k"],
        )
        if _wants_json(request):
            return JSONResponse({"status": disposition, "run_id": claims["r"]})
        if disposition == "resolved":
            return _page("Thank you", "Your response has been recorded.")
        if disposition == "duplicate":
            return _page("Already recorded", "This link has already been used.")
        if disposition in ("expired", "run_terminal", "unknown_run"):
            return _page(
                "No longer waiting",
                "This request has already been resolved another way.",
                status=409,
            )
        return _page(
            "Recorded",
            "Your response was saved and will apply when the run reaches it.",
        )

    return endpoint
