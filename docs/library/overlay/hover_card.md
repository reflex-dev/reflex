---
components:
  - rx.hover_card.root
  - rx.hover_card.content
  - rx.hover_card.trigger
meta_description: "Display rich hover cards in Python with Reflex. rx.hover_card shows detailed content on hover, for link previews and custom layouts."

only_low_level:
  - True

HoverCardRoot: |
  lambda **props: rx.hover_card.root(
      rx.hover_card.trigger(
          rx.link("Hover over me"),
      ),
      rx.hover_card.content(
          rx.text("This is the tooltip content."),
      ),
      **props
  )

HoverCardContent: |
  lambda **props: rx.hover_card.root(
      rx.hover_card.trigger(
          rx.link("Hover over me"),
      ),
      rx.hover_card.content(
          rx.text("This is the tooltip content."),
          **props
      ),
  )
---

```python exec
import reflex as rx
```

# Hovercard

The `hover_card.root` contains all the parts of a hover card.

The `hover_card.trigger` wraps the link that will open the hover card.

The `hover_card.content` contains the content of the open hover card.

```python demo
rx.text(
    "Hover over the text to see the tooltip. ",
    rx.hover_card.root(
        rx.hover_card.trigger(
            rx.link("Hover over me", color_scheme="blue", underline="always"),
        ),
        rx.hover_card.content(
            rx.text("This is the hovercard content."),
        ),
    ),
)
```

```python test
def test_hover_card_shows_on_hover(demo, page):
    expect(demo.get_by_text("Hover over the text to see the tooltip.")).to_have_text(
        "Hover over the text to see the tooltip. Hover over me"
    )
    demo.get_by_role("link", name="Hover over me").hover()
    expect(page.get_by_text("This is the hovercard content.")).to_be_visible()
    page.mouse.move(0, 0)
    expect(page.get_by_text("This is the hovercard content.")).to_be_hidden()
```

```python demo
rx.text(
    "Hover over the text to see the tooltip. ",
    rx.hover_card.root(
        rx.hover_card.trigger(
            rx.link("Hover over me", color_scheme="blue", underline="always"),
        ),
        rx.hover_card.content(
            rx.grid(
                rx.inset(
                    side="left",
                    pr="current",
                    background="url('https://images.unsplash.com/5/unsplash-kitsune-4.jpg') center/cover",
                    height="full",
                ),
                rx.box(
                    rx.text_area(placeholder="Write a comment…", style={"height": 80}),
                    rx.flex(
                        rx.checkbox("Send to group"),
                        spacing="3",
                        margin_top="12px",
                        justify="between",
                    ),
                    padding_left="12px",
                ),
                columns="120px 1fr",
            ),
            style={"width": 360},
        ),
    ),
)
```

```python test
def test_hover_card_comment_form(demo, page):
    demo.get_by_role("link", name="Hover over me").hover()
    expect(page.get_by_placeholder("Write a comment…")).to_be_visible()
    expect(page.get_by_role("checkbox", name="Send to group")).not_to_be_checked()
```

## Events when the Hovercard opens or closes

The `on_open_change` event is called when the `open` state of the hovercard changes. It is used in conjunction with the `open` prop, which is passed to the event handler.

```python demo exec
class HovercardState(rx.State):
    num_opens: int = 0
    opened: bool = False

    @rx.event
    def count_opens(self, value: bool):
        self.opened = value
        self.num_opens += 1


def hovercard_example():
    return rx.flex(
        rx.heading(
            f"Number of times hovercard opened or closed: {HovercardState.num_opens}",
            as_="h2",
        ),
        rx.heading(f"Hovercard open: {HovercardState.opened}", as_="h2"),
        rx.text(
            "Hover over the text to see the hover card. ",
            rx.hover_card.root(
                rx.hover_card.trigger(
                    rx.link("Hover over me", color_scheme="blue", underline="always"),
                ),
                rx.hover_card.content(
                    rx.text("This is the tooltip content."),
                ),
                on_open_change=HovercardState.count_opens,
            ),
        ),
        direction="column",
        spacing="3",
    )
```

```python test
def test_hover_card_on_open_change_counts(demo, page):
    headings = demo.get_by_role("heading")
    expect(headings).to_have_text([
        "Number of times hovercard opened or closed: 0",
        "Hovercard open: false",
    ])
    demo.get_by_role("link", name="Hover over me").hover()
    expect(page.get_by_text("This is the tooltip content.")).to_be_visible()
    expect(headings).to_have_text([
        "Number of times hovercard opened or closed: 1",
        "Hovercard open: true",
    ])
    page.mouse.move(0, 0)
    expect(headings).to_have_text([
        "Number of times hovercard opened or closed: 2",
        "Hovercard open: false",
    ])
```
