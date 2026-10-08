import io
import json

import google.oauth2.credentials
import reflex as rx
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from reflex_google_auth import (
    GoogleAuthState,
    handle_google_login,
    require_google_login,
)


class State(GoogleAuthState):
    @rx.var(cache=True)
    def protected_content(self) -> str:
        if self.token_is_valid:
            return f"This content can only be viewed by a logged in User. Nice to see you {self.tokeninfo.get('name')}"
        return "Not logged in."


def user_info(tokeninfo: rx.vars.ObjectVar) -> rx.Component:
    return rx.hstack(
        rx.avatar(
            src=tokeninfo["picture"],
            fallback=tokeninfo["name"],
            size="5",
        ),
        rx.vstack(
            rx.heading(tokeninfo["name"], size="6"),
            rx.text(tokeninfo["email"]),
            align_items="flex-start",
        ),
        rx.button("Logout", on_click=GoogleAuthState.logout),
        padding="10px",
    )


def index():
    return rx.vstack(
        rx.heading("Google OAuth", size="8"),
        rx.link("Protected Page", href="/protected"),
        rx.link("Partially Protected Page", href="/partially-protected"),
        rx.link("Custom Login Button", href="/custom-button"),
        rx.link("Custom Scope", href="/custom-scope"),
        align="center",
    )


@rx.page(route="/protected")
@require_google_login
def protected() -> rx.Component:
    return rx.vstack(
        user_info(GoogleAuthState.tokeninfo),
        rx.text(State.protected_content),
        rx.link("Home", href="/"),
    )


@require_google_login
def user_name_or_sign_in() -> rx.Component:
    return rx.heading(GoogleAuthState.tokeninfo["name"], size="6")


@rx.page(route="/partially-protected")
def partially_protected() -> rx.Component:
    return rx.vstack(
        rx.heading("This page is partially protected."),
        rx.text(
            "If you are signed in with google, you should see your name below, otherwise "
            "you will see a sign in button",
        ),
        user_name_or_sign_in(),
    )


@rx.page(route="/custom-button")
@require_google_login(
    button=rx.button("Google Login 🚀", on_click=handle_google_login())
)
def custom_button() -> rx.Component:
    return rx.vstack(
        user_info(GoogleAuthState.tokeninfo),
        "You clicked a custom button to login, nice",
    )


class DriveState(rx.State):
    app_data: str = ""
    loading: bool = False

    async def _get_config_json_metadata(self) -> dict[str, str] | None:
        google_auth_state = await self.get_state(GoogleAuthState)
        if not google_auth_state.token_is_valid:
            return None
        credentials = google.oauth2.credentials.Credentials(
            google_auth_state.access_token,
            refresh_token=google_auth_state.refresh_token,
        )
        service = build("drive", "v3", credentials=credentials)
        results = await rx.run_in_thread(
            service.files()
            .list(
                spaces="appDataFolder",
                fields="nextPageToken, files(id, name)",
                pageSize=10,
            )
            .execute
        )
        items = results.get("files", [])
        if not items:
            print("No files found.")  # noqa: T201
            return None
        return items[0]

    async def _save_file_to_drive(self, content: str):
        google_auth_state = await self.get_state(GoogleAuthState)
        if not google_auth_state.token_is_valid:
            return
        credentials = google.oauth2.credentials.Credentials(
            google_auth_state.access_token,
            refresh_token=google_auth_state.refresh_token,
        )
        payload = {
            "content": content,
        }
        service = build("drive", "v3", credentials=credentials)
        upload_content = MediaIoBaseUpload(
            io.BytesIO(json.dumps(payload).encode("utf-8")),
            mimetype="application/json",
            resumable=True,
        )

        existing_file = await self._get_config_json_metadata()
        if existing_file:
            file = await rx.run_in_thread(
                service.files()
                .update(
                    fileId=existing_file["id"], media_body=upload_content, fields="id"
                )
                .execute
            )
        else:
            file_metadata = {
                "name": "config.json",
                "parents": ["appDataFolder"],
            }
            file = await rx.run_in_thread(
                service.files()
                .create(body=file_metadata, media_body=upload_content, fields="id")
                .execute
            )
        print(f"File ID: {file.get('id')}")  # noqa: T201

    async def _load_file_from_drive(self) -> str:
        google_auth_state = await self.get_state(GoogleAuthState)
        if not google_auth_state.token_is_valid:
            return ""
        credentials = google.oauth2.credentials.Credentials(
            google_auth_state.access_token,
            refresh_token=google_auth_state.refresh_token,
        )
        service = build("drive", "v3", credentials=credentials)
        existing_file = await self._get_config_json_metadata()
        if not existing_file:
            return ""
        try:
            # pylint: disable=maybe-no-member
            request = await rx.run_in_thread(
                lambda: service.files().get_media(fileId=existing_file["id"])
            )
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = await rx.run_in_thread(downloader.next_chunk)
        except HttpError as error:
            print(f"An error occurred: {error}")  # noqa: T201
            file = None
        if file:
            file.seek(0)
            try:
                payload = json.loads(file.read().decode("utf-8"))
                return payload.get("content", "")
            except Exception as exc:
                print(f"Error reading config file: {exc!r}")  # noqa: T201
        return ""

    @rx.event
    async def set_app_data(self, value: str):
        self.app_data = value
        self.loading = True
        yield
        try:
            await self._save_file_to_drive(value)
        finally:
            self.loading = False

    @rx.event
    async def on_load(self):
        self.loading = True
        yield
        try:
            self.app_data = await self._load_file_from_drive()
        finally:
            self.loading = False


@rx.page(route="/custom-scope", on_load=DriveState.on_load)
@require_google_login(
    button=rx.button(
        "Login with Drive API scope",
        on_click=handle_google_login(
            scope=(
                "https://www.googleapis.com/auth/drive.appdata "
                "https://www.googleapis.com/auth/drive.file "
                "https://www.googleapis.com/auth/drive.install "
            ),
        ),
    )
)
def custom_scope() -> rx.Component:
    return rx.vstack(
        user_info(GoogleAuthState.tokeninfo),
        rx.vstack(
            rx.heading("App Data Stored in Drive"),
            rx.hstack(
                rx.text_area(
                    default_value=DriveState.app_data,
                    key=DriveState.app_data,
                    on_blur=DriveState.set_app_data,
                ),
                rx.cond(
                    DriveState.loading,
                    rx.spinner(),
                    rx.button("Refresh", on_click=DriveState.on_load),
                ),
            ),
            rx.heading("Authorized Scopes"),
            rx.foreach(
                GoogleAuthState.scopes,
                lambda scope: rx.code(scope),
            ),
            rx.heading("Raw Access Token"),
            rx.code(GoogleAuthState.access_token),
            rx.button("Refresh AT", on_click=GoogleAuthState.refresh_access_token),
            rx.hstack(
                "Time until token expiry",
                rx.moment(
                    GoogleAuthState.tokeninfo.exp,
                    unix=True,
                    duration_from_now=True,
                    interval=1000,
                ),
            ),
        ),
    )


app = rx.App()
app.add_page(index)
