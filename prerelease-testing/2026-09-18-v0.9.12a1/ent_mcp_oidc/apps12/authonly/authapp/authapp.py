"""OIDC auth exercise app: secure-by-default AuthPlugin against a local IdP.

Combines auth-tagged state with rx.memo, ComponentState and a background event
to check the guards hold across the less-travelled component paths.
"""

import asyncio

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState, GenericOIDCAuthState


_SHARED = {"v": "default-shared"}


class PublicState(rx.State):
    """State whose surface is explicitly public."""

    hits: int = rxe.field(0, auth=False)
    secret_note: str = rxe.field("top-secret", auth=True)

    @rxe.var(auth=False)
    def hits_label(self) -> str:
        """Public computed var."""
        return f"hits={self.hits}"

    @rxe.var(auth=True)
    def secret_label(self) -> str:
        """Protected computed var."""
        return f"secret={self.secret_note}"

    @rxe.var(auth=True, cache=False)
    def shared_label(self) -> str:
        """Protected uncached computed var over server-side shared data."""
        return f"shared={_SHARED['v']}"

    @rxe.var(auth=False, cache=False)
    def note_echo(self) -> str:
        """Public uncached var echoing the protected field's value."""
        return f"echo={self.secret_note}"

    @rxe.event(auth=False)
    def bump(self):
        """Public handler."""
        self.hits += 1

    @rxe.event(auth=False)
    def poison_shared(self):
        """Public handler that writes a server-only value read by a protected var."""
        _SHARED["v"] = "SERVER-ONLY-SECRET"
        self.hits += 1

    @rxe.event(auth=False)
    def poison_field(self):
        """Public handler that writes into the protected field."""
        self.secret_note = "FIELD-SECRET"
        self.hits += 1

    @rxe.event(auth=True)
    def set_secret(self, value: str):
        """Protected handler."""
        self.secret_note = value

    @rxe.event(auth=True, background=True)
    async def slow_secret(self):
        """Protected background handler."""
        await asyncio.sleep(0.1)
        async with self:
            self.secret_note = self.secret_note + "!"


class Whoami(rx.ComponentState):
    """ComponentState reading the authenticated user."""

    clicks: int = rxe.field(0, auth=False)

    @rxe.event(auth=False)
    def click(self):
        """Bump the click counter."""
        self.clicks += 1

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        """Render."""
        return rx.vstack(
            rx.text(f"cs-clicks: {cls.clicks}", id="cs-clicks"),
            rx.button("cs-click", on_click=cls.click, id="cs-click"),
        )


@rx.memo
def memo_user(name: rx.Var[str]) -> rx.Component:
    """Memoized component fed an auth-derived var."""
    return rx.text(f"memo:{name}", id="memo-user")


def nav() -> rx.Component:
    """Shared nav."""
    return rx.hstack(
        rx.link("home", href="/", id="nav-home"),
        rx.link("secret", href="/secret", id="nav-secret"),
        rx.link("login", href="/login", id="nav-login"),
        rx.link("logout", href="/logout", id="nav-logout"),
    )


@rxe.page(route="/", auth=False)
def index() -> rx.Component:
    """Public landing page."""
    return rx.container(
        nav(),
        rx.heading("public"),
        rx.text(PublicState.hits_label, id="hits"),
        rx.text(AuthUserState.provider_name, id="provider"),
        rx.text(rx.cond(AuthUserState.email != "", AuthUserState.email, "no-user"), id="email"),
        memo_user(name=rx.cond(AuthUserState.email != "", AuthUserState.email, "anon")),
        Whoami.create(),
        rx.button("bump", on_click=PublicState.bump, id="bump"),
        rx.button("set-secret", on_click=PublicState.set_secret("changed"), id="set-secret"),
        rx.button("slow-secret", on_click=PublicState.slow_secret, id="slow-secret"),
        rx.text(PublicState.secret_label, id="secret-label"),
        rx.text(PublicState.shared_label, id="shared-label"),
        rx.text(PublicState.note_echo, id="note-echo"),
        rx.text(PublicState.secret_note, id="secret-note-raw"),
        rx.button("poison-shared", on_click=PublicState.poison_shared, id="poison-shared"),
        rx.button("poison-field", on_click=PublicState.poison_field, id="poison-field"),
    )


@rxe.page(route="/secret", auth=True)
def secret() -> rx.Component:
    """Protected page."""
    return rx.container(
        nav(),
        rx.heading("secret page", id="secret-heading"),
        rx.text(PublicState.secret_label, id="secret-label-2"),
        rx.text(rx.cond(AuthUserState.email != "", AuthUserState.email, "no-user"), id="secret-email"),
        rx.button("set-secret", on_click=PublicState.set_secret("changed-on-secret"), id="set-secret-2"),
    )


app = rxe.App()
