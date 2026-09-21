---
meta_description: Connect Reflex apps to AI models, databases, and business tools. Explore OpenAI, Anthropic, Gemini, Python SDKs, API integrations, and MCP tools for Reflex Build.
---

# AI Integrations Overview

Reflex apps connect to AI models, databases, and external tools through packaged integrations, Python libraries, and APIs. **AI integrations** include OpenAI, Anthropic, Google Gemini, and orchestration tools such as LangChain. **API integrations** let your app work with operational systems such as Snowflake, Supabase, Salesforce, AWS, and GitHub using the appropriate connector or client.

In Reflex Build, use the [integrations workflow](/docs/ai/features/integration-shortcut/) to configure supported services. Where there is no packaged integration, use a Python SDK or REST API. [MCP servers](/docs/ai/integrations/mcp-overview/) can give the Builder agent access to tools and context; an app's runtime connection still needs the appropriate client, credentials, and network access.

## Key takeaways

- Choose integrations by category: AI models, databases, communication tools, and authentication providers.
- Connect multiple AI providers from Python, adapting each provider's SDK and response format.
- Use the [database ORM](/docs/database/overview/) for relational models and sessions, or a service-specific client for other data sources.
- Keep credentials in integrations or [Secrets](/docs/ai/features/secrets/), rather than frontend code or prompts.
- The catalog is a starting point. Python libraries and REST APIs support custom connections to existing business systems.

## AI providers and orchestration

| Provider or tool | Common use | Connection approach |
| --- | --- | --- |
| OpenAI | Chat and other model capabilities | OpenAI Python SDK or API |
| Anthropic | Claude-powered assistants | Anthropic Python SDK or API |
| Google Gemini | Gemini-powered apps | Google SDK or API |
| LangChain | Orchestration across models and tools | Python library with provider-specific configuration |

LangChain is an orchestration library, not a model provider. Provider credentials, supported features, and response formats differ. For a working UI and streaming pattern, start with the [Python chatbot tutorial](/docs/getting-started/chatapp-tutorial/).

## Integration categories

- **Databases:** MySQL, PostgreSQL, SQL Server, and SQLite through SQLAlchemy-compatible connections; use service clients for warehouses and other data systems.
- **AI:** OpenAI, Anthropic, Gemini, and LangChain for assistants and AI-powered business workflows.
- **Communication and business tools:** Twilio, Resend, and Airtable for messaging, email, and operational data.
- **Authentication:** Okta, Google, Azure, and Descope for supported sign-in and single sign-on workflows.

## Browse integrations

```python exec
import reflex as rx
from reflex_docs.pages.integrations.integration_gallery import (
    integration_filters,
    integration_gallery,
    integration_request_form,
)
```

```python eval
rx.el.div(
    integration_filters(),
    integration_gallery(),
    integration_request_form(),
    class_name="flex flex-col size-full justify-center items-center",
)
```

<!-- faqs-start -->
<!-- faqs-visible -->

## FAQ

### Which external tools and APIs can Reflex integrate with?

Reflex apps can connect to AI models such as OpenAI, Anthropic, and Gemini; relational databases such as MySQL, PostgreSQL, SQL Server, and SQLite; and operational systems such as Snowflake, Supabase, Salesforce, AWS, and GitHub. Use a supported integration or the relevant Python client or REST API, with credentials and permissions for each service.

### Can a Reflex app combine Snowflake data with other operational workflows?

Yes. Query Snowflake with its Python client or a configured integration, combine the results with data from another database or internal API, and assign the data needed by the UI to Reflex state. Configure access and credentials for each system.

### What if the tool I need is not in the integrations catalog?

Use a Python SDK or REST API from the app backend, or create a custom integration in Reflex Build. An MCP server can provide tools and context to the Builder agent; this is separate from implementing the deployed app’s runtime connection.

<!-- faqs-end -->
