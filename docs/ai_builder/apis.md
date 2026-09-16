---
tags: AI Builder
description: Connect a Reflex Build app to an external HTTP API and handle credentials, responses, and failures safely.
---

# Call an External API

Use a direct API call when the service you need has an HTTP API but no suitable built-in or custom integration.

Before building against it, find the service's current documentation and identify:

- The base URL and required endpoints.
- The authentication method.
- The request and response formats.
- Rate limits, timeouts, and documented errors.

## Store credentials

Add API keys and tokens to [Secrets](/docs/ai/features/secrets/). Refer to each credential by its environment-variable name in the prompt; never include the value.

```text
Use the BILLING_API_TOKEN environment variable to authenticate server-side
requests to https://api.example.com/v1. Do not expose or log the token.
```

OAuth flows usually require more than a static secret. Describe the provider's authorization flow, callback URL, and required scopes, or configure an appropriate integration first.

## Describe the request

Give the agent the endpoint, trigger, inputs, expected result, and failure behavior:

```text
When the user submits the form, POST the validated fields to /customers.
Use a 10-second timeout. Show a useful error for authentication, rate-limit,
validation, and server failures, and do not retry validation errors.
```

The agent can use a standard HTTP client or add a supported package when the API needs a specific SDK. See [Install External Packages](/docs/ai/features/installing-external-packages/).

## Review and test

- Keep credentials and privileged calls in backend code.
- Validate user-controlled values before sending them.
- Do not log tokens, passwords, or sensitive response data.
- Test success, timeout, rate-limit, authentication, and malformed-response cases.
- Confirm the integration against test data before using production credentials.

## Related

- [Webhooks](/docs/ai/webhooks/) — send event payloads to an incoming webhook.
- [Custom Integration](/docs/ai/features/integration-shortcut/#custom-integration) — save reusable service instructions and credentials at project level.
- [Python Libraries](/docs/ai/python-libraries/) — guide the agent when an API uses a specialized SDK.
