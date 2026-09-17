# Code and Review

```python exec
import reflex as rx
```

Use **Review mode** to point out visual changes in the running app. Use **Code** to inspect or edit the generated source. After either workflow, return to **Preview** and test the affected behavior.

## Annotate the app in Review mode

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/review_mode.webp",
    alt="An annotation and comment ready to send from Review mode",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

Review mode turns comments drawn on the preview into a prompt for the agent:

1. At desktop width, let the current generation finish, then open the affected route in **Preview**.
2. Select **Review mode** and wait for the captured page to load.
3. Draw around the area you want to change and add a concise comment.
4. Add more annotations on the same route, or switch routes and annotate those pages.
5. Select **Send review** to send the annotations and marked screenshots to the agent.

Each comment should say what is wrong and what the result should be. Use a normal chat prompt instead when the feedback is not tied to a specific part of the interface.

You need edit access to send a review. If another session is generating or holds the app's edit lock, wait until it finishes.

## Inspect or edit the source in Code

Open **Code** to browse and search the app's files, inspect generated diffs, or make a precise manual edit. The workspace also provides Git controls and **Terminal** and **Debug** panels.

Your plan and app access determine whether the editor is writable. See [Code Workspace](/docs/ai/features/file-tree/) for editing, file operations, diffs, and file locking.

## Choose the right workflow

- Use **Review mode** for feedback such as spacing, alignment, missing states, or a change to one visible component.
- Use **Code** when you need to understand the implementation, inspect a diff, or make a small source-level change.
- Use **Preview** after every meaningful change to test the actual workflow, including loading, empty, error, validation, and responsive states.

## Related

- [Generation Controls & Collaboration](/docs/ai/features/generation-controls/) — guide work without overlapping requests.
- [Planning](/docs/ai/features/planning/) — review the intended work before and during generation.
- [Testing](/docs/ai/features/automated-testing/) — verify the resulting behavior.
- [Restore Checkpoint](/docs/ai/features/restore-checkpoint/) — return the app to an earlier generated state.
