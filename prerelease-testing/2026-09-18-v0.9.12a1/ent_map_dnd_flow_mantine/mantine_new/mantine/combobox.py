import reflex as rx

import reflex_enterprise as rxe

from .common import demo


@rx.memo
def memo_combobox():
    return rxe.mantine.combobox(
        rxe.mantine.combobox.target(
            rx.input(
                type="button",
                on_click=lambda: rx.Var("combobox.toggleDropdown()").to(rx.EventChain),
            ),
        ),
        rxe.mantine.combobox.dropdown(
            rxe.mantine.combobox.options(
                rxe.mantine.combobox.option("Option 1"),
                rxe.mantine.combobox.option("Option 2"),
                rxe.mantine.combobox.option("Option 3"),
            ),
        ),
        label="Combobox",
        placeholder="Select a value",
        # on_change=rx.toast("Selected value: {value}"),
    )


@demo(
    route="/combobox",
    title="Combobox",
    description="A simple combobox example using Mantine.",
)
def combobox_page():
    return memo_combobox()
