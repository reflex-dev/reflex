"""Signup module."""

import contextlib
import os
from typing import Any

import httpx
from email_validator import EmailNotValidError, ValidatedEmail, validate_email

import reflex as rx
from reflex_site_shared.constants import (
    API_BASE_URL_LOOPS,
    REFLEX_DEV_WEB_NEWSLETTER_FORM_WEBHOOK_URL,
)


class IndexState(rx.State):
    """Hold the state for the home page."""

    # Whether the user signed up for the newsletter.
    signed_up: bool = False

    # Whether to show the confetti.
    show_confetti: bool = False

    @rx.event(background=True)
    async def send_contact_to_webhook(
        self,
        email: str | None,
    ) -> None:
        """Send contact to webhook."""
        with contextlib.suppress(httpx.HTTPError):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    REFLEX_DEV_WEB_NEWSLETTER_FORM_WEBHOOK_URL,
                    json={
                        "email": email,
                    },
                )
            response.raise_for_status()

    @rx.event(background=True)
    async def add_contact_to_loops(
        self,
        email: str | None,
    ):
        """Add contact to loops."""
        url: str = f"{API_BASE_URL_LOOPS}/contacts/create"
        loops_api_key: str | None = os.getenv("LOOPS_API_KEY")
        if loops_api_key is None:
            return

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {loops_api_key}",
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={
                        "email": email,
                    },
                )
                response.raise_for_status()  # Raise an exception for HTTP errors (4xx and 5xx)

        except httpx.HTTPError:
            pass

    @rx.event
    def signup_for_another_user(self):
        """Signup for another user."""
        self.signed_up = False

    @rx.event(background=True)
    async def signup(
        self,
        form_data: dict[str, Any],
    ):
        """Sign the user up for the newsletter.

        Yields:
            The event actions.
        """
        email: str | None = None
        if email_to_validate := form_data.get("input_email"):
            try:
                validated_email: ValidatedEmail = validate_email(
                    email_to_validate,
                    check_deliverability=True,
                )
                email = validated_email.normalized

            except EmailNotValidError as e:
                # Alert the error message.
                yield rx.toast.warning(
                    str(e),
                    style={
                        "border": "1px solid #3C3646",
                        "background": "linear-gradient(218deg, #1D1B23 -35.66%, #131217 100.84%)",
                    },
                )
                return
        yield IndexState.send_contact_to_webhook(email)
        yield IndexState.add_contact_to_loops(email)
        async with self:
            self.signed_up = True
            yield
        yield [
            rx.toast.success("Thanks for signing up to the Newsletter!"),
        ]
