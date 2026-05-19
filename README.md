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
> 🚀 **Try [Reflex Build](https://build.reflex.dev/)** – our AI-powered app builder that generates full-stack Reflex applications in seconds.

---

# Introduction

Reflex is a library to build full-stack web apps in pure Python.

Key features:

- **Pure Python** - Write your app's frontend and backend all in Python, no need to learn Javascript.
- **Full Flexibility** - Reflex is easy to get started with, but can also scale to complex apps.
- **Deploy Instantly** - After building, deploy your app with a [single command](https://reflex.dev/docs/hosting/deploy-quick-start/) or host it on your own server.

See our [architecture page](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) to learn how Reflex works under the hood.

## ⚙️ Installation

**Important:** We strongly recommend using a virtual environment to ensure the `reflex` command is available in your PATH.

## 🥳 Create your first app

### 1. Create the project directory

Replace `my_app_name` with your project name:

```bash
mkdir my_app_name
cd my_app_name
```

### 2. Install uv

Reflex recommends [uv](https://docs.astral.sh/uv/) for managing your project environment and dependencies.
See the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for your platform.

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Initialize the Python project

```bash
uv init
```

### 4. Add Reflex

Reflex requires Python 3.10+:

```bash
uv add reflex
```

### 5. Initialize the project

This command initializes a template app in your new directory:

```bash
uv run reflex init
```

### 6. Run the app

You can run this app in development mode:

```bash
uv run reflex run
```

You should see your app running at http://localhost:3000.

Now you can modify the source code in `my_app_name/my_app_name.py`. Reflex has fast refreshes so you can see your changes instantly when you save your code.

### Troubleshooting

If the `reflex` command is not on your PATH, run it through uv instead: `uv run reflex init` and `uv run reflex run`

## 🫧 Example App

Build an image generation app in Python with Reflex: define the UI, manage state in a class, and call an image model from an event handler.

<div align="center">
<video src="https://github.com/user-attachments/assets/aaff28ad-8b3c-43bf-967e-439ee34c8a87" width="900" controls muted poster="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex-image-generation-app.png">
  <a href="https://github.com/user-attachments/assets/aaff28ad-8b3c-43bf-967e-439ee34c8a87">
    <img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex-image-generation-app.png" alt="Preview of an image generation app built with Reflex" width="900">
  </a>
</video>
</div>

## 📑 Resources

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; | &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; | &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; | &nbsp; 🖼️ [Templates](https://reflex.dev/templates/) &nbsp; | &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy-quick-start) &nbsp;

</div>

## ✅ Status

Reflex launched in December 2022 with the name Pynecone.

🚀 Introducing [Reflex Build](https://build.reflex.dev/) — Our AI-Powered Builder
Reflex Build uses AI to generate complete full-stack Python applications. It helps you quickly create, customize, and refine your Reflex apps — from frontend components to backend logic — so you can focus on your ideas instead of boilerplate code. Whether you’re prototyping or scaling, Reflex Build accelerates development by intelligently scaffolding and optimizing your app’s entire stack.

Alongside this, [Reflex Cloud](https://cloud.reflex.dev) launched in 2025 to offer the best hosting experience for your Reflex apps. We’re continuously improving the platform with new features and capabilities.

Reflex has new releases and features coming every week! Make sure to :star: star and :eyes: watch this repository to stay up to date.

## Contributing

We welcome contributions of any size! Below are some good ways to get started in the Reflex community.

- **Join Our Discord**: Our [Discord](https://discord.gg/T5WSbC2YtQ) is the best place to get help on your Reflex project and to discuss how you can contribute.
- **GitHub Discussions**: A great way to talk about features you want added or things that are confusing/need clarification.
- **GitHub Issues**: [Issues](https://github.com/reflex-dev/reflex/issues) are an excellent way to report bugs. Additionally, you can try and solve an existing issue and submit a PR.

We are actively looking for contributors, no matter your skill level or experience. To contribute check out [CONTRIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md)

## All Thanks To Our Contributors:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## License

Reflex is open-source and licensed under the [Apache License 2.0](https://raw.githubusercontent.com/reflex-dev/reflex/main/LICENSE).
