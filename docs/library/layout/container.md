---
components:
  - rx.container
---

```python exec
import reflex as rx
```

# Container

Constrains the maximum width of page content, while keeping flexible margins
for responsive layouts.

A Container is generally used to wrap the main content for a page.

## Basic Example

```python demo
rx.box(
    rx.container(
        rx.card("This content is constrained to a max width of 448px.", width="100%"),
        size="1",
    ),
    rx.container(
        rx.card("This content is constrained to a max width of 688px.", width="100%"),
        size="2",
    ),
    rx.container(
        rx.card("This content is constrained to a max width of 880px.", width="100%"),
        size="3",
    ),
    rx.container(
        rx.card("This content is constrained to a max width of 1136px.", width="100%"),
        size="4",
    ),
    background_color="var(--gray-3)",
    width="100%",
)
```

```python test
def test_container_max_widths(demo):
    inners = demo.locator(".rt-ContainerInner")
    expect(inners).to_have_count(4)
    for i, px in enumerate(["448px", "688px", "880px", "1136px"]):
        expect(inners.nth(i)).to_have_css("max-width", px)
        expect(inners.nth(i)).to_have_text(
            f"This content is constrained to a max width of {px}."
        )
```
