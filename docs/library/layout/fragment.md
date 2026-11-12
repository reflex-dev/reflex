---
components:
  - rx.fragment
---

# Fragment

```python exec
import reflex as rx
```

A Fragment is a Component that allow you to group multiple Components without a wrapper node.

Refer to the React docs at [React/Fragment](https://react.dev/reference/react/Fragment) for more information on its use-case.

```python demo
rx.fragment(rx.text("Component1"), rx.text("Component2"))
```

```python test
def test_fragment_adds_no_wrapper(demo):
    # Both texts are direct children of the demo preview, with no wrapper node.
    expect(demo.locator(".docs-demo-preview > p")).to_have_text([
        "Component1",
        "Component2",
    ])
```

```md video https://youtube.com/embed/ITOZkzjtjUA?start=3196&end=3340
# Video: Fragment
```
