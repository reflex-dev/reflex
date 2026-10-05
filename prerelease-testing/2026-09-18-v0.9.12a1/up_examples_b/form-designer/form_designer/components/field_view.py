import reflex as rx

from ..models import Field, FieldType, Option


class OptionItemCallable:
    def __call__(
        self, *children: rx.Component, value: rx.Var[str], **props
    ) -> rx.Component: ...


def option_value_label_id(option: Option) -> rx.Component:
    return rx.cond(
        option.value != "",
        option.value,
        rx.cond(
            option.label != "",
            option.label,
            option.id.to_string(),
        ),
    )


def foreach_field_options(
    options: list[Option], component: OptionItemCallable
) -> rx.Component:
    return rx.foreach(
        options,
        lambda option: component(
            option.label,
            value=option_value_label_id(option),
        ),
    )


def field_select(field: Field) -> rx.Component:
    return rx.select.root(
        rx.select.trigger(
            placeholder="Select an option",
            width="100%",
        ),
        rx.select.content(
            rx.cond(
                field.options,
                foreach_field_options(field.options, rx.select.item),
            ),
        ),
        name=field.name,
    )


def radio_item(*children: rx.Component, value: rx.Var[str], **props) -> rx.Component:
    return rx.el.label(
        rx.hstack(
            rx.radio.item(value=value, **props),
            *children,
            align="center",
        ),
    )


def field_radio(field: Field) -> rx.Component:
    return rx.cond(
        field.options,
        rx.radio.root(
            rx.vstack(
                foreach_field_options(field.options, radio_item),
                align="start",
            ),
            name=field.name,
        ),
        rx.text("No options defined"),
    )


def checkbox_item(field: Field, option: Option):
    value = option_value_label_id(option)
    return rx.box(
        rx.checkbox(
            option.label,
            value=value,
            name=f"{field.name}___{value}",
        ),
        margin_right="2em",
    )


def field_checkbox(field: Field) -> rx.Component:
    return rx.cond(
        field.options,
        rx.foreach(
            field.options,
            lambda option: checkbox_item(field, option),
        ),
        rx.text("No options defined"),
    )


def field_input(field: Field):
    return rx.match(
        field.type_,
        (FieldType.checkbox.value, field_checkbox(field)),
        (FieldType.radio.value, field_radio(field)),
        (FieldType.select.value, field_select(field)),
        (
            FieldType.textarea.value,
            rx.text_area(
                placeholder=field.prompt,
                name=field.name,
            ),
        ),
        rx.input(
            placeholder=field.prompt,
            type=field.type_.to(str),
            name=field.name,
            aria_label=field.name,
        ),
    )


def field_prompt(field: Field, show_name: bool = False):
    name = f" ({field.name})" if show_name else ""
    return rx.cond(
        field,
        rx.cond(
            field.prompt != "",
            rx.text(f"{field.prompt}{name}"),
            rx.cond(
                field.name != "",
                rx.text(field.name),
                rx.text("[unnamed field]"),
            ),
        ),
    )


def field_view(field: Field, *children: rx.Component, card_props: dict | None = None):
    return rx.form.field(
        rx.card(
            rx.hstack(
                field_prompt(field),
                rx.text(rx.cond(field.required, "*", "")),
            ),
            rx.hstack(
                field_input(field),
                flex_wrap="wrap",
            ),
            *children,
            **(card_props or {}),
        ),
    )
