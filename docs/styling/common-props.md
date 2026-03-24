# Style and Layout Props

```python exec
import reflex as rx
from pcweb.styles.styles import get_code_style, cell_style
from pcweb.styles.colors import c_color

props = {
    "align": {
        "description": "In a flex, it controls the alignment of items on the cross axis and in a grid layout, it controls the alignment of items on the block axis within their grid area (equivalent to align_items)",
        "values": ["stretch", "center", "start", "end", "flex-start", "baseline"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/align-items",
    },
    "backdrop_filter": {
        "description": "Lets you apply graphical effects such as blurring or color shifting to the area behind an element",
        "values": ["url(commonfilters.svg#filter)", "blur(2px)", "hue-rotate(120deg)", "drop-shadow(4px 4px 10px blue)"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter",
    },
    "background": {
        "description": "Sets all background style properties at once, such as color, image, origin and size, or repeat method (equivalent to bg)",
        "values": ["green", "radial-gradient(crimson, skyblue)", "no-repeat url('../lizard.png')"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/background",
    },
    "background_color": {
        "description": "Sets the background color of an element",
        "values": ["brown", "rgb(255, 255, 128)", "#7499ee"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/background-color",
    },
    "background_image": {
        "description": "Sets one or more background images on an element",
        "values": ["url('../lizard.png')", "linear-gradient(#e66465, #9198e5)"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/background-image",
    },
    "border": {
        "description": "Sets an element's border, which sets the values of border_width, border_style, and border_color.",
        "values": ["solid", "dashed red", "thick double #32a1ce", "4mm ridge rgba(211, 220, 50, .6)"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/border",
    },
    "border_top / border_bottom / border_right / border_left": {
        "description": "Sets an element's top / bottom / right / left border. It sets the values of border-(top / bottom / right / left)-width, border-(top / bottom / right / left)-style and border-(top / bottom / right / left)-color",
        "values": ["solid", "dashed red", "thick double #32a1ce", "4mm ridge rgba(211, 220, 50, .6)"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/border-bottom",
    },
    "border_color": {
        "description": "Sets the color of an element's border (each side can be set individually using border_top_color, border_right_color, border_bottom_color, and border_left_color)",
        "values": ["red", "red #32a1ce", "red rgba(170, 50, 220, .6) green", "red yellow green transparent"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/border-color",
    },
    "border_radius": {
        "description": "Rounds the corners of an element's outer border edge and you can set a single radius to make circular corners, or two radii to make elliptical corners",
        "values": ["30px", "25% 10%", "10% 30% 50% 70%", "10% / 50%"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/border-radius",
    },
    "border_width": {
        "description": "Sets the width of an element's border",
        "values": ["thick", "1em", "4px 1.25em", "0 4px 8px 12px"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/border-width",
    },
    "box_shadow": {
        "description": "Adds shadow effects around an element's frame. You can set multiple effects separated by commas. A box shadow is described by X and Y offsets relative to the element, blur and spread radius, and color",
        "values": ["10px 5px 5px red", "60px -16px teal", "12px 12px 2px 1px rgba(0, 0, 255, .2)", "3px 3px red, -1em 0 .4em olive;"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/box-shadow",
    },

    "color": {
        "description": "Sets the foreground color value of an element's text",
        "values": ["rebeccapurple", "rgb(255, 255, 128)", "#00a400"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/color",
    },
    "display": {
        "description": "Sets whether an element is treated as a block or inline box and the layout used for its children, such as flow layout, grid or flex",
        "values": ["block", "inline", "inline-block", "flex", "inline-flex", "grid", "inline-grid", "flow-root"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/display",
    },
    "flex_grow": {
        "description": " Sets the flex grow factor, which specifies how much of the flex container's remaining space should be assigned to the flex item's main size",
        "values": ["1", "2", "3"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/flex-grow",
    },
    "height": {
        "description": "Sets an element's height",
        "values": ["150px", "20em", "75%", "auto"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/height",
    },
    "justify": {
        "description": "Defines how the browser distributes space between and around content items along the main-axis of a flex container, and the inline axis of a grid container (equivalent to justify_content)",
        "values": ["start", "center", "flex-start", "space-between", "space-around", "space-evenly", "stretch"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/justify-content",
    },
    "margin": {
        "description": "Sets the margin area (creates extra space around an element) on all four sides of an element",
        "values": ["1em", "5% 0", "10px 50px 20px", "10px 50px 20px 0"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/margin",
    },
    "margin_x / margin_y": {
        "description": "Sets the margin area (creates extra space around an element) along the x-axis / y-axis and a positive value places it farther from its neighbors, while a negative value places it closer",
        "values": ["1em", "10%", "10px"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/margin",
    },
    "margin_top / margin_right / margin_bottom / margin_left ": {
        "description": "Sets the margin area (creates extra space around an element) on the top / right / bottom / left of an element",
        "values": ["1em", "10%", "10px"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/margin-top",
    },
    "max_height / min_height": {
        "description": "Sets the maximum / minimum height of an element and prevents the used value of the height property from becoming larger / smaller than the value specified for max_height / min_height",
        "values": ["150px", "7em", "75%"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/max-height",
    },
    "max_width / min_width": {
        "description": "Sets the maximum / minimum width of an element and prevents the used value of the width property from becoming larger / smaller than the value specified for max_width / min_width",
        "values": ["150px", "20em", "75%"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/max-width",
    },
    "padding": {
        "description": "Sets the padding area (creates extra space within an element) on all four sides of an element at once",
        "values": ["1em", "10px 50px 30px 0", "0", "10px 50px 20px"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/padding",
    },
    "padding_x / padding_y": {
        "description": "Creates extra space within an element along the x-axis / y-axis",
        "values": ["1em", "10%", "10px"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/padding",
    },
    "padding_top / padding_right / padding_bottom / padding_left ": {
        "description": "Sets the height of the padding area on the top / right / bottom / left of an element",
        "values": ["1em", "10%", "20px"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/padding-top",
    },
    "position": {
        "description": "Sets how an element is positioned in a document and the top, right, bottom, and left properties determine the final location of positioned elements",
        "values": ["static", "relative", "absolute", "fixed", "sticky"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/position",
    },
    "text_align": {
        "description": "Sets the horizontal alignment of the inline-level content inside a block element or table-cell box",
        "values": ["start", "end", "center", "justify", "left", "right"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/text-align",
    },
    "text_wrap": {
        "description": "Controls how text inside an element is wrapped",
        "values": ["wrap", "nowrap", "balance", "pretty"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/text-wrap",
    },
    "top / bottom / right / left": {
        "description": "Sets the vertical / horizontal position of a positioned element. It does not effect non-positioned elements.",
        "values": ["0", "4em", "10%", "20px"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/top",
    },
    "width": {
        "description": "Sets an element's width",
        "values": ["150px", "20em", "75%", "auto"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/width",
    },
    "white_space": {
        "description": "Sets how white space inside an element is handled",
        "values": ["normal", "nowrap", "pre", "break-spaces"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/white-space",
    },
    "word_break": {
        "description": "Sets whether line breaks appear wherever the text would otherwise overflow its content box",
        "values": ["normal", "break-all", "keep-all", "break-word"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/word-break",
    },
    "z_index": {
        "description": "Sets the z-order of a positioned element and its descendants or flex and grid items, and overlapping elements with a larger z-index cover those with a smaller one",
        "values": ["auto", "1", "5", "200"],
        "link": "https://developer.mozilla.org/en-US/docs/Web/CSS/z-index",
    },
    

}


def show_props(key, props_dict):
    prop_details = props_dict[key]
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.hstack(
                    rx.code(key, style=get_code_style("violet")),
                    rx.icon("square_arrow_out_up_right", color=c_color("slate", 9), size=15, flex_shrink="0"),
                    align="center"
                ),
                href=prop_details["link"],
                is_external=True,
            ), 
            justify="start",),
        rx.table.cell(prop_details["description"], justify="start", style=cell_style),
        rx.table.cell(rx.hstack(*[rx.code(value, style=get_code_style("violet")) for value in prop_details["values"]], flex_wrap="wrap"), justify="start",),
        justify="center",
        align="center",
        
    )

```

Any [CSS](https://developer.mozilla.org/en-US/docs/Web/CSS) prop can be used in a component in Reflex. This is a short list of the most commonly used props. To see all CSS props that can be used check out this [documentation](https://developer.mozilla.org/en-US/docs/Web/CSS). 

Hyphens in CSS property names may be replaced by underscores to use as valid python identifiers, i.e. the CSS prop `z-index` would be used as `z_index` in Reflex.

```python eval
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell(
                "Prop", justify="center"
            ),
            rx.table.column_header_cell(
                "Description",
                justify="center",
                
            ),
            rx.table.column_header_cell(
                "Potential Values",
                justify="center",
            ),
        )
    ),
    rx.table.body(
        *[show_props(key, props) for key in props]
    ),
    width="100%",
    padding_x="0",
    size="1",
)
```