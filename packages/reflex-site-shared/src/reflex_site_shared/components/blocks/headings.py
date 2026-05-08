# pyright: reportArgumentType=false, reportReturnType=false, reportOperatorIssue=false
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
    ) -> rx.Component:
        """Create.

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
                text,
                id=id_,
                as_=heading,
                style=style if style is not None else {},
                class_name=class_name + " " + scroll_margin + " mt-" + mt,
            ),
            rx.icon(
                tag="link",
                size=18,
                class_name="!text-violet-11 invisible transition-[visibility_0.075s_ease-out] group-hover:visible mt-"
                + mt,
            ),
            underline="none",
            href=href,
            on_click=lambda: rx.set_clipboard(href),
            class_name="flex flex-row items-center gap-2 hover:!text-violet-11 cursor-pointer mb-3 transition-colors group text-m-slate-12 dark:text-m-slate-3 ",
        )


h_comp_common = HeadingLink.create


@rx.memo
def h1_comp(text: str) -> rx.Component:
    """H1 comp.

    Returns:
        The component.
    """
    return h_comp_common(
        text=text,
        heading="h1",
        class_name="lg:text-4xl text-3xl font-semibold",
    )


@rx.memo
def h1_comp_xd(text: str) -> rx.Component:
    """H1 comp xd.

    Returns:
        The component.
    """
    return h_comp_common(
        text=text,
        heading="h1",
        class_name="lg:text-4xl text-3xl font-semibold",
    )


@rx.memo
def h2_comp(text: str) -> rx.Component:
    """H2 comp.

    Returns:
        The component.
    """
    return h_comp_common(
        text=text,
        heading="h2",
        mt="8",
        class_name="lg:text-3xl text-2xl font-semibold",
    )


@rx.memo
def h2_comp_xd(text: str) -> rx.Component:
    """H2 comp xd.

    Returns:
        The component.
    """
    return h_comp_common(
        text=text,
        heading="h2",
        mt="8",
        class_name="lg:text-2xl text-xl font-semibold",
    )


@rx.memo
def h3_comp(text: str) -> rx.Component:
    """H3 comp.

    Returns:
        The component.
    """
    return h_comp_common(
        text=text,
        heading="h3",
        mt="4",
        class_name="lg:text-xl text-lg font-semibold",
    )


@rx.memo
def h3_comp_xd(text: str) -> rx.Component:
    """H3 comp xd.

    Returns:
        The component.
    """
    return h_comp_common(
        text=text,
        heading="h3",
        mt="4",
        class_name="lg:text-xl text-lg font-semibold",
    )


@rx.memo
def h4_comp(text: str) -> rx.Component:
    """H4 comp.

    Returns:
        The component.
    """
    return h_comp_common(
        text=text,
        heading="h4",
        mt="2",
        class_name="lg:text-base text-base font-semibold",
    )


@rx.memo
def h4_comp_xd(text: str) -> rx.Component:
    """H4 comp xd.

    Returns:
        The component.
    """
    return h_comp_common(
        text=text,
        heading="h4",
        mt="2",
        class_name="lg:text-base text-base font-semibold",
    )


@rx.memo
def img_comp_xd(src: str) -> rx.Component:
    """Img comp xd.

    Returns:
        The component.
    """
    return rx.image(
        src=src,
        class_name="rounded-lg border border-secondary-a4 mb-2",
    )
