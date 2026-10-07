"""Shared helpers for the dataeditor_components cluster app."""

import importlib.metadata as md
import os

import reflex as rx

assert f"/envs/{os.environ["REFLEX_TEST_ENV"]}/" in rx.__file__, rx.__file__

REFLEX_VERSION = md.version("reflex")
IS_ALPHA = REFLEX_VERSION.startswith("0.10")
DE_VERSION = md.version("reflex-components-dataeditor")

PAGES = [
    ("/", "home"),
    ("/de", "dataeditor"),
    ("/de-multi", "de-multi"),
    ("/de-filter", "de-filter"),
    ("/de-big", "de-big"),
    ("/de-foreach", "de-foreach"),
    ("/forms", "forms"),
    ("/match", "match"),
    ("/memo-names", "memo-names"),
    ("/plotly", "plotly"),
    ("/recharts", "recharts"),
    ("/radix", "radix"),
    ("/code", "code"),
    ("/download", "download"),
]


def nav() -> rx.Component:
    """Navigation bar with client-side links and a version banner.

    Returns:
        The nav component.
    """
    return rx.hstack(
        rx.text(f"reflex {REFLEX_VERSION} / dataeditor {DE_VERSION}", id="ver"),
        *[rx.link(label, href=href, id=f"nav-{label}") for href, label in PAGES],
        wrap="wrap",
        spacing="2",
    )


def guarded(label: str, build) -> rx.Component:
    """Build a component, rendering the construction error instead of raising.

    Args:
        label: Identifier used for the error box id.
        build: Zero-arg callable returning a component.

    Returns:
        The component, or an error box.
    """
    try:
        return build()
    except Exception as e:  # noqa: BLE001
        print(f"CONSTRUCTION_ERROR {label}: {type(e).__name__}: {e}", flush=True)
        return rx.box(
            rx.text(f"construction-error {label}: {type(e).__name__}: {e}"),
            id=f"err-{label}",
            class_name="construction-error",
            color="red",
        )
