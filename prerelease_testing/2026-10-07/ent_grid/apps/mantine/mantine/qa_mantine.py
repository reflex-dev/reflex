"""QA page (added by the ent_grid cluster): other rxe.mantine components bound to State."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class QaMantineState(rx.State):
    """State for the QA mantine page."""

    fruit: str = ""
    picks: list[str] = ["React"]
    progress: int = 30
    json_text: str = '{"a": 1}'
    opened: bool = False

    @rx.event
    def set_fruit(self, value: str):
        self.fruit = value

    @rx.event
    def set_picks(self, value: list[str]):
        self.picks = value

    @rx.event
    def bump(self):
        self.progress = min(100, self.progress + 20)

    @rx.event
    def set_json_text(self, value: str):
        self.json_text = value

    @rx.event
    def toggle(self):
        self.opened = not self.opened


@demo(
    route="/qa-mantine",
    title="QA Mantine",
    description="Autocomplete, MultiSelect, RingProgress, JsonInput, NumberFormatter, Collapse bound to State.",
)
def qa_mantine_page():
    return rx.vstack(
        rxe.mantine.autocomplete(
            label="Fruit",
            placeholder="Pick a fruit",
            data=["Apple", "Banana", "Cherry"],
            # rxe Autocomplete (0.9.7a4) has no on_change trigger; on_option_submit is the only value event
            on_option_submit=QaMantineState.set_fruit,
            id="qa-autocomplete",
        ),
        rx.text("fruit: ", QaMantineState.fruit, id="qa-fruit"),
        rxe.mantine.multi_select(
            label="Frameworks",
            data=["React", "Vue", "Svelte"],
            value=QaMantineState.picks,
            on_change=QaMantineState.set_picks,
            id="qa-multiselect",
        ),
        rx.text("picks: ", QaMantineState.picks.join(","), id="qa-picks"),
        rxe.mantine.ring_progress(
            sections=[{"value": QaMantineState.progress, "color": "blue"}],
            label=rx.text(QaMantineState.progress, "%", id="qa-ring-label"),
        ),
        rx.button("bump", on_click=QaMantineState.bump, id="qa-bump"),
        rxe.mantine.json_input(
            label="JSON",
            value=QaMantineState.json_text,
            on_change=QaMantineState.set_json_text,
            validation_error="Invalid JSON",
            format_on_blur=True,
            autosize=True,
            id="qa-json",
        ),
        rx.text("json: ", QaMantineState.json_text, id="qa-json-text"),
        rxe.mantine.number_formatter(value=QaMantineState.progress * 1000, thousand_separator=True, prefix="$ "),
        rx.button("toggle collapse", on_click=QaMantineState.toggle, id="qa-toggle"),
        rxe.mantine.collapse(rx.text("collapsed content", id="qa-collapsed"), in_=QaMantineState.opened),
        align="start",
        spacing="3",
    )
