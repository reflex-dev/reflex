"""Demo form component for collecting user information and scheduling enterprise calls.

This module provides a comprehensive demo form that validates company emails,
sends data to PostHog and Slack, and redirects users to appropriate Cal.com links
based on company size.
"""

from typing import Any

import reflex as rx
from reflex.event import EventType
from reflex.experimental.client_state import ClientStateVar
from reflex.vars.base import get_unique_variable_name
from reflex_ui.blocks.telemetry.posthog import track_demo_form_posthog_submission
from reflex_ui.components.base.button import button
from reflex_ui.components.base.dialog import dialog
from reflex_ui.components.base.input import input
from reflex_ui.components.base.textarea import textarea
from reflex_ui.components.icons.hugeicon import hi
from reflex_ui.components.icons.others import select_arrow
from reflex_ui.utils.twmerge import cn

demo_form_error_message = ClientStateVar.create("demo_form_error_message", "")
demo_form_open_cs = ClientStateVar.create("demo_form_open", False)

PERSONAL_EMAIL_PROVIDERS = r"^(?!.*@(gmail|outlook|hotmail|yahoo|icloud|aol|protonmail|mail|yandex|zoho|live|msn|me|mac|googlemail)\.com$|.*@(yahoo|outlook|hotmail)\.co\.uk$|.*@yahoo\.ca$|.*@yahoo\.co\.in$|.*@proton\.me$).*$"


def get_element_value(element_id: str) -> str:
    """Get the value of an element by ID.

    Returns:
        The component.
    """
    return f"document.getElementById('{element_id}')?.value"


def check_if_company_email(email: str) -> bool:
    """Check if an email address is from a company domain (not a personal email provider).

    Args:
        email: The email address to check

    Returns:
        True if it's likely a company email, False if it's from a personal provider
    """
    if not email or "@" not in email:
        return False

    domain = email.split("@")[-1].lower()

    # List of common personal email providers
    personal_domains = {
        "gmail.com",
        "outlook.com",
        "hotmail.com",
        "yahoo.com",
        "icloud.com",
        "aol.com",
        "protonmail.com",
        "proton.me",
        "mail.com",
        "yandex.com",
        "zoho.com",
        "live.com",
        "msn.com",
        "me.com",
        "mac.com",
        "googlemail.com",
        "yahoo.co.uk",
        "yahoo.ca",
        "yahoo.co.in",
        "outlook.co.uk",
        "hotmail.co.uk",
    }

    return domain not in personal_domains and ".edu" not in domain


def check_if_default_value_is_selected(value: str) -> bool:
    """Check if the default value is selected.

    Returns:
        The component.
    """
    return bool(value.strip())


class DemoFormStateUI(rx.State):
    """State for handling demo form submissions and validation."""

    @rx.event
    def validate_email(self, email: str):
        """Validate the email address.

        Yields:
            The event actions.
        """
        if not check_if_company_email(email):
            yield [
                demo_form_error_message.push(
                    "Please enter a valid company email - gmails, aol, me, etc are not allowed"
                ),
            ]
        else:
            yield demo_form_error_message.push("")

    @rx.event
    def track_demo_form_posthog(self, form_data: dict[str, Any]):
        """Send demo form fields to PostHog (identify + capture) in the browser.

        Returns:
            Event that runs PostHog identify and capture in the browser.
        """
        return track_demo_form_posthog_submission(form_data)


def input_field(
    label: str,
    placeholder: str,
    name: str,
    type: str = "text",
    required: bool = False,
) -> rx.Component:
    """Create a labeled input field component.

    Args:
        label: The label text to display above the input
        placeholder: Placeholder text for the input
        name: The name attribute for the input field
        type: The input type (text, email, tel, etc.)
        required: Whether the field is required

    Returns:
        A Reflex component containing the labeled input field
    """
    return rx.el.div(
        rx.el.label(
            label + (" *" if required else ""),
            class_name="block text-sm font-medium text-secondary-12",
        ),
        input(
            placeholder=placeholder,
            name=name,
            type=type,
            required=required,
            max_length=255,
            class_name="w-full",
        ),
        class_name="flex flex-col gap-1.5",
    )


def validation_input_field(
    label: str,
    placeholder: str,
    name: str,
    type: str = "text",
    required: bool = False,
    pattern: str | None = None,
    on_blur: EventType[()] | None = None,
    id: str = "",
) -> rx.Component:
    """Create a labeled input field component.

    Args:
        label: The label text to display above the input
        placeholder: Placeholder text for the input
        name: The name attribute for the input field
        type: The input type (text, email, tel, etc.)
        pattern: Regex pattern for input validation
        required: Whether the field is required
        on_blur: Event handler for when the input is blurred
        id: The ID attribute for the input field

    Returns:
        A Reflex component containing the labeled input field
    """
    return rx.el.div(
        rx.el.label(
            label + (" *" if required else ""),
            class_name="block text-sm font-medium text-secondary-12",
        ),
        input(
            placeholder=placeholder,
            id=id,
            name=name,
            type=type,
            required=required,
            max_length=255,
            pattern=pattern,
            class_name="w-full",
            on_blur=on_blur,
        ),
        class_name="flex flex-col gap-1.5",
    )


def text_area_field(
    label: str, placeholder: str, name: str, required: bool = False
) -> rx.Component:
    """Create a labeled textarea field component.

    Args:
        label: The label text to display above the textarea
        placeholder: Placeholder text for the textarea
        name: The name attribute for the textarea field
        required: Whether the field is required

    Returns:
        A Reflex component containing the labeled textarea field
    """
    return rx.el.div(
        rx.el.label(label, class_name="block text-sm font-medium text-secondary-12"),
        textarea(
            placeholder=placeholder,
            name=name,
            required=required,
            class_name="w-full min-h-14",
            max_length=800,
        ),
        class_name="flex flex-col gap-1.5",
    )


def select_field(
    label: str,
    name: str,
    items: list[str],
    required: bool = False,
) -> rx.Component:
    """Create a labeled select field component.

    Args:
        label: The label text to display above the select
        name: The name attribute for the select field
        items: List of options to display in the select
        required: Whether the field is required

    Returns:
        A Reflex component containing the labeled select field
    """
    return rx.el.div(
        rx.el.label(
            label + (" *" if required else ""),
            class_name="block text-xs lg:text-sm font-medium text-secondary-12 truncate min-w-0",
        ),
        rx.el.div(
            rx.el.select(
                rx.el.option("Select", value=""),
                *[rx.el.option(item, value=item) for item in items],
                default_value="",
                name=name,
                required=required,
                class_name=cn(
                    "w-full appearance-none pr-9",
                    button.class_names.for_button("outline", "md"),
                    "outline-primary-6 focus:border-primary-6",
                ),
            ),
            select_arrow(
                class_name="size-4 text-secondary-9 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
            ),
            class_name="relative",
        ),
        class_name="flex flex-col gap-1.5 min-w-0",
    )


def demo_form(id_prefix: str = "", **props) -> rx.Component:
    """Create and return the demo form component.

    Builds a complete form with all required fields, validation,
    and styling. The form includes personal info, company details,
    and preferences.

    Args:
        id_prefix: Optional prefix for all element IDs to ensure uniqueness when multiple forms exist.
                If empty, a unique prefix will be auto-generated.
        **props: Additional properties to pass to the form component

    Returns:
        A Reflex form component with all demo form fields
    """
    prefix = id_prefix or get_unique_variable_name()
    email_id = f"{prefix}_user_email"
    form = rx.el.form(
        rx.el.div(
            input_field("First name", "John", "first_name", "text", True),
            input_field("Last name", "Smith", "last_name", "text", True),
            class_name="grid grid-cols-2 gap-4",
        ),
        validation_input_field(
            "Business Email",
            "john@company.com",
            "email",
            "email",
            True,
            PERSONAL_EMAIL_PROVIDERS,
            id=email_id,
            on_blur=DemoFormStateUI.validate_email(rx.Var(get_element_value(email_id))),
        ),
        rx.el.div(
            input_field("Job title", "CTO", "job_title", "text", True),
            input_field("Company name", "Pynecone, Inc.", "company_name", "text", True),
            class_name="grid grid-cols-2 gap-4",
        ),
        text_area_field(
            "What are you looking to build? *",
            "Please list any apps, requirements, or data sources you plan on using",
            "internal_tools",
            True,
        ),
        rx.el.div(
            select_field(
                "Number of employees?",
                "number_of_employees",
                ["1", "2-5", "6-10", "11-50", "51-100", "101-500", "500+"],
                required=True,
            ),
            select_field(
                "How did you hear about us?",
                "how_did_you_hear_about_us",
                [
                    "Google Search",
                    "Social Media",
                    "Word of Mouth",
                    "Blog",
                    "Conference",
                    "LLM (Claude, ChatGPT, etc)",
                    "Other",
                ],
                required=True,
            ),
            class_name="grid grid-cols-1 md:grid-cols-2 gap-4",
        ),
        select_field(
            "How technical are you?",
            "technical_level",
            ["Non-technical", "Neutral", "Technical"],
            True,
        ),
        rx.cond(
            demo_form_error_message.value,
            rx.el.span(
                demo_form_error_message.value,
                class_name="text-destructive-10 text-sm font-medium px-2 py-1 rounded-md bg-destructive-3 border border-destructive-4",
            ),
        ),
        button(
            "Submit",
            type="submit",
            class_name="w-full",
        ),
        class_name=cn(
            "@container flex flex-col lg:gap-6 gap-2 p-6",
            props.pop("class_name", ""),
        ),
        on_submit=[
            DemoFormStateUI.track_demo_form_posthog,
            rx.call_function(demo_form_open_cs.set_value(False)),
        ],
        data_default_form_id="965991",
        **props,
    )
    return rx.fragment(
        form,
    )


def demo_form_dialog(
    trigger: rx.Component | None = None, id_prefix: str = "", **props
) -> rx.Component:
    """Return a demo form dialog container element.

    Args:
        trigger: The component that triggers the dialog
        id_prefix: Optional prefix for all element IDs to ensure uniqueness when multiple dialogs exist
        **props: Additional properties to pass to the dialog root

    Returns:
        A Reflex dialog component containing the demo form
    """
    if trigger is None:
        trigger = rx.fragment()
    class_name = cn("w-auto", props.pop("class_name", ""))
    return dialog.root(
        dialog.trigger(render_=trigger),
        dialog.portal(
            dialog.backdrop(),
            dialog.popup(
                rx.el.div(
                    rx.el.div(
                        rx.el.h1(
                            "Book a Demo",
                            class_name="text-xl font-bold text-secondary-12",
                        ),
                        dialog.close(
                            render_=button(
                                hi("Cancel01Icon"),
                                variant="ghost",
                                size="icon-sm",
                                class_name="text-secondary-11",
                            ),
                        ),
                        class_name="flex flex-row justify-between items-center gap-1 px-6 pt-4 -mb-4",
                    ),
                    demo_form(id_prefix=id_prefix, class_name="w-full max-w-md"),
                    class_name="relative isolate overflow-hidden -m-px w-full max-w-md",
                ),
                class_name="h-fit mt-1 overflow-hidden w-full max-w-md",
            ),
        ),
        open=demo_form_open_cs.value,
        on_open_change=demo_form_open_cs.set_value,
        on_open_change_complete=[
            rx.call_function(demo_form_error_message.set_value(""))
        ],
        class_name=class_name,
        **props,
    )
