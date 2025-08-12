import sqlalchemy

import reflex as rx

from .. import routes
from ..models import Form
from ..state import AppState


class FormSelectState(AppState):
    forms: list[Form] = []

    def load_forms(self):
        if not self.is_authenticated:
            return
        with rx.session() as session:
            query = Form.select()
            if not self.is_admin:
                query = query.where(Form.owner_id == self.authenticated_user.id)
            else:
                query = query.options(sqlalchemy.orm.selectinload(Form.user))
            self.forms = session.exec(query).all()

    def on_select_change(self, value: str):
        if value == "":
            return rx.redirect(routes.FORM_EDIT_NEW)
        return rx.redirect(routes.edit_form(value))


def form_name(form: Form):
    # The Admin user needs to see who owns the form.
    parenthesized_owner = rx.cond(
        form.user,
        rx.cond(
            form.user.id != AppState.authenticated_user.id,
            f" ({form.user.username})",
            "",
        ),
        "",
    )
    return form.name + parenthesized_owner


def form_select():
    return rx.box(
        rx.select.root(
            rx.select.trigger(placeholder="Existing Forms", width="100%"),
            rx.select.content(
                rx.foreach(
                    FormSelectState.forms,
                    lambda form: rx.select.item(
                        form_name(form), value=form.id.to_string()
                    ),
                ),
            ),
            value=rx.State.form_id,
            on_change=FormSelectState.on_select_change,
            on_mount=FormSelectState.load_forms,
        ),
        width="100%",
    )
