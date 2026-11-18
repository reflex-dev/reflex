---
components:
  - rx.text.quote
---

```python exec
import reflex as rx
```

# Quote

A short inline quotation.

```python demo
rx.text(
    "His famous quote, ",
    rx.text.quote("Styles come and go. Good design is a language, not a style"),
    ", elegantly sums up Massimo’s philosophy of design.",
)
```

```python test
def test_inline_quote(demo):
    expect(demo.locator("p")).to_have_text(
        "His famous quote, Styles come and go. Good design is a language, not a style,"
        " elegantly sums up Massimo’s philosophy of design."
    )
    expect(demo.locator("q")).to_have_text(
        "Styles come and go. Good design is a language, not a style"
    )
```
