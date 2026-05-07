import reflex as rx

from .integration_gallery import (
    integration_filters,
    integration_gallery,
    integration_request_form,
)
from .integration_header import integration_header


# @mainpage(path="/integrations", title="Reflex · Integrations", meta=meta_tags)
def integration_page():
    return rx.el.div(
        integration_header(),
        integration_filters(),
        integration_gallery(),
        integration_request_form(),
        class_name="flex flex-col size-full justify-center items-center",
    )
