import reflex as rx
import reflex_ui as ui
from reflex_ui_shared.components.marketing_button import button
from reflex_ui_shared.constants import REFLEX_ASSETS_CDN
from reflex_ui_shared.views.hosting_banner import HostingBannerState

from reflex_docs.pages.docs import getting_started


def hero() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.p(
                "About Reflex",
                class_name="text-sm font-[525] text-primary-10 dark:text-m-slate-6",
            ),
            rx.el.h1(
                "Reflex Documentation",
                class_name="text-m-slate-12 dark:text-m-slate-3 lg:text-5xl text-3xl font-[575] lg:text-nowrap",
            ),
            rx.el.p(
                "Get up and running with Reflex in minutes. A complete set ",
                rx.el.br(class_name="max-lg:hidden"),
                " of resources to build, deploy, and scale your application. ",
                class_name="text-base text-m-slate-7 dark:text-m-slate-6 font-[475]",
            ),
            rx.el.a(
                button(
                    "Get Started",
                    ui.icon("ArrowRightIcon"),
                    variant="primary",
                    size="md",
                    native_button=False,
                    class_name="w-fit",
                ),
                to=getting_started.introduction.path,
            ),
            class_name=ui.cn(
                "flex flex-col gap-6 max-lg:text-center relative just-start lg:pb-24",
                rx.cond(
                    HostingBannerState.is_banner_visible,
                    "lg:pt-[14.5rem] pt-[12.5rem]",
                    "lg:pt-[10.5rem] pt-[7.5rem]",
                ),
            ),
        ),
        rx.el.div(
            rx.image(
                alt="Squares Docs Logo",
                custom_attrs={"fetchPriority": "high"},
                src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/squares_docs_logo.svg",
                class_name="pointer-events-none h-auto w-auto lg:absolute max-lg:hidden",
            ),
            class_name=ui.cn(
                "flex",
                rx.cond(
                    HostingBannerState.is_banner_visible,
                    "lg:pt-[8.5rem] pt-0",
                    "lg:pt-[4.5rem] pt-0",
                ),
            ),
        ),
        class_name=ui.cn(
            "flex lg:flex-row flex-col max-w-(--docs-layout-max-width) mx-auto w-full max-lg:pb-10 max-xl:px-6",
        ),
    )
