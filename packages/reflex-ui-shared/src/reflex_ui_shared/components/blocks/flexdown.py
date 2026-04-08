"""Flexdown module."""

# pyright: reportAttributeAccessIssue=false
import flexdown
import reflex_ui as ui
from reflex_base.constants.colors import ColorType

import reflex as rx
from reflex_ui_shared.components.blocks.code import (
    code_block_markdown,
    code_block_markdown_dark,
)
from reflex_ui_shared.components.blocks.collapsible import collapsible_box
from reflex_ui_shared.components.blocks.demo import docdemo, docdemobox, docgraphing
from reflex_ui_shared.components.blocks.headings import (
    h1_comp_xd,
    h2_comp_xd,
    h3_comp_xd,
    h4_comp_xd,
    img_comp_xd,
)
from reflex_ui_shared.components.blocks.typography import (
    code_comp,
    definition,
    doclink2,
    list_comp,
    ordered_list_comp,
    text_comp,
    unordered_list_comp,
)
from reflex_ui_shared.constants import REFLEX_ASSETS_CDN
from reflex_ui_shared.styles.colors import c_color
from reflex_ui_shared.styles.fonts import base, code


def get_code_style(color: ColorType):
    """Get code style.

    Returns:
        The component.
    """
    return {
        "p": {"margin_y": "0px"},
        "code": {
            "color": rx.color(color, 11),
            "border_radius": "4px",
            "border": f"1px solid {rx.color(color, 5)}",
            "background": rx.color(color, 4),
            **code,
        },
        **base,
    }


class AlertBlock(flexdown.blocks.MarkdownBlock):
    """A block that displays a component along with its code."""

    starting_indicator = "```md alert"
    ending_indicator = "```"

    include_indicators = True

    def render(self, env: dict) -> rx.Component:
        """Render.

        Returns:
            The component.
        """
        lines = self.get_lines(env)

        args = lines[0].removeprefix(self.starting_indicator).split()

        if len(args) == 0:
            args = ["info"]
        status = args[0]

        if lines[1].startswith("#"):
            title = lines[1].strip("#").strip()
            content = "\n".join(lines[2:-1])
        else:
            title = ""
            content = "\n".join(lines[1:-1])

        colors: dict[str, ColorType] = {
            "info": "accent",
            "success": "grass",
            "warning": "amber",
            "error": "red",
        }

        color: ColorType = colors.get(status, "blue")

        has_content = bool(content.strip())

        icon = rx.box(
            rx.match(
                status,
                ("info", rx.icon(tag="info", size=18, margin_right=".5em")),
                ("success", rx.icon(tag="circle_check", size=18, margin_right=".5em")),
                (
                    "warning",
                    rx.icon(tag="triangle_alert", size=18, margin_right=".5em"),
                ),
                ("error", rx.icon(tag="ban", size=18, margin_right=".5em")),
            ),
            color=f"{rx.color(color, 11)}",
        )
        title_comp = (
            markdown_with_shiki(
                title,
                margin_y="0px",
                style=get_code_style(color),
            )
            if title
            else self.render_fn(content=content)
        )

        if has_content:
            body = (
                rx.accordion.content(
                    markdown(content), padding="0px", margin_top="16px"
                )
                if title
                else rx.fragment()
            )
            return collapsible_box([icon, title_comp], body, color)

        return rx.vstack(
            rx.hstack(
                icon,
                markdown_with_shiki(
                    title,
                    color=f"{rx.color(color, 11)}",
                    margin_y="0px",
                    style=get_code_style(color),
                ),
                align_items="center",
                width="100%",
                spacing="1",
                padding=["16px", "24px"],
            ),
            border=f"1px solid {rx.color(color, 4)}",
            background_color=f"{rx.color(color, 3)}",
            border_radius="12px",
            margin_bottom="16px",
            margin_top="16px",
            width="100%",
        )


class SectionBlock(flexdown.blocks.Block):
    """A block that displays a component along with its code."""

    starting_indicator = "```md section"
    ending_indicator = "```"

    def render(self, env: dict) -> rx.Component:
        """Render.

        Returns:
            The component.
        """
        lines = self.get_lines(env)

        # Split up content into sections based on markdown headers.
        header_indices = [i for i, line in enumerate(lines) if line.startswith("#")]
        header_indices.append(len(lines))
        sections = [
            (
                lines[header_indices[i]].strip("#"),
                "\n".join(lines[header_indices[i] + 1 : header_indices[i + 1]]),
            )
            for i in range(len(header_indices) - 1)
        ]

        return rx.box(
            rx.vstack(
                *[
                    rx.fragment(
                        rx.text(
                            rx.text.span(
                                header,
                                font_weight="bold",
                            ),
                            width="100%",
                        ),
                        rx.box(
                            markdown(section),
                            width="100%",
                        ),
                    )
                    for header, section in sections
                ],
                text_align="left",
                margin_y="1em",
                width="100%",
            ),
            border_left=f"1.5px {c_color('slate', 4)} solid",
            padding_left="1em",
            width="100%",
            align_items="center",
        )


class DefinitionBlock(flexdown.blocks.Block):
    """DefinitionBlock."""

    starting_indicator = "```md definition"
    ending_indicator = "```"

    def render(self, env: dict) -> rx.Component:
        """Render.

        Returns:
            The component.
        """
        lines = self.get_lines(env)

        # Split up content into sections based on markdown headers.
        header_indices = [i for i, line in enumerate(lines) if line.startswith("#")]
        header_indices.append(len(lines))
        sections = [
            (
                lines[header_indices[i]].removeprefix("#"),
                "\n".join(lines[header_indices[i] + 1 : header_indices[i + 1]]),
            )
            for i in range(len(header_indices) - 1)
        ]

        defs = [definition(title, content) for title, content in sections]

        return rx.fragment(
            rx.mobile_only(rx.vstack(*defs)),
            rx.tablet_and_desktop(
                rx.grid(
                    *[rx.box(d) for d in defs],
                    columns="2",
                    width="100%",
                    gap="1rem",
                    margin_bottom="1em",
                )
            ),
        )


class DemoOnly(flexdown.blocks.Block):
    """A block that displays only a component demo without showing the code."""

    starting_indicator = "```python demo-only"
    ending_indicator = "```"
    include_indicators = True
    theme: str | None = None

    def render(self, env: dict) -> rx.Component:
        """Render.

        Returns:
            The component.
        """
        lines = self.get_lines(env)
        code = "\n".join(lines[1:-1])

        args = lines[0].removeprefix(self.starting_indicator).split()

        exec_mode = env.get("__exec", False)
        comp: rx.Component = rx.fragment()

        for arg in args:
            if arg.startswith("id="):
                comp_id = arg.rsplit("id=")[-1]
                break
        else:
            comp_id = None

        if "exec" in args:
            env["__xd"].exec(code, env, self.filename)
            if not exec_mode:
                comp = env[list(env.keys())[-1]]()
        elif "graphing" in args:
            env["__xd"].exec(code, env, self.filename)
            if not exec_mode:
                comp = env[list(env.keys())[-1]]()
                # Get all the code before the final "def".
                parts = code.rpartition("def")
                data, code = parts[0], parts[1] + parts[2]
                return docgraphing(code, comp=comp, data=data)
        elif exec_mode:
            return comp
        elif "box" in args:
            comp = eval(code, env, env)
            return rx.box(comp, margin_bottom="1em", id=comp_id)
        else:
            comp = eval(code, env, env)

        # Return only the component without any code display
        return rx.box(comp, margin_bottom="1em", id=comp_id)


class DemoBlock(flexdown.blocks.Block):
    """A block that displays a component along with its code."""

    starting_indicator = "```python demo"
    ending_indicator = "```"
    include_indicators = True
    theme: str | None = None

    def render(self, env: dict) -> rx.Component:
        """Render.

        Returns:
            The component.
        """
        lines = self.get_lines(env)
        code = "\n".join(lines[1:-1])

        args = lines[0].removeprefix(self.starting_indicator).split()

        exec_mode = env.get("__exec", False)
        comp: rx.Component = rx.fragment()

        for arg in args:
            if arg.startswith("id="):
                comp_id = arg.rsplit("id=")[-1]
                break
        else:
            comp_id = None

        if "exec" in args:
            env["__xd"].exec(code, env, self.filename)
            if not exec_mode:
                comp = env[list(env.keys())[-1]]()
        elif "graphing" in args:
            env["__xd"].exec(code, env, self.filename)
            if not exec_mode:
                comp = env[list(env.keys())[-1]]()
                # Get all the code before the final "def".
                parts = code.rpartition("def")
                data, code = parts[0], parts[1] + parts[2]
                return docgraphing(code, comp=comp, data=data)
        elif exec_mode:
            return comp
        elif "box" in args:
            comp = eval(code, env, env)
            return rx.box(docdemobox(comp), margin_bottom="1em", id=comp_id)
        else:
            comp = eval(code, env, env)

        # Sweep up additional CSS-like props to apply to the demobox itself
        demobox_props = {}
        for arg in args:
            prop, equals, value = arg.partition("=")
            if equals:
                demobox_props[prop] = value

        if "toggle" in args:
            demobox_props["toggle"] = True

        return docdemo(
            code, comp=comp, demobox_props=demobox_props, theme=self.theme, id=comp_id
        )


class DemoBlockDark(DemoBlock):
    """DemoBlockDark."""

    theme = "dark"


class DemoBlockNestedMarkdown(DemoBlock):
    """Used when the block contains literal markdown with triple backticks."""

    starting_indicator = "````python demo"
    ending_indicator = "````"


class DemoBlockNestedMarkdownDark(DemoBlockNestedMarkdown):
    """DemoBlockNestedMarkdownDark."""

    theme = "dark"


class VideoBlock(flexdown.blocks.MarkdownBlock):
    """A block that displays a video."""

    starting_indicator = "```md video"
    ending_indicator = "```"

    include_indicators = True

    def render(self, env: dict) -> rx.Component:
        """Render.

        Returns:
            The component.
        """
        lines = self.get_lines(env)

        args = lines[0].removeprefix(self.starting_indicator).split()

        if len(args) == 0:
            args = ["info"]
        url = args[0]

        title = lines[1].strip("#").strip() if lines[1].startswith("#") else ""

        color: ColorType = "blue"

        trigger = [
            markdown_with_shiki(
                title or "Video Description",
                margin_y="0px",
                style=get_code_style(color),
            ),
        ]
        body = rx.accordion.content(
            rx.video(
                src=url,
                width="100%",
                height="500px",
                border_radius="10px",
                overflow="hidden",
            ),
            margin_top="16px",
            padding="0px",
        )
        return collapsible_box(trigger, body, color, item_border_radius="0px")


class QuoteBlock(flexdown.blocks.MarkdownBlock):
    """A block that displays a quote."""

    starting_indicator = "```md quote"
    ending_indicator = "```"

    include_indicators = True

    def _parse(self, env: dict) -> dict[str, str]:
        lines = self.get_lines(env)
        quote_content = []
        data = {
            "name": "",
            "role": "",
            "image": "",
            "variant": "small",
        }

        for line in lines[1:-1]:  # Skip the first and last lines (indicators)
            if line.startswith("- name:"):
                data["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("- role:"):
                data["role"] = line.split(":", 1)[1].strip()
            elif line.startswith("- image:"):
                data["image"] = line.split(":", 1)[1].strip()
            elif line.startswith("- variant:"):
                data["variant"] = line.split(":", 1)[1].strip().lower()
            else:
                quote_content.append(line)

        data["quote_text"] = "\n".join(quote_content).strip()
        return data

    def _author(self, name: str, role: str, class_name: str = "") -> rx.Component:
        return rx.el.div(
            rx.el.span(
                name,
                class_name="text-xs font-mono uppercase font-[415] text-secondary-12",
            ),
            rx.el.span(
                role,
                class_name="text-xs font-mono font-[415] text-secondary-11 uppercase",
            ),
            class_name=ui.cn("flex flex-col gap-0.5", class_name),
        )

    def _avatar(
        self, name: str, image: str, class_name: str = ""
    ) -> rx.Component | None:
        if not image:
            return None
        avatar_class = ui.cn("rounded-full object-cover aspect-square", class_name)
        return rx.image(
            src=f"{REFLEX_ASSETS_CDN}case_studies/people/{image}",
            alt=f"{name} profile picture",
            class_name=avatar_class,
        )

    def _render_medium(self, data: dict[str, str]) -> rx.Component:
        return rx.el.div(
            rx.el.div(
                self._avatar(data["name"], data["image"], class_name="size-6"),
                class_name="p-4 shrink-0 lg:border-r border-secondary-8 border-dashed max-lg:border-b bg-secondary-1",
            ),
            rx.el.span(
                f'"{data["quote_text"]}"',
                class_name="text-secondary-12 text-base font-[575] p-4 bg-white-1 w-full",
            ),
            class_name="flex lg:flex-row flex-col border border-dashed border-secondary-8 mt-2 mb-6 rounded-lg overflow-hidden box-border bg-white-1",
        )

    def _render_small(self, data: dict[str, str]) -> rx.Component:
        return rx.el.div(
            rx.el.span(
                f'"{data["quote_text"]}"',
                class_name="text-secondary-12 text-lg font-[575] p-6 lg:border-r border-secondary-8 border-dashed max-lg:border-b bg-white-1",
            ),
            rx.el.div(
                rx.el.div(
                    self._author(data["name"], data["role"]),
                    class_name="text-end text-nowrap",
                ),
                self._avatar(data["name"], data["image"], class_name="size-14"),
                class_name="flex flex-row gap-6 items-center p-6 shrink-0 bg-secondary-1",
            ),
            class_name="flex lg:flex-row flex-col border border-dashed border-secondary-8 mt-2 mb-6 rounded-lg overflow-hidden box-border bg-white-1",
        )

    def _render_big(self, data: dict[str, str]) -> rx.Component:
        return rx.el.div(
            rx.el.div(
                rx.el.span(
                    f"{data['quote_text']}",
                    class_name="text-secondary-12 text-2xl font-[575]",
                ),
                rx.el.div(
                    self._avatar(data["name"], data["image"], class_name="size-6"),
                    self._author(
                        data["name"],
                        data["role"],
                        class_name="flex-row gap-3.5 items-center",
                    ),
                    class_name="flex flex-row gap-3.5 items-center",
                ),
                class_name="flex flex-col gap-12 pr-[12.5rem] relative z-10",
            ),
            rx.image(
                src=f"{REFLEX_ASSETS_CDN}common/{rx.color_mode_cond('light', 'dark')}/quote_squares.svg",
                loading="lazy",
                alt="Quote icon",
                class_name="absolute right-0 inset-y-0 h-[calc(100%)] min-h-full w-auto origin-right pointer-events-none object-contain object-right",
            ),
            class_name="flex flex-col dark:border bg-white-1 dark:border-secondary-4 mt-2 mb-6 overflow-hidden shadow-[0_0_0_1px_rgba(0,0,0,0.12)_inset,0_6px_12px_0_rgba(0,0,0,0.06),0_1px_1px_0_rgba(0,0,0,0.01),0_4px_6px_0_rgba(0,0,0,0.02)] rounded-xl py-8 px-8 relative",
        )

    def render(self, env: dict) -> rx.Component:
        """Render.

        Returns:
            The component.
        """
        data = self._parse(env)
        renderers = {
            "small": self._render_small,
            "medium": self._render_medium,
            "big": self._render_big,
        }
        renderer = renderers.get(data["variant"], self._render_small)
        return renderer(data)


class TabsBlock(flexdown.blocks.Block):
    """A block that displays content in tabs."""

    starting_indicator = "---md tabs"
    ending_indicator = "---"

    def render(self, env: dict) -> rx.Component:
        """Render.

        Returns:
            The component.
        """
        lines = self.get_lines(env)

        tab_sections = []
        current_section = []
        current_title = ""

        for line in lines[1:-1]:  # Skip the first and last lines (indicators)
            stripped_line = line.strip()

            if stripped_line.startswith("--tab "):
                if current_title:
                    tab_sections.append((current_title, "\n".join(current_section)))
                current_title = stripped_line[6:].strip()
                current_section = []
            elif stripped_line == "--":
                if current_title:
                    tab_sections.append((current_title, "\n".join(current_section)))
                    current_title = ""
                    current_section = []
            else:
                current_section.append(line)

        # Add the last section if there's content
        if current_title and current_section:
            tab_sections.append((current_title, "\n".join(current_section)))

        # Create tab components
        triggers = []
        contents = []

        for i, (title, content) in enumerate(tab_sections):
            value = f"tab{i + 1}"
            triggers.append(
                rx.tabs.trigger(
                    title,
                    value=value,
                    class_name="tab-style font-base font-semibold text-[1.25rem]",
                )
            )

            # Render the tab content
            tab_content = []
            for block in env["__xd"].get_blocks(content, self.filename):
                if isinstance(block, flexdown.blocks.MarkdownBlock):
                    block.render_fn = env["__xd"].flexdown_memo
                tab_content.append(block.render(env=env))

            contents.append(rx.tabs.content(rx.fragment(*tab_content), value=value))

        return rx.tabs.root(
            rx.tabs.list(*triggers, class_name="mt-4"), *contents, default_value="tab1"
        )


def _markdown_table(*children, **props) -> rx.Component:
    return rx.box(
        rx.el.table(
            *children,
            class_name="w-full border-collapse text-sm border border-secondary-4 rounded-lg overflow-hidden bg-white-1 ",
            **props,
        ),
        class_name="w-full rounded-xl border border-secondary-a4 my-6 max-w-full overflow-hidden",
    )


def _markdown_thead(*children, **props) -> rx.Component:
    return rx.el.thead(
        *children,
        class_name="bg-secondary-1 border-b border-secondary-4",
        **props,
    )


def _markdown_tbody(*children, **props) -> rx.Component:
    return rx.el.tbody(
        *children,
        class_name="[&_tr:nth-child(even)]:bg-secondary-1",
        **props,
    )


def _markdown_tr(*children, **props) -> rx.Component:
    return rx.el.tr(
        *children,
        class_name="border-b border-secondary-4 last:border-b-0",
        **props,
    )


def _markdown_th(*children, **props) -> rx.Component:
    return rx.el.th(
        *children,
        class_name="px-3 py-2.5 text-left text-xs font-[575] text-secondary-12 align-top",
        **props,
    )


def _markdown_td(*children, **props) -> rx.Component:
    return rx.el.td(
        *children,
        class_name="px-3 py-2.5 text-xs font-medium first:font-[575] text-secondary-11 align-top",
        **props,
    )


_markdown_table_component_map: dict[str, object] = {
    "table": _markdown_table,
    "thead": _markdown_thead,
    "tbody": _markdown_tbody,
    "tr": _markdown_tr,
    "th": _markdown_th,
    "td": _markdown_td,
}

component_map = {
    "h1": lambda text: h1_comp_xd(text=text),
    "h2": lambda text: h2_comp_xd(text=text),
    "h3": lambda text: h3_comp_xd(text=text),
    "h4": lambda text: h4_comp_xd(text=text),
    "p": lambda text: text_comp(text=text),
    "li": lambda text: list_comp(text=text),
    "a": doclink2,
    "code": lambda text: code_comp(text=text),
    "pre": code_block_markdown,
    "img": lambda src: img_comp_xd(src=src),
    **_markdown_table_component_map,
}
comp2 = component_map.copy()
comp2["pre"] = code_block_markdown_dark
comp2["ul"] = lambda items: unordered_list_comp(items=items)
comp2["ol"] = lambda items: ordered_list_comp(items=items)


xd = flexdown.Flexdown(
    block_types=[
        DemoOnly,
        DemoBlock,
        DemoBlockNestedMarkdown,
        AlertBlock,
        DefinitionBlock,
        SectionBlock,
        VideoBlock,
        TabsBlock,
        QuoteBlock,
    ],
    component_map=component_map,
)
xd.clear_modules()
xd2 = flexdown.Flexdown(
    block_types=[
        DemoBlockDark,
        DemoBlockNestedMarkdownDark,
        AlertBlock,
        DefinitionBlock,
        SectionBlock,
        VideoBlock,
        TabsBlock,
        QuoteBlock,
    ],
    component_map=comp2,
)
xd2.clear_modules()


def markdown(text: str):
    """Markdown.

    Returns:
        The component.
    """
    return xd.get_default_block().render_fn(content=text)


def markdown_codeblock(value: str, **props: object) -> rx.Component:
    """Render a code block using the Shiki-based code block component.

    Returns:
        The component.
    """
    return rx._x.code_block(value, **props)


def markdown_with_shiki(*args, **kwargs):
    """Wrapper for the markdown component with a customized component map.
    Uses the experimental Shiki-based code block (rx._x.code_block)
    instead of the default CodeBlock component for code blocks.

    Note: This wrapper should be removed once the default codeblock
    in rx.markdown component map is updated to the Shiki-based code block.

    Returns:
            The component.
    """
    return rx.markdown(
        *args,
        component_map={
            "h1": lambda text: h1_comp_xd(text=text),
            "h2": lambda text: h2_comp_xd(text=text),
            "h3": lambda text: h3_comp_xd(text=text),
            "h4": lambda text: h4_comp_xd(text=text),
            "p": lambda text: text_comp(text=text),
            "li": lambda text: list_comp(text=text),
            "a": doclink2,
            "pre": markdown_codeblock,
            "img": lambda src: img_comp_xd(src=src),
        },
        **kwargs,
    )
