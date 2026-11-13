---
components:
  - rx.text.em
---

```python exec
import reflex as rx
```

# Em (Emphasis)

Marks text to stress emphasis.

```python demo
rx.text("We ", rx.text.em("had"), " to do something about it.")
```

```python test
def test_em_emphasizes_word(demo):
    expect(demo.get_by_text("We had to do something about it.")).to_be_visible()
    em = demo.locator("em")
    expect(em).to_have_text("had")
    expect(em).to_have_css("font-style", "italic")
```
