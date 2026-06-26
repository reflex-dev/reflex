---
tags: DevTools
description: Integrate with GitHub to automate workflows and interact with your code repositories.
---

# Connecting to Github

```python exec
import reflex as rx
```

The Github integration is important to make sure that you don't lose your progress. It also allows you to revert to previous versions of your app.


```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/connecting_to_github.avif",
        alt='Connecting a Reflex AI Builder app to GitHub',
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
)
```

The GitHub integration allows you to:

- Save your app progress
- Work on your code locally and push your local changes back to Reflex.Build


## Github Commit History

The commit history is a great way to see the changes that you have made to your app. You can also revert to previous versions of your app from here.

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/github_commit_history.avif",
        alt='GitHub commit history for a Reflex AI Builder app',
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
)
```

