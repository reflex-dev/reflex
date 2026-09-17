---
tags: DevTools
description: Browse, compare, lock, and edit generated app files in the Code workspace.
---

# Code Workspace

```python exec
import reflex as rx
```

Open **Code** in an app to work directly with its generated source. Use it when you need more detail than Preview or the agent's summary provides.

## Find and inspect files

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/code_workspace.webp",
    alt="The searchable file tree in the Code workspace",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

Use the file tree and search to find a path, then select it to open the editor. Changed-file indicators and diff counts show where a generation added, removed, or modified code. Open the diff view to compare the generated change before continuing.

The **Terminal** and **Debug** panels help you inspect the running app and diagnose failures. Git controls show the connected repository workflow when the app uses one.

## Edit files

Manual code editing is available on paid plans and requires edit access to the app:

1. Wait for the current generation to finish.
2. Open a file and make the change.
3. Select **Save**, or press `Cmd+S` on macOS or `Ctrl+S` on Windows and Linux.
4. Return to **Preview** and test the affected workflow.

Depending on your access, the file tree also lets you create, rename, delete, and upload files. These operations change the app source, so check the selected path before confirming them.

## Lock files

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/file_locking.webp",
    alt="The Lock file action in the Code workspace file tree",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

Lock a file when the agent must preserve your manual implementation during later generations. The agent skips locked files until you unlock them.

Use locks sparingly. A lock can prevent the agent from completing a change that depends on that file, so unlock it when the protected implementation no longer needs to be preserved.

For work outside Builder, connect a [Git repository](/docs/ai/features/connect-to-git-providers/) or [download the app](/docs/ai/app-lifecycle/download-app/). Avoid editing the same files in two places at once.

## Related

- [Code and Review](/docs/ai/features/editor-modes/) — choose between source-level work and annotated visual feedback.
- [Generation Controls & Collaboration](/docs/ai/features/generation-controls/) — understand app edit locks and concurrent work.
- [Files](/docs/ai/files/) — attach documents and structured data to a prompt.
