---
tags: AI Builder
description: Send app events to an external service through an incoming webhook without exposing its URL in client-side code or logs.
---

# Webhooks

Use an outgoing webhook when an event in your app should send data to a service that provides an incoming webhook URL.

## Create and store the webhook

1. Create an incoming webhook in the destination service.
2. Copy its URL.
3. Store the URL in [Secrets](/docs/ai/features/secrets/) with a descriptive name such as `SIGNUP_WEBHOOK_URL`.

Treat the URL as a credential. Do not paste it into chat, source code, logs, screenshots, or client-side code.

## Describe the event and payload

Tell the agent when to send the webhook, which fields to include, and how to handle failures:

```text
After a user completes signup, POST their internal user ID, plan name, and
signup timestamp to the URL in SIGNUP_WEBHOOK_URL. Do not include passwords,
tokens, or profile fields. Use the destination's documented JSON format.
```

Specify whether a failed webhook should block the user action, retry in the background, or only record an error. For important events, request idempotency or another duplicate-delivery safeguard supported by the destination.

## Test the webhook

Use test credentials and non-sensitive sample data first. Verify:

- The event sends exactly once under normal conditions.
- The payload matches the destination's expected schema.
- Timeouts and non-success responses are handled without exposing the URL.
- Retries do not create duplicate records or notifications.

## Related

- [Call an External API](/docs/ai/apis/) — implement a request-and-response API workflow.
- [Custom Integration](/docs/ai/features/integration-shortcut/#custom-integration) — store reusable context for a service.
- [Testing](/docs/ai/features/automated-testing/) — cover the app behavior that triggers the webhook.
