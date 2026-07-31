# Your First Reflex Build App

In this tutorial, you will create an employee dashboard, improve it through focused prompts, test the main workflow, and prepare it to share.

```python exec
import reflex as rx
```

## 1. Create the App

Open a project, select **Builder**, and start from the **Your Apps** tab. Enter this prompt:

```text
Create a responsive employee dashboard. Add a table with sample employees and
columns for name, department, and salary. Below it, add a bar chart that compares
salary by employee. Use five sample employees from different departments.
```

Before sending the prompt, you can attach a visual reference, choose a design system, set the app visibility, or add an integration. Keep **Agent Effort** on **Auto** unless you know the task needs more or less reasoning.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/builder_dashboard.webp",
    alt="Reflex Build dashboard with the app creation prompt",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## 2. Check the First Result

When generation finishes, use **Preview** to interact with the app. Check that the table and chart render and that the page works at different widths.

If the result is close, keep it and ask for one targeted improvement at a time.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/tutorial/tutorial_first_result.webp",
    alt="The first generated employee dashboard shown in Preview",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## 3. Add Filtering

```text
Above the employee table, add a name search input and a department filter.
Apply both filters together and update the table and chart immediately.
Include a clear-filters action.
```

Confirm that the table and chart stay in sync for a name search, a department selection, and the combined filters.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/tutorial/tutorial_filtering.webp",
    alt="The employee dashboard with its department filter open",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## 4. Add Employee Management

```text
Add an "Add employee" button that opens a form for name, department, and salary.
Validate every required field. Also add edit and delete actions for each row,
and keep the table and chart synchronized after every change.
```

This prompt explicitly requests create, edit, and delete behavior. If the generated app uses only sample in-memory data, ask the agent to connect a database before relying on the data in production.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/tutorial/tutorial_employee_management.webp",
    alt="The Add employee form generated for the employee dashboard",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## 5. Add a Second Page

```text
Create a Chat page and add it to the navigation. Include a message history,
message input, and send button. For now, reply by echoing the user's message.
Match the dashboard's layout, spacing, and component styles.
```

Use the route selector in **Preview** to check both pages and verify that navigation works in each direction.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/tutorial/tutorial_second_page.webp",
    alt="The generated Chat page open in Preview",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## 6. Review the Result

Open **Preview** and test the result. Switch Preview to a desktop width so **Review mode** is available. For feedback tied to a specific visual area, select **Review mode**, draw around the chart spacing and title, and add a comment such as:

```text
Keep the table behavior unchanged. Reduce the empty space above the chart and
align the chart title with the left edge of the table.
```

Select **Send review** to send the annotation and marked screenshot to the agent. Wait for the follow-up generation to finish, then check the same area again. Use a normal chat prompt for feedback that does not point to a specific UI region.

See [Code and Review](/docs/ai/features/editor-modes/) for the complete workflow.

## 7. Test the Main Workflow

Select **Testing** in the app workspace and create a browser test in plain language:

```text
Open the dashboard, search for an employee, clear the filters, add a valid
employee, edit that employee, and delete it. Verify the table and chart update
after each action.
```

Generate the test, run it, and use the result to fix any broken interaction. See [Testing](/docs/ai/features/automated-testing/) for the complete workflow.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/testing_browser.webp",
    alt="Passing tests in the Reflex Build Testing panel",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## 8. Share or Deploy

Use the menu next to **Deploy** to copy or download the app. Public apps can also be shared with a read-only link. When the app is ready for production, select **Deploy** and follow the deployment steps.

You now have a useful first version and a repeatable workflow: create, preview, refine, test, and ship.
