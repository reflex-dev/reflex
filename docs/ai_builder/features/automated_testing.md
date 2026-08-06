# Testing

Reflex Build can generate and run tests from plain-language descriptions. Use tests to verify important app behavior after generation and before sharing or deploying.

```python exec
import reflex as rx
```

## Create a Test

1. Select **Testing** in the app workspace navigation.
2. Select **Add Test**.
3. Choose a test type:
   - **Unit test** for isolated state, calculations, validation, and other logic.
   - **Browser test** for user workflows that interact with the rendered app.
4. Describe the behavior and expected result in plain language.
5. Select **Generate**, review the generated test, and run it.

For example:

```text
Open the sign-in page, submit an invalid email, and verify that the form shows
an error without navigating. Then enter valid credentials and verify that the
dashboard opens.
```

## Run and Review Tests

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/testing_browser.webp",
    alt="Passing tests in the Reflex Build Testing panel",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

The Testing panel lets you search existing tests, run an individual test, or use **Run All**. Review the status and output of a failed test before asking the agent to change the app.

A failed test can indicate a problem in the app, an outdated expectation, or an ambiguous test description. Check the tested workflow in **Preview** before deciding which one to change.

## What to Test

Prioritize behavior that would block a user:

- Navigation and authentication.
- Forms, validation, and submission.
- Create, edit, and delete workflows.
- Filters and search.
- Data loading, empty states, and error states.
- Integrations and other external-service boundaries.

Keep each test focused on one workflow. Small tests are easier to understand and maintain than one test that tries to cover the whole app.
