```python exec
import reflex as rx
```

# Chat App

A chat interface renders a running list of messages and lets the user send new ones. Each
message is a `{"role": ..., "content": ...}` dictionary held in state, and the component
loops over that list to draw bubbles. This recipe covers a basic chat UI and the
streaming patterns that keep the loading experience clean.

## Basic Chat UI

Store messages in state, append the user's message on submit, and produce a reply. The
example below echoes the input so it runs on its own; in a real app you would call your
model provider instead.

```python demo exec
class ChatUIState(rx.State):
    messages: list[dict[str, str]] = []

    @rx.event
    def send_message(self, form_data: dict):
        text = form_data.get("message", "").strip()
        if not text:
            return
        self.messages.append({"role": "user", "content": text})
        self.messages.append({"role": "assistant", "content": f"You said: {text}"})


def message_bubble(message: dict[str, str]) -> rx.Component:
    is_user = message["role"] == "user"
    return rx.el.div(
        rx.el.div(
            message["content"],
            class_name=rx.cond(
                is_user,
                "bg-blue-500 text-white rounded-lg px-4 py-2 max-w-md",
                "bg-gray-100 text-gray-900 rounded-lg px-4 py-2 max-w-md",
            ),
        ),
        class_name=rx.cond(is_user, "flex justify-end", "flex justify-start"),
    )


def chat_ui() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.foreach(ChatUIState.messages, message_bubble),
            class_name="flex flex-col gap-3 p-4 h-96 overflow-y-auto",
        ),
        rx.el.form(
            rx.el.input(
                name="message",
                placeholder="Type a message...",
                class_name="flex-1 border rounded-lg px-3 py-2",
            ),
            rx.el.button(
                "Send",
                type="submit",
                class_name="px-4 py-2 bg-blue-500 text-white rounded-lg",
            ),
            on_submit=ChatUIState.send_message,
            reset_on_submit=True,
            class_name="flex gap-2 p-4 border-t",
        ),
        class_name="max-w-xl mx-auto border rounded-xl",
    )
```

## Streaming Responses

When a model streams its reply token by token, show a loading indicator immediately and
append the assistant message only once the stream actually starts producing content.

The key rule: **do not pre-append an empty assistant message** before the response
begins. Doing so renders a blank bubble alongside the loading dots, producing a broken
double-indicator experience.

Both snippets below use the [`openai`](https://pypi.org/project/openai/) package and read
the API key from the `OPENAI_API_KEY` environment variable. They also run as
[background events](/docs/events/background-events/), so all state mutations happen inside
`async with self:` blocks with deltas being sent to the client after exiting the block.

### Implementation

The loading dots show first, and the assistant bubble appears only on the first streamed
token. Two more details make this safe:

* The streaming LLM call is wrapped in a `try/finally` so
  `is_streaming` always resets even if the API call raises
* An `is_generating` guard serializes requests while the assistant message is updated
  by a captured index rather than `self.messages[-1]`, which would otherwise point
  at whichever message is currently last and let overlapping streams write to the
  wrong bubble:

```python
import openai


class ChatState(rx.State):
    messages: list[dict[str, str]] = []
    is_generating: bool = False

    @rx.event(background=True)
    async def send_message(self, form_data: dict):
        user_msg = form_data.get("message", "").strip()
        if not user_msg:
            return

        async with self:
            if self.is_generating:
                return  # a reply is still streaming; ignore overlapping submits
            self.is_generating = True
            self.messages.append({"role": "user", "content": user_msg})
            self.is_streaming = True
            request_messages = [
                {"role": m["role"], "content": m["content"]} for m in self.messages
            ]

        assistant_index = None
        try:
            client = openai.AsyncOpenAI()
            stream = await client.chat.completions.create(
                model="gpt-4o",
                messages=request_messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if not delta:
                    continue
                async with self:
                    if assistant_index is None:
                        # First token: create the bubble and capture its index
                        self.messages.append({"role": "assistant", "content": delta})
                        assistant_index = len(self.messages) - 1
                        self.is_streaming = False  # hide dots on first token
                    else:
                        self.messages[assistant_index]["content"] += delta
        finally:
            async with self:
                self.is_streaming = False
                self.is_generating = False
```

### Key Details

1. Build the API request from `self.messages` directly — there is no trailing empty
   message to slice off with `[:-1]`.
2. Append the assistant message only on the first token from the stream.
3. Hide the loading indicator after the first token, not at the end of the stream.
4. Wrap the stream in `try/finally` so `is_streaming` resets even when the API call fails.
5. Guard overlapping submits with `is_generating` and update the assistant message by its
   captured index (not `self.messages[-1]`) — background events run concurrently, so a
   second stream could otherwise append tokens to the wrong message.

````md alert info
## Gotchas to Avoid

An empty assistant bubble appears next to the loading dots because it is appended before
any content arrives:

```python
import openai


class ChatState(rx.State):
    messages: list[dict[str, str]] = []
    is_streaming: bool = False

    @rx.event(background=True)
    async def send_message(self, form_data: dict):
        user_msg = form_data.get("message", "").strip()
        if not user_msg:
            return

        async with self:
            self.messages.append({"role": "user", "content": user_msg})
            # BAD: appending an empty assistant message creates a blank bubble
            self.messages.append({"role": "assistant", "content": ""})
            self.is_streaming = True
            request_messages = [
                {"role": m["role"], "content": m["content"]} for m in self.messages[:-1]
            ]

        client = openai.AsyncOpenAI()
        # BAD: the stream is not wrapped in try/finally, so is_streaming may not reset
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=request_messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            async with self:
                self.messages[-1]["content"] += delta

        async with self:
            self.is_streaming = False
```
````