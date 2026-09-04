# Skills

```python exec
import reflex as rx


def _summary_card(kicker: str, title: str, body: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(kicker, class_name="text-xs font-semibold uppercase text-primary-10"),
        rx.el.h3(title, class_name="text-base font-semibold text-secondary-12"),
        rx.el.p(body, class_name="text-sm leading-6 text-secondary-11"),
        class_name="flex flex-col gap-2 rounded-lg border border-secondary-a4 bg-white-1 p-4",
    )


def skills_summary_cards() -> rx.Component:
    return rx.el.div(
        _summary_card(
            "Docs",
            "Current Reflex guidance",
            "Point agents to the right Reflex docs for state, vars, components, routing, styling, deployment, and more.",
        ),
        _summary_card(
            "Setup",
            "Python environment workflow",
            "Teach agents how to create a virtual environment, install Reflex, and initialize a new project safely.",
        ),
        _summary_card(
            "Runtime",
            "Process management",
            "Give agents a repeatable way to compile, run, restart, and debug Reflex apps without guessing at processes.",
        ),
        _summary_card(
            "Context",
            "Pairs well with MCP",
            "Use skills for durable local instructions and MCP for structured lookup of current docs and component data.",
        ),
        class_name="grid grid-cols-1 gap-3 md:grid-cols-2 my-6",
    )
```

Reflex Agent Skills give AI coding assistants up-to-date guidance for building Reflex applications. They package Reflex-specific knowledge, setup steps, and process-management workflows into reusable `SKILL.md` files that agents can load when the conversation or codebase calls for them.

The skills are maintained in the [reflex-dev/agent-skills](https://github.com/reflex-dev/agent-skills) repository and are designed for agents that support the Agent Skills standard, including Claude Code, Cursor, OpenCode, OpenAI Codex, and Pi.

```python eval
skills_summary_cards()
```

## When to Use Skills

Use Reflex Agent Skills when you want an AI assistant to follow Reflex-specific workflows instead of relying only on general training data. They are especially useful when an assistant needs to:

- Build or edit a Reflex app.
- Set up a new Python environment.
- Decide which Reflex docs apply to the task.
- Compile, run, restart, or debug a local Reflex server.
- Keep generated code aligned with current Reflex patterns.

Skills load contextually. For example, when an assistant sees a Python file importing `reflex as rx`, it can load the Reflex docs skill. When you ask it to start a new app, it can load the Python environment setup skill before running project commands.

## Skills vs MCP

Skills and MCP solve related but different problems. For the best experience, use both.

```md definition
# Skills

Local instruction packs that tell the agent how to work with Reflex, which workflows to follow, and which references matter for common development tasks.

# MCP

Structured runtime access to Reflex documentation and component information through a hosted server. Use it when an agent or editor can call MCP tools directly.
```

```md alert info
# Use Skills for durable local guidance. Use MCP for structured documentation lookup and richer tool-assisted context.
```

## Installation

Choose the install path that matches your assistant.

`````md tabs

## Claude Code

Install the plugin from the Claude Code plugin marketplace:

```text
/plugin marketplace add reflex-dev/agent-skills
/plugin install reflex@reflex-agent-skills
```

Restart or refresh Claude Code after installation if the skills do not appear immediately.


## Cursor

Install from the Cursor Marketplace, or add the repository manually from:

```text
reflex-dev/agent-skills
```

In Cursor, add it through **Settings > Rules > Add Rule > Remote Rule (GitHub)**.


## CLI

If your environment supports the `skills` CLI, install the package with:

```bash
npx skills add reflex-dev/agent-skills
```

Use the CLI's update command later to keep the skill pack current.


## Manual

Clone the repository:

```bash
git clone https://github.com/reflex-dev/agent-skills.git
```

Then copy the folders inside `skills/` into the appropriate location:

| Agent | Skill Directory |
| --- | --- |
| Claude Code | `~/.claude/skills/` |
| Cursor | `~/.cursor/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| OpenAI Codex | `~/.codex/skills/` |
| Pi | `~/.pi/agent/skills/` |

Copy the skill folders themselves, not the parent `skills/` directory.

`````

## Included Skills

The Reflex skill pack includes three core skills.

`````md tabs

## Docs

The `reflex-docs` skill gives the assistant a Reflex-specific reference map and a summary of the framework's core concepts.

### Use this skill when the assistant is:

- Building full-stack Python web apps with Reflex.
- Writing files that import `reflex` or use the `rx` namespace.
- Creating components.
- Managing state, vars, computed vars, or event handlers.
- Working with routing, styling, database models, assets, authentication, client storage, API routes, custom components, or wrapped React components.

### It points the assistant to docs for:

- Core app structure: getting started, components, state and vars, events, pages, and routing.
- UI and styling: styling, assets, the component library, and recipes.
- Backend features: database models, authentication, client storage, API routes, and API reference.
- Advanced integrations: custom components and wrapped React components.

It also reminds the assistant to prefer current Reflex documentation over pre-trained knowledge when there is a conflict.


## Setup

The `setup-python-env` skill guides the assistant through setting up a Python environment for a Reflex app.

### Use this skill when:

- Starting a new Reflex project.
- Setting up a development environment.
- There is no `.venv` directory.
- Reflex imports fail because dependencies are missing.

### Preferred workflow:

```bash
uv venv .venv
source .venv/bin/activate
uv add reflex
reflex init
```

If `uv` is not available, the skill falls back to:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install reflex
reflex init
```

The workflow checks for an existing `.venv`, verifies Python 3.10 or newer, and installs Reflex only when needed.


## Process

The `reflex-process-management` skill teaches the assistant how to compile, run, reload, and debug Reflex apps.

### Use this skill when:

- Testing that a Reflex app compiles.
- Starting a local Reflex server.
- Restarting a server after code changes.
- Reading logs to diagnose app errors.

### Validation command:

```bash
reflex compile --dry
```

### Run command:

```bash
reflex run --env prod --single-port 2>&1 | tee reflex.log
```

Production mode does not hot reload. To apply code changes, the assistant should stop the listening process for the app port and restart the server:

```bash
lsof -i :<port> -sTCP:LISTEN -t
kill -INT $(lsof -i :<port> -sTCP:LISTEN -t)
```

Using `-sTCP:LISTEN` helps the assistant target the server process instead of browser connections.

`````

## Recommended Workflow

`````md tabs

## New App

1. Install Reflex Agent Skills in your assistant.
2. Ask the assistant to create or initialize a Reflex app.
3. The assistant should load `setup-python-env`.
4. After the environment is ready, the assistant can run `reflex init`.
5. As the app is built, the assistant should use `reflex-docs` for current framework guidance.
6. Before handing the app back, the assistant should use `reflex-process-management` to compile or run the project.


## Existing

1. Open your Reflex project in an agent-enabled editor.
2. Ask for the feature, bug fix, or refactor you want.
3. The assistant should load `reflex-docs` when it sees Reflex code.
4. For local verification, the assistant should compile the app with `reflex compile --dry` or run it with the process-management workflow.


## Debugging

1. Ask the assistant to inspect the error.
2. The assistant should read `reflex.log` if the app was started through the process-management workflow.
3. The assistant should identify the failing import, component, event handler, route, or state update.
4. After applying a fix, the assistant should restart the app if it is running in production mode.

`````

## Keeping Skills Updated

Because Reflex evolves quickly, update the skill pack regularly.

If you installed through a marketplace or skills CLI, update through that same tool. If you cloned the repository manually, pull the latest changes:

```bash
cd agent-skills
git pull
```

Then copy the updated skill folders back into your assistant's skills directory if your setup does not read directly from the cloned repository.

## Troubleshooting

`````md tabs

## Loading

Check that:

- Your assistant supports Agent Skills.
- The skill folders are in the correct skills directory.
- Each skill folder contains a `SKILL.md` file.
- The assistant was restarted or refreshed after installation if required.


## Outdated Advice

Ask the assistant to use the Reflex docs skill, or pair the skill pack with the Reflex MCP integration for structured access to current docs and component information.


## Commands

Ask the assistant to follow the `setup-python-env` skill again and verify:

- The virtual environment is active.
- Python is version 3.10 or newer.
- Reflex is installed in the active environment.
- The command is being run from the project root.


## App Updates

If the app was started with `--env prod`, it will not hot reload. Restart the server with the `reflex-process-management` workflow.

`````

## Contributing

Each skill lives in `skills/<name>/` and contains a `SKILL.md` manifest. To contribute new guidance, update or add a skill in the [reflex-dev/agent-skills](https://github.com/reflex-dev/agent-skills) repository and follow the [Agent Skills spec](https://agentskills.io/) for the skill format.
