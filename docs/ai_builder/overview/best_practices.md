# Reflex Build Best Practices

Reliable results come from clear context, focused prompts, and short review cycles. Start with the smallest useful version of your app, then add one workflow at a time.

## Plan the First Version

Before generating, write down:

- The app's primary user and goal.
- The first page or workflow that must work.
- The data that page needs.
- Three to five essential features.
- Any visual references or design rules.

For a large specification, ask the agent to break it into ordered, buildable tasks. Build and verify each task instead of requesting the entire product in one generation.

## Write Outcome-Oriented Prompts

State the desired behavior, important components, data, and constraints. Replace subjective language with details the agent can verify.

```diff
- Build a nice admin dashboard.
+ Create a responsive admin dashboard with a collapsible left navigation,
+ four summary cards, and a searchable user table. Use compact spacing and
+ large rounded corners. Preserve the existing color palette.
```

When correcting a result, identify what should stay and what should change:

```diff
- Fix the sidebar.
+ Keep the current navigation items and colors. Make the sidebar collapsible,
+ preserve the selected item after navigation, and use a drawer below 768 px.
```

## Build in Focused Steps

A useful sequence is:

1. Create the layout and navigation.
2. Add the primary components and sample data.
3. Implement state and user interactions.
4. Connect real data or external services.
5. Add validation, empty states, loading states, and error handling.
6. Test the critical workflow and polish the interface.

Review **Preview** after every meaningful step. Use **Review mode** to draw on a specific UI area, add a comment, and send the annotated screenshot to the agent. When something is unclear, ask the agent to summarize what changed, then verify the affected workflow in the preview.

If the agent is already working, queue a short follow-up only when it adds a clear constraint. For a change in direction, wait for the current step, review it, and send one consolidated request. See [Generation Controls & Collaboration](/docs/ai/features/generation-controls/).

## Use Images as References

Attach screenshots, wireframes, or annotated sketches when visual structure matters. Explain what to copy, what to ignore, and which existing styles must remain. See [Images and Attachments](/docs/ai/features/image-as-prompt/) for a complete example and current upload guidance.

When you need an original visual instead of a reference, ask the agent to generate it and specify its composition, intended size, and where text will appear. See [Agent Tools](/docs/ai/features/agent-tools/).

## Choose Agent Effort and Planning

The create screen lets you control **Agent Effort** and whether the agent should **Plan first**.

- Keep **Agent Effort** on **Auto** for most work. Use a higher setting for complex, cross-cutting tasks and a lower setting for small, well-defined edits.
- Keep **Plan first** on **Auto** unless you want to require a plan for a complex task or skip planning for a small change.

Higher effort can improve difficult tasks, but it can also take longer. A precise prompt is still more important than the setting.

## Store Reusable Instructions in Knowledge

Use **Knowledge** for guidance that should apply beyond one prompt:

- Add project-wide conventions to project knowledge.
- Add app-specific architecture, behavior, or content rules to app instructions.
- Use a design system for reusable visual tokens and component guidance.

Keep these instructions concrete and remove rules that no longer apply. See [Knowledge](/docs/ai/features/knowledge/) for details.

## Connect and Test Deliberately

Add an integration before asking the agent to build against it, and describe the intended data flow. Store credentials in the integration or [Secrets](/docs/ai/features/secrets/) rather than in prompts or source code.

Create browser tests for the workflows users depend on and unit tests for isolated logic. After a major change, rerun the affected tests and manually check the most important path in **Preview**.

## Before You Ship

- Verify the primary workflow with realistic data.
- Check loading, empty, error, and validation states.
- Test the pages at desktop and mobile widths.
- Confirm secrets and credentials are not exposed.
- Review app visibility before sharing.
- Copy or download the app before a large experimental change.
