# Secrets

The **Secrets** feature allows you to securely store environment-specific values that your app can use, such as API keys, tokens, or other sensitive information.


```python exec
import reflex as rx


def render_image():
    return rx.el.div(
        rx.image(
            src="https://web.reflex-assets.dev/ai_builder/features/secrets_light.avif",
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        class_name="w-full flex flex-col rounded-md",
    )
```

```python eval
rx.el.div(render_image())
```

## Adding Secrets

### 1. Add Individually
- **Description:** Set a single secret by providing a key and value.
- **Example:**
  - Key: `OPENAI_API_KEY`
  - Value: `sk-xxxxxx`
- **Behavior:** The secret is encrypted and accessible to your app at runtime.

### 2. Add in Bulk (Raw Editor)
- **Description:** Upload multiple secrets at once using a simple `VAR=VALUE` format.
- **Example:**

```text
DATABASE_URL=postgresql://user:pass@host:5432/db
STRIPE_SECRET_KEY=sk_test_xxxxx
OPENAI_API_KEY=sk-xxxxxx
```

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/features/secret_bulk_light.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```


- **Behavior:** Each secret is securely stored and immediately available in the app environment.
