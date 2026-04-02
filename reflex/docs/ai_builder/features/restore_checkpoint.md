# Restore Checkpoint

The **Restore Checkpoint** feature allows you to roll back your app to any previous state during your AI Builder conversation. This is useful when you want to undo recent changes and return to an earlier version of your app.

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/features/restore_light.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

## How It Works

Every time the AI agent makes changes to your app, a checkpoint is automatically created. You can restore to any of these checkpoints at any time, effectively undoing all changes made after that point.

## Using Restore Checkpoint

1. **Locate the Restore Icon**: At the end of each AI agent message that made changes to your app, you'll see a circular arrow icon (↻).

2. **Click to Restore**: Click the circular arrow icon next to the message you want to restore to.

3. **Confirm the Action**: The app will restore to the exact state it was in after that specific message was processed.

4. **Continue Building**: After restoring, you can continue the conversation and make new changes from that point.

## When to Use Restore Checkpoint

- **Undo Unwanted Changes**: When the AI made changes you don't like
- **Try Different Approaches**: Restore and ask the AI to implement a feature differently
- **Fix Broken Functionality**: Roll back when new changes break existing features
- **Experiment Safely**: Test different solutions knowing you can always restore to a checkpoint

## Important Notes

- Restoring will **permanently delete** all changes made after the selected message
- You cannot undo a restore operation - choose your restore point carefully
- The conversation history remains intact, but code changes after the restore point are lost
- Restore checkpoint only affects your current building session

> **Tip:** Before making major changes, note which message represents your last stable checkpoint so you can easily restore if needed.
