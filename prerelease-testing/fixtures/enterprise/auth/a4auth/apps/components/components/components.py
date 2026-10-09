"""Minimal own app for the anonymous MCP check (a4auth/check_mcp.py).

The 10-05 matrix ran this check against a copy of reflex-enterprise's integration-test AG Grid app plus map demo
modules; check_mcp.py only touches AgentState, so the fixture keeps just that (no proprietary enterprise source).
"""

import reflex_enterprise as rxe

import reflex as rx


class AgentState(rx.State):
    """Small state surface for anonymous MCP session isolation checks."""

    count: int = 0

    @rx.event
    def bump(self, amount: int = 1):
        """Increment the current agent session.

        Args:
            amount: Counter increment.
        """
        self.count += amount

    @rx.var
    def doubled(self) -> int:
        """Return the counter multiplied by two.

        Returns:
            Twice the current counter.
        """
        return self.count * 2

    @rxe.mcp.resource
    def summary(self, label: str) -> dict:
        """Return a parameterized read-only summary.

        Args:
            label: Label supplied through the resource URI.

        Returns:
            The label and current counter.
        """
        return {"label": label, "count": self.count}


def index() -> rx.Component:
    """Show the counter.

    Returns:
        The index page.
    """
    return rx.vstack(rx.text(AgentState.count), rx.button("bump", on_click=AgentState.bump(1)))


app = rxe.App()
app.add_page(index)
