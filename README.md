<div align="center">

<h1 align="center">
  <img width="600" src="docs/images/logo.svg#gh-light-mode-only" alt="Pynecone Logo">
  <img width="600" src="docs/images/logo_white.svg#gh-dark-mode-only" alt="Pynecone Logo">
</h1>

**Build performant, customizable web apps in pure Python.**

[![PyPI version](https://badge.fury.io/py/pynecone.svg)](https://badge.fury.io/py/pynecone)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/build.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/pynecone-io.svg)
[![License](https://img.shields.io/badge/License-Apache_2.0-yellowgreen.svg)](https://opensource.org/licenses/Apache-2.0)  
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)

<div align="left">

## Getting Started

Pynecone is a full-stack Python framework that makes it easy to build and deploy web apps in minutes. All the information for getting started can be found in this README. However, a more detailed explanation of the following topics can be found on our website:

<div align="center">

### [Docs](https://pynecone.io/docs/getting-started/introduction) | [Component Library](https://pynecone.io/docs/library) | [Gallery](https://pynecone.io/docs/gallery) | [Deployment](https://pynecone.io/docs/hosting/deploy) 

<div align="left">

## Installation
  
Pynecone requires the following to get started:

* Python 3.7+
* [Node.js 12.22.0+](https://nodejs.org/en/) (Don't worry, you'll never have to write any Javascript)

```
$ pip install pynecone
```

## Create your first Pynecone App

Installing Pynecone also installs the `pc` command line tool. Test that the install was successful by creating a new project. 

Replace my_app_name with your project name:

```
$ mkdir my_app_name
$ cd my_app_name
$ pc init
```

When you run this command for the first time, we will download and install [bun](https://bun.sh/) automatically.

This command initializes a template app in your new directory.
You can run this app in development mode:
```
$ pc run
```

You should see your app running at http://localhost:3000.


Now you can modify the source code in `my_app_name/my_app_name.py`. Pynecone has fast refreshes so you can see your changes instantly when you save your code.


## Example Pynecone App

Let's go over an example of creating a UI around DALL·E. For simplicity of the example below, we call the OpenAI DALL·E API, but you could replace this with any ML model locally.

<div align="center">
<img src="docs/images/dalle.gif" alt="drawing" width="550" style="border-radius:2%"/>
<div align="left">

Here is the complete code to create this. This is all done in one Python file!

```python
import pynecone as pc
import openai

openai.api_key = "YOUR_API_KEY"

class State(pc.State):
    """The app state."""
    prompt = ""
    image_url = ""
    image_processing = False
    image_made = False

    def process_image(self):
        """Set the image processing flag to true and indicate image is not made yet."""
        self.image_processing = True
        self.image_made = False        

    def get_image(self):
        """Get the image from the prompt."""
        response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
        self.image_url = response["data"][0]["url"]
        self.image_processing = False
        self.image_made = True

def index():
    return pc.center(
        pc.vstack(
            pc.heading("DALL·E", font_size="1.5em"),
            pc.input(placeholder="Enter a prompt..", on_blur=State.set_prompt),
            pc.button(
                "Generate Image",
                on_click=[State.process_image, State.get_image],
                width="100%",
            ),
            pc.divider(),
            pc.cond(
                State.image_processing,
                pc.circular_progress(is_indeterminate=True),
                pc.cond(
                     State.image_made,
                     pc.image(
                         src=State.image_url,
                         height="25em",
                         width="25em",
                    )
                )
            ),
            bg="white",
            padding="2em",
            shadow="lg",
            border_radius="lg",
        ),
        width="100%",
        height="100vh",
        bg="radial-gradient(circle at 22% 11%,rgba(62, 180, 137,.20),hsla(0,0%,100%,0) 19%)",
    )

# Add state and page to the app.
app = pc.App(state=State)
app.add_page(index, title="Pynecone:DALL·E")
app.compile()
```
Let's break this down.

### **UI In Pynecone**

Lets start by talking about the UI this Pynecone App.

```python 
def index():
    return pc.center(
        ...
    )
```
This index function defines the frontend of the app. We use different components such as `center`, `vstack`, `input`, and `button` to build the front end. Components can be nested to create complex layouts and styled using CSS's full power. Just pass them in as keyword args.

Pynecone comes with [50+ built-in components](https://pynecone.io/docs/library) to help you get started. We are actively adding more components, plus it's easy to create your own components.

### **State**

``` python
class State(pc.State):
    """The app state."""
    prompt = ""
    image_url = ""
    image_processing = False
    image_made = False
```
The state defines all the variables (called vars) in an app that can change and the functions that change them.
Here the state is comprised of a `prompt` and `image_url`. There are also the booleans `image_processing` and `image_made` to indicate when to show the circular progress and image.

### **Event Handlers**

```python
    def process_image(self):
        """Set the image processing flag to true and indicate image is not made yet."""
        self.image_processing = True
        self.image_made = False        

    def get_image(self):
        """Get the image from the prompt."""
        response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
        self.image_url = response["data"][0]["url"]
        self.image_processing = False
        self.image_made = True
```
Within the state, we define functions called event handlers that change the state vars. Event handlers are the way that we can modify the state in Pynecone. They can be called in response to user actions, such as clicking a button or typing in a text box. These actions are called events.

Our DALL·E. app has two event handlers, `process_image` to indicate that the image is being generated and `get_image`, which calls the OpenAI API.

### **Routing** 

Finally we define our app and tell it what state to use.
```python
app = pc.App(state=State)
```
We add a route from the root of the app to the index component. We also add a title that will show up in the page preview/ browser tab.
```python
app.add_page(index, title="Pynecone:DALL-E")
app.compile()
```
You can create a multi-page app by adding more routes.

## Status

As of December 2022, Pynecone has just been released publicly and is in the **Alpha Stage**.

 - :large_orange_diamond: **Public Alpha**: Anyone can install and use Pynecone. There may be issues, but we are working to resolve them actively.
 - **Public Beta**: Stable enough for non-enterprise use-cases.
 - **Public Hosting Beta**: **Optionally** Deploy and Host your own apps on Pynecone!
 - **Public**: Pynecone is production ready.

Pynecone has new releases and features coming every week! Make sure to: :star: star and :eyes: watch this repository to stay up to date.
 
## Contributing

We welcome contributions of any size! Below are some good ways to get started in the Pynecone community.

- **Join Our Discord**: Our [Discord](https://discord.gg/T5WSbC2YtQ) is the best place to get help on your Pynecone project and to discuss how you can contribute.
- **GitHub Discussions**: A great way to talk about features you want added or things that are confusing/need clarification.
- **GitHub Issues**: These are an excellent way to report bugs. Additionally, you can try and solve an existing issue and submit a PR.

We are actively looking for contributors, no matter your skill level or experience.

## License

Pynecone is open-source and licensed under the [Apache License 2.0](LICENSE).
