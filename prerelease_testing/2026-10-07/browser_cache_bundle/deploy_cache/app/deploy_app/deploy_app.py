"""Account quota dashboard for stale-build hydration and history checks."""

import importlib.metadata
import os
import uuid

import reflex as rx

assert f"/envs/{os.environ['TEST_REFLEX_ENV']}/" in rx.__file__, rx.__file__
print("PUBLISHED_PACKAGE", importlib.metadata.version("reflex"), rx.__file__, flush=True)
REVISION = os.environ.get("DEPLOY_REVISION", "A")


class Account(rx.State):
    """A small account dashboard with per-session state and persisted settings."""

    quota: int = 100 if REVISION == "A" else 250
    tier: str = "Starter" if REVISION == "A" else "Professional"
    ordered_features: dict[str, str] = (
        {"reports": "enabled", "exports": "enabled"}
        if REVISION == "A"
        else {"exports": "enabled", "reports": "enabled"}
    )
    used: int = 0
    density: str = rx.LocalStorage("compact", name="dashboard-density")
    observed: str = ""

    @rx.var
    def remaining(self) -> int:
        """Return the current remaining report quota."""
        return self.quota - self.used

    @rx.event
    def use_report(self):
        """Consume one report and echo the backend's values."""
        self.used += 1
        self.observed = f"{REVISION}:{self.tier}:{self.quota}:{self.used}"

    @rx.event
    def roomy(self):
        """Persist the user's preferred dashboard density."""
        self.density = "roomy"


class Session(rx.State):
    """Keep nondeterministic defaults separate from the deterministic account."""

    identity: str = rx.field(default_factory=lambda: uuid.uuid4().hex)


if os.environ.get("DEPLOY_EXTRA_STATE") == "1":

    class Billing(rx.State):
        """New state introduced by the next backend deployment."""

        currency: str = "USD"


def index():
    """Render the account dashboard compiled into this frontend build."""
    return rx.vstack(
        rx.heading("Report dashboard"),
        rx.text(f"Frontend build {REVISION}", id="build"),
        rx.text(Account.tier, id="tier"),
        rx.text(Account.quota, id="quota"),
        rx.text(Account.used, id="used"),
        rx.text(Account.remaining, id="remaining"),
        rx.text(Session.identity, id="identity"),
        rx.text(Account.density, id="density"),
        rx.text(Account.is_hydrated.to_string(), id="hydrated"),
        rx.foreach(Account.ordered_features, lambda item: rx.text(item[0], class_name="feature")),
        rx.button("Generate report", id="use", on_click=Account.use_report),
        rx.button("Roomy layout", id="roomy", on_click=Account.roomy),
        rx.text(Account.observed, id="observed"),
        rx.el.a("External help", href="http://127.0.0.1:3730/help.html", id="help"),
        padding="2em",
    )


app = rx.App()
app.add_page(index)
