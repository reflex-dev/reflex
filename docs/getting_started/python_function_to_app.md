---
title: Turn a Python Function into a Web App with Reflex
meta_description: Add a web form and result view to a Python function with Reflex. Validate inputs, handle errors, and grow the example into a model interface.
---

# Turn a Python function into a web app

Expose a Python function through a Reflex interface by collecting inputs in a form, calling the function from an event handler, and storing the result in state. This example calculates a loan's monthly payment. It runs locally without a service or API key and keeps the calculation independent of the UI.

Create a blank app using the [installation guide](/docs/getting-started/installation/). Replace the app module with the code below and the two registration lines that follow it.

## Form, function, and result

```python demo exec defer id=function_to_app_demo
import math
from typing import Any

import reflex as rx


def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    """Calculate a fixed-rate monthly payment, excluding fees and taxes."""
    if not math.isfinite(principal) or not 0 < principal <= 10_000_000:
        raise ValueError("Amount must be between 0 and 10,000,000.")
    if not math.isfinite(annual_rate) or not 0 <= annual_rate <= 100:
        raise ValueError("Annual interest must be between 0 and 100 percent.")
    if not 1 <= years <= 50:
        raise ValueError("Term must be between 1 and 50 years.")
    months = years * 12
    rate = annual_rate / 1200
    if rate == 0:
        return principal / months
    return principal * rate / -math.expm1(-months * math.log1p(rate))


class PaymentState(rx.State):
    result: str = ""
    error: str = ""

    @rx.event
    def calculate(self, form_data: dict[str, Any]):
        """Validate submitted values and replace the previous result."""
        self.result = ""
        self.error = ""
        try:
            amount = float(form_data.get("amount", ""))
            rate = float(form_data.get("rate", ""))
            years = int(form_data.get("years", ""))
        except ValueError:
            self.error = "Enter an amount, interest rate, and whole number of years."
            return
        try:
            payment = monthly_payment(amount, rate, years)
        except ValueError as error:
            self.error = str(error)
            return
        self.result = f"Monthly payment: ${payment:,.2f}"


def payment_app():
    """Render a labelled form and its result or validation message."""
    return rx.vstack(
        rx.form(
            rx.vstack(
                rx.el.label("Loan amount", html_for="loan-amount"),
                rx.input(id="loan-amount", name="amount", default_value="10000"),
                rx.el.label("Annual interest (%)", html_for="loan-rate"),
                rx.input(id="loan-rate", name="rate", default_value="5"),
                rx.el.label("Term (years)", html_for="loan-years"),
                rx.input(id="loan-years", name="years", default_value="3"),
                rx.button("Calculate", type="submit"),
                spacing="3",
            ),
            on_submit=PaymentState.calculate,
        ),
        rx.text(PaymentState.result, role="status"),
        rx.text(PaymentState.error, role="alert", color="red"),
        spacing="4",
    )
```

```python
app = rx.App()
app.add_page(payment_app)
```

Run `uv run reflex run` and submit the form. At zero interest, 12,000 over one year returns 1,000 per month. An invalid input clears the previous result and displays an error. This is a simplified calculation, not a lending quote.

## What happens on submit

Each input's `name` becomes a key in `form_data`. The browser sends the form submission to `PaymentState.calculate`; the backend parses and validates it, calls `monthly_payment`, and sends the changed state to the interface. The result and error views update from that state.

The calculation remains an ordinary Python function. You can call it from tests, a script, or another service independently of Reflex. This explicit form-to-handler mapping does not automatically infer an interface from a function signature.

## Replace the calculation with your workflow

The same pattern can call a data transformation, a loaded model, or an external service. Keep input validation at the backend boundary even when the form has browser validation. Keep secrets out of state variables sent to the frontend.

For fast local calculations, a normal handler is sufficient. For a slow API call, use an async SDK and show a loading state. If other events need to run while work is pending, use a [background event](/docs/events/background-events/) and hold the state lock only while reading or updating state. CPU-heavy inference needs a separate execution strategy; marking a function async does not make blocking computation asynchronous.

Continue with [model and media interfaces](/docs/guides/model-and-media-interfaces/), [streaming chat](/docs/getting-started/chatapp-tutorial/), and [self-hosting](/docs/hosting/self-hosting/).
