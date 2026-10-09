from typing import Any, Optional

import reflex as rx
import reflex_local_auth
import sqlmodel
from reflex_local_auth.pages.components import MIN_WIDTH, PADDING_TOP, input_100w


class UserInfo(sqlmodel.SQLModel, table=True):
    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    email: str
    created_from_ip: str

    user_id: int = sqlmodel.Field(foreign_key="localuser.id")


class MyLocalAuthState(reflex_local_auth.LocalAuthState):
    @rx.var(cache=True, initial_value=None)
    def authenticated_user_info(self) -> Optional[UserInfo]:
        if self.authenticated_user.id is not None and self.authenticated_user.id < 0:
            return
        with rx.session() as session:
            return session.exec(
                sqlmodel.select(UserInfo).where(
                    UserInfo.user_id == self.authenticated_user.id
                ),
            ).one_or_none()


class MyRegisterState(reflex_local_auth.RegistrationState):
    @rx.event
    def handle_registration_email(self, form_data: dict[str, Any]):
        registration_result = self.handle_registration(form_data)
        if self.new_user_id >= 0:
            with rx.session() as session:
                session.add(
                    UserInfo(
                        email=form_data["email"],
                        created_from_ip=getattr(
                            self.router.headers,
                            "x_forwarded_for",
                            self.router.session.client_ip,
                        ),
                        user_id=self.new_user_id,
                    )
                )
                session.commit()
        return registration_result


def register_error() -> rx.Component:
    """Render the registration error message."""
    return rx.cond(
        reflex_local_auth.RegistrationState.error_message != "",
        rx.callout(
            reflex_local_auth.RegistrationState.error_message,
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
    )


def register_form() -> rx.Component:
    """Render the registration form."""
    return rx.form(
        rx.vstack(
            rx.heading("Create an account with Email and IP tracking", size="7"),
            register_error(),
            rx.text("Username"),
            input_100w("username"),
            rx.text("Email"),
            input_100w("email"),
            rx.text("Password"),
            input_100w("password", type="password"),
            rx.text("Confirm Password"),
            input_100w("confirm_password", type="password"),
            rx.button("Sign up", width="100%"),
            rx.center(
                rx.link(
                    "Login",
                    on_click=lambda: rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE),
                ),
                width="100%",
            ),
            min_width=MIN_WIDTH,
        ),
        on_submit=MyRegisterState.handle_registration_email,
    )


@rx.page(route="/custom-register")
def register_page() -> rx.Component:
    """Render the registration page.

    Returns:
        A reflex component.
    """

    return rx.center(
        rx.cond(
            reflex_local_auth.RegistrationState.success,
            rx.vstack(
                rx.text("Registration successful!"),
            ),
            rx.card(register_form()),
        ),
        padding_top=PADDING_TOP,
    )


@rx.page()
@reflex_local_auth.require_login
def user_info():
    return rx.vstack(
        rx.text(f"Username: {MyLocalAuthState.authenticated_user.username}"),
        rx.cond(
            MyLocalAuthState.authenticated_user_info,
            rx.fragment(
                rx.text(f"Email: {MyLocalAuthState.authenticated_user_info.email}"),
                rx.text(
                    f"Account Created From: {MyLocalAuthState.authenticated_user_info.created_from_ip}"
                ),
            ),
            rx.text(f"No extra UserInfo for {MyLocalAuthState.authenticated_user.id}"),
        ),
        align="center",
    )
