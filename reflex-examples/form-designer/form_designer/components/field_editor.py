"""Edit Field modal."""

from typing import Any
import reflex as rx

from .. import constants, routes, utils
from ..models import Field, FieldType, Option
from ..state import AppState
from .form_editor import FormEditorState
from .field_view import field_input


class FieldEditorState(AppState):
    """Handle editing of a single field."""

    field: Field = Field()
    form_owner_id: int = -1
    options_editor_open: bool = False
    field_editor_open: bool = False

    def _user_has_access(self):
        return self.form_owner_id == self.authenticated_user.id or self.is_admin

    def handle_submit(self, form_data: dict[str, Any]):
        self.field.name = form_data["field_name"]
        self.field.type_ = form_data["type_"]
        self.field.required = bool(form_data.get("required"))
        self.field_editor_open = False
        return [
            FormEditorState.update_field(self.field),
            rx.redirect(routes.edit_form(self.form_id)),
        ]

    def handle_required_change(self, is_checked: bool):
        self.field.required = is_checked

    def handle_modal_open_change(self, is_open: bool):
        self.field_editor_open = is_open
        if not is_open:
            return rx.redirect(routes.edit_form(self.form_id))

    async def load_field(self):
        form_state = await self.get_state(FormEditorState)
        self.form_owner_id = form_state.form.owner_id
        if not self._user_has_access():
            return
        if self.field_id == "new":
            self.field = Field(form_id=self.form_id)
        else:
            with rx.session() as session:
                self.field = session.get(Field, self.field_id)
        self.field_editor_open = True

    def set_type(self, type_: str):
        self.field.type_ = FieldType(type_)

    def set_field(self, key: str, value: str):
        setattr(self.field, key, value)

    def set_option(self, index: int, key: str, value: str):
        if not self._user_has_access():
            return
        with rx.session() as session:
            session.add(self.field)
            if self.field.id is None:
                session.commit()
                session.refresh(self.field)
            option = self.field.options[index]
            option.field_id = self.field.id
            setattr(option, key, value)
            session.add(option)
            session.commit()
            session.refresh(self.field)

    def add_option(self):
        if not self._user_has_access():
            return
        with rx.session() as session:
            session.add(self.field)
            if not self.field.id:
                session.commit()
                session.refresh(self.field)
            option = Option(field_id=self.field.id)
            self.field.options.append(option)
            session.add(option)
            session.add(self.field)
            session.commit()
            session.refresh(self.field)
            return utils.focus_input_in_class("fd-Option-Label")

    def delete_option(self, index: int):
        if not self._user_has_access():
            return
        with rx.session() as session:
            session.add(self.field)
            option_to_delete = session.get(Option, self.field.options[index].id)
            if option_to_delete is not None:
                session.delete(option_to_delete)
            del self.field.options[index]
            session.commit()
            session.refresh(self.field)


def field_is_enumerated_cond(
    if_enumerated: rx.Component | rx.Var,
) -> rx.Component | rx.Var:
    return rx.cond(
        rx.Var.create(
            [
                FieldType.select.value,
                FieldType.radio.value,
                FieldType.checkbox.value,
            ]
        ).contains(FieldEditorState.field.type_),
        if_enumerated,
    )


def option_editor(option: Option, index: int):
    return rx.card(
        rx.hstack(
            rx.el.label(
                rx.text("Label"),
                rx.input(
                    placeholder="Label",
                    class_name="fd-Option-Label",
                    value=option.label,
                    on_change=lambda v: FieldEditorState.set_option(index, "label", v),
                ),
            ),
            rx.el.label(
                rx.text("Value"),
                rx.input(
                    placeholder=rx.cond(option.label != "", option.label, "Value"),
                    value=option.value,
                    on_change=lambda v: FieldEditorState.set_option(index, "value", v),
                ),
            ),
            rx.button(
                rx.icon(tag="x"),
                on_click=FieldEditorState.delete_option(index),
                type="button",
                color_scheme="tomato",
            ),
            align="end",
        ),
    )


def options_editor():
    return rx.form(
        rx.vstack(
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(FieldEditorState.field.options, option_editor),
                ),
                max_height="60vh",
            ),
            rx.hstack(
                rx.icon_button(
                    "plus",
                    on_click=FieldEditorState.add_option().prevent_default,
                    type="submit",
                ),
                rx.dialog.close(rx.button("Done")),
                justify="between",
            ),
        ),
    )


def options_editor_modal():
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Edit Options"),
            rx.container(
                options_editor(),
                stack_children_full_width=True,
            ),
        ),
        open=FieldEditorState.options_editor_open,
        on_open_change=FieldEditorState.set_options_editor_open,
    )


def field_editor_input(key: str):
    return rx.el.label(
        key.capitalize(),
        rx.input(
            placeholder=key.capitalize(),
            name=f"field_{key}",
            value=getattr(FieldEditorState.field, key),
            on_change=lambda v: FieldEditorState.set_field(key, v),
            width="100%",
        ),
        width="100%",
    )


def field_editor():
    return rx.fragment(
        rx.form(
            rx.vstack(
                field_editor_input("name"),
                field_editor_input("prompt"),
                rx.hstack(
                    "Type",
                    rx.select.root(
                        rx.select.trigger(),
                        rx.select.content(
                            *[
                                rx.select.item(t.value, value=t.value or "unset")
                                for t in FieldType
                            ],
                        ),
                        name="type_",
                        value=FieldEditorState.field.type_.to(str),
                        on_change=FieldEditorState.set_type,
                    ),
                    field_is_enumerated_cond(
                        rx.button(
                            "Edit Options",
                            on_click=FieldEditorState.set_options_editor_open(True),
                            type="button",
                            size="1",
                        ),
                    ),
                    rx.spacer(),
                    rx.box(
                        rx.checkbox(
                            "Required",
                            name="required",
                            checked=FieldEditorState.field.required,
                            on_change=FieldEditorState.handle_required_change,
                        ),
                    ),
                    align="center",
                ),
                field_is_enumerated_cond(
                    rx.scroll_area(
                        field_input(FieldEditorState.field),
                        max_height="200px",
                    ),
                ),
                rx.button("Save", type="submit"),
                align="start",
            ),
            on_submit=FieldEditorState.handle_submit,
        ),
        field_is_enumerated_cond(options_editor_modal()),
    )


def field_editor_modal():
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Edit Field"),
            rx.container(
                field_editor(),
                stack_children_full_width=True,
            ),
        ),
        open=FieldEditorState.field_editor_open,
        on_open_change=FieldEditorState.handle_modal_open_change,
    )


def field_edit_title():
    form_name = rx.cond(
        rx.State.form_id == "",
        "New Form",
        rx.cond(
            FormEditorState.form,
            FormEditorState.form.name,
            "Unknown Form",
        ),
    )
    field_name = rx.cond(
        rx.State.field_id == "",
        "New Field",
        rx.cond(
            FieldEditorState.field,
            FieldEditorState.field.name,
            "Unknown Field",
        ),
    )
    return f"{constants.TITLE} | {form_name} | {field_name}"
