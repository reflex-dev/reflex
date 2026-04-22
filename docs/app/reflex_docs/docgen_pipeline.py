"""Pipeline for rendering reflex-shipped docs via reflex_docgen.markdown."""

import sys
import types
from pathlib import Path

import reflex as rx
from reflex_base.constants.colors import ColorType
from reflex_docgen.markdown import (
    Block,
    CodeBlock,
    DirectiveBlock,
    Document,
    HeadingBlock,
    ListBlock,
    QuoteBlock,
    TableBlock,
    TextBlock,
    ThematicBreakBlock,
    parse_document,
)
from reflex_docgen.markdown._types import (
    BoldSpan,
    CodeSpan,
    FrontMatter,
    ImageSpan,
    ItalicSpan,
    LineBreakSpan,
    LinkSpan,
    ListItem,
    Span,
    StrikethroughSpan,
    TableCell,
    TableRow,
    TextSpan,
)
from reflex_docgen.markdown.transformer import DocumentTransformer
from reflex_site_shared.components.blocks.code import code_block
from reflex_site_shared.components.blocks.collapsible import collapsible_box
from reflex_site_shared.components.blocks.demo import docdemo, docdemobox, docgraphing
from reflex_site_shared.components.blocks.headings import (
    h1_comp_xd,
    h2_comp_xd,
    h3_comp_xd,
    h4_comp_xd,
    img_comp_xd,
)
from reflex_site_shared.components.blocks.typography import (
    code_comp,
    doclink2,
    list_comp,
    text_comp,
)
from reflex_site_shared.constants import REFLEX_ASSETS_CDN

# ---------------------------------------------------------------------------
# Exec environment — mirrors reflex_docgen's module-based exec mechanism
# ---------------------------------------------------------------------------

# One in-memory module per file — all exec blocks within a doc accumulate
# into the same namespace, so later definitions shadow earlier ones cleanly.
_file_modules: dict[str, types.ModuleType] = {}
_executed_blocks: set[tuple[str, str]] = set()

# Register the parent package so pickle can resolve child modules.
_PARENT_PKG = "_docgen_exec"
if _PARENT_PKG not in sys.modules:
    _pkg = types.ModuleType(_PARENT_PKG)
    _pkg.__path__ = []  # package needs __path__ for submodule imports
    _pkg.__package__ = _PARENT_PKG
    sys.modules[_PARENT_PKG] = _pkg


def _make_module_name(filename: str) -> str:
    """Create a valid Python module name from a filepath."""
    import re

    slug = re.sub(r"[^a-zA-Z0-9]", "_", filename)
    return f"{_PARENT_PKG}.{slug}"


def _last_defined_name(content: str) -> str | None:
    """Return the name of the last top-level definition in *content*.

    Considers functions, async functions, classes, and simple/annotated
    assignments with a value.

    Args:
        content: A string of Python source code.

    Returns:
        The name of the last top-level definition, or None if there are none.
    """
    import ast

    last: str | None = None
    for node in ast.parse(content).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            last = node.name
        elif isinstance(node, ast.Assign):
            target = node.targets[0]
            if isinstance(target, ast.Name):
                last = target.id
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.target, ast.Name)
        ):
            last = node.target.id
    return last


def _exec_code(content: str, env: dict, filename: str) -> None:
    """Execute a ``python exec`` code block via an in-memory module.

    All exec blocks within the same file share one module so that State
    subclass redefinitions shadow correctly.  When the same block is
    encountered a second time (e.g. the frontend is evaluated twice —
    once for compilation and once on the backend), skip re-execution and
    just populate *env* from the cached module namespace.
    """
    key = (filename, content)
    if key in _executed_blocks:
        env.update(_file_modules[filename].__dict__)
        return

    if filename not in _file_modules:
        mod_name = _make_module_name(filename)
        module = types.ModuleType(mod_name)
        module.__package__ = _PARENT_PKG
        sys.modules[mod_name] = module
        setattr(sys.modules[_PARENT_PKG], mod_name.split(".")[-1], module)
        _file_modules[filename] = module

    module = _file_modules[filename]
    module.__dict__.update(env)

    exec(compile(content, filename or "<docgen-exec>", "exec"), module.__dict__)

    env.update(module.__dict__)
    _executed_blocks.add(key)


# ---------------------------------------------------------------------------
# Span → rx.Component helpers
# ---------------------------------------------------------------------------


def _render_spans(spans: tuple[Span, ...]) -> list[rx.Component | str]:
    """Convert a sequence of spans into a list of Reflex children."""
    out: list[rx.Component | str] = []
    for span in spans:
        match span:
            case TextSpan(text=text):
                out.append(text)
            case BoldSpan(children=children):
                out.append(rx.el.strong(*_render_spans(children)))
            case ItalicSpan(children=children):
                out.append(rx.el.em(*_render_spans(children)))
            case StrikethroughSpan(children=children):
                inner = "".join(
                    c if isinstance(c, str) else "" for c in _render_spans(children)
                )
                out.append(rx.text("~" + inner + "~", as_="span"))
            case CodeSpan(code=code):
                out.append(code_comp(text=code))
            case LinkSpan(children=children, target=target):
                inner = "".join(
                    c if isinstance(c, str) else "" for c in _render_spans(children)
                )
                out.append(doclink2(text=inner, href=target))
            case ImageSpan(src=src):
                out.append(img_comp_xd(src=src))
            case LineBreakSpan(soft=soft):
                out.append("\n" if soft else rx.el.br())
    return out


def _spans_to_plaintext(spans: tuple[Span, ...]) -> str:
    """Extract plain text from spans (for headings, etc.)."""
    parts: list[str] = []
    for span in spans:
        match span:
            case TextSpan(text=text):
                parts.append(text)
            case (
                BoldSpan(children=children)
                | ItalicSpan(children=children)
                | StrikethroughSpan(children=children)
                | LinkSpan(children=children)
            ):
                parts.append(_spans_to_plaintext(children))
            case CodeSpan(code=code):
                parts.append(code)
            case _:
                pass
    return "".join(parts)


# ---------------------------------------------------------------------------
# ReflexDocTransformer
# ---------------------------------------------------------------------------


class ReflexDocTransformer(DocumentTransformer[rx.Component]):
    """Transforms a reflex_docgen Document into Reflex components.

    Mirrors the rendering that the reflex_docgen pipeline produces, so docs from
    the parent docs directory look identical to the locally-authored ones.
    """

    def __init__(self, virtual_filepath: str = "", filename: str = "") -> None:
        self.virtual_filepath = virtual_filepath
        self.filename = filename
        self.env: dict = {}

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def transform(self, document: Document) -> rx.Component:
        if document.frontmatter is not None:
            # Populate env with component preview metadata.
            for preview in document.frontmatter.component_previews:
                self.env[preview.name] = preview.source
            self.env["REFLEX_ASSETS_CDN"] = REFLEX_ASSETS_CDN

        children: list[rx.Component] = []
        for block in document.blocks:
            comp = self.transform_block(block)
            if comp is not None:
                children.append(comp)

        return rx.fragment(*children)

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------

    def frontmatter(self, block: FrontMatter) -> rx.Component:
        return rx.fragment()

    def heading(self, block: HeadingBlock) -> rx.Component:
        text = _spans_to_plaintext(block.children)
        match block.level:
            case 1:
                return h1_comp_xd(text=text)
            case 2:
                return h2_comp_xd(text=text)
            case 3:
                return h3_comp_xd(text=text)
            case _:
                return h4_comp_xd(text=text)

    def text_block(self, block: TextBlock) -> rx.Component:
        children = _render_spans(block.children)
        if len(children) == 1 and isinstance(children[0], str):
            return text_comp(text=children[0])
        return rx.text(
            *children,
            class_name="font-[475] text-secondary-11 mb-4 leading-7",
        )

    def code_block(self, block: CodeBlock) -> rx.Component:
        flags = set(block.flags)
        language = block.language or "plain"

        # ``python demo`` or ``python demo exec``
        if language == "python" and "demo" in flags:
            return self._render_demo(block.content, flags)

        # ``python demo-only`` or ``python demo-only exec``
        if language == "python" and "demo-only" in flags:
            return self._render_demo_only(block.content, flags)

        # ``python exec`` only — execute code, produce nothing visible.
        if language == "python" and "exec" in flags:
            _exec_code(block.content, self.env, self.virtual_filepath)
            return rx.fragment()

        # ``python eval`` (standalone) — eval and return the component directly.
        if language == "python" and "eval" in flags:
            return eval(block.content, self.env, self.env)

        # Regular code block (includes unknown flags like ``python box``).

        return code_block(code=block.content, language=language)

    def directive(self, block: DirectiveBlock) -> rx.Component:
        """Handle ```md <directive>``` blocks (alert, video, etc.)."""
        match block.name:
            case "alert":
                return self._render_alert(block)
            case "video":
                return self._render_video(block)
            case "quote":
                return self._render_quote_directive(block)
            case "tabs":
                return self._render_tabs(block)
            case "definition":
                return self._render_definition(block)
            case "section":
                return self._render_section(block)
            case _:
                return self._render_children(block.children)

    def list_block(self, block: ListBlock) -> rx.Component:
        items = [self.transform_list_item(item) for item in block.items]
        if block.ordered:
            return rx.list.ordered(*items, class_name="mb-6")
        return rx.list.unordered(*items, class_name="mb-6")

    @staticmethod
    def _list_item_from_spans(spans: tuple[Span, ...]) -> rx.Component:
        """Render a list item, preserving inline code/links when present."""
        if all(isinstance(s, TextSpan) for s in spans):
            return list_comp(text=_spans_to_plaintext(spans))
        return rx.list_item(
            *_render_spans(spans),
            class_name="font-[475] text-secondary-11 mb-4",
        )

    def transform_list_item(self, item: ListItem) -> rx.Component:
        children: list[rx.Component] = []
        for child_block in item.children:
            match child_block:
                case TextBlock(children=spans):
                    children.append(self._list_item_from_spans(spans))
                case _:
                    children.append(self.transform_block(child_block))
        if len(children) == 1:
            return children[0]
        return rx.fragment(*children)

    def quote(self, block: QuoteBlock) -> rx.Component:
        children = [self.transform_block(b) for b in block.children]
        return rx.box(
            *children,
            class_name="border-l-[3px] border-slate-4 pl-6 mt-2 mb-6",
        )

    def table(self, block: TableBlock) -> rx.Component:
        header_cells = [
            rx.table.column_header_cell(
                *_render_spans(cell.children),
                class_name="font-small text-slate-12 font-bold",
            )
            for cell in block.header.cells
        ]
        rows = []
        for row in block.rows:
            cells = [
                rx.table.cell(
                    *_render_spans(cell.children),
                    class_name="font-small text-slate-11",
                )
                for cell in row.cells
            ]
            rows.append(rx.table.row(*cells))

        return rx.table.root(
            rx.table.header(rx.table.row(*header_cells)),
            rx.table.body(*rows),
            variant="surface",
            size="1",
            class_name="w-full border border-slate-4 mb-4",
        )

    def transform_table_row(self, row: TableRow) -> rx.Component:
        cells = [self.transform_table_cell(cell) for cell in row.cells]
        return rx.table.row(*cells)

    def transform_table_cell(self, cell: TableCell) -> rx.Component:
        return rx.table.cell(*_render_spans(cell.children))

    def thematic_break(self, block: ThematicBreakBlock) -> rx.Component:
        return rx.separator(class_name="my-6")

    # ------------------------------------------------------------------
    # Spans (not used directly by DocumentTransformer dispatch, but
    # kept for completeness if someone calls transform_span)
    # ------------------------------------------------------------------

    def text_span(self, span: TextSpan) -> rx.Component:
        return rx.text(span.text, as_="span")

    def bold(self, span: BoldSpan) -> rx.Component:
        return rx.el.strong(*self.transform_spans(span.children))

    def italic(self, span: ItalicSpan) -> rx.Component:
        return rx.el.em(*self.transform_spans(span.children))

    def strikethrough(self, span: StrikethroughSpan) -> rx.Component:
        return rx.text("~", *self.transform_spans(span.children), "~", as_="span")

    def code_span(self, span: CodeSpan) -> rx.Component:
        return code_comp(text=span.code)

    def link(self, span: LinkSpan) -> rx.Component:
        inner = _spans_to_plaintext(span.children)
        return doclink2(text=inner, href=span.target)

    def image(self, span: ImageSpan) -> rx.Component:
        return img_comp_xd(src=span.src)

    def line_break(self, span: LineBreakSpan) -> rx.Component:
        return rx.fragment()

    # ------------------------------------------------------------------
    # Demo / exec helpers
    # ------------------------------------------------------------------

    def _exec_and_get_last_callable(self, content: str):
        """Run _exec_code and return the last callable defined by the block."""
        _exec_code(content, self.env, self.virtual_filepath)
        last_name = _last_defined_name(content)
        if last_name is None:
            msg = "Exec block defines no function or class"
            raise RuntimeError(msg)
        last = self.env[last_name]
        if not callable(last):
            msg = f"Last defined name {last_name!r} is not callable"
            raise TypeError(msg)
        return last()

    def _render_demo(self, content: str, flags: set[str]) -> rx.Component:
        """Render a ``python demo`` block — code + live component."""
        comp_id = None
        for flag in flags:
            if flag.startswith("id="):
                comp_id = flag.split("=", 1)[1]

        try:
            if "exec" in flags:
                comp = self._exec_and_get_last_callable(content)
            elif "graphing" in flags:
                comp = self._exec_and_get_last_callable(content)
                parts = content.rpartition("def")
                data, code = parts[0], parts[1] + parts[2]
                return docgraphing(code, comp=comp, data=data)
            elif "box" in flags:
                comp = eval(content, self.env, self.env)
                return rx.box(docdemobox(comp), margin_bottom="1em", id=comp_id)
            else:
                comp = eval(content, self.env, self.env)
        except Exception as e:
            e.add_note(
                f"While rendering demo block in {self.virtual_filepath}:\n{content[:200]}"
            )
            raise

        demobox_props: dict = {}
        for flag in flags:
            k, sep, v = flag.partition("=")
            if sep:
                demobox_props[k] = v
        if "toggle" in flags:
            demobox_props["toggle"] = True

        return docdemo(content, comp=comp, demobox_props=demobox_props, id=comp_id)

    def _render_demo_only(self, content: str, flags: set[str]) -> rx.Component:
        """Render a ``python demo-only`` block — component only, no code."""
        comp_id = None
        for flag in flags:
            if flag.startswith("id="):
                comp_id = flag.split("=", 1)[1]

        try:
            if "exec" in flags:
                comp = self._exec_and_get_last_callable(content)
            elif "graphing" in flags:
                comp = self._exec_and_get_last_callable(content)
                parts = content.rpartition("def")
                data, code = parts[0], parts[1] + parts[2]
                return docgraphing(code, comp=comp, data=data)
            elif "box" in flags:
                comp = eval(content, self.env, self.env)
            else:
                comp = eval(content, self.env, self.env)
        except Exception as e:
            e.add_note(
                f"While rendering demo-only block in {self.virtual_filepath}:\n{content[:200]}"
            )
            raise

        return rx.box(comp, margin_bottom="1em", id=comp_id)

    def _render_children(self, blocks: tuple[Block, ...]) -> rx.Component:
        """Render a sequence of parsed blocks into a single component."""
        rendered = [self.transform_block(b) for b in blocks]
        return rx.fragment(*rendered) if len(rendered) != 1 else rendered[0]

    def _split_children_by_heading(
        self, blocks: tuple[Block, ...]
    ) -> list[tuple[str, tuple[Block, ...]]]:
        """Split directive children into (title, blocks) by top-level headings.

        Only headings matching the level of the first heading are used as
        section delimiters — deeper headings stay inside their section.
        """
        split_level: int | None = None
        sections: list[tuple[str, list[Block]]] = []
        for child in blocks:
            if isinstance(child, HeadingBlock):
                if split_level is None:
                    split_level = child.level
                if child.level == split_level:
                    sections.append((_spans_to_plaintext(child.children), []))
                    continue
            if sections:
                sections[-1][1].append(child)
        return [(title, tuple(body)) for title, body in sections]

    def _render_alert(self, block: DirectiveBlock) -> rx.Component:
        """Render a ``md alert`` directive."""
        status = block.args[0] if block.args else "info"
        colors: dict[str, ColorType] = {
            "info": "accent",
            "success": "grass",
            "warning": "amber",
            "error": "red",
        }
        color: ColorType = colors.get(status, "blue")

        # First child may be a heading used as the alert title.
        children = block.children
        title_spans: tuple[Span, ...] = ()
        if children and isinstance(children[0], HeadingBlock):
            title_spans = children[0].children
            children = children[1:]

        icon_map = {
            "info": "info",
            "success": "circle_check",
            "warning": "triangle_alert",
            "error": "ban",
        }
        icon_tag = icon_map.get(status, "info")

        def title_comp() -> rx.Component:
            return rx.box(
                *_render_spans(title_spans),
                class_name="font-[475]",
                color=f"{rx.color(color, 11)}",
            )

        trigger: list[rx.Component] = [
            rx.box(
                rx.icon(tag=icon_tag, size=18, margin_right=".5em"),
                color=f"{rx.color(color, 11)}",
            ),
        ]

        if children and title_spans:
            # Has heading + body — render as collapsible accordion.
            trigger.append(title_comp())
            body = rx.accordion.content(
                self._render_children(children),
                padding="0px",
                margin_top="16px",
            )
            return collapsible_box(trigger, body, color)

        # Title only, or text-only (no heading) — simple non-collapsible box.
        if title_spans:
            trigger.append(title_comp())
        elif children:
            # Render inline spans directly — avoid text_block's mb-4 margin.
            spans: list[rx.Component | str] = []
            for child in children:
                if isinstance(child, TextBlock):
                    spans.extend(_render_spans(child.children))
                else:
                    spans.append(self.transform_block(child))
            trigger.append(
                rx.box(
                    *spans,
                    class_name="font-[475]",
                    color=f"{rx.color(color, 11)}",
                ),
            )
        return rx.vstack(
            rx.hstack(
                *trigger,
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

    def _render_video(self, block: DirectiveBlock) -> rx.Component:
        """Render a ``md video`` directive — accordion-wrapped."""
        url = block.args[0] if block.args else ""
        # First child heading is the video title.
        children = block.children
        title = "Video Description"
        if children and isinstance(children[0], HeadingBlock):
            title = _spans_to_plaintext(children[0].children)

        color: ColorType = "blue"
        trigger = [
            rx.text(title, class_name="font-[475]", color=f"{rx.color(color, 11)}"),
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

    def _render_quote_directive(self, block: DirectiveBlock) -> rx.Component:
        """Render a ``md quote`` directive."""
        quote_parts: list[rx.Component | str] = []
        name = ""
        role = ""
        for child in block.children:
            if isinstance(child, TextBlock):
                quote_parts.extend(_render_spans(child.children))
            elif isinstance(child, ListBlock):
                for item in child.items:
                    for sub in item.children:
                        if isinstance(sub, TextBlock):
                            text = _spans_to_plaintext(sub.children)
                            if text.startswith("name:"):
                                name = text.split(":", 1)[1].strip()
                            elif text.startswith("role:"):
                                role = text.split(":", 1)[1].strip()

        return rx.box(
            rx.text(
                '"',
                *quote_parts,
                '"',
                class_name="text-slate-11 font-base italic",
            ),
            rx.box(
                rx.text(name, class_name="text-slate-11 font-base"),
                rx.text(role, class_name="text-slate-10 font-base"),
                class_name="flex flex-col gap-0.5",
            ),
            class_name="flex flex-col gap-4 border-l-[3px] border-slate-4 pl-6 mt-2 mb-6",
        )

    def _render_tabs(self, block: DirectiveBlock) -> rx.Component:
        """Render a ``md tabs`` directive. Sections split by ``##`` headings."""
        sections = self._split_children_by_heading(block.children)
        triggers = []
        contents = []
        for i, (title, body_blocks) in enumerate(sections):
            value = f"tab{i + 1}"
            triggers.append(
                rx.tabs.trigger(
                    title,
                    value=value,
                    class_name="tab-style font-base font-semibold text-[1.25rem]",
                )
            )
            contents.append(
                rx.tabs.content(self._render_children(body_blocks), value=value),
            )

        return rx.tabs.root(
            rx.tabs.list(*triggers, class_name="mt-4"),
            *contents,
            default_value="tab1",
        )

    def _render_definition(self, block: DirectiveBlock) -> rx.Component:
        """Render a ``md definition`` directive."""
        from reflex_site_shared.components.blocks.typography import definition

        sections = self._split_children_by_heading(block.children)
        defs = [
            definition(title, self._render_children(body)) for title, body in sections
        ]
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

    def _render_section(self, block: DirectiveBlock) -> rx.Component:
        """Render a ``md section`` directive."""
        from reflex_site_shared.styles.colors import c_color

        sections = self._split_children_by_heading(block.children)
        return rx.box(
            rx.vstack(
                *[
                    rx.fragment(
                        rx.text(
                            rx.text.span(header, font_weight="bold"),
                            width="100%",
                        ),
                        rx.box(self._render_children(body), width="100%"),
                    )
                    for header, body in sections
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _parse_doc(filepath: str | Path) -> Document:
    source = Path(filepath).read_text(encoding="utf-8")
    return parse_document(source)


def render_docgen_document(
    virtual_filepath: str | Path, actual_filepath: str | Path
) -> rx.Component:
    """Parse and render a doc file from the reflex package using reflex_docgen."""
    doc = _parse_doc(actual_filepath)
    transformer = ReflexDocTransformer(
        virtual_filepath=str(virtual_filepath), filename=str(actual_filepath)
    )
    return transformer.transform(doc)


def get_docgen_toc(filepath: str | Path) -> list[tuple[int, str]]:
    """Extract TOC headings as (level, text) tuples — same format as reflex_docgen's get_toc."""
    doc = _parse_doc(filepath)
    return [(h.level, _spans_to_plaintext(h.children)) for h in doc.headings]


def render_markdown(text: str) -> rx.Component:
    """Render a plain markdown text string into Reflex components."""
    doc = parse_document(text)
    transformer = ReflexDocTransformer()
    return transformer.transform(doc)
