import pytest
from statistics import mean
import reflex as rx


class State(rx.State):
        count: int = 0

        def increment(self):
            self.count += 1

        def decrement(self):
            self.count -= 1

def test_page():
    return rx.hstack(
            rx.button(
                "Decrement",
                bg="#fef2f2",
                color="#b91c1c",
                border_radius="lg",
                on_click=State.decrement,
            ),
            rx.heading(State.count, font_size="2em"),
            rx.button(
                "Increment",
                bg="#ecfdf5",
                color="#047857",
                border_radius="lg",
                on_click=State.increment,
            ),
            spacing="1em",
        )

@pytest.mark.benchmark
def test_mean_compile_time():
    """Test that the mean compile time is less than 1 second."""
    import reflex as rx

    app = rx.App()
    for i in range(10):
        app.add_page(test_page, route=f"/{i}")