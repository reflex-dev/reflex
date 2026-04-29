# How Reflex Works

We'll use the following basic app that displays Github profile images as an example to explain the different parts of the architecture.

```python demo exec
import requests
import reflex as rx


class GithubState(rx.State):
    url: str = "https://github.com/reflex-dev"
    profile_image: str = "https://avatars.githubusercontent.com/u/104714959"

    @rx.event
    def set_profile(self, username: str):
        if username == "":
            return
        try:
            github_data = requests.get(
                f"https://api.github.com/users/{username}"
            ).json()
        except:
            return
        self.url = github_data["url"]
        self.profile_image = github_data["avatar_url"]


def index():
    return rx.hstack(
        rx.link(
            rx.avatar(src=GithubState.profile_image),
            href=GithubState.url,
        ),
        rx.input(
            placeholder="Your Github username",
            on_blur=GithubState.set_profile,
        ),
    )
```

## The Reflex Architecture

Full-stack web apps are made up of a frontend and a backend. The frontend is the user interface, and is served as a web page that runs on the user's browser. The backend handles the logic and state management (such as databases and APIs), and is run on a server.

In traditional web development, these are usually two separate apps, and are often written in different frameworks or languages. For example, you may combine a Flask backend with a React frontend. With this approach, you have to maintain two separate apps and end up writing a lot of boilerplate code to connect the frontend and backend.

We wanted to simplify this process in Reflex by defining both the frontend and backend in a single codebase, while using Python for everything. Developers should only worry about their app's logic and not about the low-level implementation details.

### TLDR

Under the hood, Reflex apps compile down to a [React](https://react.dev) frontend app and a [FastAPI](https://github.com/tiangolo/fastapi) backend app. Only the UI is compiled to Javascript; all the app logic and state management stays in Python and is run on the server. Reflex uses [WebSockets](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) to send events from the frontend to the backend, and to send state updates from the backend to the frontend.

The diagram below provides a detailed overview of how a Reflex app works. We'll go through each part in more detail in the following sections.


```python eval
rx.el.a(
    rx.image(src="https://web.reflex-assets.dev/other/architecture.webp"),
    href="https://web.reflex-assets.dev/other/architecture.webp",
    target="_blank",
)
```

```python eval
rx.box(height="1em")
```

## Frontend

We wanted Reflex apps to look and feel like a traditional web app to the end user, while still being easy to build and maintain for the developer. To do this, we built on top of mature and popular web technologies.

When you run `uv run reflex run`, Reflex compiles the frontend down to a single-page [Next.js](https://nextjs.org) app and serves it on a port (by default `3000`) that you can access in your browser.

The frontend's job is to reflect the app's state, and send events to the backend when the user interacts with the UI. No actual logic is run on the frontend.

### Components

Reflex frontends are built using components that can be composed together to create complex UIs. Instead of using a templating language that mixes HTML and Python, we just use Python functions to define the UI.

```python
def index():
    return rx.hstack(
        rx.link(
            rx.avatar(src=GithubState.profile_image),
            href=GithubState.url,
        ),
        rx.input(
            placeholder="Your Github username",
            on_blur=GithubState.set_profile,
        ),
    )
```

In our example app, we have components such as `rx.hstack`, `rx.avatar`, and `rx.input`. These components can have different **props** that affect their appearance and functionality - for example the `rx.input` component has a `placeholder` prop to display the default text.

We can make our components respond to user interactions with events such as `on_blur`, which we will discuss more below.

Under the hood, these components compile down to React components. For example, the above code compiles down to the following React code:

```jsx
<HStack>
    <Link href={GithubState.url}>
        <Avatar src={GithubState.profile_image}/>
    </Link>
    <Input
        placeholder="Your Github username"
        // This would actually be a websocket call to the backend.
        onBlur={GithubState.set_profile}
    >
</HStack>
```

Many of our core components are based on [Radix](https://radix-ui.com/), a popular React component library. We also have many other components for graphing, datatables, and more.

We chose React because it is a popular library with a huge ecosystem. Our goal isn't to recreate the web ecosystem, but to make it accessible to Python developers.

This also lets our users bring their own components if we don't have a component they need. Users can [wrap their own React components](/docs/wrapping-react/overview) and then [publish them](/docs/custom-components/overview) for others to use. Over time we will build out our [third party component ecosystem](/docs/custom-components/overview) so that users can easily find and use components that others have built.

### Styling

We wanted to make sure Reflex apps look good out of the box, while still giving developers full control over the appearance of their app.

We have a core [theming system](/docs/styling/theming) that lets you set high level styling options such as dark mode and accent color throughout your app to give it a unified look and feel.

Beyond this, Reflex components can be styled using the full power of CSS. We leverage the [Emotion](https://emotion.sh/docs/introduction) library to allow "CSS-in-Python" styling, so you can pass any CSS prop as a keyword argument to a component. This includes [responsive props](/docs/styling/responsive) by passing a list of values.

## Backend

Now let's look at how we added interactivity to our apps.

In Reflex only the frontend compiles to Javascript and runs on the user's browser, while all the state and logic stays in Python and is run on the server. When you run `uv run reflex run`, we start a FastAPI server (by default on port `8000`) that the frontend connects to through a websocket.

All the state and logic are defined within a `State` class.

```python
class GithubState(rx.State):
    url: str = "https://github.com/reflex-dev"
    profile_image: str = "https://avatars.githubusercontent.com/u/104714959"

    def set_profile(self, username: str):
        if username == "":
            return
        github_data = requests.get(f"https://api.github.com/users/{username}").json()
        self.url = github_data["url"]
        self.profile_image = github_data["avatar_url"]
```

The state is made up of **vars** and **event handlers**.

Vars are any values in your app that can change over time. They are defined as class attributes on your `State` class, and may be any Python type that can be serialized to JSON. In our example, `url` and `profile_image` are vars.

Event handlers are methods in your `State` class that are called when the user interacts with the UI. They are the only way that we can modify the vars in Reflex, and can be called in response to user actions, such as clicking a button or typing in a text box. In our example, `set_profile` is an event handler that updates the `url` and `profile_image` vars.

Since event handlers are run on the backend, you can use any Python library within them. In our example, we use the `requests` library to make an API call to Github to get the user's profile image.

## Event Processing

Now we get into the interesting part - how we handle events and state updates.

Normally when writing web apps, you have to write a lot of boilerplate code to connect the frontend and backend. With Reflex, you don't have to worry about that - we handle the communication between the frontend and backend for you. Developers just have to write their event handler logic, and when the vars are updated the UI is automatically updated.

You can refer to the diagram above for a visual representation of the process. Let's walk through it with our Github profile image example.

### Event Triggers

The user can interact with the UI in many ways, such as clicking a button, typing in a text box, or hovering over an element. In Reflex, we call these **event triggers**.

```python
rx.input(
    placeholder="Your Github username",
    on_blur=GithubState.set_profile,
)
```

In our example we bind the `on_blur` event trigger to the `set_profile` event handler. This means that when the user types in the input field and then clicks away, the `set_profile` event handler is called.

### Event Queue

On the frontend, we maintain an event queue of all pending events. An event consists of three major pieces of data:

- **client token**: Each client (browser tab) has a unique token to identify it. This let's the backend know which state to update.
- **event handler**: The event handler to run on the state.
- **arguments**: The arguments to pass to the event handler.

Let's assume I type my username "picklelo" into the input. In this example, our event would look something like this:

```json
{
  "client_token": "abc123",
  "event_handler": "GithubState.set_profile",
  "arguments": ["picklelo"]
}
```

On the frontend, we maintain an event queue of all pending events.

When an event is triggered, it is added to the queue. We have a `processing` flag to make sure only one event is processed at a time. This ensures that the state is always consistent and there aren't any race conditions with two event handlers modifying the state at the same time.

```md alert info
# There are exceptions to this, such as [background events](/docs/events/background_events) which allow you to run events in the background without blocking the UI.
```

Once the event is ready to be processed, it is sent to the backend through a WebSocket connection.

### State Manager

Once the event is received, it is processed on the backend.

Reflex uses a **state manager** which maintains a mapping between client tokens and their state. By default, the state manager is just an in-memory dictionary, but it can be extended to use a database or cache. In production we use Redis as our state manager.

### Event Handling

Once we have the user's state, the next step is to run the event handler with the arguments.

```python
def set_profile(self, username: str):
    if username == "":
        return
    github_data = requests.get(f"https://api.github.com/users/{username}").json()
    self.url = github_data["url"]
    self.profile_image = github_data["avatar_url"]
```

In our example, the `set_profile` event handler is run on the user's state. This makes an API call to Github to get the user's profile image, and then updates the state's `url` and `profile_image` vars.

### State Updates

Every time an event handler returns (or [yields](/docs/events/yield_events)), we save the state in the state manager and send the **state updates** to the frontend to update the UI.

To maintain performance as your state grows, internally Reflex keeps track of vars that were updated during the event handler (**dirty vars**). When the event handler is done processing, we find all the dirty vars and create a state update to send to the frontend.

In our case, the state update may look something like this:

```json
{
  "url": "https://github.com/picklelo",
  "profile_image": "https://avatars.githubusercontent.com/u/104714959"
}
```

We store the new state in our state manager, and then send the state update to the frontend. The frontend then updates the UI to reflect the new state. In our example, the new Github profile image is displayed.
