---
tags: AI Builder
description: Guide an active Reflex Build generation and work safely with teammates.
---

# Generation Controls & Collaboration

Reflex Build lets you refine a request while the agent works and avoid overlapping changes from another session.

## Queue Follow-Up Instructions

You do not have to wait for the current generation to finish before adding context. Send another message while the agent is working to queue a follow-up instruction. The agent picks it up at its next step.

Use queued messages for small corrections or missing constraints:

```text
Keep the current desktop layout. Make the new table responsive below 768 px
and do not change the existing filters.
```

Avoid queueing several competing changes at once. If the direction has changed substantially, let the current step finish, review the result, and send one consolidated follow-up.

## Follow Generation Progress

The workspace shows the agent's current activity, including planning, web searches, workspace operations, tests, and generated screenshots. A screenshot includes the page route it represents, which helps distinguish results from multi-page apps.

You can continue browsing **Preview** and **Plan** while the work runs. Review the latest result before sending another broad request so you do not accidentally reverse a useful change.

## Work with Teammates

When an app is already being edited in another session, Reflex Build locks it against overlapping edits. Wait for the active generation to finish and the edit lock to clear before starting work in another session. Then, before starting a large generation:

1. Check whether someone else is editing the affected area.
2. Keep the request scoped to a clear workflow.
3. State what must remain unchanged.
4. Review the latest preview and test results before beginning another overlapping generation.

Project roles determine who can open, edit, and administer an app. See [Roles & Permissions](/docs/ai/organization/roles-and-permissions/).

## Related

- [Planning](/docs/ai/features/planning/) — review and adjust work before or during generation.
- [Code and Review](/docs/ai/features/editor-modes/) — inspect source changes or send annotated visual feedback.
- [Code Workspace](/docs/ai/features/file-tree/) — inspect, compare, lock, or edit generated files.
- [Restore Checkpoint](/docs/ai/features/restore-checkpoint/) — return the app to an earlier generated state.
