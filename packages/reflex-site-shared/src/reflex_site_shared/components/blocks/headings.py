"""Template for documentation pages."""

from typing import ClassVar

import reflex as rx
from reflex_site_shared.views.hosting_banner import HostingBannerState

icon_margins = {
    "h1": "10px",
    "h2": "5px",
    "h3": "2px",
    "h4": "0px",
}

# Tag, top margin and classes for each Markdown heading level.
HEADING_STYLES = {
    1: ("h1", "4", "lg:text-4xl text-3xl font-medium"),
    2: ("h2", "12", "lg:text-3xl text-2xl font-medium"),
    3: ("h3", "8", "lg:text-2xl text-xl font-medium"),
    4: ("h4", "2", "lg:text-base text-base font-semibold"),
}


class HeadingLink(rx.link.__self__):
    """HeadingLink."""

    # This function is imported from 'hast-util-to-string' package.
    HAST_NODE_TO_STRING: ClassVar = rx.vars.FunctionStringVar(
        _js_expr="hastNodeToString",
    )

    # This function is defined by add_custom_code.
    SLUGIFY_MIXED_TEXT_HAST_NODE: ClassVar = rx.vars.FunctionStringVar(
        _js_expr="slugifyMixedTextHastNode",
    )

    def add_custom_code(self) -> list[rx.Var]:
        """Add custom code.

        Returns:
            The component.
        """

        def node_to_string(node: rx.Var) -> rx.vars.StringVar:
            return rx.cond(
                node.js_type() == "string",
                node,
                rx.cond(
                    (node.js_type() == "object")
                    & node.to(dict)["props"].to(dict)["node"],
                    self.HAST_NODE_TO_STRING(node.to(dict)["props"].to(dict)["node"]),
                    "object",
                ),
            ).to(str)

        def slugify(node: rx.Var) -> rx.vars.StringVar:
            return (
                rx
                .cond(
                    rx.vars.function.ARRAY_ISARRAY(node),
                    rx.vars.sequence.map_array_operation(
                        node,
                        rx.vars.function.ArgsFunctionOperation.create(
                            args_names=["childNode"],
                            return_expr=node_to_string(rx.vars.Var("childNode")),
                        ),
                    ).join("-"),
                    node_to_string(node),
                )
                .to(str)
                .lower()
                .split(" ")
                .join("-")
            )

        return [
            f"const {self.SLUGIFY_MIXED_TEXT_HAST_NODE!s} = "
            + str(
                rx.vars.function.ArgsFunctionOperation.create(
                    args_names=["givenNode"],
                    return_expr=slugify(rx.vars.Var("givenNode")),
                )
            )
        ]

    def add_imports(self) -> dict[str, list[rx.ImportVar]]:
        """Add imports.

        Returns:
            The component.
        """
        return {
            "hast-util-to-string@3.0.1": [
                rx.ImportVar(tag="toString", alias="hastNodeToString", is_default=False)
            ],
        }

    @classmethod
    def slugify(cls, node: rx.Var) -> rx.vars.StringVar:
        """Slugify.

        Returns:
            The component.
        """
        return cls.SLUGIFY_MIXED_TEXT_HAST_NODE(node).to(str)

    @classmethod
    def create(
        cls,
        text: str,
        heading: str,
        style: dict | None = None,
        mt: str = "4",
        class_name: str = "",
        content: rx.Component | None = None,
    ) -> rx.Component:
        """Create.

        Args:
            text: The heading's plain text, which its anchor is made from.
            heading: The heading tag.
            style: Extra style for the heading.
            mt: The top margin.
            class_name: Classes for the heading.
            content: What to show in place of ``text``, such as text with inline
                code in it.

        Returns:
            The component.
        """
        id_ = cls.slugify(text)
        href = rx.State.router.url + "#" + id_
        scroll_margin = rx.cond(
            HostingBannerState.is_banner_visible,
            "scroll-mt-[113px]",
            "scroll-mt-[77px]",
        )

        return super().create(
            rx.heading(
                text if content is None else content,
                id=id_,
                as_=heading,
                style={
                    "letter_spacing": "-0.03em" if heading == "h1" else "-0.025em",
                    "line_height": "1.2" if heading == "h1" else "1.25",
                    **(style or {}),
                },
                class_name=class_name + " " + scroll_margin + " mt-" + mt,
            ),
            rx.icon(
                tag="link",
                size=18,
                class_name="!text-foreground invisible transition-[visibility_0.075s_ease-out] group-hover:visible mt-"
                + mt,
            ),
            underline="none",
            href=href,
            on_click=lambda: rx.set_clipboard(href),
            class_name="flex flex-row items-center gap-2 hover:!text-foreground cursor-pointer mb-3 transition-colors group text-foreground ",
        )


h_comp_common = HeadingLink.create


def heading_comp(
    text: str | rx.Var[str], level: int, content: rx.Component | None = None
) -> rx.Component:
    """Render a Markdown heading with a link to its own anchor.

    Args:
        text: The heading's plain text, which its anchor is made from.
        level: The heading level; anything past four is styled as four.
        content: What to show in place of ``text``, such as text with inline
            code in it.

    Returns:
        The component.
    """
    heading, mt, class_name = HEADING_STYLES[min(level, 4)]
    return h_comp_common(
        text=text, heading=heading, mt=mt, class_name=class_name, content=content
    )


@rx.memo
def h1_comp(text: rx.Var[str]) -> rx.Component:
    """H1 comp.

    Returns:
        The component.
    """
    return heading_comp(text, 1)


@rx.memo
def h1_comp_xd(text: rx.Var[str]) -> rx.Component:
    """H1 comp xd.

    Returns:
        The component.
    """
    return heading_comp(text, 1)


@rx.memo
def h2_comp(text: rx.Var[str]) -> rx.Component:
    """H2 comp.

    Returns:
        The component.
    """
    return heading_comp(text, 2)


@rx.memo
def h2_comp_xd(text: rx.Var[str]) -> rx.Component:
    """H2 comp xd.

    Returns:
        The component.
    """
    return heading_comp(text, 2)


@rx.memo
def h3_comp(text: rx.Var[str]) -> rx.Component:
    """H3 comp.

    Returns:
        The component.
    """
    return heading_comp(text, 3)


@rx.memo
def h3_comp_xd(text: rx.Var[str]) -> rx.Component:
    """H3 comp xd.

    Returns:
        The component.
    """
    return heading_comp(text, 3)


@rx.memo
def h4_comp(text: rx.Var[str]) -> rx.Component:
    """H4 comp.

    Returns:
        The component.
    """
    return heading_comp(text, 4)


@rx.memo
def h4_comp_xd(text: rx.Var[str]) -> rx.Component:
    """H4 comp xd.

    Returns:
        The component.
    """
    return heading_comp(text, 4)


@rx.memo
def img_comp_xd(src: rx.Var[str]) -> rx.Component:
    """Img comp xd.

    Returns:
        The component.
    """
    return rx.image(
        src=src,
        alt="Documentation image",
        class_name="rounded-lg border border-border-subtle mb-2",
    )
