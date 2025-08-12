import reflex as rx

from .. import constants, routes, style, utils
from ..components import field_prompt, navbar
from ..models import Form, Response
from ..state import AppState


class ResponsesState(AppState):
    form: Form = Form()
    responses: list[Response] = []

    def load_responses(self):
        if not self.is_authenticated:
            return
        try:
            form_id = int(self.form_id)
        except ValueError:
            return
        with rx.session() as session:
            form = session.get(Form, form_id)
            if not self._user_has_access(form) or form is None:
                self.form = Form()
                return
            self.form = form
            self.responses = session.exec(
                Response.select().where(Response.form_id == form_id)
            ).all()

    def delete_response(self, id: int):
        if not self._user_has_access():
            return
        with rx.session() as session:
            session.delete(session.get(Response, id))
            session.commit()
            return ResponsesState.load_responses


def response_content(response: Response):
    return rx.vstack(
        rx.moment(response.ts),
        rx.foreach(
            response.field_values,
            lambda fv: rx.vstack(
                field_prompt(fv.field),
                rx.cond(
                    fv.value != "",
                    rx.text(fv.value),
                    rx.text("No response provided."),
                ),
                align="start",
            ),
        ),
        gap="2em",
    )


def response(r: Response):
    return rx.accordion.item(
        header=rx.hstack(
            rx.text(r.client_token),
            rx.tooltip(
                rx.button(
                    rx.icon(tag="x", size=16),
                    color_scheme="tomato",
                    margin_right="1em",
                    on_click=ResponsesState.delete_response(r.id).stop_propagation,
                ),
                content="Delete this Response",
            ),
            justify="between",
            align="center",
        ),
        content=response_content(r),
        value=r.id.to(str),
    )


def responses_title():
    form_name = rx.cond(
        rx.State.form_id == "",
        "Unknown Form",
        ResponsesState.form.name,
    )
    return f"{constants.TITLE} | {form_name} | Responses"


def responses_accordion(**props):
    return rx.accordion.root(
        rx.foreach(
            ResponsesState.responses,
            response,
        ),
        collapsible=True,
        type="multiple",
        **props,
    )


@utils.require_login
def responses_page(**props):
    return style.layout(
        navbar(),
        rx.link("< Edit", href=routes.edit_form(ResponsesState.form.id)),
        rx.center(rx.heading(ResponsesState.form.name)),
        responses_accordion(
            variant="outline",
            radius="small",
        ),
    )
