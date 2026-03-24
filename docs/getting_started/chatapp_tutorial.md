```python exec
import os

import reflex as rx
import openai

from pcweb.constants import CHAT_APP_URL
from pcweb import constants
from pcweb.pages.docs import components
from pcweb.pages.docs import styling
from pcweb.pages.docs import library
from pcweb.pages.docs import events
from pcweb.pages.docs import state
from pcweb.pages.docs import hosting

from docs.getting_started import chat_tutorial_style as style
from docs.getting_started.chat_tutorial_utils import ChatappState

# If it's in environment, no need to hardcode (openai SDK will pick it up)
if "OPENAI_API_KEY" not in os.environ:
    openai.api_key = "YOUR_OPENAI_KEY"

```

# Interactive Tutorial: AI Chat App

This tutorial will walk you through building an AI chat app with Reflex. This app is fairly complex, but don't worry - we'll break it down into small steps.

You can find the full source code for this app [here]({CHAT_APP_URL}).

### What You'll Learn

In this tutorial you'll learn how to:

1. Install `reflex` and set up your development environment.
2. Create components to define and style your UI.
3. Use state to add interactivity to your app.
4. Deploy your app to share with others.




## Setting up Your Project

```md video https://youtube.com/embed/ITOZkzjtjUA?start=175&end=445
# Video: Example of Setting up the Chat App
```

We will start by creating a new project and setting up our development environment. First, create a new directory for your project and navigate to it.

```bash
~ $ mkdir chatapp
~ $ cd chatapp
```

Next, we will create a virtual environment for our project. This is optional, but recommended. In this example, we will use [venv]({constants.VENV_URL}) to create our virtual environment.

```bash
chatapp $ python3 -m venv venv
$ source venv/bin/activate
```

Now, we will install Reflex and create a new project. This will create a new directory structure in our project directory.

> **Note:** When prompted to select a template, choose option 0 for a blank project.


```bash
chatapp $ pip install reflex
chatapp $ reflex init
────────────────────────────────── Initializing chatapp ───────────────────────────────────
Success: Initialized chatapp
chatapp $ ls
assets          chatapp         rxconfig.py     venv
```

```python eval
rx.box(height="20px")
```
You can run the template app to make sure everything is working.

```bash
chatapp $ reflex run
─────────────────────────────────── Starting Reflex App ───────────────────────────────────
Compiling:  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 1/1 0:00:00
─────────────────────────────────────── App Running ───────────────────────────────────────
App running at: http://localhost:3000
```

```python eval
rx.box(height="20px")
```

You should see your app running at [http://localhost:3000]({"http://localhost:3000"}).

Reflex also starts the backend server which handles all the state management and communication with the frontend. You can test the backend server is running by navigating to [http://localhost:8000/ping]({"http://localhost:8000/ping"}).

Now that we have our project set up, in the next section we will start building our app!




## Basic Frontend

Let's start with defining the frontend for our chat app. In Reflex, the frontend can be broken down into independent, reusable components. See the [components docs]({components.props.path}) for more information.

### Display A Question And Answer

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

We also add some basic styling to the components. Components take in keyword arguments, called [props]({components.props.path}), that modify the appearance and functionality of the component. We use the `text_align` prop to align the text to the left and right.

### Reusing Components

Now that we have a component that displays a single question and answer, we can reuse it to display multiple questions and answers. We will move the component to a separate function `question_answer` and call it from the `index` function.

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
        ("What can I make with it?", "Anything from a simple website to a complex web app!"),
    ]
    return rx.box(*[qa(question, answer) for question, answer in qa_pairs])


def index() -> rx.Component:
    return rx.container(chat())
```

### Chat Input

Now we want a way for the user to input a question. For this, we will use the [input]({library.forms.input.path}) component to have the user add text and a [button]({library.forms.button.path}) component to submit the question.

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

Let's add some styling to the app. More information on styling can be found in the [styling docs]({styling.overview.path}). To keep our code clean, we will move the styling to a separate file `chatapp/style.py`.

```python
# style.py
import reflex as rx

# Common styles for questions and answers.
shadow = "rgba(0, 0, 0, 0.15) 0px 2px 8px"
chat_margin = "20%"
message_style = dict(
    padding="1em",
    border_radius="5px",
    margin_y="0.5em",
    box_shadow=shadow,
    max_width="30em",
    display="inline-block",
)

# Set specific styles for questions and answers.
question_style = message_style | dict(margin_left=chat_margin, background_color=rx.color("gray", 4))
answer_style = message_style | dict(margin_right=chat_margin, background_color=rx.color("accent", 8))

# Styles for the action bar.
input_style = dict(
    border_width="1px", padding="0.5em", box_shadow=shadow,width="350px"
)
button_style = dict(background_color=rx.color("accent", 10), box_shadow=shadow)
```

We will import the styles in `chatapp.py` and use them in the components. At this point, the app should look like this:

```python exec
def qa4(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(rx.text(question, style=style.question_style), text_align="right"),
        rx.box(rx.text(answer, style=style.answer_style), text_align="left"),
        margin_y="1em",
        width="100%",
    )


def chat4() -> rx.Component:
    qa_pairs = [
        ("What is Reflex?", "A way to build web apps in pure Python!"),
        (
            "What can I make with it?",
            "Anything from a simple website to a complex web app!",
        ),
    ]
    return rx.box(*[qa4(question, answer) for question, answer in qa_pairs])


def action_bar4() -> rx.Component:
    return rx.hstack(
        rx.input(placeholder="Ask a question", style=style.input_style),
        rx.button("Ask", style=style.button_style),
    )
```

```python demo box
rx.center(
    rx.vstack(
        chat4(),
        action_bar4(),
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
        ("What can I make with it?", "Anything from a simple website to a complex web app!"),
    ]
    return rx.box(*[qa(question, answer) for question, answer in qa_pairs])


def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(placeholder="Ask a question", style=style.input_style),
        rx.button("Ask", style=style.button_style),
    )


def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            chat(),
            action_bar(),
            align="center",
        )
    )


app = rx.App()
app.add_page(index)
```

The app is looking good, but it's not very useful yet! In the next section, we will add some functionality to the app.






## State

Now let’s make the chat app interactive by adding state. The state is where we define all the variables that can change in the app and all the functions that can modify them. You can learn more about state in the [state docs]({state.overview.path}).

### Defining State

We will create a new file called `state.py` in the `chatapp` directory. Our state will keep track of the current question being asked and the chat history. We will also define an event handler `answer` which will process the current question and add the answer to the chat history.

```python
# state.py
import reflex as rx


class State(rx.State):

    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]]

    @rx.event
    def answer(self):
        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, answer))

```

### Binding State to Components

Now we can import the state in `chatapp.py` and reference it in our frontend components. We will modify the `chat` component to use the state instead of the current fixed questions and answers.

```python exec
def qa(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(rx.text(question, style=style.question_style), text_align="right"),
        rx.box(rx.text(answer, style=style.answer_style), text_align="left"),
        margin_y="1em",
        width="100%",
    )


def chat1() -> rx.Component:
    return rx.box(
        rx.foreach(
            ChatappState.chat_history, lambda messages: qa(messages[0], messages[1])
        )
    )


def action_bar1() -> rx.Component:
    return rx.hstack(
        rx.input(
            placeholder="Ask a question",
            on_change=ChatappState.set_question,
            style=style.input_style,
        ),
        rx.button("Ask", on_click=ChatappState.answer, style=style.button_style),
    )
```

```python demo box
rx.container(
    chat1(),
    action_bar1(),
)
```

```python
# chatapp.py
from chatapp.state import State


def chat() -> rx.Component:
    return rx.box(
        rx.foreach(
            State.chat_history,
            lambda messages: qa(messages[0], messages[1])
        )
    )



def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(placeholder="Ask a question", on_change=State.set_question1, style=style.input_style),
        rx.button("Ask", on_click=State.answer, style=style.button_style),
    )
```

Normal Python `for` loops don't work for iterating over state vars because these values can change and aren't known at compile time. Instead, we use the [foreach]({library.dynamic_rendering.foreach.path}) component to iterate over the chat history.

We also bind the input's `on_change` event to the `set_question` event handler, which will update the `question` state var while the user types in the input. We bind the button's `on_click` event to the `answer` event handler, which will process the question and add the answer to the chat history. The `set_question` event handler is a built-in implicitly defined event handler. Every base var has one. Learn more in the [events docs]({events.setters.path}) under the Setters section.

### Clearing the Input

Currently the input doesn't clear after the user clicks the button. We can fix this by binding the value of the input to `question`, with `value=State.question`, and clear it when we run the event handler for `answer`, with `self.question = ''`.

```python exec
def action_bar2() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=ChatappState.question,
            placeholder="Ask a question",
            on_change=ChatappState.set_question,
            style=style.input_style,
        ),
        rx.button("Ask", on_click=ChatappState.answer2, style=style.button_style),
    )
```

```python demo box
rx.container(
    chat1(),
    action_bar2(),
)
```

```python
# chatapp.py
def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=State.question,
            placeholder="Ask a question",
            on_change=State.set_question2,
            style=style.input_style),
        rx.button("Ask", on_click=State.answer, style=style.button_style),
    )
```

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

Normally state updates are sent to the frontend when an event handler returns. However, we want to stream the text from the chatbot as it is generated. We can do this by yielding from the event handler. See the [yield events docs]({events.yield_events.path}) for more info.

```python exec
def action_bar3() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=ChatappState.question,
            placeholder="Ask a question",
            on_change=ChatappState.set_question,
            style=style.input_style,
        ),
        rx.button("Ask", on_click=ChatappState.answer3, style=style.button_style),
    )
```

```python demo box
rx.container(
    chat1(),
    action_bar3(),
)
```

```python
# state.py
import asyncio

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
        self.chat_history[-1] = (self.chat_history[-1][0], answer[:i + 1])
        yield
```

In the next section, we will finish our chatbot by adding AI!



## Final App

We will use OpenAI's API to give our chatbot some intelligence.

### Configure the OpenAI API Key

First, ensure you have an active OpenAI subscription.
Next, install the latest openai package:
```bash
pip install --upgrade openai
```

Direct Configuration of API in Code

Update the state.py file to include your API key directly:

```python
# state.py
import os
from openai import AsyncOpenAI

import reflex as rx

# Initialize the OpenAI client
client = AsyncOpenAI(api_key="YOUR_OPENAI_API_KEY")  # Replace with your actual API key

```

### Using the API

Making your chatbot intelligent requires connecting to a language model API. This section explains how to integrate with OpenAI's API to power your chatbot's responses.

1. First, the user types a prompt that is updated via the `on_change` event handler.
2. Next, when a prompt is ready, the user can choose to submit it by clicking the `Ask` button which in turn triggers the `State.answer` method inside our `state.py` file.
3. Finally, if the method is triggered, the `prompt` is sent via a request to OpenAI client and returns an answer that we can trim and use to update the chat history!


```python
# chatapp.py
def action_bar() -> rx.Component:
    return rx.hstack(
        rx.input(
            value=State.question,
            placeholder="Ask a question",
            # on_change event updates the input as the user types a prompt.
            on_change=State.set_question3,
            style=style.input_style),

        # on_click event triggers the API to send the prompt to OpenAI.
        rx.button("Ask", on_click=State.answer, style=style.button_style),
    )
```

```python
# state.py
import os

from openai import AsyncOpenAI

@rx.event
async def answer(self):
    # Our chatbot has some brains now!
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    session = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            \{"role": "user", "content": self.question}
        ],
        stop=None,
        temperature=0.7,
        stream=True,
    )

    # Add to the answer as the chatbot responds.
    answer = ""
    self.chat_history.append((self.question, answer))

    # Clear the question input.
    self.question = ""
    # Yield here to clear the frontend input before continuing.
    yield

    async for item in session:
        if hasattr(item.choices[0].delta, "content"):
            if item.choices[0].delta.content is None:
                # presence of 'None' indicates the end of the response
                break
            answer += item.choices[0].delta.content
            self.chat_history[-1] = (self.chat_history[-1][0], answer)
            yield
```

Finally, we have our chatbot!

### Final Code

This application is a simple, interactive chatbot built with Reflex that leverages OpenAI's API for intelligent responses. The chatbot features a clean interface with streaming responses for a natural conversation experience.

Key Features

1. Real-time streaming responses
2. Clean, visually distinct chat bubbles for questions and answers
3. Simple input interface with question field and submit button

Project Structure

Below is the full chatbot code with a commented title that corresponds to the filename.

```text
chatapp/
├── chatapp.py    # UI components and app setup
├── state.py      # State management and API integration
└── style.py      # Styling definitions
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
            placeholder="Ask a question",
            on_change=State.set_question,
            style=style.input_style,
        ),
        rx.button(
            "Ask",
            on_click=State.answer,
            style=style.button_style,
        ),
    )

def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            chat(),
            action_bar(),
            align="center",
        )
    )

app = rx.App()
app.add_page(index)
```


The `state.py` file:

```python
import os
from openai import AsyncOpenAI
import reflex as rx

class State(rx.State):
    question: str
    chat_history: list[tuple[str, str]] = []

    async def answer(self):
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

        # Start streaming completion from OpenAI
        session = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                \{"role": "user", "content": self.question}
            ],
            temperature=0.7,
            stream=True,
        )

        # Initialize response and update UI
        answer = ""
        self.chat_history.append((self.question, answer))
        self.question = ""
        yield

        # Process streaming response
        async for item in session:
            if hasattr(item.choices[0].delta, "content"):
                if item.choices[0].delta.content is None:
                    break
                answer += item.choices[0].delta.content
                self.chat_history[-1] = (self.chat_history[-1][0], answer)
                yield
```


The `style.py` file:

```python
import reflex as rx

# Common style base
shadow = "rgba(0, 0, 0, 0.15) 0px 2px 8px"
chat_margin = "20%"
message_style = dict(
    padding="1em",
    border_radius="5px",
    margin_y="0.5em",
    box_shadow=shadow,
    max_width="30em",
    display="inline-block",
)

# Styles for questions and answers
question_style = message_style | dict(
    margin_left=chat_margin,
    background_color=rx.color("gray", 4),
)
answer_style = message_style | dict(
    margin_right=chat_margin,
    background_color=rx.color("accent", 8),
)

# Styles for input elements
input_style = dict(border_width="1px", padding="0.5em", box_shadow=shadow, width="350px")
button_style = dict(background_color=rx.color("accent", 10), box_shadow=shadow)
```


### Next Steps

Congratulations! You have built your first chatbot. From here, you can read through the rest of the documentations to learn about Reflex in more detail. The best way to learn is to build something, so try to build your own app using this as a starting point!

### One More Thing

With our hosting service, you can deploy this app with a single command within minutes. Check out our [Hosting Quick Start]({hosting.deploy_quick_start.path}).
