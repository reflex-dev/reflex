---
components:
  - rx.text.strong
---

```python exec
import reflex as rx
```

# Strong

Marks text to signify strong importance.

```python demo
rx.text(
    "The most important thing to remember is, ", rx.text.strong("stay positive"), "."
)
```

```python test
def test_strong_marks_importance(demo):
    expect(demo.locator("p")).to_have_text(
        "The most important thing to remember is, stay positive."
    )
    strong = demo.locator("strong")
    expect(strong).to_have_text("stay positive")
    expect(strong).to_have_css("font-weight", "700")
```
