```python exec
import reflex as rx
from pcweb.pages.docs import components
from pcweb.pages.docs import styling
from pcweb.pages.docs import library
import docs.tutorial.tutorial_style as style
```

# Basic Frontend

Let's start with defining the frontend for our chat app. In Reflex, the frontend can be broken down into independent, reusable components. See the [components docs]({components.props.path}) for more information.

## Display A Question And Answer

We will modify the `index` function in `chatapp/chatapp.py` file to return a component that displays a single question and answer.

```python demo box
rx.fragment(
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

We also add some basic styling to the components. Components take in keyword arguments, called [props]({components.style_props.path}), that modify the appearance and functionality of the component. We use the `text_align` prop to align the text to the left and right.

## Reusing Components

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

## Chat Input

Now we want a way for the user to input a question. For this, we will use the [input]({library.chakra.forms.input.path}) component to have the user add text and a [button]({library.forms.button.path}) component to submit the question.

```python exec
def action_bar() -> rx.Component:
    return rx.hstack(
        rx.chakra.input(placeholder="Ask a question"),
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
        rx.chakra.input(placeholder="Ask a question"),
        rx.button("Ask"),
    )

def index() -> rx.Component:
    return rx.container(
        chat(),
        action_bar(),
    )
```

## Styling

Let's add some styling to the app. More information on styling can be found in the [styling docs]({styling.overview.path}). To keep our code clean, we will move the styling to a separate file `chatapp/style.py`.

```python
# style.py

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
question_style = message_style | dict(margin_left=chat_margin)
answer_style = message_style | dict(margin_right=chat_margin)

# Styles for the action bar.
input_style = dict(
    border_width="1px", padding="1em", box_shadow=shadow
)
button_style = dict(
    background_color="#CEFFEE", box_shadow=shadow
)
```

We will import the styles in `chatapp.py` and use them in the components. At this point, the app should look like this:

```python exec
def qa4(question: str, answer: str) -> rx.Component:
    return rx.box(
        rx.box(rx.text(question, style=style.question_style), background_color="#F5EFFE", text_align="right"),
        rx.box(rx.text(answer, style=style.answer_style), background_color="#DEEAFD", text_align="left"),
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
        rx.chakra.input(placeholder="Ask a question", style=style.input_style),
        rx.button("Ask", style=style.button_style),
    )
```

```python demo box
rx.container(
    chat4(),
    action_bar4(),
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
    )

def chat() -> rx.Component:
    qa_pairs = [
        ("What is Reflex?", "A way to build web apps in pure Python!"),
        ("What can I make with it?", "Anything from a simple website to a complex web app!"),
    ]
    return rx.box(*[qa(question, answer) for question, answer in qa_pairs])


def action_bar() -> rx.Component:
    return rx.hstack(
        rx.chakra.input(placeholder="Ask a question", style=style.input_style),
        rx.button("Ask", style=style.button_style),
    )


def index() -> rx.Component:
    return rx.container(
        chat(),
        action_bar(),
    )


app = rx.App()
app.add_page(index)
```

The app is looking good, but it's not very useful yet! In the next section, we will add some functionality to the app.
