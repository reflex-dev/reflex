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

### Incorrect

An empty assistant bubble appears next to the loading dots because it is appended before
any content arrives:

```python
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

        client = openai.AsyncOpenAI()
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": m["role"], "content": m["content"]} for m in self.messages[:-1]],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            async with self:
                self.messages[-1]["content"] += delta

        async with self:
            self.is_streaming = False
```

### Correct

The loading dots show first, and the assistant bubble appears only on the first streamed
token:

```python
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
            self.is_streaming = True
            yield  # show the loading indicator immediately

        client = openai.AsyncOpenAI()
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": m["role"], "content": m["content"]} for m in self.messages],
            stream=True,
        )

        # Append the assistant message only after the stream starts producing content
        first_token = True
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if not delta:
                continue
            async with self:
                if first_token:
                    self.messages.append({"role": "assistant", "content": delta})
                    self.is_streaming = False  # hide loading dots on the first token
                    first_token = False
                else:
                    self.messages[-1]["content"] += delta

        async with self:
            self.is_streaming = False
```

The differences that matter:

1. Set `is_streaming = True` and `yield` to show the loading indicator right away.
2. Build the API request from `self.messages` directly — there is no trailing empty
   message to slice off with `[:-1]`.
3. Append the assistant message only on the first token from the stream.
4. Hide the loading indicator on the first token, not at the end of the stream.
