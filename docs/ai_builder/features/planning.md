# Planning

The **Plan** view turns a large prompt into an implementation plan that can be reviewed and adjusted while the agent works.

```python exec
import reflex as rx
```

## Choose When to Plan

The create screen and chat controls let you set **Plan first** to:

- **Auto** — the agent decides whether the request needs a plan.
- **Always** — create a plan before implementation.
- **Never** — start implementing without a separate plan.

Use a plan for work that affects several pages, integrations, or systems. Small, isolated edits usually do not need one.

## Review and Adjust the Plan

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/plan_mode.webp",
    alt="A populated implementation plan in Reflex Build",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

Open **Plan** in the app workspace to review the current sections and tasks. You can:

- Add or reorganize plan sections.
- Edit the plan before generation starts.
- Comment on plan items or ask the agent to revise them.
- Adjust the plan during generation; the agent picks up the latest changes.

For a multi-page or integration-heavy request, wait until the agent produces the plan. Confirm that each section describes a concrete outcome, dependencies appear in the right order, and validation is included before implementation begins. Keep manual edits focused so the plan remains useful as a progress record.

## Move Between Plan and Implementation

You can keep the **Plan** view open while generation runs and move back to **Preview** without discarding the plan. When you revise a plan during generation, make the change explicit in chat as well so the agent can reconcile the latest instruction with work already in progress.

After implementation, compare the finished result in **Preview** with the plan. Send focused feedback for any task or visual detail that still needs work.
