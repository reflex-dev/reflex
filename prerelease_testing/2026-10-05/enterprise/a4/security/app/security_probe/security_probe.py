"""Use ordinary app default factories to simulate a cleanup dependency outage."""

import json
from pathlib import Path

import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState
from reflex_enterprise.auth.oidc.state import GenericOIDCAuthState

ROOT = Path("/private/tmp/reflex-enterprise-a4-20261005-security")


def fresh_record() -> dict[str, str]:
    """Load a default record, failing when the app dependency is unavailable.

    Returns:
        The empty per-user record.

    Raises:
        RuntimeError: The simulated app dependency is unavailable.
    """
    if (ROOT / "frontend-unavailable").exists():
        raise RuntimeError("Application record-default service unavailable")
    return {"owner": "none", "secret": "empty"}


def fresh_cache() -> dict[str, str]:
    """Load a default backend cache, failing during the simulated outage.

    Returns:
        The empty per-user cache.

    Raises:
        RuntimeError: The simulated cache dependency is unavailable.
    """
    if (ROOT / "backend-unavailable").exists():
        raise RuntimeError("Application cache-default service unavailable")
    return {"owner": "none", "secret": "empty"}


class BackendState(rx.State):
    """Hold protected per-user data in an ordinary factory-backed cache."""

    _cache: dict[str, str] = rx.field(default_factory=fresh_cache)

    @rxe.var(initial_value="private-placeholder")
    def private_cache(self) -> str:
        """Read the protected cached secret.

        Returns:
            The cache's secret marker.
        """
        return self._cache["secret"]


class ActionState(rx.State):
    """Expose nonsecret action audit fields without making the action public."""

    calls: int = rxe.field(0, auth=False)
    last_actor: str = rxe.field("none", auth=False)

    @rxe.event
    async def protected_action(self):
        """Record a real protected mutation without overwriting private records."""
        user = await AuthUserState.current() or {}
        self.calls += 1
        self.last_actor = user.get("sub", "anonymous")
        with (ROOT / "logs/actions.jsonl").open("a") as output:
            output.write(
                json.dumps({"actor": self.last_actor, "calls": self.calls}) + "\n"
            )


class RecordState(rx.State):
    """Keep an app record whose factory can fail independently of auth code."""

    private_record: dict[str, str] = rx.field(default_factory=fresh_record)
    armed: str = rxe.field("none", auth=False)

    @rxe.event
    async def prime(self):
        """Populate both private stores with the current user's distinct marker."""
        user = await AuthUserState.current() or {}
        actor = user.get("sub", "anonymous")
        record = {"owner": actor, "secret": actor + "-PRIVATE-RECORD"}
        self.private_record = record
        backend = await self.get_state(BackendState)
        backend._cache = {"owner": actor, "secret": actor + "-PRIVATE-CACHE"}

    @rxe.event
    def arm_frontend(self):
        """Simulate loss of the frontend record's default dependency."""
        (ROOT / "frontend-unavailable").touch()
        self.armed = "frontend"

    @rxe.event
    def arm_backend(self):
        """Simulate loss of the server-side cache's default dependency."""
        (ROOT / "backend-unavailable").touch()
        self.armed = "backend"

    @rxe.event(auth=False)
    def recover_dependency(self):
        """Restore the app's simulated dependency without touching auth internals."""
        (ROOT / "frontend-unavailable").unlink(missing_ok=True)
        (ROOT / "backend-unavailable").unlink(missing_ok=True)
        self.armed = "none"

    @rxe.mcp.resource
    def private_summary(self) -> dict[str, str]:
        """Read the authenticated caller's record through a protected MCP resource.

        Returns:
            The caller's private record.
        """
        return self.private_record


def surface() -> rx.Component:
    """Show private data, current identity, and independently observed actions.

    Returns:
        The shared public diagnostic page.
    """
    return rx.vstack(
        rx.text(AuthUserState.sub, id="identity"),
        rx.text(RecordState.private_record.to_string(), id="private-record"),
        rx.text(BackendState.private_cache, id="private-cache"),
        rx.text(ActionState.calls, id="calls"),
        rx.text(ActionState.last_actor, id="last-actor"),
        rx.text(RecordState.armed, id="armed"),
        GenericOIDCAuthState.get_login_button(),
        rx.button("Prime private data", on_click=RecordState.prime),
        rx.button("Protected action", on_click=ActionState.protected_action),
        rx.button("Arm frontend outage", on_click=RecordState.arm_frontend),
        rx.button("Arm backend outage", on_click=RecordState.arm_backend),
        rx.button("Recover dependency", on_click=RecordState.recover_dependency),
        rx.button("Logout", on_click=AuthUserState.logout),
    )


@rxe.page(route="/", auth=False)
def index() -> rx.Component:
    """Render protected surfaces on a public page.

    Returns:
        The diagnostic component.
    """
    return surface()


@rxe.page(route="/profile")
def profile() -> rx.Component:
    """Require login before showing the same diagnostic surface.

    Returns:
        The diagnostic component.
    """
    return surface()


app = rxe.App()
