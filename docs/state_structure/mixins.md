```python exec
import reflex as rx
```

# State Mixins

State mixins allow you to define shared functionality that can be reused across multiple State classes. This is useful for creating reusable components, shared business logic, or common state patterns.

## What are State Mixins?

A state mixin is a State class marked with `mixin=True` that cannot be instantiated directly but can be inherited by other State classes. Mixins provide a way to share:

- Base variables
- Computed variables
- Event handlers
- Backend variables

## Basic Mixin Definition

To create a state mixin, inherit from `rx.State` and pass `mixin=True`:

```python demo exec
class CounterMixin(rx.State, mixin=True):
    count: int = 0

    @rx.var
    def count_display(self) -> str:
        return f"Count: {self.count}"

    @rx.event
    def increment(self):
        self.count += 1


class MyState(CounterMixin, rx.State):
    name: str = "App"


def counter_example():
    return rx.vstack(
        rx.heading(MyState.name, as_="h2"),
        rx.text(MyState.count_display),
        rx.button("Increment", on_click=MyState.increment),
        spacing="4",
        align="center",
    )
```

```python test
def test_mixin_counter_increments(demo):
    expect(demo.get_by_role("heading")).to_have_text("App")
    expect(demo.get_by_text("Count: 0", exact=True)).to_be_visible()
    demo.get_by_role("button", name="Increment").click()
    expect(demo.get_by_text("Count: 1", exact=True)).to_be_visible()
```

In this example, `MyState` automatically inherits the `count` variable, `count_display` computed variable, and `increment` event handler from `CounterMixin`.

## Multiple Mixin Inheritance

You can inherit from multiple mixins to combine different pieces of functionality:

```python demo exec
class TimestampMixin(rx.State, mixin=True):
    last_updated: str = ""

    @rx.event
    def update_timestamp(self):
        import datetime

        self.last_updated = datetime.datetime.now().strftime("%H:%M:%S")


class LoggingMixin(rx.State, mixin=True):
    log_messages: list[str] = []

    @rx.event
    def log_message(self, message: str):
        self.log_messages.append(message)


class CombinedState(CounterMixin, TimestampMixin, LoggingMixin, rx.State):
    app_name: str = "Multi-Mixin App"

    @rx.event
    def increment_with_log(self):
        self.increment()
        self.update_timestamp()
        self.log_message(f"Count incremented to {self.count}")


def multi_mixin_example():
    return rx.vstack(
        rx.heading(CombinedState.app_name, as_="h2"),
        rx.text(CombinedState.count_display),
        rx.text(f"Last updated: {CombinedState.last_updated}"),
        rx.button("Increment & Log", on_click=CombinedState.increment_with_log),
        rx.cond(
            CombinedState.log_messages.length() > 0,
            rx.vstack(
                rx.foreach(CombinedState.log_messages[-3:], rx.text), spacing="1"
            ),
            rx.text("No logs yet"),
        ),
        spacing="4",
        align="center",
    )
```

```python test
def test_multiple_mixins_combine(demo):
    expect(demo.get_by_role("heading")).to_have_text("Multi-Mixin App")
    expect(demo.get_by_text("No logs yet")).to_be_visible()
    expect(demo.get_by_text("Last updated: ", exact=True)).to_be_visible()
    demo.get_by_role("button", name="Increment & Log").click()
    expect(demo.get_by_text("Count: 1", exact=True)).to_be_visible()
    expect(demo.get_by_text("Count incremented to 1")).to_be_visible()
    expect(demo.get_by_text(re.compile(r"^Last updated: "))).to_have_text(
        re.compile(r"^Last updated: \d\d:\d\d:\d\d$")
    )
    expect(demo.get_by_text("No logs yet")).to_be_hidden()
```

## Backend Variables in Mixins

Mixins can also include backend variables (prefixed with `_`) that are not sent to the client:

```python demo exec
class DatabaseMixin(rx.State, mixin=True):
    _db_connection: dict = {}  # Backend only
    user_count: int = 0  # Sent to client

    @rx.event
    def fetch_user_count(self):
        # Simulate database query
        self.user_count = len(self._db_connection.get("users", []))


class AppState(DatabaseMixin, rx.State):
    app_title: str = "User Management"


def database_example():
    return rx.vstack(
        rx.heading(AppState.app_title, as_="h2"),
        rx.text(f"User count: {AppState.user_count}"),
        rx.button("Fetch Users", on_click=AppState.fetch_user_count),
        spacing="4",
        align="center",
    )
```

```python test
def test_backend_mixin_var_stays_on_server(demo):
    expect(demo.get_by_role("heading")).to_have_text("User Management")
    demo.get_by_role("button", name="Fetch Users").click()
    expect(demo.get_by_text("User count: 0", exact=True)).to_be_visible()
```

Backend variables are useful for storing sensitive data, database connections, or other server-side state that shouldn't be exposed to the client.

## Computed Variables in Mixins

Computed variables in mixins work the same as in regular State classes:

```python demo exec
class FormattingMixin(rx.State, mixin=True):
    value: float = 0.0

    @rx.var
    def formatted_value(self) -> str:
        return f"${self.value:.2f}"

    @rx.var
    def is_positive(self) -> bool:
        return self.value > 0


class PriceState(FormattingMixin, rx.State):
    product_name: str = "Widget"

    @rx.event
    def set_price(self, price: str):
        try:
            self.value = float(price)
        except ValueError:
            self.value = 0.0


def formatting_example():
    return rx.vstack(
        rx.heading(f"Product: {PriceState.product_name}", as_="h2"),
        rx.text(f"Price: {PriceState.formatted_value}"),
        rx.text(f"Positive: {PriceState.is_positive}"),
        rx.input(
            placeholder="Enter price",
            on_blur=PriceState.set_price,
        ),
        spacing="4",
        align="center",
    )
```

```python test
def test_mixin_computed_vars_format_price(demo):
    expect(demo.get_by_role("heading")).to_have_text("Product: Widget")
    expect(demo.get_by_text("Price: $0.00")).to_be_visible()
    expect(demo.get_by_text("Positive: false")).to_be_visible()
    demo.get_by_placeholder("Enter price").fill("12.5")
    demo.get_by_placeholder("Enter price").blur()
    expect(demo.get_by_text("Price: $12.50")).to_be_visible()
    expect(demo.get_by_text("Positive: true")).to_be_visible()
```

## Nested Mixin Inheritance

Mixins can inherit from other mixins to create hierarchical functionality:

```python demo exec
class BaseMixin(rx.State, mixin=True):
    base_value: str = "base"


class ExtendedMixin(BaseMixin, mixin=True):
    extended_value: str = "extended"

    @rx.var
    def combined_value(self) -> str:
        return f"{self.base_value}-{self.extended_value}"


class FinalState(ExtendedMixin, rx.State):
    final_value: str = "final"


def nested_mixin_example():
    return rx.vstack(
        rx.text(f"Base: {FinalState.base_value}"),
        rx.text(f"Extended: {FinalState.extended_value}"),
        rx.text(f"Combined: {FinalState.combined_value}"),
        rx.text(f"Final: {FinalState.final_value}"),
        spacing="4",
        align="center",
    )
```

```python test
def test_nested_mixin_values(demo):
    expect(demo.locator("p")).to_have_text([
        "Base: base",
        "Extended: extended",
        "Combined: base-extended",
        "Final: final",
    ])
```

This pattern allows you to build complex functionality by composing simpler mixins.

## Best Practices

```md alert info
# Mixin Design Guidelines

- **Single Responsibility**: Each mixin should have a focused purpose
- **Avoid Deep Inheritance**: Keep mixin hierarchies shallow for clarity
- **Document Dependencies**: If mixins depend on specific variables, document them
- **Test Mixins**: Create test cases for mixin functionality
- **Naming Convention**: Use descriptive names ending with "Mixin"
```

## Limitations

```md alert warning
# Important Limitations

- Mixins cannot be instantiated directly - they must be inherited by concrete State classes
- Variable name conflicts between mixins are resolved by method resolution order (MRO)
- Mixins cannot override methods from the base State class
- The `mixin=True` parameter is required when defining a mixin
```

## Common Use Cases

State mixins are particularly useful for:

- **Form Validation**: Shared validation logic across forms
- **UI State Management**: Common modal, loading, or notification patterns
- **Logging**: Centralized logging and debugging
- **API Integration**: Shared HTTP client functionality
- **Data Formatting**: Consistent data presentation across components

```python demo exec
import asyncio


class ValidationMixin(rx.State, mixin=True):
    errors: dict[str, str] = {}
    is_loading: bool = False

    @rx.event
    def validate_email(self, email: str) -> bool:
        if "@" not in email or "." not in email:
            self.errors["email"] = "Invalid email format"
            return False
        self.errors.pop("email", None)
        return True

    @rx.event
    def validate_required(self, field: str, value: str) -> bool:
        if not value.strip():
            self.errors[field] = f"{field.title()} is required"
            return False
        self.errors.pop(field, None)
        return True

    @rx.event
    def clear_errors(self):
        self.errors = {}


class ContactFormState(ValidationMixin, rx.State):
    name: str = ""
    email: str = ""
    message: str = ""

    def set_name(self, value: str):
        self.name = value

    def set_email(self, value: str):
        self.email = value

    def set_message(self, value: str):
        self.message = value

    @rx.event
    async def submit_form(self):
        self.clear_errors()
        valid_name = self.validate_required("name", self.name)
        valid_email = self.validate_email(self.email)
        valid_message = self.validate_required("message", self.message)

        if valid_name and valid_email and valid_message:
            self.is_loading = True
            yield
            await asyncio.sleep(1)
            self.is_loading = False
            self.name = ""
            self.email = ""
            self.message = ""


def validation_example():
    return rx.vstack(
        rx.heading("Contact Form", as_="h2"),
        rx.input(
            placeholder="Name",
            value=ContactFormState.name,
            on_change=ContactFormState.set_name,
        ),
        rx.cond(
            ContactFormState.errors.contains("name"),
            rx.text(ContactFormState.errors["name"], color="red"),
        ),
        rx.input(
            placeholder="Email",
            value=ContactFormState.email,
            on_change=ContactFormState.set_email,
        ),
        rx.cond(
            ContactFormState.errors.contains("email"),
            rx.text(ContactFormState.errors["email"], color="red"),
        ),
        rx.text_area(
            placeholder="Message",
            value=ContactFormState.message,
            on_change=ContactFormState.set_message,
        ),
        rx.cond(
            ContactFormState.errors.contains("message"),
            rx.text(ContactFormState.errors["message"], color="red"),
        ),
        rx.button(
            "Submit",
            on_click=ContactFormState.submit_form,
            loading=ContactFormState.is_loading,
        ),
        spacing="4",
        align="center",
        width="300px",
    )
```

```python test
def test_validation_mixin_reports_and_clears_errors(demo):
    demo.get_by_role("button", name="Submit").click()
    expect(demo.get_by_text("Name is required")).to_be_visible()
    expect(demo.get_by_text("Invalid email format")).to_be_visible()
    expect(demo.get_by_text("Message is required")).to_be_visible()
    demo.get_by_placeholder("Name").fill("Ada")
    demo.get_by_placeholder("Email").fill("ada@example.com")
    demo.get_by_placeholder("Message").fill("Hello")
    demo.get_by_role("button", name="Submit").click()
    expect(demo.get_by_text("Name is required")).to_be_hidden()
    expect(demo.get_by_text("Invalid email format")).to_be_hidden()
    expect(demo.get_by_placeholder("Name")).to_have_value("")
    expect(demo.get_by_placeholder("Message")).to_have_value("")
```

By using state mixins, you can create modular, reusable state logic that keeps your application organized and reduces code duplication.
