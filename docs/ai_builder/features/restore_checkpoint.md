# Restore Checkpoint

Restore a checkpoint to return the app source to the state produced by an earlier agent message.

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/restore_checkpoint.webp",
        alt="The Revert to this version action on an agent checkpoint",
        class_name="rounded-md h-auto mb-4",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

## Restore an earlier state

Agent messages that change the app create checkpoints:

1. Find the message that produced the state you want.
2. Select its restore icon.
3. Confirm the restore.
4. Check the result in **Preview** before continuing.

The conversation remains visible, but the app source returns to the selected checkpoint. Later code changes are removed from the current app state.

```md alert warning
# Check the restore point before confirming
A checkpoint restore cannot be undone from the restore dialog. Copy the app or save important work to Git before restoring when you may need the current state later.
```

## When to use a checkpoint

- Return to the last working version after a generation breaks a workflow.
- Try a different implementation from a known state.
- Remove a group of recent changes without reverting files one by one.

For version history shared outside the Builder conversation, connect the app to [GitHub](/docs/ai/features/connect-to-github/).
