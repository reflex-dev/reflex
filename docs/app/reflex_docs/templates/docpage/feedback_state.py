"""The state for the integration request form."""

import reflex as rx
from reflex_site_shared.backend.slack import escape_slack_text, post_to_slack
from reflex_site_shared.constants import SLACK_INTEGRATION_REQUEST_CHANNEL


class FeedbackState(rx.State):
    """The state for the integration request form."""

    @rx.event
    async def handle_integration_request(self, form_data: dict):
        """Post an integration request to the integration request Slack channel.

        Args:
            form_data: Submitted request fields.

        Returns:
            A toast telling the reader whether the request was sent.
        """
        request = form_data.get("request", "")
        if not 10 <= len(request) <= 2000:
            return rx.toast.warning(
                "Please describe your integration request. Between 10 and 2000 characters.",
                close_button=True,
            )

        message = f"Integration Request: {escape_slack_text(request)}"
        if not await post_to_slack(message, SLACK_INTEGRATION_REQUEST_CHANNEL):
            return rx.toast.error(
                "An error occurred while submitting your request. If the issue "
                "persists, please file a GitHub issue or stop by our Discord.",
                close_button=True,
            )
        return rx.toast.success(
            "Thank you for your integration request!",
            close_button=True,
        )
