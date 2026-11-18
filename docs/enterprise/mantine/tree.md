---
title: Tree
---

# Tree component

`rxe.mantine.tree` is a component for displaying hierarchical data in a tree structure. It allows users to expand and collapse nodes, making it easy to navigate through large datasets.

```md alert warning
# Due to some technical limitations(pydantic), the tree component only supports 5 levels of depths for the `data` props.
```

```python demo exec
import reflex as rx
import reflex_enterprise as rxe


def tree_example():
    # return rx.text("Placeholder for tree example")
    return rxe.mantine.tree(
        data=[
            {
                "value": "0",
                "label": "Root",
                "children": [
                    {"value": "0-1", "label": "Child 1"},
                    {"value": "0-2", "label": "Child 2"},
                ],
            }
        ],
    )
```

```python test
def test_expand_root_node(demo):
    root = demo.get_by_role("treeitem", name="Root")
    expect(demo.get_by_role("treeitem", name="Child 1")).to_be_hidden()
    root.click()
    expect(demo.get_by_role("treeitem")).to_have_text([
        re.compile("^Root"),
        "Child 1",
        "Child 2",
    ])
```
