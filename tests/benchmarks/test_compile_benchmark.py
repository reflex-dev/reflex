import pytest
import reflex
import importlib

rx = reflex
class State(rx.State):
    count: int = 0

    def increment(self):
        self.count += 1

    def decrement(self):
        self.count -= 1


class SliderVariation(rx.State):
    value: int = 50

    def set_end(self, value: int):
        self.value = value


def sample_small_page():
    return rx.vstack(
        *[rx.button(State.count, font_size="2em") for i in range(100)],
        spacing="1em",
    )


def sample_large_page():
    return rx.vstack(
        *[
            rx.vstack(
                rx.heading(SliderVariation.value),
                rx.slider(on_change_end=SliderVariation.set_end),
                width="100%",
            )
            for i in range(100)
        ],
        spacing="1em",
    )


def add_small_pages(app):
    for i in range(10):
        app.add_page(sample_small_page, route=f"/{i}")


def add_large_pages(app):
    for i in range(10):
        app.add_page(sample_large_page, route=f"/{i}")


def test_mean_import_time(benchmark):
    """Test that the mean import time is less than 1 second."""

    def import_reflex():
        importlib.reload(reflex)

    # Benchmark the import
    benchmark(import_reflex)


def test_mean_add_small_page_time(benchmark):
    """Test that the mean add page time is less than 1 second."""

    app = rx.App(state=State)
    benchmark(add_small_pages, app)


def test_mean_add_large_page_time(benchmark):
    """Test that the mean add page time is less than 1 second."""

    app = rx.App(state=State)
    results = benchmark(add_large_pages, app)
    print(results)
