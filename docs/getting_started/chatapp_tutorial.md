---
meta_description: Build a streaming AI assistant in Python with Reflex and OpenAI. Create a custom chatbot UI, manage chat state, and display responses as they arrive.
---

```python exec
import reflex as rx

chat_margin = "12%"
message_style = dict(
    padding="0.875em 1em",
    border_radius="16px",
    margin_y="0.5em",
    max_width="34em",
    display="inline-block",
    overflow_wrap="anywhere",
    line_height="1.65",
    font_size="0.95rem",
    text_align="left",
)
question_style = message_style | dict(
    margin_left=chat_margin,
    background_color=rx.color("accent", 3),
    color=rx.color("accent", 12),
    border=f"1px solid {rx.color('accent', 5)}",
)
answer_style = message_style | dict(
    margin_right=chat_margin,
    background_color=rx.color("slate", 2),
    color=rx.color("slate", 12),
    border=f"1px solid {rx.color('slate', 4)}",
)
input_style = dict(
    width="100%",
    min_width="0",
    flex="1",
    height="44px",
    border_radius="12px",
    background_color=rx.color("slate", 1),
    border=f"1px solid {rx.color('slate', 7)}",
    box_shadow="none",
    **{
        "& input": {
            "padding": "0 14px",
            "font_size": "14px",
            "border": "none",
            "outline": "none",
            "box_shadow": "none",
            "background": "transparent",
        },
        "& input::placeholder": {"color": rx.color("slate", 11)},
        "&:focus-within": {
            "border_color": rx.color("accent", 8),
            "box_shadow": f"0 0 0 3px {rx.color('accent', 3)}",
        },
    },
)
button_style = dict(
    flex_shrink="0",
    height="44px",
    padding="0 20px",
    border_radius="12px",
    font_weight="600",
    background_color=rx.color("accent", 9),
    color="white",
    cursor="pointer",
    _hover={"background_color": rx.color("accent", 10)},
    _disabled={"opacity": "0.65", "cursor": "not-allowed"},
)

from types import SimpleNamespace

style = SimpleNamespace(
    question_style=question_style,
    answer_style=answer_style,
    input_style=input_style,
    button_style=button_style,
)
```

# AI Assistant Tutorial: Build a Streaming Chatbot in Python

```md tutorial-intro 30
Build a streaming AI assistant in Python with Reflex and OpenAI. Create a custom chatbot interface, manage conversation history, and display model responses as they arrive—all in one app. You can reuse the UI and state pattern with other AI providers by adapting the API integration.

**Before you start:** Familiarity with Python helps; the [Basics Guide](/docs/getting-started/basics/) introduces Reflex. You will need an OpenAI API key for the final integration step.
```

You can find the full source code for this app on [GitHub](https://github.com/reflex-dev/reflex-chat).

**Preview:** This static example shows the finished chat styling. Its controls are disabled; you will build a working version below.

```python eval
rx.box(
    rx.vstack(
        rx.vstack(
            rx.box(
                rx.text("What is Reflex?", style=style.question_style),
                text_align="right",
                width="100%",
            ),
            rx.box(
                rx.text(
                    "Reflex is a way to build full-stack web apps in pure Python — "
                    "frontend, backend, and state all in one place.",
                    style=style.answer_style,
                ),
                text_align="left",
                width="100%",
            ),
            rx.box(
                rx.text("Can I deploy it?", style=style.question_style),
                text_align="right",
                width="100%",
            ),
            rx.box(
                rx.text(
                    "Yes. You can deploy it with Reflex Cloud when you are ready.",
                    style=style.answer_style,
                ),
                text_align="left",
                width="100%",
            ),
            spacing="0",
            width="100%",
        ),
        rx.hstack(
            rx.input(
                placeholder="Ask a question",
                style=style.input_style,
                disabled=True,
            ),
            rx.button("Ask", style=style.button_style, disabled=True),
            spacing="3",
            padding_top="1.5em",
            justify="center",
            width="100%",
        ),
        align="stretch",
        spacing="0",
        width="100%",
        padding=rx.breakpoints(initial="1em", sm="2em"),
    ),
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    margin_y="1em",
)
```

## Key takeaways

- Build a custom AI assistant interface with Python components, state variables, and event handlers.
- Display responses as they arrive using `yield` inside an async event handler.
- Connect a language model through the OpenAI Python SDK, with the API key kept on the backend.
- Reuse the chat UI when integrating another provider or adding document retrieval for an internal AI assistant.

## What You'll Learn

In this tutorial you'll learn how to:

1. Install `reflex` and set up your development environment.
2. Create components to define and style your UI.
3. Use state to add interactivity to your app.
4. Connect an AI model, stream its responses, and prepare the app for deployment.

## Setting up Your Project

```md video https://youtube.com/embed/ITOZkzjtjUA?start=175&end=445
# Video: Example of Setting up the Chat App
```

We will start by creating a new project and setting up our development environment. If you haven't installed [uv](https://docs.astral.sh/uv/) yet, see the [installation guide](/docs/getting-started/installation/). Then create a new project directory and scaffold a Reflex app:

```bash
mkdir chatapp
cd chatapp
uv init
uv add reflex
uv run reflex init
```

```md alert info
When prompted to select a template, choose option **0** for a blank project.
```

You can run the template app to make sure everything is working.

```bash
uv run reflex run
```

You should see your app running at [http://localhost:3000](http://localhost:3000).

Reflex also starts the backend server which handles all the state management and communication with the frontend. You can test the backend server is running by navigating to [http://localhost:8000/ping](http://localhost:8000/ping).

Keep `app = rx.App()` and `app.add_page(index)` at the end of `chatapp/chatapp.py`, after all component definitions. As you follow the steps, replace earlier versions of functions instead of appending duplicate definitions.

## Basic Frontend

Let's start with defining the frontend for our chat app. In Reflex, the frontend can be broken down into independent, reusable components. See the [components docs](/docs/components/props/) for more information.

### Display Q&A

We will modify the `index` function in `chatapp/chatapp.py` file to return a component that displays a single question and answer.

```python demo box
rx.container(
    rx.box(
        "What is Reflex?",
        # The user's question is on the right.
        text_align="right",
    ),
    rx.box(
        "A way to build web apps in pure Python!",
        # The answer is on the left.
        text_align="left",
    ),
)
```

```python
# chatapp.py

import reflex as rx


def index() -> rx.Component:
    return rx.container(
        rx.box(
            "What is Reflex?",
            # The user's question is on the right.
            text_align="right",
        ),
        rx.box(
            "A way to build web apps in pure Python!",
            # The answer is on the left.
            text_align="left",
        ),
    )


# Add state and page to the app.
app = rx.App()
app.add_page(index)
```

Components can be nested inside each other to create complex layouts. Here we create a parent container that contains two boxes for the question and answer.

We also add some basic styling to the components. Components take in keyword arguments, called [props](/docs/components/props/), that modify the appearance and functionality of the component. We use the `text_align` prop to align the text to the left and right.

### Reusing Components

Now that we have a component that displays a single question and answer, we can reuse it to display multiple questions and answers. We will move the component to a separate function `qa` and call it from the `index` function.

```python exec
def qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(question, text_align="right"),
        rx.box(answer, text_align="left"),
        margin_y="1em",
    )


qa_pairs = [
    ("What is Reflex?", "A way to build web apps in pure Python!"),
    (
        "What can I make with it?",
        "Anything from a simple website to a complex web app!",
    ),
]


def chat() -> rx.Component:
    qa_pairs = [
        ("What is Reflex?", "A way to build web apps in pure Python!"),
        (
            "What can I make with it?",
            "Anything from a simple website to a complex web app!",
        ),
    ]
    return rx.box(*[qa(question, answer) for question, answer in qa_pairs])
```

```python demo box
rx.container(chat())
```

```python
def qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(question, text_align="right"),
        rx.box(answer, text_align="left"),
        margin_y="1em",
    )


def chat() -> rx.Component:
    qa_pairs = [
        ("What is Reflex?", "A way to build web apps in pure Python!"),
        (
            "What can I make with it?",
            "Anything from a simple website to a complex web app!",
        ),
    ]
    return rx.box(*[qa(question, answer) for question, answer in qa_pairs])


def index() -> rx.Component:
    return rx.container(chat())
```

### Chat Input

Now we want a way for the user to input a question. For this, we will use the [input](/docs/library/forms/input/) component to have the user add text and a [button](/docs/library/forms/button/) component to submit the question.

```python exec
def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(placeholder="Ask a question"),
        rx.button("Ask"),
    )
```

```python demo box
rx.container(
    chat(),
    action_bar(),
)
```

```python
def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(placeholder="Ask a question"),
        rx.button("Ask"),
    )


def index() -> rx.Component:
    return rx.container(
        chat(),
        action_bar(),
    )
```

### Styling

Let's add some styling to the app. More information on styling can be found in the [styling docs](/docs/styling/overview/). To keep our code clean, we will move the styling to a separate file `chatapp/style.py`.

```python
# style.py
import reflex as rx

chat_margin = "12%"
message_style = dict(
    padding="0.875em 1em",
    border_radius="16px",
    margin_y="0.5em",
    max_width="34em",
    display="inline-block",
    overflow_wrap="anywhere",
    line_height="1.65",
    font_size="0.95rem",
    text_align="left",
)
question_style = message_style | dict(
    margin_left=chat_margin,
    background_color=rx.color("accent", 3),
    color=rx.color("accent", 12),
    border=f"1px solid {rx.color('accent', 5)}",
)
answer_style = message_style | dict(
    margin_right=chat_margin,
    background_color=rx.color("slate", 2),
    color=rx.color("slate", 12),
    border=f"1px solid {rx.color('slate', 4)}",
)
input_style = dict(
    width="100%",
    min_width="0",
    flex="1",
    height="44px",
    border_radius="12px",
    background_color=rx.color("slate", 1),
    border=f"1px solid {rx.color('slate', 7)}",
    box_shadow="none",
    **{
        "& input": {
            "padding": "0 14px",
            "font_size": "14px",
            "border": "none",
            "outline": "none",
            "box_shadow": "none",
            "background": "transparent",
        },
        "& input::placeholder": {"color": rx.color("slate", 11)},
        "&:focus-within": {
            "border_color": rx.color("accent", 8),
            "box_shadow": f"0 0 0 3px {rx.color('accent', 3)}",
        },
    },
)
button_style = dict(
    flex_shrink="0",
    height="44px",
    padding="0 20px",
    border_radius="12px",
    font_weight="600",
    background_color=rx.color("accent", 9),
    color="white",
    cursor="pointer",
    _hover={"background_color": rx.color("accent", 10)},
    _disabled={"opacity": "0.65", "cursor": "not-allowed"},
)
```

We will import the styles in `chatapp.py` and use them in the components. At this point, the app should look like this:

```python exec
def styled_qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(rx.text(question, style=style.question_style), text_align="right"),
        rx.box(rx.text(answer, style=style.answer_style), text_align="left"),
        margin_y="1em",
        width="100%",
    )


def styled_chat() -> rx.Component:
    qa_pairs = [
        ("What is Reflex?", "A way to build web apps in pure Python!"),
        (
            "What can I make with it?",
            "Anything from a simple website to a complex web app!",
        ),
    ]
    return rx.box(*[styled_qa(question, answer) for question, answer in qa_pairs])


def styled_action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(placeholder="Ask a question", style=style.input_style),
        rx.button("Ask", style=style.button_style),
        width="100%",
    )
```

```python demo box
rx.center(
    rx.vstack(
        styled_chat(),
        styled_action_bar(),
        align="center",
    )
)
```

```python
# chatapp.py
import reflex as rx

from chatapp import style


def qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(rx.text(question, style=style.question_style), text_align="right"),
        rx.box(rx.text(answer, style=style.answer_style), text_align="left"),
        margin_y="1em",
        width="100%",
    )


def chat() -> rx.Component:
    qa_pairs = [
        ("What is Reflex?", "A way to build web apps in pure Python!"),
        (
            "What can I make with it?",
            "Anything from a simple website to a complex web app!",
        ),
    ]
    return rx.box(*[qa(question, answer) for question, answer in qa_pairs])


def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(placeholder="Ask a question", style=style.input_style),
        rx.button("Ask", style=style.button_style),
        width="100%",
    )


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            chat(),
            action_bar(),
            align="stretch",
            width="100%",
            max_width="48em",
            padding="1em",
        )
    )


app = rx.App()
app.add_page(index)
```

The app is looking good, but it's not very useful yet! In the next section, we will add some functionality to the app.

## State

Now let’s make the chat app interactive by adding state. The state is where we define all the variables that can change in the app and all the functions that can modify them. You can learn more about state in the [state docs](/docs/state/overview/).

### Defining State

We will create a new file called `state.py` in the `chatapp` directory. Our state will keep track of the current question being asked and the chat history. We will also define an event handler `answer` which will process the current question and add the answer to the chat history.

```python
# state.py
import reflex as rx


class State(rx.State):
    # The current question being asked.
    question: str = ""

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]] = []

    @rx.event
    def set_question(self, value: str):
        self.question = value

    @rx.event
    def answer(self):
        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, answer))
```

### Binding State to Components

Now we can import the state in `chatapp.py` and reference it in our frontend components. We will modify the `chat` component to use the state instead of the current fixed questions and answers.

```python exec
class BasicChatState(rx.State):
    question: str = ""
    chat_history: list[tuple[str, str]] = []

    @rx.event
    def set_question(self, value: str):
        self.question = value

    @rx.event
    def answer(self):
        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, answer))


def qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(rx.text(question, style=style.question_style), text_align="right"),
        rx.box(rx.text(answer, style=style.answer_style), text_align="left"),
        margin_y="1em",
        width="100%",
    )


def basic_chat() -> rx.Component:
    return rx.box(
        rx.foreach(
            BasicChatState.chat_history, lambda messages: qa(messages[0], messages[1])
        )
    )


def basic_action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            placeholder="Ask a question",
            on_change=BasicChatState.set_question,
            style=style.input_style,
        ),
        rx.button("Ask", on_click=BasicChatState.answer, style=style.button_style),
        width="100%",
    )
```

```python demo box
rx.container(
    basic_chat(),
    basic_action_bar(),
)
```

```python
# chatapp.py
from chatapp.state import State


def chat() -> rx.Component:
    return rx.box(
        rx.foreach(State.chat_history, lambda messages: qa(messages[0], messages[1]))
    )


def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            placeholder="Ask a question",
            on_change=State.set_question,
            style=style.input_style,
        ),
        rx.button("Ask", on_click=State.answer, style=style.button_style),
        width="100%",
    )
```

Normal Python `for` loops don't work for iterating over state vars because these values can change and aren't known at compile time. Instead, we use the [foreach](/docs/library/dynamic-rendering/foreach/) component to iterate over the chat history.

We also bind the input's `on_change` event to the `set_question` event handler, which will update the `question` state var while the user types in the input. We bind the button's `on_click` event to the `answer` event handler, which will process the question and add the answer to the chat history.

### Clearing the Input

Currently the input doesn't clear after the user clicks the button. We can fix this by binding the value of the input to `question`, with `value=State.question`, and clear it when we run the event handler for `answer`, with `self.question = ''`.

```python exec
class ClearingChatState(rx.State):
    question: str = ""
    chat_history: list[tuple[str, str]] = []

    @rx.event
    def set_question(self, value: str):
        self.question = value

    @rx.event
    def answer(self):
        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, answer))
        # Clear the question input.
        self.question = ""


def clearing_chat() -> rx.Component:
    return rx.box(
        rx.foreach(
            ClearingChatState.chat_history,
            lambda messages: qa(messages[0], messages[1]),
        )
    )


def clearing_action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=ClearingChatState.question,
            placeholder="Ask a question",
            on_change=ClearingChatState.set_question,
            style=style.input_style,
        ),
        rx.button("Ask", on_click=ClearingChatState.answer, style=style.button_style),
        width="100%",
    )
```

```python demo box
rx.container(
    clearing_chat(),
    clearing_action_bar(),
)
```

```python
# chatapp.py
def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=State.question,
            placeholder="Ask a question",
            on_change=State.set_question,
            style=style.input_style,
        ),
        rx.button("Ask", on_click=State.answer, style=style.button_style),
        width="100%",
    )
```

Replace the existing `answer` method inside `State`:

```python
# state.py
@rx.event
def answer(self):
    # Our chatbot is not very smart right now...
    answer = "I don't know!"
    self.chat_history.append((self.question, answer))
    self.question = ""
```

### Streaming Text

Add `import asyncio` at the top of `state.py` and replace the `answer` method **inside `State`** with the method below. This step simulates streaming with a fixed response; it does not call a model yet.

Normally state updates are sent to the frontend when an event handler returns. However, we want to stream the text from the chatbot as it is generated. We can do this by yielding from the event handler. See the [yield events docs](/docs/events/yield-events/) for more info.

```python exec
import asyncio


class StreamingChatState(rx.State):
    question: str = ""
    chat_history: list[tuple[str, str]] = []

    @rx.event
    def set_question(self, value: str):
        self.question = value

    @rx.event
    async def answer(self):
        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, ""))
        # Clear the question input.
        self.question = ""
        # Yield here to clear the frontend input before continuing.
        yield

        for i in range(len(answer)):
            await asyncio.sleep(0.1)
            self.chat_history[-1] = (self.chat_history[-1][0], answer[: i + 1])
            yield


def streaming_chat() -> rx.Component:
    return rx.box(
        rx.foreach(
            StreamingChatState.chat_history,
            lambda messages: qa(messages[0], messages[1]),
        )
    )


def streaming_action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=StreamingChatState.question,
            placeholder="Ask a question",
            on_change=StreamingChatState.set_question,
            style=style.input_style,
        ),
        rx.button("Ask", on_click=StreamingChatState.answer, style=style.button_style),
        width="100%",
    )
```

```python demo box
rx.container(
    streaming_chat(),
    streaming_action_bar(),
)
```

```python
# state.py
import asyncio


@rx.event
async def answer(self):
    # Our chatbot is not very smart right now...
    answer = "I don't know!"
    self.chat_history.append((self.question, ""))

    # Clear the question input.
    self.question = ""
    # Yield here to clear the frontend input before continuing.
    yield

    for i in range(len(answer)):
        # Pause to show the streaming effect.
        await asyncio.sleep(0.1)
        # Add one letter at a time to the output.
        self.chat_history[-1] = (self.chat_history[-1][0], answer[: i + 1])
        yield
```

In the next section, we will finish our chatbot by adding AI!

## Final App

We will connect OpenAI's API to turn the interface into a working AI assistant. The Python SDK sends the prompt to a language model and streams the response into the chat history.

### Configure OpenAI

First, configure access to the OpenAI API and install the `openai` Python SDK:

```bash
uv add openai
```

Stop the development server, then set your API key in the same terminal before restarting it. On macOS or Linux:

```bash
export OPENAI_API_KEY="sk-..."
```

For PowerShell, use `$env:OPENAI_API_KEY="your-api-key"`. Restart with `uv run reflex run`. Keep the key in the backend environment; do not put it in frontend code or commit it to the repository. The examples below use `gpt-4o-mini`; your API project must have access to that model.

> **Using another AI provider?** You can keep the same chat interface and state structure while adapting the `answer` event handler for Anthropic, Google Gemini, or Cohere. Use the provider's Python SDK, credentials, request format, and streaming response format. Changing only the model name is not enough when switching between different APIs.

### Using the API

Replace `state.py` with the complete state class below. It adds `processing` to prevent duplicate requests and `error` to display failures. Replace `action_bar` and `index` in `chatapp.py` with the versions below. The input and button reflect `State.processing`, and the alert beneath them displays `State.error`. Keep app registration after these functions.

1. First, the user types a prompt that is updated via the `on_change` event handler.
2. Next, when a prompt is ready, the user can choose to submit it by clicking the `Ask` button which in turn triggers the `State.answer` method inside our `state.py` file.
3. The handler sends the current question and earlier conversation turns to OpenAI, then appends each text chunk to the visible answer.

```python
# chatapp.py
def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=State.question,
            disabled=State.processing,
            placeholder="Ask a question",
            # on_change event updates the input as the user types a prompt.
            on_change=State.set_question,
            style=style.input_style,
        ),
        # on_click event triggers the API to send the prompt to OpenAI.
        rx.button(
            "Ask",
            on_click=State.answer,
            loading=State.processing,
            style=style.button_style,
        ),
        width="100%",
    )


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            chat(),
            action_bar(),
            rx.cond(State.error != "", rx.text(State.error, color="red", role="alert")),
            width="100%",
            max_width="48em",
            padding="1em",
            align="stretch",
        )
    )
```

```python
# state.py
import os

import reflex as rx
from openai import APIError, AsyncOpenAI


class State(rx.State):
    question: str = ""
    chat_history: list[tuple[str, str]] = []
    processing: bool = False
    error: str = ""

    @rx.event
    def set_question(self, value: str):
        self.question = value

    @rx.event
    async def answer(self):
        question = self.question.strip()
        if not question or self.processing:
            return

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self.error = "Set OPENAI_API_KEY and restart the app."
            return

        messages = []
        for previous_question, previous_answer in self.chat_history:
            messages.append({"role": "user", "content": previous_question})
            messages.append({"role": "assistant", "content": previous_answer})
        messages.append({"role": "user", "content": question})

        self.processing = True
        self.error = ""
        self.question = ""
        self.chat_history.append((question, ""))
        yield

        try:
            async with AsyncOpenAI(api_key=api_key) as client:
                stream = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    stream=True,
                )
                async with stream:
                    async for chunk in stream:
                        if not chunk.choices:
                            continue
                        text = chunk.choices[0].delta.content
                        if text:
                            previous = self.chat_history[-1][1]
                            self.chat_history[-1] = (question, previous + text)
                            yield
        except APIError:
            self.chat_history.pop()
            self.question = question
            self.error = "The request failed. Check your API access and try again."
        finally:
            self.processing = False
            yield
```

The handler skips chunks without text rather than treating them as the end of the response; see [OpenAI streaming documentation](https://developers.openai.com/api/docs/guides/streaming-responses). Both the client and stream are closed with async context managers. On API failure, the unfinished turn is removed and the question is restored for retry.

For longer conversations, add a history limit or summarization so requests stay within the model's context window. This tutorial keeps conversation history in session state, not persistent storage.

### Final Code

Inside the generated `chatapp/` package, the finished project is split across three files — `chatapp.py` for UI and app setup, `state.py` for state and API integration, and `style.py` for styling:

```text
chatapp/
├── chatapp.py
├── state.py
└── style.py
```

The `chatapp.py` file:

```python
import reflex as rx
from chatapp import style
from chatapp.state import State


def qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(rx.text(question, style=style.question_style), text_align="right"),
        rx.box(rx.text(answer, style=style.answer_style), text_align="left"),
        margin_y="1em",
    )


def chat() -> rx.Component:
    return rx.box(
        rx.foreach(
            State.chat_history,
            lambda messages: qa(messages[0], messages[1]),
        )
    )


def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=State.question,
            disabled=State.processing,
            placeholder="Ask a question",
            on_change=State.set_question,
            style=style.input_style,
        ),
        rx.button(
            "Ask",
            on_click=State.answer,
            loading=State.processing,
            style=style.button_style,
        ),
        width="100%",
    )


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            chat(),
            action_bar(),
            rx.cond(State.error != "", rx.text(State.error, color="red", role="alert")),
            width="100%",
            max_width="48em",
            padding="1em",
            align="stretch",
        )
    )


app = rx.App()
app.add_page(index)
```

The `state.py` file:

```python
import os

import reflex as rx
from openai import APIError, AsyncOpenAI


class State(rx.State):
    question: str = ""
    chat_history: list[tuple[str, str]] = []
    processing: bool = False
    error: str = ""

    @rx.event
    def set_question(self, value: str):
        self.question = value

    @rx.event
    async def answer(self):
        question = self.question.strip()
        if not question or self.processing:
            return

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self.error = "Set OPENAI_API_KEY and restart the app."
            return

        messages = []
        for previous_question, previous_answer in self.chat_history:
            messages.append({"role": "user", "content": previous_question})
            messages.append({"role": "assistant", "content": previous_answer})
        messages.append({"role": "user", "content": question})

        self.processing = True
        self.error = ""
        self.question = ""
        self.chat_history.append((question, ""))
        yield

        try:
            async with AsyncOpenAI(api_key=api_key) as client:
                stream = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    stream=True,
                )
                async with stream:
                    async for chunk in stream:
                        if not chunk.choices:
                            continue
                        text = chunk.choices[0].delta.content
                        if text:
                            previous = self.chat_history[-1][1]
                            self.chat_history[-1] = (question, previous + text)
                            yield
        except APIError:
            self.chat_history.pop()
            self.question = question
            self.error = "The request failed. Check your API access and try again."
        finally:
            self.processing = False
            yield
```

The `style.py` file:

```python
# style.py
import reflex as rx

chat_margin = "12%"
message_style = dict(
    padding="0.875em 1em",
    border_radius="16px",
    margin_y="0.5em",
    max_width="34em",
    display="inline-block",
    overflow_wrap="anywhere",
    line_height="1.65",
    font_size="0.95rem",
    text_align="left",
)
question_style = message_style | dict(
    margin_left=chat_margin,
    background_color=rx.color("accent", 3),
    color=rx.color("accent", 12),
    border=f"1px solid {rx.color('accent', 5)}",
)
answer_style = message_style | dict(
    margin_right=chat_margin,
    background_color=rx.color("slate", 2),
    color=rx.color("slate", 12),
    border=f"1px solid {rx.color('slate', 4)}",
)
input_style = dict(
    width="100%",
    min_width="0",
    flex="1",
    height="44px",
    border_radius="12px",
    background_color=rx.color("slate", 1),
    border=f"1px solid {rx.color('slate', 7)}",
    box_shadow="none",
    **{
        "& input": {
            "padding": "0 14px",
            "font_size": "14px",
            "border": "none",
            "outline": "none",
            "box_shadow": "none",
            "background": "transparent",
        },
        "& input::placeholder": {"color": rx.color("slate", 11)},
        "&:focus-within": {
            "border_color": rx.color("accent", 8),
            "box_shadow": f"0 0 0 3px {rx.color('accent', 3)}",
        },
    },
)
button_style = dict(
    flex_shrink="0",
    height="44px",
    padding="0 20px",
    border_radius="12px",
    font_weight="600",
    background_color=rx.color("accent", 9),
    color="white",
    cursor="pointer",
    _hover={"background_color": rx.color("accent", 10)},
    _disabled={"opacity": "0.65", "cursor": "not-allowed"},
)
```

### Next Steps

Run `uv run reflex run`, submit a question, and ask a follow-up that refers to the first answer. You should see the response appear incrementally, the input disabled during generation, and the conversation retained for follow-up requests. A missing API key or failed request should leave a readable error and allow you to retry.

### Deploy your app

With our hosting service, you can deploy this app with a single command within minutes. Check out our [Hosting Quick Start](https://reflex.dev/docs/hosting/deploy-quick-start/).

## Build an internal AI assistant over your documents

The same chat interface can become the starting point for an assistant that answers questions from company documents. Add a retrieval step to the `answer` handler, select relevant passages, and include them with the user's question in the model request. This is commonly called retrieval-augmented generation (RAG). Document ingestion, retrieval, and access controls are additional work beyond this tutorial.

## FAQ

```md faq
# Which Python framework can I use to build an AI assistant with a custom user interface?

Reflex lets you write a chatbot's UI, state, and event handlers in Python. This tutorial uses ordinary components for the conversation and input controls, so you can customize the interface while using an async event handler to stream model responses.
```

```md faq
# Can I use Anthropic, Gemini, or another AI provider instead of OpenAI?

Yes. Reuse the chat components and state structure, then adapt the `answer` handler to the provider's SDK, authentication, message format, and stream events. The OpenAI integration shown here is one implementation of that pattern.
```

```md faq
# How is this different from a general-purpose AI chatbot?

This tutorial builds a general-purpose chatbot with a custom interface. To make it a task-specific AI assistant, add instructions, document retrieval, or integrations for the task you want it to perform. The UI and streaming state pattern provide a starting point; those additional capabilities are not included in the example.
```
