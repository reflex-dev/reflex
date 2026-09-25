"""The layout every playground page shares, including the benchmark hooks."""

import reflex as rx

from playground.state import BenchState

ROOT_MARKER = "m-initial-root"  # bench:hmr-target root

NAV_LINKS = [
    ("Home", "/"),
    ("Counter", "/counter"),
    ("Board", "/board"),
    ("Item 42", "/item/42"),
]


def navbar() -> rx.Component:
    """Render the navigation bar.

    Returns:
        The logo and a link to each page.
    """
    return rx.hstack(
        rx.image(src="/favicon.ico", alt="Reflex logo", width="2em", height="2em"),
        *[rx.link(label, href=href) for label, href in NAV_LINKS],
        align="center",
        spacing="4",
        class_name="playground-nav",
    )


def bench_hooks() -> rx.Component:
    """Render the elements the macro benchmarks wait for, drive and read.

    Returns:
        The readiness marker, the event round trip and the hot reload targets.
    """
    return rx.el.footer(
        rx.el.span("Benchmark hooks:"),
        rx.cond(BenchState.is_hydrated, rx.el.span(id="bench-hydrated")),
        rx.el.span(ROOT_MARKER, id="bench-marker-root"),
        rx.image(src="/mark.svg", alt="Playground mark", id="bench-mark", width="1em"),
        rx.el.span(BenchState.last_seq, id="bench-seq"),
        rx.el.button("set_seq(7)", on_click=BenchState.set_seq(7), id="bench-set-seq"),
        rx.el.span(
            BenchState.parts_total,
            " ",
            BenchState.parts_scaled,
            " ",
            BenchState.parts_label,
            id="bench-parts",
        ),
        rx.el.span(BenchState.handler_value, id="bench-handler-value"),
        rx.el.button(
            "bench_value", on_click=BenchState.bench_value, id="bench-handler"
        ),
        class_name="bench-hooks",
    )


def layout(content: rx.Component) -> rx.Component:
    """Wrap the content of a page in the shared layout.

    Args:
        content: The content of the page.

    Returns:
        The navigation bar, the content and the benchmark hooks.
    """
    return rx.container(rx.vstack(navbar(), content, bench_hooks(), spacing="5"))
