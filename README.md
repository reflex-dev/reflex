
## ⚙️ Installation

Open a terminal and run (Requires Python 3.7+):

```bash
pip install nextpy
```

## 🥳 Create your first app

Installing `nextpy` also installs the `nextpy` command line tool.

Test that the install was successful by creating a new project. (Replace `my_app_name` with your project name):

```bash
mkdir my_app_name
cd my_app_name
nextpy init
```

This command initializes a boilerplate app in your new directory. 

You can run this app in development mode:

```bash
nextpy run
```

You should see your app running at http://localhost:3000.

Now you can modify the source code in `my_app_name/my_app_name.py`. Nextpy has fast refreshes so you can see your changes instantly when you save your code.


## 🫧 Example App

Let's go over an example: creating an image generation UI around DALL·E. For simplicity, we just call the OpenAI API, but you could replace this with an ML model run locally.

&nbsp;



&nbsp;

Here is the complete code to create this. This is all done in one Python file!

```python
import nextpy as xt
from openai import OpenAI
client = OpenAI()


class State(xt.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Get the image from the prompt."""
        if self.prompt == "":
            return xt.window_alert("Prompt Empty")

        self.processing, self.complete = True, False
        yield
        response = client.images.generate(
            model="dall-e-3",
            prompt="a white siamese cat",
            size="1024x1024",
            quality="standard",
            n=1,
            )
        self.image_url = response.data[0].url
        self.processing, self.complete = False, True
        

def index():
    return xt.center(
        xt.vstack(
            xt.heading("DALL·E"),
            xt.input(placeholder="Enter a prompt", on_blur=State.set_prompt),
            xt.button(
                "Generate Image",
                on_click=State.get_image,
                is_loading=State.processing,
                width="100%",
            ),
            xt.cond(
                State.complete,
                     xt.image(
                         src=State.image_url,
                         height="25em",
                         width="25em",
                    )
            ),
            padding="2em",
            shadow="lg",
            border_radius="lg",
        ),
        width="100%",
        height="100vh",
    )

# Add state and page to the app.
app = xt.App()
app.add_page(index, title="nextpy:DALL·E")
app.compile()
```

## Let's break this down.

### **Nextpy UI**

Now let's explore the main components of the DALL·E image generation app.

### **The index Function**

```python
def index():
    return xt.center(
        ...
    )
```

This `index` function serves as the main entry point for defining the structure and content of the app's front-end user interface. This function utilizes Nextpy's declarative UI components to specify what the app should look like. When the app runs, whatever is returned by the index function is rendered on the screen.

We use different components such as `center`, `vstack`, `input`, and `button` to build the frontend. Components can be nested within each other
to create complex layouts. And you can use keyword args to style them with the full power of CSS.


### **State**

Nextpy represents your UI as a function of your state.

```python
class State(xt.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

The State class defines the reactive variables, or "vars," that store the application's data and state. In this example, we have:

- prompt: A string to capture user input for image generation.
- image_url: A string to store the URL of the generated image.
- processing: A boolean indicating whether the image generation is in progress.
- complete: A boolean that turns true when image processing is finished.

Here the state is comprised of a `prompt` and `image_url`. There are also the booleans `processing` and `complete` to indicate when to show the circular progress and image.

## State
```python
class State(xt.State):
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```
The State class defines the reactive variables, or "vars," that store the application's data and state. In this example, we have:

- `prompt`: A string to capture user input for image generation.
- `image_url`: A string to store the URL of the generated image.
- `processing`: A boolean indicating whether the image generation is in progress.
- `complete`: A boolean that turns true when image processing is finished.

Furthermore, the `State` class also contains event handlers that react to user-expressed actions, altering the state as required. The `get_image` event handler initiates image generation when a user submits a prompt, using the `yield` statement to refresh the UI whenever needed.

```python
def get_image(self):
    if self.prompt == "":
        return xt.window_alert("Prompt Empty")
    self.processing, self.complete = True, False
    yield
    response = client.images.generate(...)
    self.image_url = ...  # Extract image URL from response
    self.processing, self.complete = False, True
```


## App Configuration and Routing
```python
app = xt.App()
app.add_page(index, title="nextpy:DALL·E")
app.compile()
```
The app's configuration is established with an instance of `xt.App` which encapsulates the entire Nextpy application. The `index` function is added as the root page, and the `app.compile()` call prepares the app for execution.

This breakdown demonstrates how to structure a Nextpy application, implement state management, define event handlers, and construct a responsive UI, culminating in a deployable web application.
