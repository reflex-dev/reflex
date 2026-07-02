"""Hosting Banner module."""

import datetime

import reflex_components_internal as ui

import reflex as rx
from reflex_site_shared.constants import REFLEX_ASSETS_CDN, REFLEX_BUILD_URL


def glow() -> rx.Component:
    """Glow.

    Returns:
        The component.
    """
    return rx.box(
        class_name="absolute w-[120rem] h-[23.75rem] flex-shrink-0 rounded-[120rem] left-1/2 -translate-x-1/2 z-[0] top-[-16rem] dark:[background-image:radial-gradient(50%_50%_at_50%_50%,_rgba(58,45,118,1)_0%,_rgba(21,22,24,0.00)_100%)] [background-image:radial-gradient(50%_50%_at_50%_50%,_rgba(235,228,255,0.95)_0%,_rgba(252,252,253,0.00)_100%)] saturate-200 dark:saturate-100 group-hover:saturate-300 transition-[saturate] dark:group-hover:saturate-100",
    )


# July 7, 2026 12:01 AM PDT (UTC-7) = July 7, 2026 07:01 AM UTC
DEADLINE = datetime.datetime(2026, 7, 7, 7, 1, tzinfo=datetime.UTC)


class HostingBannerState(rx.State):
    """HostingBannerState."""

    show_banner: rx.Field[bool] = rx.field(True)
    force_hide_banner: rx.Field[bool] = rx.field(False)

    @rx.event
    def hide_banner(self):
        """Hide banner."""
        self.force_hide_banner = True

    @rx.event
    def check_deadline(self):
        """Check deadline."""
        if datetime.datetime.now(datetime.UTC) < DEADLINE:
            self.show_banner = True

    @rx.event
    def show_promo_banner(self):
        """Show the limited-time Pro promo banner."""
        self.show_banner = True

    @rx.var
    def is_banner_visible(self) -> bool:
        """Is banner visible.

        Returns:
            The component.
        """
        return self.show_banner and not self.force_hide_banner


def timer():
    """Timer.

    Returns:
        The component.
    """
    remove_negative_sign = rx.vars.function.ArgsFunctionOperation.create(
        args_names=("t",),
        return_expr=rx.vars.sequence.string_replace_operation(
            rx.Var("t").to(str), "-", ""
        ),
    )

    return rx.el.div(
        rx.moment(
            date=DEADLINE,
            duration_from_now=True,
            format="DD[d] HH[h] mm[m] ss[s]",
            custom_attrs={"filter": remove_negative_sign},
            interval=1000,
            class_name="font-medium text-sm",
        ),
        class_name="items-center gap-1 z-[1] bg-orange-4 border border-orange-5 rounded-md px-1.5 py-0.5 text-orange-11 font-medium text-sm md:flex hidden",
    )


def hosting_banner() -> rx.Component:
    """Hosting banner.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.cond(
            HostingBannerState.is_banner_visible,
            rx.el.div(
                rx.el.elements.a(
                    rx.box(
                        rx.image(
                            src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/squares_banner.svg",
                            alt="Square Banner",
                            class_name="pointer-events-none absolute -left-[16rem] max-lg:hidden",
                        ),
                        rx.box(
                            # Header text with responsive spans
                            rx.el.span(
                                "Limited time",
                                class_name="items-center font-[525] px-2.5 h-7 rounded-lg text-sm text-white z-[1] max-lg:hidden lg:inline-flex border border-white/16",
                            ),
                            rx.el.span(
                                "Get Pro for $3 until July 6th",
                                rx.el.span(
                                    ". Upgrade now",
                                    class_name="lg:hidden text-white/70",
                                ),
                                class_name="text-white font-[525] text-sm lg:text-nowrap inline-block",
                            ),
                            rx.el.span(
                                class_name="w-px h-7 bg-gradient-to-b from-transparent via-white/24 to-transparent max-lg:hidden",
                            ),
                            ui.button(
                                "Upgrade now",
                                ui.icon("ArrowRight01Icon"),
                                variant="ghost-highlight",
                                size="xs",
                                aria_label="Upgrade to Reflex Pro",
                                class_name="max-lg:hidden text-white hover:text-primary-10",
                            ),
                            class_name="flex flex-row items-center md:gap-4 gap-2",
                        ),
                        rx.image(
                            src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/squares_banner.svg",
                            alt="Square Banner",
                            class_name="pointer-events-none absolute -right-[16rem] max-lg:hidden",
                        ),
                        class_name="flex flex-row items-center relative",
                    ),
                    href=REFLEX_BUILD_URL,
                    class_name="flex justify-start md:justify-center md:col-start-2 max-w-[73rem]",
                ),
                rx.el.button(
                    ui.icon(
                        "MultiplicationSignIcon",
                    ),
                    aria_label="Close banner",
                    type="button",
                    class_name="cursor-pointer hover:text-white/80 transition-colors text-white z-10 size-10 flex items-center justify-center shrink-0 md:col-start-3 justify-self-end ml-auto",
                    on_click=HostingBannerState.hide_banner,
                ),
                class_name="px-5 lg:px-0 w-screen min-h-[2rem] lg:h-10 flex md:grid md:grid-cols-[1fr_auto_1fr] items-center bg-secondary-12 dark:bg-[#6550B9] gap-4 overflow-hidden relative lg:py-0 py-2 max-w-full group",
            ),
        ),
        on_mount=HostingBannerState.show_promo_banner,
    )
