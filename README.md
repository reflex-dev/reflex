<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg">
  <img alt="Reflex Logo" src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex.svg" width="300px">
</picture>

<hr>

### **✨ Performant, customizable web apps in pure Python. Deploy in seconds. ✨**

[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentation](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![PyPI Downloads](https://static.pepy.tech/badge/reflex)](https://pepy.tech/projects/reflex)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
[![Twitter](https://img.shields.io/twitter/follow/getreflex)](https://x.com/getreflex)

</div>

---

> [!NOTE]
> Build faster with Reflex:
>
> - **[AI Builder](https://build.reflex.dev/)** - Generate full-stack Reflex apps in seconds.
> - **[Agent Toolkit](https://reflex.dev/docs/ai/integrations/ai-onboarding/)** - Connect MCP and Skills to your coding assistant.
> - **[App Management](https://reflex.dev/hosting)** - Deploy and manage your Reflex apps.

---

# Introduction

Reflex is a library to build full-stack web apps in pure Python.

Key features:

- **Pure Python** - Write your app's frontend and backend all in Python, no need to learn Javascript.
- **Full Flexibility** - Reflex is easy to get started with, but can also scale to complex apps.

See our [architecture page](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) to learn how Reflex works under the hood.

## ⚙️ Installation

**Important:** We strongly recommend using a virtual environment to ensure the `reflex` command is available in your PATH.

## 🥳 Create your first app

Create a project, add Reflex, and start the development server with [uv](https://docs.astral.sh/uv/):

```shell
mkdir my_app_name
cd my_app_name
uv init

uv add reflex
uv run reflex init
uv run reflex run
```

You should see your app running at http://localhost:3000.

Now you can modify the source code in `my_app_name/my_app_name.py`. Reflex has fast refreshes so you can see your changes instantly when you save your code.

## 🫧 Example App

Build an image generation app in Python with Reflex: define the UI, manage state in a class, and call an image model from an event handler.

<div align="center">
<video src="https://github.com/user-attachments/assets/aaff28ad-8b3c-43bf-967e-439ee34c8a87" width="900" controls muted poster="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex-image-generation-app.png">
  <a href="https://web.reflex-assets.dev/video/reflex-dalle-video-2x.mp4">
    <img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex-image-generation-app.png" alt="Preview of an image generation app built with Reflex" width="900">
  </a>
</video>
</div>

```python
import reflex as rx
import openai

client = openai.AsyncOpenAI()


class State(rx.State):
    prompt: str = ""
    image_url: str = ""
    processing: bool = False

    @rx.event
    def set_prompt(self, value: str):
        self.prompt = value

    @rx.event
    async def generate(self):
        self.processing = True
        yield
        response = await client.images.generate(
            model="gpt-image-1.5",
            prompt=self.prompt,
        )
        self.image_url = f"data:image/png;base64,{response.data[0].b64_json}"
        self.processing = False


def index():
    return rx.vstack(
        rx.heading("Image Generator"),
        rx.input(placeholder="Enter a prompt...", on_change=State.set_prompt),
        rx.button("Generate", on_click=State.generate, loading=State.processing),
        rx.image(src=State.image_url),
    )


app = rx.App()
app.add_page(index, title="Reflex:Image Generation")
```

## All Thanks To Our Contributors:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>
