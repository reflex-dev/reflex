import reflex as rx

from .. import constants, routes
from ..models import Field, Form
from ..state import AppState
from .field_view import field_input, field_prompt
from .form_select import FormSelectState


class FormEditorState(AppState):
    form: Form = Form()

    def _new_form(self):
        return Form(owner_id=self.authenticated_user.id)

    def load_form(self):
        if not self.is_authenticated:
            return
        if self.form_id != "":
            self.load_form_by_id(self.form_id)
        else:
            self.form = self._new_form()

    def load_form_by_id(self, id_: int):
        with rx.session() as session:
            form = session.get(Form, id_)
            if not self._user_has_access(form) or form is None:
                self.form = self._new_form()
                return
            self.form = form

    def delete_form(self):
        if self.form.id is not None:
            if not self._user_has_access():
                return
            with rx.session() as session:
                session.delete(session.get(Form, self.form.id))
                session.commit()
                yield rx.redirect(routes.FORM_EDIT_NEW)

    def set_name(self, name: str):
        if not self._user_has_access():
            return
        with rx.session() as session:
            if self.form.id is not None:
                form = session.get(Form, self.form.id)
            else:
                form = self.form
            form.name = name
            session.add(form)
            session.commit()
            yield FormSelectState.load_forms
            if form.id is not None and form.id > 0:
                return rx.redirect(routes.edit_form(form.id))

    def update_field(self, field: Field):
        if not self._user_has_access():
            return
        with rx.session() as session:
            session.add(self.form)
            session.commit()
            if field.id is None:
                self.form.fields.append(field)
                session.add(field)
                session.add(self.form)
                session.commit()
            else:
                for existing_field in self.form.fields:
                    if existing_field.id == field.id:
                        existing_field.name = field.name
                        existing_field.type_ = field.type_
                        existing_field.required = field.required
                        existing_field.prompt = field.prompt
                        session.add(existing_field)
                        session.commit()
            return FormEditorState.load_form_by_id(self.form.id)

    def delete_field(self, field_id):
        if not self._user_has_access():
            return
        with rx.session() as session:
            session.delete(session.get(Field, field_id))
            session.commit()
            return FormEditorState.load_form_by_id(self.form.id)


def field_edit_view(field: Field):
    return rx.card(
        rx.hstack(
            rx.link(
                field_prompt(field, show_name=True),
                href=routes.edit_field(FormEditorState.form.id, field.id),
            ),
            rx.spacer(),
            rx.tooltip(
                rx.link(
                    rx.icon(tag="x"), on_click=FormEditorState.delete_field(field.id)
                ),
                content="Delete Field",
            ),
            margin_bottom="12px",
        ),
        rx.hstack(
            rx.hstack(
                field_input(field),
                flex_wrap="wrap",
            ),
            rx.text(
                rx.cond(field.required, "(required)", "(optional)"), size="1", ml="3"
            ),
            justify="between",
        ),
    )


def form_editor():
    return rx.vstack(
        rx.hstack(
            rx.el.label(
                "Form Name",
                rx.input(
                    placeholder="Form Name",
                    name="name",
                    value=FormEditorState.form.name,
                    on_change=FormEditorState.set_name,
                    debounce_timeout=1000,
                ),
            ),
            rx.cond(
                FormEditorState.form_id != "",
                rx.hstack(
                    rx.button(
                        "Preview",
                        on_click=rx.redirect(routes.show_form(FormEditorState.form.id)),
                        type="button",
                    ),
                    rx.button(
                        "Responses",
                        on_click=rx.redirect(
                            routes.form_responses(FormEditorState.form.id)
                        ),
                    ),
                    rx.spacer(),
                    rx.button(
                        "Delete Form",
                        color_scheme="tomato",
                        on_click=FormEditorState.delete_form,
                        type="button",
                    ),
                ),
            ),
            align="end",
            justify="start",
        ),
        rx.divider(),
        rx.foreach(
            FormEditorState.form.fields,
            field_edit_view,
        ),
    )


def form_edit_title():
    form_name = rx.cond(
        rx.State.form_id == "",
        "New Form",
        rx.cond(
            FormEditorState.form,
            FormEditorState.form.name,
            "Unknown Form",
        ),
    )
    return f"{constants.TITLE} | {form_name}"
