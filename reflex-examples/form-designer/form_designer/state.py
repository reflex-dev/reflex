import reflex as rx

from reflex_local_auth import LocalAuthState

from .models import Form


class AppState(LocalAuthState):
    @rx.var(cache=True)
    def is_admin(self) -> bool:
        # The first user created is automatically the admin.
        return self.authenticated_user.id == 1

    def _user_has_access(self, form: Form | None = None):
        if form is None and hasattr(self, "form"):
            form = self.form
        return (
            form is not None and form.owner_id == self.authenticated_user.id
        ) or self.is_admin
