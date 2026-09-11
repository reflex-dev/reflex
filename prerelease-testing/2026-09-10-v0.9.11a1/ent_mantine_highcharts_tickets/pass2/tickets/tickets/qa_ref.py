"""ADDED BY PRE-RELEASE QA (not part of the shipped demo).

Diagnostic for the dead-UI finding: the page at ``/`` never dispatches an event
because the hydrate delta carries reflex-enterprise's OIDC auth substates, for
which the compiled page has no dispatch function, and reflex latches
``backend_state_mismatch`` permanently.  This page renders the very same ticket
UI plus a reference to those two substates, which makes the compiler emit
dispatch functions for them.  If this page works while ``/`` does not, the
mechanism is confirmed and "render something from every substate the backend
knows about" is the workaround.

Only registered when QA_REF=1 is set.
"""

import os

import reflex as rx

if os.environ.get("QA_REF"):
    from reflex_enterprise.auth.oidc.state import GenericOIDCAuthState, IsIframedState

    from .tickets import TicketState, index

    def ref_page() -> rx.Component:
        """The ticket list plus a reference to the unrendered auth substates.

        Returns:
            The page component.
        """
        return rx.fragment(
            rx.text(
                "iframed: ",
                IsIframedState.is_iframed.to_string(),
                " | oidc_error: ",
                GenericOIDCAuthState.user_error_message,
                id="qa-ref",
            ),
            index(),
        )

    page = rx.page(route="/ref", title="QA dispatch reference", on_load=TicketState.load_tickets)(
        ref_page
    )

    from .tickets import ticket_page

    def ref_detail_page() -> rx.Component:
        """The ticket detail page plus the same substate reference.

        Returns:
            The page component.
        """
        return rx.fragment(
            rx.text("iframed: ", IsIframedState.is_iframed.to_string(), id="qa-ref"),
            ticket_page(),
        )

    detail = rx.page(
        route="/ticket-ref",
        title="QA dispatch reference detail",
        on_load=TicketState.load_ticket_detail,
    )(ref_detail_page)
