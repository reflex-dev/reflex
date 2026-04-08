# Knowledge

The **Knowledge** feature lets you add context or rules that the AI Builder can reference when generating apps. This ensures your apps follow your guidelines, standards, or specific business logic.

```python exec
import reflex as rx


def render_image():
    return rx.el.div(
        rx.image(
            src="https://web.reflex-assets.dev/ai_builder/features/knowledge_light.avif",
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        class_name="w-full flex flex-col rounded-md",
    )
```

```python eval
rx.el.div(render_image())
```

## How to Add Knowledge

1. In the AI Builder top bar, click the more 3 dots icon and then click the **`Knowledge`** tab.
2. Enter your rule, guideline, or context description.
3. Save the entry. The AI Builder will automatically use it when generating apps.

## How It Works

- The AI Builder references your knowledge entries as rules or guidelines.
- Rules can define naming conventions, component usage, layout preferences, or other custom logic.
- Multiple rules can be added to cover different aspects of app generation.

## Common Use Cases

- **Maintain Consistency**
  Ensure all generated apps follow your company’s design or naming standards.

- **Enforce Business Logic**
  Guide the AI Builder to follow specific workflows, validations, or feature requirements.

- **Quickly Adapt AI Behavior**
  Add or update rules to influence new app generations without manual edits.
