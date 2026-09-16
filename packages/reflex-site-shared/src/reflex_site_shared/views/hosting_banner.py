"""Hosting Banner module."""

import datetime

import reflex as rx


def glow() -> rx.Component:
    """Glow.

    Returns:
        The component.
    """
    return rx.box(
        class_name="absolute w-[120rem] h-[23.75rem] flex-shrink-0 rounded-[120rem] left-1/2 -translate-x-1/2 z-[0] top-[-16rem] dark:[background-image:radial-gradient(50%_50%_at_50%_50%,_rgba(58,45,118,1)_0%,_rgba(21,22,24,0.00)_100%)] [background-image:radial-gradient(50%_50%_at_50%_50%,_rgba(235,228,255,0.95)_0%,_rgba(252,252,253,0.00)_100%)] saturate-200 dark:saturate-100 group-hover:saturate-300 transition-[saturate] dark:group-hover:saturate-100",
    )


AGENT_TOOLKIT_EARLY_ACCESS_URL = (
    "https://us.posthog.com/external_surveys/019e669c-939f-0000-a8b1-0aaceee08e3b"
)

# October 25, 2025 12:01 AM PDT (UTC-7) = October 25, 2025 07:01 AM UTC
DEADLINE = datetime.datetime(2025, 10, 25, 7, 1, tzinfo=datetime.timezone.utc)


ANNOUNCEMENT_RELEASE = "xy-in-reflex-build-v1"


class HostingBannerState(rx.State):
    """HostingBannerState."""

    dismissed_release: str = rx.LocalStorage(
        name="reflex_announcement_dismissed_release", sync=True
    )

    show_banner: rx.Field[bool] = rx.field(True)
    force_hide_banner: rx.Field[bool] = rx.field(False)

    @rx.event
    def hide_banner(self):
        """Hide banner."""
        self.force_hide_banner = True
        self.dismissed_release = ANNOUNCEMENT_RELEASE

    @rx.event
    def check_deadline(self):
        """Check deadline."""
        if datetime.datetime.now(datetime.timezone.utc) < DEADLINE:
            self.show_banner = True

    @rx.event
    def show_agent_toolkit_banner(self):
        """Show the Agent Toolkit launch banner."""
        self.show_banner = True

    @rx.var
    def is_banner_visible(self) -> bool:
        """Is banner visible.

        Returns:
            The component.
        """
        return (
            self.show_banner
            and not self.force_hide_banner
            and self.dismissed_release != ANNOUNCEMENT_RELEASE
        )


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
    """Render the shared marketing announcement through the legacy entry point.

    Returns:
        The rendered component.
    """
    from reflex_site_shared.views.announcement_banner import announcement_banner

    return announcement_banner()
