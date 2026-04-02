# Integrations Shortcut

Reflex Build supports powerful integrations like databases, OpenAI, and Databricks, allowing you to connect external services to your app without complex setup. These integrations help you add advanced functionality—like AI-powered features, data analytics, or persistent storage—while speeding up development.

The **Add Integrations** button makes it easy to connect external services to your app while chatting with the AI Builder. A panel with a list of available integrations will appear, you can quickly add integrations that your app can reference and connect to.

Once in your app, you can access your integrations by clicking the flow or cog icon in the bottom left inside the chat area.

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src=rx.color_mode_cond(
            "https://web.reflex-assets.dev/ai_builder/features/shortcut_light.webp",
            "https://web.reflex-assets.dev/ai_builder/features/shortcut_dark.webp",
        ),
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

## How to Use

1. In the AI Builder home, click the **Add Integrations** button. And if you're already in an app, click the flow or cog icon in the bottom left inside the chat area.
2. A list of available integrations will appear (e.g. Database, Databricks, OpenAI, etc.).
3. Click the Add button next to an integration to select it.
4. The integration will be added to your app and becomes available for connection. Then you can fill the required fields for the integration.
5. The AI Builder now knows your app has access to this integration and can generate code that uses it.

## What It Does

- **Quick Access** – Easily browse and select from available integrations.
- **Automatic Connection** – Integrations are added to your app and become available for the AI to use in generated code.
- **No Manual Setup** – Skip complex configuration—the AI Builder handles the integration setup for you.

## Common Use Cases

- **Database Queries**
  Show me the top 10 users ordered by signup date from my database.

- **AI Features**
  Create a chat application that uses OpenAI to generate responses.
