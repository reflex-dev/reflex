---
title: Spoiler
---

# Spoiler component

`rxe.mantine.spoiler` is a component that allows you to hide or reveal content. It is useful for displaying additional information or details that may not be immediately relevant to the user.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def spoiler_example():
    return rx.vstack(
        rxe.mantine.spoiler(
            "This is a spoiler zone where lorem ipsum text dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit...",
            max_height=50,
            show_label="Show more",
            hide_label="Show less",
        ),
    )
```
