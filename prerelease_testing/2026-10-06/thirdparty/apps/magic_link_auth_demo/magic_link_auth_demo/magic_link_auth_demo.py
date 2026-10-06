from typing import Any

import reflex as rx
import reflex_google_recaptcha_v2
from reflex.utils.exec import is_prod_mode
from reflex_magic_link_auth import MagicLinkAuthState, send_magic_link_mailgun

# These are test keys
if not reflex_google_recaptcha_v2.is_key_set():
    reflex_google_recaptcha_v2.set_site_key("6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI")
    reflex_google_recaptcha_v2.set_secret_key(
        "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
    )


class State(rx.State):
    login_error: str = ""

    @rx.var(cache=True)
    def is_prod_mode(self) -> bool:
        return is_prod_mode()

    @rx.event
    async def handle_submit_login(self, form_data: dict[str, Any]):
        magic_link = await self.get_state(MagicLinkAuthState)
        self.login_error = ""
        record, otp = magic_link._generate_otp(form_data["email"])
        if otp is None or record is None:
            if record is not None:
                self.login_error = "Too many attempts. Please try again later."
            else:
                self.login_error = (
                    "Invalid email, or too many attempts. Please try again later."
                )
            return
        if self.is_prod_mode:
            recaptcha_state = await self.get_state(
                reflex_google_recaptcha_v2.GoogleRecaptchaV2State
            )
            if not recaptcha_state.token_is_valid:
                self.login_error = "Captcha verification failed. Please try again."
                return
        yield rx.redirect("/check-your-email")
        if self.is_prod_mode:
            try:
                send_magic_link_mailgun(
                    record.email,
                    magic_link._get_magic_link(record, otp),
                )
            except Exception as e:
                print(e)  # noqa: T201
        else:
            print(magic_link._get_magic_link(record, otp))  # noqa: T201


def login_controls() -> rx.Component:
    return rx.vstack(
        rx.input(name="email", placeholder="Email", type="email", width="100%"),
        rx.cond(
            State.is_prod_mode,
            reflex_google_recaptcha_v2.google_recaptcha_v2(),
        ),
        rx.button("Send Magic Link", width="100%"),
    )


def login_form() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Enter your email to log in", size="8", margin_bottom="10px"),
            rx.cond(
                State.login_error,
                rx.callout.root(
                    rx.callout.text(State.login_error, color="red"),
                    width="100%",
                ),
            ),
            rx.form(
                login_controls(),
                on_submit=State.handle_submit_login,
                on_mount=MagicLinkAuthState.get_base_url,
            ),
            align="center",
        ),
        margin="25px",
    )


def home() -> rx.Component:
    return rx.vstack(
        rx.heading("Welcome back!", size="9"),
        rx.text(f"You are logged in as {MagicLinkAuthState.auth_session.email}."),
        rx.button("Logout", on_click=MagicLinkAuthState.logout),
        align="center",
        spacing="7",
    )


def index() -> rx.Component:
    return rx.cond(
        State.is_hydrated,
        rx.cond(
            MagicLinkAuthState.session_is_valid,
            home(),
            rx.vstack(login_form(), align="center"),
        ),
    )


@rx.page()
def check_your_email() -> rx.Component:
    return rx.vstack(
        rx.heading("Check your email for a magic link!", size="9"),
        rx.text("This page will redirect when your session is validated."),
        rx.moment(
            interval=rx.cond(
                MagicLinkAuthState.session_is_valid,
                500,
                0,
            ),
            on_change=rx.redirect("/"),
            display="none",
        ),
        align="center",
        spacing="7",
    )


# Add state and page to the app.
app = rx.App()
app.add_page(index)

# Create the database if it does not exist (hosting service does not migrate automatically)
rx.Model.migrate()
