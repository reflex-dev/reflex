"""Shared tab primitives for documentation cards."""

import reflex as rx

__all__ = ["doc_tab_card", "doc_tab_list", "doc_tab_trigger"]

_DOC_TAB_LIST_CLASS = (
    "doc-demo-tab-list relative z-10 -mb-px flex w-full items-end justify-end "
    "!gap-0 !border-b-0 !bg-transparent !p-0 !shadow-none "
    "before:!hidden after:!hidden"
)

_DOC_TAB_CLASS = (
    "doc-demo-tab cursor-pointer appearance-none !rounded-none "
    "first:!rounded-tl-xl last:!rounded-tr-xl "
    "!border !border-secondary-4 -ml-px first:!ml-0 "
    "!bg-secondary-3 !px-4 !py-2.5 !text-sm !font-medium "
    "!text-secondary-11 !shadow-none transition-colors duration-150 "
    "before:!hidden after:!hidden hover:!text-secondary-12 "
    "dark:!bg-secondary-4 dark:!text-secondary-10 "
    "dark:data-[state=inactive]:hover:!bg-secondary-5 "
    "dark:data-[state=inactive]:hover:!text-secondary-11 "
    "data-[state=active]:!z-10 data-[state=active]:!border-b-transparent "
    "data-[state=active]:!bg-secondary-2 data-[state=active]:!text-secondary-12 "
    "dark:data-[state=active]:!bg-secondary-2 "
    "dark:data-[state=active]:!text-secondary-12 "
    "[&_.rt-BaseTabListTriggerInner]:!bg-transparent"
)

_DOC_TAB_CARD_CLASS = (
    "doc-demo-tab-card relative w-full overflow-hidden rounded-xl rounded-tr-none "
    "border border-secondary-4 bg-secondary-2"
)


def doc_tab_list(*children: rx.Component) -> rx.Component:
    """Create a connected tab strip for a documentation card.

    Args:
        children: Tab triggers to render.

    Returns:
        The styled tab list.
    """
    return rx.tabs.list(*children, class_name=_DOC_TAB_LIST_CLASS)


def doc_tab_trigger(label: str, *, value: str, icon: str) -> rx.Component:
    """Create a folder-style trigger for a documentation card.

    Args:
        label: Visible trigger label.
        value: Value of the corresponding tab panel.
        icon: Lucide icon name to render before the label.

    Returns:
        The styled tab trigger.
    """
    return rx.tabs.trigger(
        rx.el.span(
            rx.icon(icon, size=15, aria_hidden="true"),
            rx.el.span(label),
            class_name="inline-flex items-center gap-2",
        ),
        value=value,
        class_name=_DOC_TAB_CLASS,
    )


def doc_tab_card(*children: rx.Component) -> rx.Component:
    """Create the shared surface beneath a documentation tab strip.

    Args:
        children: Tab panels to render.

    Returns:
        The styled tab card.
    """
    return rx.box(*children, class_name=_DOC_TAB_CARD_CLASS)
