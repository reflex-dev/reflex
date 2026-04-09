"""The state for the navbar component."""

import contextlib
from typing import Optional

import httpx
import reflex as rx
from httpx import Response
from reflex_ui_shared.constants import REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL


class FeedbackState(rx.State):
    """The state for feedback components."""

    score: Optional[int] = None

    @rx.event
    def set_score(self, value: int):
        self.score = value

    def _send_to_webhook(self, payload: dict, webhook_url: str) -> bool:
        """Send payload to webhook URL.

        Returns:
            True if successful, False otherwise
        """
        try:
            with httpx.Client() as client:
                response: Response = client.post(
                    webhook_url,
                    json=payload,
                )
                response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def _build_feedback_message(self, form_data: dict) -> str:
        """Build Discord message for feedback form."""
        current_page_route: str = self.router.page.raw_path
        email: str = form_data.get("email", "")
        feedback: str = form_data["feedback"]

        return f"""
Contact: {email}
Page: {current_page_route}
Score: {"👍" if self.score == 1 else "👎"}
Feedback: {feedback}
"""

    def _build_integration_request_message(self, form_data: dict) -> str:
        """Build Discord message for integration request form."""
        request: str = form_data["request"]

        return f"""
Integration Request: {request}
"""

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle feedback form submission."""
        feedback = form_data.get("feedback", "")

        # Validation
        if len(feedback) < 10 or len(feedback) > 500:
            return rx.toast.warning(
                "Please enter your feedback. Between 10 and 500 characters.",
                close_button=True,
            )

        # Send to general webhook (suppressed errors)
        with contextlib.suppress(httpx.HTTPError) and httpx.Client() as client:
            client.post(
                REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL,
                json=form_data,
            )

        # Build and send Discord message
        discord_message = self._build_feedback_message(form_data)
        payload = {"text": discord_message}

        success = self._send_to_webhook(
            payload, REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL
        )

        if not success:
            return rx.toast.error(
                """An error occurred while submitting your feedback. If the issue persists,
please file a Github issue or stop by our Discord.""",
                close_button=True,
            )

        yield rx.toast.success(
            "Thank you for your feedback!",
            close_button=True,
        )

    @rx.event
    def handle_integration_request(self, form_data: dict):
        """Handle integration request form submission."""
        request = form_data.get("request", "")

        # Validation
        if len(request) < 10 or len(request) > 2000:
            return rx.toast.warning(
                "Please describe your integration request. Between 10 and 2000 characters.",
                close_button=True,
            )

        # Build and send Discord message
        discord_message = self._build_integration_request_message(form_data)
        payload = {"text": discord_message}

        success = self._send_to_webhook(
            payload, REFLEX_DEV_WEB_GENERAL_FORM_FEEDBACK_WEBHOOK_URL
        )

        if not success:
            return rx.toast.error(
                """An error occurred while submitting your request. If the issue persists,
please file a Github issue or stop by our Discord.""",
                close_button=True,
            )

        yield rx.toast.success(
            "Thank you for your integration request!",
            close_button=True,
        )
