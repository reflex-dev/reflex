---
title: Build AI Applications and Custom Chat Interfaces in Python
meta_description: Build Reflex interfaces for streaming AI chat, document assistants, and model tools. Connect Python SDKs with state, sources, and progress views.
---

# AI applications with Reflex

Reflex provides the interface and application state for an AI application while your Python code calls the model provider. A custom chat interface can display a response as it arrives and combine messages with forms, charts, files, and other components.

Start with the [streaming chat tutorial](/docs/getting-started/chatapp-tutorial/) for a complete application. It demonstrates asynchronous provider calls, conversation history, loading and error states, and incremental output. The [chat recipe](/docs/recipes/others/chat/) provides another interface you can adapt. You do not need to use Reflex Build to write an AI application with the framework.

## Choose the interaction

| Workflow | Interface | Python work |
| --- | --- | --- |
| Chat assistant | Messages, composer, loading and retry controls | Call a provider SDK and stream response chunks |
| Document question answering | Question, answer, and source excerpts | Retrieve authorized passages, call the model, and retain source references |
| Structured extraction | File input, editable fields, validation feedback | Parse input, validate model output, and save reviewed fields |
| Agent or tool workflow | Progress steps, intermediate results, approval controls | Execute permitted tools and record their results |
| Model demo | Parameter form and result view | Call a local prediction function or model service |

For the last pattern, use [model and media interfaces](/docs/guides/model-and-media-interfaces/). For a minimal starting point, [turn a Python function into an app](/docs/getting-started/python-function-to-app/).

## Connect a provider SDK

Call the SDK from backend Python. Keep the provider's credentials in server configuration, not in state variables exposed to the browser. Translate SDK-specific responses into your own application data: message text, sources, structured fields, or progress steps.

Streaming is a sequence of state updates. Consume the provider's async stream outside a background event's state lock, then use short `async with self` blocks to append output. Handle chunks without text, provider errors, and timeouts. The chat tutorial implements these boundaries rather than holding the lock across the whole request.

A second model provider may have a different request format, chunk shape, or cancellation API. Adapt that boundary while retaining the UI. Do not assume providers are interchangeable merely because they both stream text.

## Add document retrieval and sources

A document assistant adds a retrieval step before the model call:

1. Identify the authenticated user on the backend.
2. Query documents that user is allowed to read. Apply permissions in retrieval, before passages enter the prompt.
3. Select a bounded set of relevant passages and give each a stable source identifier.
4. Send the question and passages to the model using your provider's API.
5. Store the answer with the allowed source identifiers, and display matching titles and excerpts beside it.

Treat uploaded text as data, not instructions granting access or permission to run tools. A model-produced citation identifier must be checked against the passages supplied for that answer. If no relevant authorized passage is available, represent that explicitly instead of inventing a source.

Start by testing retrieval with a small set of known documents and questions. Verify both a relevant match and a no-match result, then test two users with different document access. A working chat UI alone does not establish that retrieval or authorization is correct.

## Persist conversations

Session state can hold the current view, but persistent conversations belong in a database or storage service. Store a conversation owner, messages, status, timestamps, and source references. On every load or update, check the current user's access to that conversation. A conversation ID from the browser is an identifier, not proof of permission.

Load a bounded page of history rather than sending an entire growing conversation to the browser or model. The [database guide](/docs/database/overview/) covers database access. [Reflex Enterprise authentication](/docs/enterprise/auth/overview/) is a separate authentication option; the framework does not automatically give a chat app a login system or record-level permissions.

## Represent progress, retries, and cancellation

Use explicit statuses such as idle, retrieving, generating, complete, and failed. Disable or reject duplicate submissions while a request is active. Preserve the question after an error so retry does not require retyping it. Decide whether a partial answer remains visible and mark it as incomplete.

A Stop button can stop displaying chunks without cancelling the provider request. To cancel work, connect the control to the provider's cancellation mechanism or an application-managed task and verify that it actually stops. Background events are not a durable job queue: use a worker and persistent job records when work must survive a server restart.

For tools that change external data, distinguish a proposed action from a completed operation. Perform backend permission checks and use an idempotency strategy before repeating an action after a timeout.

## Before deployment

Exercise missing credentials, provider failures, empty responses, duplicate clicks, disconnected clients, and two independent users. Record latency to first output separately from total generation time. Use [performance and execution](/docs/advanced-onboarding/performance-and-execution/) to identify where time is spent, then follow [self-hosting](/docs/hosting/self-hosting/) for deployment.
