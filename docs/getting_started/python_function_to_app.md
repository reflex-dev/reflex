---
title: Turn a Python Function into a Web App with Reflex
meta_description: Add a web form and result view to a Python function with Reflex. Validate inputs, handle errors, and grow the example into a model interface.
---

# Turn a Python function into a web app

To turn a Python function into a web app with Reflex, collect inputs in a form, call the function from an event handler, and store the result in state. This example calculates a loan's monthly payment. It runs locally without a service or API key and keeps the calculation independent of the UI.

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
    # Convert the annual percentage rate to a monthly decimal rate.
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


def payment_field(label: str, name: str, value: str, unit: str):
    """Render a full-width input with a visible label and unit.

    Args:
        label: The input's accessible label.
        name: The submitted form key.
        value: The initial input value.
        unit: The unit displayed beside the input.

    Returns:
        A labelled input group.
    """
    return rx.vstack(
        rx.el.label(
            label, html_for=f"loan-{name}", font_size="0.875rem", font_weight="500"
        ),
        rx.input(
            rx.input.slot(
                rx.text(unit, size="2", color=rx.color("gray", 10)), side="right"
            ),
            id=f"loan-{name}",
            name=name,
            default_value=value,
            input_mode="numeric" if name == "years" else "decimal",
            size="3",
            width="100%",
        ),
        spacing="2",
        align_items="stretch",
        width="100%",
        min_width="0",
    )


def payment_app():
    """Render the loan calculator and an accessible payment summary."""
    return rx.vstack(
        rx.hstack(
            rx.center(
                rx.icon("calculator", size=22, aria_hidden=True),
                width="3rem",
                height="3rem",
                border_radius="14px",
                color=rx.color("violet", 11),
                background=rx.color("violet", 3),
                flex_shrink="0",
            ),
            rx.vstack(
                rx.heading(
                    "Payment calculator", size="6", as_="h2", letter_spacing="-0.03em"
                ),
                rx.text(
                    "Explore a monthly payment in a few simple steps.",
                    size="2",
                    color=rx.color("gray", 11),
                ),
                spacing="1",
                align_items="start",
            ),
            spacing="3",
            align="center",
        ),
        rx.grid(
            rx.form(
                rx.vstack(
                    payment_field("Loan amount", "amount", "10000", "USD"),
                    payment_field("Annual interest", "rate", "5", "%"),
                    payment_field("Loan term", "years", "3", "years"),
                    rx.button(
                        "Calculate payment",
                        rx.icon("arrow-right", size=16, aria_hidden=True),
                        type="submit",
                        size="3",
                        color_scheme="violet",
                        width="100%",
                        cursor="pointer",
                        margin_top="0.25rem",
                    ),
                    rx.cond(
                        PaymentState.error != "",
                        rx.text(
                            PaymentState.error,
                            role="alert",
                            size="2",
                            color=rx.color("red", 11),
                        ),
                    ),
                    spacing="4",
                    align_items="stretch",
                ),
                on_submit=PaymentState.calculate,
                width="100%",
                min_width="0",
            ),
            rx.vstack(
                rx.hstack(
                    rx.icon("wallet", size=18, aria_hidden=True),
                    rx.text(
                        "MONTHLY PAYMENT",
                        size="1",
                        weight="bold",
                        letter_spacing="0.08em",
                    ),
                    color=rx.color("violet", 11),
                    align="center",
                    spacing="2",
                ),
                rx.box(
                    rx.cond(
                        PaymentState.result != "",
                        rx.text(
                            PaymentState.result.replace("Monthly payment: ", ""),
                            font_size="clamp(1.75rem, 5vw, 2.75rem)",
                            line_height="1.15",
                            weight="bold",
                            letter_spacing="-0.04em",
                            overflow_wrap="anywhere",
                            color=rx.color("violet", 12),
                        ),
                        rx.text("—", size="8", color=rx.color("violet", 9)),
                    ),
                    rx.text(
                        rx.cond(
                            PaymentState.result != "",
                            "per month",
                            "Enter your details and calculate.",
                        ),
                        size="2",
                        color=rx.color("violet", 11),
                        margin_top="0.5rem",
                    ),
                    role="status",
                    aria_live="polite",
                ),
                rx.text(
                    "Fixed-rate estimate · excludes fees and taxes",
                    size="1",
                    color=rx.color("gray", 11),
                ),
                justify="between",
                align_items="stretch",
                spacing="5",
                padding="1.5rem",
                min_height="260px",
                min_width="0",
                background=rx.color("violet", 2),
                border=f"1px solid {rx.color('violet', 5)}",
                border_radius="14px",
            ),
            grid_template_columns="repeat(auto-fit, minmax(min(100%, 15rem), 1fr))",
            gap="1.5rem",
            width="100%",
        ),
        spacing="5",
        align_items="stretch",
        width="100%",
        max_width="48rem",
        padding=["1rem", "1.5rem"],
        margin="0 auto",
        background=rx.color("gray", 1),
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="18px",
        box_shadow="0 4px 20px rgba(0, 0, 0, 0.03)",
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

For a complete data-analysis workflow, try the [pandas data app](/docs/getting-started/pandas-data-app/): upload a CSV, filter records, and download a grouped summary.

Continue with [model and media interfaces](/docs/guides/model-and-media-interfaces/), [streaming chat](/docs/getting-started/chatapp-tutorial/), and [self-hosting](/docs/hosting/self-hosting/).
