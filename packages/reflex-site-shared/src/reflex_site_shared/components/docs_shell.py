"""Shared structural components for documentation sites."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import reflex_components_internal as ui
from reflex_components_internal.blocks.demo_form import demo_form_dialog

import reflex as rx
from reflex_site_shared.backend.status import StatusState
from reflex_site_shared.components.icons import get_icon
from reflex_site_shared.components.marketing_button import button
from reflex_site_shared.components.server_status import server_status
from reflex_site_shared.constants import (
    DISCORD_URL,
    FORUM_URL,
    GITHUB_URL,
    LINKEDIN_URL,
    ROADMAP_URL,
    TWITTER_URL,
)
from reflex_site_shared.views.footer import dark_mode_toggle
from reflex_site_shared.views.hosting_banner import HostingBannerState, hosting_banner


class DocsFeedbackState(rx.State):
    """Store the feedback selection shared by documentation shells."""

    score: int = -1

    @rx.event
    def set_score(self, score: int) -> None:
        """Select a documentation feedback score.

        Args:
            score: Positive or negative feedback value.
        """
        self.score = score

    @rx.event
    def handle_submit(self, form_data: dict[str, Any]) -> None:
        """Accept an optional documentation feedback comment.

        Args:
            form_data: Submitted feedback fields.
        """
        del form_data


def docs_navbar_frame(
    logo: rx.Component,
    navigation: rx.Component,
    *,
    show_banner: bool = True,
) -> rx.Component:
    """Render the navbar frame shared by official and package docs sites.

    Args:
        logo: Site-specific navbar logo.
        navigation: Site-specific navigation menu.
        show_banner: Whether to render the shared announcement banner.

    Returns:
        Fixed documentation navbar.
    """
    return rx.el.div(
        hosting_banner() if show_banner else rx.fragment(),
        rx.el.header(
            rx.el.div(
                logo,
                navigation,
                class_name="relative mx-auto flex h-full w-full max-w-[108rem] flex-row items-center justify-between gap-6",
            ),
            class_name="mx-auto flex h-[4.5rem] w-full max-w-full flex-row items-center bg-gradient-to-b from-secondary-2 to-secondary-1 px-6 shadow-[0_-2px_2px_1px_rgba(0,0,0,0.02),0_1px_1px_0_rgba(0,0,0,0.08),0_4px_8px_0_rgba(0,0,0,0.03),0_0_0_1px_#FFF_inset] backdrop-blur-[16px] dark:border-b dark:border-secondary-4 dark:shadow-none 3xl:px-16",
        ),
        class_name="fixed top-0 z-[9999] flex w-full flex-col self-center",
    )


def docs_left_sidebar(
    content: rx.Component,
    *,
    show_banner: bool = True,
) -> rx.Component:
    """Render the shared fixed-width documentation sidebar column.

    Args:
        content: Site-specific sidebar navigation.
        show_banner: Whether the shared announcement banner is rendered.

    Returns:
        Responsive left sidebar column.
    """
    return rx.box(
        content,
        class_name=ui.cn(
            "sticky left-0 z-10 hidden w-[19.5rem] shrink-0 border-r border-secondary-4 before:absolute before:bottom-0 before:right-0 before:top-0 before:-z-10 before:w-[100vw] before:bg-white-1 lg:block",
            (
                rx.cond(
                    HostingBannerState.is_banner_visible,
                    "top-[113px] h-[calc(100vh-113px)]",
                    "top-[77px] h-[calc(100vh-77px)]",
                )
                if show_banner
                else "top-[77px] h-[calc(100vh-77px)]"
            ),
        ),
    )


@rx.memo
def docs_sidebar_leaf(
    title: rx.vars.StringVar[str],
    href: rx.vars.StringVar[str],
    active: rx.vars.BooleanVar,
    guide_margin_class: rx.vars.StringVar[str],
) -> rx.Component:
    """Render the leaf row shared by every documentation sidebar.

    Args:
        title: Visible navigation label.
        href: Documentation route.
        active: Whether this route is selected.
        guide_margin_class: Indentation aligned with the section guide.

    Returns:
        Official documentation sidebar leaf.
    """
    return rx.el.li(
        rx.link(
            rx.cond(
                active,
                rx.el.div(
                    class_name="absolute left-0 top-1/2 -translate-y-1/2 w-full h-8 rounded-lg bg-secondary-3 z-[-1]",
                ),
                rx.fragment(),
            ),
            rx.flex(
                rx.cond(
                    active,
                    rx.el.div(
                        class_name="pointer-events-none absolute -bottom-1 -top-1 left-0 w-px bg-primary-10",
                    ),
                    rx.fragment(),
                ),
                rx.text(
                    title,
                    class_name=rx.cond(
                        active,
                        "m-0 pl-4 text-sm font-[525] text-primary-10 transition-color",
                        "m-0 w-full text-sm font-[525] text-secondary-11 transition-color hover:text-secondary-12",
                    ),
                ),
                class_name=rx.cond(
                    active,
                    f"relative {guide_margin_class} flex h-8 max-w-[14rem] items-center",
                    "relative flex h-8 items-center pl-4",
                ),
            ),
            href=href,
            underline="none",
            class_name=rx.cond(
                active,
                "relative block w-full",
                f"block w-full {guide_margin_class}",
            ),
        ),
        class_name="relative m-0 w-full list-none p-0 !overflow-visible",
    )


def docs_sidebar_section(
    title: str,
    href: str,
    *children: rx.Component,
    connected_line: bool = True,
) -> rx.Component:
    """Render a titled documentation sidebar section.

    Args:
        title: Section heading.
        href: Section landing route.
        *children: Sidebar leaves or nested groups.
        connected_line: Whether to draw the shared vertical guide.

    Returns:
        Official documentation sidebar section.
    """
    return rx.el.li(
        rx.link(
            rx.el.h2(
                title,
                class_name="m-0 font-mono text-[0.8125rem] font-medium uppercase leading-6 text-secondary-12 hover:text-primary-10 dark:hover:text-primary-9",
            ),
            underline="none",
            href=href,
            class_name="mb-2 ml-[2.5rem] flex h-8 items-center justify-start",
        ),
        rx.el.ul(
            *(
                (
                    rx.el.li(
                        class_name="pointer-events-none absolute bottom-0 left-[3rem] top-0 -z-10 m-0 w-px list-none !rounded-none bg-secondary-4 p-0",
                    ),
                )
                if connected_line
                else ()
            ),
            *children,
            class_name=ui.cn(
                "m-0 ml-0 flex w-full list-none flex-col rounded-none p-0 pl-0 !bg-transparent !shadow-none",
                "relative gap-0" if connected_line else "gap-1",
            ),
        ),
        class_name="m-0 ml-0 flex w-full list-none flex-col items-start p-0",
    )


def docs_sidebar_category(
    name: str,
    href: str,
    icon: str,
    active: rx.Var[bool] | bool,
) -> rx.Component:
    """Render an official top-level documentation category row.

    Args:
        name: Visible category label.
        href: Category landing route.
        icon: Lucide icon identifier.
        active: Whether the category is selected.

    Returns:
        Documentation category row.
    """
    return rx.el.li(
        rx.link(
            rx.cond(
                active,
                rx.el.div(
                    class_name="absolute left-0 top-1/2 -translate-y-1/2 w-full h-8 rounded-lg bg-secondary-3 z-[-1]",
                ),
                rx.fragment(),
            ),
            rx.box(
                rx.icon(tag=icon, size=16),
                rx.el.h3(name, class_name="m-0 w-full font-[525]"),
                class_name=ui.cn(
                    "cursor-pointer flex flex-row justify-start items-center gap-2.5 ml-[3rem] text-sm text-secondary-11 hover:text-secondary-12 h-8",
                    rx.cond(active, "text-primary-10 hover:text-primary-10", ""),
                ),
            ),
            href=href,
            underline="none",
            class_name="block w-full relative no-underline",
            custom_attrs={"aria-label": f"Navigate to {name}"},
        ),
        class_name="m-0 p-0 w-full relative list-none",
    )


def docs_sidebar_group(
    title: str,
    *children: rx.Component,
    icon: str | None = None,
    open_: rx.Var[bool] | bool = False,
) -> rx.Component:
    """Render an official collapsible documentation sidebar group.

    Args:
        title: Visible group label.
        *children: Nested sidebar rows.
        icon: Optional Lucide icon identifier.
        open_: Whether the group is expanded.

    Returns:
        Collapsible documentation group row.
    """
    has_icon = icon is not None
    guide_left = "left-[3rem]" if has_icon else "left-[2.5rem]"
    return rx.el.li(
        rx.el.details(
            rx.el.summary(
                rx.icon(tag=icon, size=16, class_name="mr-4")
                if icon is not None
                else rx.fragment(),
                rx.text(title, class_name="m-0 text-sm font-[525]"),
                rx.box(class_name="flex-grow"),
                ui.icon(
                    "ArrowDown01Icon",
                    class_name="size-4 group-open/details:rotate-180 transition-transform",
                ),
                class_name="!px-0 m-0 flex items-center justify-start !ml-[2.5rem] !bg-transparent !hover:bg-transparent !py-1 !pr-0 w-[calc(100%-2.5rem)] !text-secondary-11 hover:!text-secondary-12 transition-color group xl:max-w-[14rem] cursor-pointer list-none [&::-webkit-details-marker]:hidden [&::marker]:hidden",
            ),
            rx.el.ul(
                rx.el.li(
                    class_name=f"m-0 p-0 absolute {guide_left} top-0 bottom-0 w-px bg-secondary-4 z-[-1] pointer-events-none !rounded-none list-none",
                ),
                *children,
                class_name="!my-1 p-0 flex flex-col items-start gap-1 list-none !bg-transparent !rounded-none !shadow-none relative",
            ),
            open=open_,
            class_name="group/details m-0 p-0 w-full !bg-transparent border-none",
        ),
        class_name="m-0 p-0 border-none w-full !bg-transparent list-none",
    )


def _feedback_choice_button(
    label: str,
    icon: str,
    score: int,
    class_name: str,
) -> rx.Component:
    """Render one shared feedback choice.

    Args:
        label: Visible choice label.
        icon: Icon identifier.
        score: Stored feedback score.
        class_name: Shape and layout classes.

    Returns:
        Feedback choice button.
    """
    active = DocsFeedbackState.score == score
    return rx.el.button(
        ui.icon(icon),
        label,
        type="button",
        class_name=rx.cond(
            active,
            ui.cn(
                "border-primary-6 bg-primary-3 text-primary-11 shadow-none",
                class_name,
            ),
            ui.cn(
                "border-secondary-5 bg-secondary-1 text-secondary-9 shadow-large hover:bg-secondary-3 hover:text-secondary-11",
                class_name,
            ),
        ),
        aria_label=label,
        on_click=DocsFeedbackState.set_score(score),
    )


def _feedback_thumb_card(score: int, icon: str, label: str) -> rx.Component:
    """Render one official feedback-form score button.

    Args:
        score: Stored feedback score.
        icon: Icon identifier.
        label: Visible choice label.

    Returns:
        Feedback-form thumb button.
    """
    return rx.el.button(
        ui.icon(icon, size=16),
        label,
        type="button",
        on_click=DocsFeedbackState.set_score(score),
        class_name=rx.cond(
            DocsFeedbackState.score == score,
            "flex h-9 items-center justify-center gap-2 rounded-md border border-primary-6 bg-primary-3 px-3 text-sm font-medium text-primary-11 transition-colors",
            "flex h-9 items-center justify-center gap-2 rounded-md border border-secondary-5 bg-secondary-1 px-3 text-sm font-medium text-secondary-9 transition-colors hover:bg-secondary-3 hover:text-secondary-11",
        ),
    )


def _feedback_content() -> rx.Component:
    """Render the shared documentation feedback form.

    Returns:
        Feedback form content.
    """
    return rx.el.div(
        rx.el.div(
            rx.form(
                rx.el.div(
                    ui.textarea(
                        name="feedback",
                        placeholder="Write a comment…",
                        type="text",
                        max_length=500,
                        enter_key_submit=True,
                        resize="vertical",
                        required=True,
                    ),
                    rx.hstack(
                        _feedback_thumb_card(1, "ThumbsUpIcon", "Helpful"),
                        _feedback_thumb_card(0, "ThumbsDownIcon", "Not helpful"),
                        gap="8px",
                        wrap="wrap",
                    ),
                    ui.input(
                        name="email",
                        type="email",
                        placeholder="Contact email (optional)",
                        max_length=100,
                    ),
                    ui.popover.close(
                        ui.button("Send feedback", type="submit", class_name="w-full")
                    ),
                    class_name="w-full gap-4 flex flex-col",
                ),
                class_name="w-full",
                reset_on_submit=True,
                on_submit=DocsFeedbackState.handle_submit,
            ),
            class_name="flex flex-col gap-4 w-full",
        ),
        class_name="p-2",
    )


def docs_feedback_button() -> rx.Component:
    """Render the shared Yes/No footer feedback control.

    Returns:
        Feedback popover trigger.
    """
    shared_class = "flex w-full cursor-pointer flex-row items-center justify-center gap-2 whitespace-nowrap border px-3 py-0.5 font-small transition-colors"
    return ui.popover.root(
        ui.popover.trigger(
            render_=rx.el.div(
                _feedback_choice_button(
                    "Yes",
                    "ThumbsUpIcon",
                    1,
                    ui.cn("rounded-[20px_0_0_20px] border-r-0", shared_class),
                ),
                _feedback_choice_button(
                    "No",
                    "ThumbsDownIcon",
                    0,
                    ui.cn("rounded-[0_20px_20px_0]", shared_class),
                ),
                class_name="flex w-full flex-row items-center lg:w-auto",
            ),
        ),
        ui.popover.portal(ui.popover.positioner(ui.popover.popup(_feedback_content()))),
    )


def docs_feedback_button_toc() -> rx.Component:
    """Render the shared right-sidebar feedback control.

    Returns:
        Feedback popover.
    """
    return ui.popover(
        trigger=button(
            ui.icon("ThumbsUpIcon"),
            "Send feedback",
            variant="ghost",
            size="sm",
            type="button",
            on_click=DocsFeedbackState.set_score(1),
            class_name="justify-start pl-0 text-secondary-11",
        ),
        content=_feedback_content(),
    )


def docs_right_sidebar(
    toc: Sequence[tuple[int, str]],
    *,
    path: str = "",
    feedback: rx.Component | None = None,
    slugger: Callable[[str], str] | None = None,
    show_banner: bool = True,
) -> rx.Component:
    """Render the shared on-page table of contents.

    Args:
        toc: Heading levels and labels.
        path: Optional page route prepended to anchors.
        feedback: Optional feedback control.
        slugger: Optional heading-to-fragment converter.
        show_banner: Whether the shared announcement banner is rendered.

    Returns:
        Sticky right sidebar.
    """
    # Default must match HeadingLink.slugify (blocks/headings.py), which stamps
    # the heading element ids client-side, or in-page TOC anchors won't resolve.
    make_slug = slugger or (lambda text: text.lower().replace(" ", "-"))
    return rx.box(
        rx.el.nav(
            rx.box(
                rx.el.p(
                    rx.icon("align-left", size=14, class_name="text-secondary-12"),
                    "On This Page",
                    class_name="flex h-8 items-center justify-start gap-1.5 text-sm font-[525] text-secondary-12",
                ),
                rx.el.ul(
                    *(
                        rx.el.li(
                            rx.el.a(
                                text,
                                class_name=ui.cn(
                                    "line-clamp-2 py-1 text-sm font-[525] text-secondary-11 transition-colors hover:text-secondary-12",
                                    "pl-4" if level <= 2 else "pl-8",
                                ),
                                href=f"{path}#{make_slug(text)}",
                            )
                        )
                        for level, text in toc
                    ),
                    id="toc-navigation",
                    class_name="flex max-h-[60vh] list-none flex-col gap-y-1 overflow-y-auto scroll-mask-y-10 shadow-[1.5px_0_0_0_var(--secondary-4)_inset] [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden",
                ),
                rx.el.div(
                    feedback or docs_feedback_button_toc(),
                    class_name="mt-1.5 flex flex-col justify-start",
                ),
                class_name="sticky top-4 flex flex-col justify-start gap-y-4 overflow-y-auto",
            ),
            class_name=ui.cn(
                "h-full w-full",
                (
                    rx.cond(
                        HostingBannerState.is_banner_visible,
                        "mt-[146px]",
                        "mt-[90px]",
                    )
                    if show_banner
                    else "mt-[90px]"
                ),
            ),
        ),
        class_name="sticky top-0 hidden h-screen w-[240px] shrink-0 2xl:block",
    )


def docs_footer_shell(
    feedback: rx.Component,
    actions: rx.Component,
    link_columns: rx.Component,
    controls: rx.Component,
    copyright_status: rx.Component,
) -> rx.Component:
    """Render the footer structure shared by documentation sites.

    Args:
        feedback: Feedback prompt and control.
        actions: Page-level issue and edit actions.
        link_columns: Site footer navigation groups.
        controls: Theme and social controls.
        copyright_status: Copyright and optional service status.

    Returns:
        Documentation footer.
    """
    return rx.el.footer(
        rx.box(
            feedback,
            actions,
            class_name="flex w-full flex-row items-center justify-center border-y-0 border-secondary-4 pb-6 pt-0 lg:justify-between lg:border-y lg:pb-8 lg:pt-8",
        ),
        rx.box(
            link_columns,
            controls,
            copyright_status,
            class_name="flex w-full flex-col justify-between gap-10 py-6 lg:py-8",
        ),
        class_name="flex w-full max-w-full flex-col lg:max-w-none",
    )


def _docs_footer_link(
    text: str,
    href: str,
    *,
    root_site: bool = False,
) -> rx.Component:
    """Render an official documentation footer link.

    Args:
        text: Visible link label.
        href: Link destination.
        root_site: Whether the destination bypasses the docs router basename.

    Returns:
        Styled footer link.
    """
    class_name = (
        "font-small text-secondary-9 hover:!text-secondary-11 "
        "transition-color no-underline"
    )
    if root_site:
        return rx.el.elements.a(text, href=href, class_name=class_name)
    return rx.link(text, href=href, class_name=class_name, underline="none")


def _docs_footer_link_column(
    heading: str,
    *links: rx.Component,
) -> rx.Component:
    """Render an official documentation footer link column.

    Args:
        heading: Column heading.
        *links: Links displayed in the column.

    Returns:
        Footer link column.
    """
    return rx.box(
        rx.el.h4(
            heading,
            class_name="font-semibold text-secondary-12 text-sm tracking-[-0.01313rem]",
        ),
        *links,
        class_name="flex flex-col gap-4",
    )


def _docs_social_menu_item(icon: str, url: str, name: str) -> rx.Component:
    """Render one official documentation social link.

    Args:
        icon: Shared icon identifier.
        url: Social destination.
        name: Accessible social name.

    Returns:
        Social icon link.
    """
    return rx.el.elements.a(
        button(
            get_icon(icon, class_name="shrink-0"),
            variant="ghost",
            size="icon-sm",
            class_name="text-secondary-11",
            native_button=False,
        ),
        href=url,
        custom_attrs={"aria-label": f"Social link for {name}"},
        target="_blank",
    )


def _docs_social_menu() -> rx.Component:
    """Render the official documentation social menu.

    Returns:
        Row of social links.
    """
    return rx.box(
        _docs_social_menu_item("twitter_footer", TWITTER_URL, "Twitter"),
        _docs_social_menu_item("github_navbar", GITHUB_URL, "Github"),
        _docs_social_menu_item("discord_navbar", DISCORD_URL, "Discord"),
        _docs_social_menu_item("linkedin_footer", LINKEDIN_URL, "LinkedIn"),
        _docs_social_menu_item("forum_footer", FORUM_URL, "Forum"),
        class_name="flex flex-row items-center gap-2",
    )


def _docs_footer_action(
    text: str,
    href: str | rx.vars.StringVar[str],
) -> rx.Component:
    """Render an official documentation page action.

    Args:
        text: Visible action label.
        href: Action destination.

    Returns:
        Responsive action pill.
    """
    return rx.link(
        text,
        href=href,
        underline="none",
        class_name="lg:flex hidden flex-row justify-center items-center gap-2 lg:border-secondary-5 bg-secondary-3 lg:bg-secondary-1 hover:bg-secondary-3 shadow-none lg:shadow-large px-3 py-0.5 lg:border lg:border-solid border-none rounded-lg lg:rounded-full w-auto font-small font-small text-secondary-9 !hover:text-secondary-11 hover:!text-secondary-9 truncate whitespace-nowrap transition-bg transition-color cursor-pointer",
    )


def _docs_page_footer_content(
    issue_href: str | rx.vars.StringVar[str],
    edit_href: str | rx.vars.StringVar[str],
    *,
    external_docs_links: bool,
) -> rx.Component:
    """Render the complete official documentation footer content.

    Args:
        issue_href: Repository issue URL for the current page.
        edit_href: Repository edit URL for the current Markdown source.
        external_docs_links: Whether Reflex links leave the current docs app.

    Returns:
        Official documentation feedback, links, controls, and status footer.
    """
    feedback = rx.box(
        rx.text(
            "Did you find this useful?",
            class_name="whitespace-nowrap font-small text-secondary-11 lg:text-secondary-9",
        ),
        docs_feedback_button(),
        class_name="flex w-full flex-col items-center gap-3 rounded-lg bg-secondary-3 p-4 lg:w-auto lg:flex-row lg:gap-4 lg:bg-transparent lg:p-0",
    )
    actions = rx.box(
        _docs_footer_action("Raise an issue", issue_href),
        _docs_footer_action("Edit this page", edit_href),
        class_name="hidden w-auto flex-row items-center gap-2 lg:flex",
    )
    docs_prefix = "https://reflex.dev/docs" if external_docs_links else ""
    root_prefix = "https://reflex.dev" if external_docs_links else ""
    link_columns = rx.box(
        _docs_footer_link_column(
            "Links",
            _docs_footer_link(
                "Home",
                f"{docs_prefix}/" if external_docs_links else "/",
                root_site=external_docs_links,
            ),
            _docs_footer_link("Blog", f"{root_prefix}/blog/", root_site=True),
            _docs_footer_link(
                "Changelog",
                f"{docs_prefix}/changelog/" if external_docs_links else "/changelog/",
                root_site=external_docs_links,
            ),
        ),
        _docs_footer_link_column(
            "Documentation",
            _docs_footer_link(
                "Introduction",
                f"{docs_prefix}/getting-started/introduction/",
                root_site=external_docs_links,
            ),
            _docs_footer_link(
                "Installation",
                f"{docs_prefix}/getting-started/installation/",
                root_site=external_docs_links,
            ),
            _docs_footer_link(
                "Components",
                f"{docs_prefix}/library/",
                root_site=external_docs_links,
            ),
            _docs_footer_link(
                "Hosting",
                f"{docs_prefix}/hosting/deploy-quick-start/",
                root_site=external_docs_links,
            ),
        ),
        _docs_footer_link_column(
            "Resources",
            _docs_footer_link("FAQ", f"{root_prefix}/faq/", root_site=True),
            _docs_footer_link("Roadmap", ROADMAP_URL),
            _docs_footer_link("Forum", FORUM_URL),
        ),
        class_name="flex w-full flex-wrap justify-between gap-12",
    )
    controls = rx.box(
        rx.box(dark_mode_toggle(), class_name="[&>div]:!ml-0"),
        _docs_social_menu(),
        class_name="flex w-full flex-row items-end justify-between gap-6",
    )
    copyright_status = rx.el.div(
        rx.text(
            f"Copyright © {datetime.now().year} Pynecone, Inc.",
            class_name="font-small text-secondary-9",
        ),
        server_status(StatusState.status),
        class_name="flex w-full flex-row items-center justify-between gap-4",
    )
    return docs_footer_shell(
        feedback,
        actions,
        link_columns,
        controls,
        copyright_status,
    )


def docs_page_footer(
    issue_href: str | rx.vars.StringVar[str],
    edit_href: str | rx.vars.StringVar[str],
) -> rx.Component:
    """Render the official footer inside the Reflex documentation router.

    Args:
        issue_href: Repository issue URL for the current page.
        edit_href: Repository edit URL for the current Markdown source.

    Returns:
        Official documentation footer using internal Reflex docs links.
    """
    return _docs_page_footer_content(
        issue_href,
        edit_href,
        external_docs_links=False,
    )


@rx.memo
def _docs_external_page_footer_memo(
    issue_href: rx.Var[str],
    edit_href: rx.Var[str],
) -> rx.Component:
    """Memoize the official footer used by external documentation apps.

    Args:
        issue_href: Repository issue URL for the current page.
        edit_href: Repository edit URL for the current Markdown source.

    Returns:
        Official documentation footer with absolute reflex.dev links.
    """
    return _docs_page_footer_content(
        issue_href,
        edit_href,
        external_docs_links=True,
    )


def docs_external_page_footer(
    issue_href: str | rx.vars.StringVar[str],
    edit_href: str | rx.vars.StringVar[str],
) -> rx.Component:
    """Render the official footer from another documentation application.

    Args:
        issue_href: Repository issue URL for the current page.
        edit_href: Repository edit URL for the current Markdown source.

    Returns:
        Memoized official footer with absolute reflex.dev links.
    """
    return _docs_external_page_footer_memo(
        issue_href=rx.Var.create(issue_href),
        edit_href=rx.Var.create(edit_href),
    )


def docs_book_demo_action() -> rx.Component:
    """Render the official documentation Book a Demo action.

    Returns:
        Demo form dialog and trigger.
    """
    return demo_form_dialog(
        trigger=button(
            "Book a Demo",
            size="sm",
            variant="primary",
            class_name="whitespace-nowrap",
            native_button=False,
        )
    )


__all__ = [
    "docs_book_demo_action",
    "docs_external_page_footer",
    "docs_feedback_button",
    "docs_feedback_button_toc",
    "docs_footer_shell",
    "docs_left_sidebar",
    "docs_navbar_frame",
    "docs_page_footer",
    "docs_right_sidebar",
    "docs_sidebar_category",
    "docs_sidebar_group",
    "docs_sidebar_leaf",
    "docs_sidebar_section",
]
