"""Cta Card module."""

import reflex_components_internal as ui
from reflex_components_internal.blocks.demo_form import demo_form_dialog

import reflex as rx
from reflex_site_shared.components.marketing_button import button as marketing_button
from reflex_site_shared.constants import REFLEX_ASSETS_CDN, REFLEX_BUILD_URL


@rx.memo
def cta_card():
    """Cta card.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                "The Platform to Build and Scale Enterprise Apps",
                class_name="text-slate-12 lg:text-3xl text-2xl font-[575]",
            ),
            rx.el.span(
                "Describe your idea, and let AI transform it into a complete, production-ready Python web application.",
                class_name="text-m-slate-7 dark:text-m-slate-6 text-sm font-medium",
            ),
            rx.el.div(
                demo_form_dialog(
                    trigger=marketing_button(
                        "Book a Demo",
                        variant="primary",
                    ),
                ),
                rx.el.elements.a(
                    marketing_button(
                        "Try for free",
                        ui.icon("ArrowRight01Icon"),
                        variant="ghost",
                    ),
                    href=REFLEX_BUILD_URL,
                    target="_blank",
                ),
                class_name="flex flex-row gap-4 items-center",
            ),
            class_name="flex flex-col gap-6 justify-center max-w-[29.25rem]",
        ),
        rx.image(
            f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/cta_gray_lines_2.svg",
            class_name="w-auto h-full pointer-events-none",
            loading="lazy",
            alt="CTA Card",
        ),
        class_name="flex flex-row justify-between max-w-(--landing-layout-max-width) mx-auto w-full bg-white/96 dark:bg-m-slate-11 backdrop-blur-[16px] rounded-xl relative overflow-hidden shadow-[0_0_0_1px_rgba(0,0,0,0.04),0_12px_24px_0_rgba(0,0,0,0.08),0_1px_1px_0_rgba(0,0,0,0.01),0_4px_8px_0_rgba(0,0,0,0.03)] dark:shadow-none dark:border dark:border-m-slate-9 pl-16 max-lg:hidden mb-12 mt-24",
    )
