"""#7080: generated .pyi union props must type-check when left unset."""
import reflex as rx
import reflex_components_markdown as rxmd


def page() -> rx.Component:
    return rx.vstack(
        rx.el.div("hello", class_name="x"),
        rx.el.div(),
        rx.markdown("# hi"),
        rx.markdown("# hi", use_math=True, use_gfm=False),
        rx.markdown("# hi", use_math=None),
        rx.data_editor(columns=[], data=[]),
        rx.recharts.sankey_chart(data={"nodes": [], "links": []}),
        rx.recharts.line_chart(rx.recharts.line(data_key="v"), data=[]),
        rx.text("t"),
        rx.box(rx.text("inner")),
        rx.cond(True, rx.text("a"), rx.text("b")),
    )


app = rx.App()
app.add_page(page, route="/")
