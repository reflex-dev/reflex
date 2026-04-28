# AI Onboarding

```python exec
import reflex as rx


def _resource_card(
    title: str, body: str, href: str, action: str, target: str = "_self"
) -> rx.Component:
    return rx.el.a(
        rx.el.div(
            rx.el.h3(title, class_name="text-base font-semibold text-secondary-12"),
            rx.el.p(body, class_name="text-sm leading-6 text-secondary-11"),
            rx.el.div(action, class_name="text-sm font-semibold text-primary-10"),
            class_name="flex h-full flex-col gap-2 rounded-lg border border-secondary-a4 bg-white-1 p-4 transition-colors hover:bg-secondary-2 shadow-xs",
        ),
        href=href,
        target=target,
        class_name="no-underline",
    )


def onboarding_resources() -> rx.Component:
    return rx.el.div(
        _resource_card(
            "Docs for Agents",
            "Give your agent current Reflex documentation as Markdown, llms.txt, or structured MCP context.",
            "/llms.txt",
            "Open llms.txt",
            target="_blank",
        ),
        _resource_card(
            "MCP",
            "Connect supported AI tools to Reflex documentation and component information through MCP.",
            "/ai/integrations/mcp-overview/",
            "View MCP overview",
        ),
        _resource_card(
            "Skills",
            "Install Reflex Agent Skills so assistants follow Reflex-specific workflows for docs, setup, and process management.",
            "/ai/integrations/skills/",
            "Install skills",
        ),
        _resource_card(
            "Reflex Build",
            "Use Reflex Build when you want an AI-native environment for creating, editing, previewing, and shipping apps.",
            "/ai/overview/best-practices/",
            "Read best practices",
        ),
        class_name="grid grid-cols-1 gap-3 md:grid-cols-2 my-6",
    )
```

Everything you need to onboard your AI coding assistant to Reflex.

If you are building Reflex apps with AI, combine current docs, structured MCP context, and local skills so the assistant can plan, code, run, and debug with the same assumptions as the Reflex docs.

```python eval
onboarding_resources()
```

## Prerequisite: Choose Your Workflow

You do not need an API key to read Reflex documentation. Start by deciding how your assistant will work with Reflex:

- For local app development, use Python 3.10 or newer and a project virtual environment.
- For current documentation context, give the assistant Markdown docs or `llms.txt`.
- For structured tool access, use the Reflex MCP integration.
- For repeatable agent behavior, install Reflex Agent Skills.
- For a browser-based AI builder, use Reflex Build.

## Reflex Docs for Agents

You can give your assistant current Reflex documentation in a few ways.

`````md tabs

## Markdown Pages

Every docs page has a Markdown version that agents can read directly. Add `.md` to the docs path:

```text
https://reflex.dev/docs/ai/integrations/ai-onboarding.md
```

Use this when an agent needs one focused page.


## llms.txt

Use the generated docs index when an agent needs a broad map of Reflex docs:

```text
https://reflex.dev/docs/llms.txt
```

The index groups docs by section and links to agent-friendly Markdown assets.


## MCP

Use MCP when your editor or agent can call tools for structured documentation and component lookup:

```text
https://mcp.reflex.dev/mcp
```

See the [MCP overview](/docs/ai/integrations/mcp-overview/) and [MCP installation](/docs/ai/integrations/mcp-installation/) guides for details.

`````

## Reflex MCP

The Reflex MCP integration gives supported AI tools structured access to Reflex framework docs and component information. Use it when your assistant can connect to an MCP server and benefit from tool-assisted lookup while editing code.

```md alert warning
# The Reflex MCP integration is currently only available for enterprise customers. Please [book a demo](https://reflex.dev/pricing/) to discuss access.
```

## Reflex Agent Skills

Reflex Agent Skills are local instruction packs that teach AI assistants how to work with Reflex projects. They cover:

- Current Reflex docs and concept lookup.
- Python environment setup for Reflex projects.
- Reflex compile, run, restart, and debugging workflows.

Install the skill pack from the [reflex-dev/agent-skills](https://github.com/reflex-dev/agent-skills) repository, or follow the [Skills installation guide](/docs/ai/integrations/skills/).

```bash
npx skills add reflex-dev/agent-skills
```

## Quick Start Prompts

Use these prompts to give your agent a strong starting point.

`````md tabs

## New App

```text
Create a new Reflex app. Use current Reflex documentation, set up a Python 3.10+ virtual environment, initialize the project, and validate it with reflex compile --dry before handing it back.
```


## Existing App

```text
Work on this existing Reflex app. First inspect the project structure and current dependencies. Use Reflex docs for current APIs, make the requested change, then run reflex compile --dry or the project's existing test command.
```


## Debugging

```text
Debug this Reflex app. Read the error and relevant logs, identify whether the failure is in imports, state, event handlers, routing, components, or runtime setup, then apply the smallest fix and re-run validation.
```

`````

## Reflex Build

Reflex Build is the AI-native way to create Reflex apps in the browser. Use it when you want to generate, edit, preview, and share apps without setting up a local environment first.

Start with the [Reflex Build best practices](/docs/ai/overview/best-practices/) guide, then use MCP and Skills when you want your local assistant to keep working with the same Reflex concepts.

## Recommended Validation

Ask your assistant to validate Reflex changes before it hands work back:

```bash
reflex compile --dry
```

For running apps, pair that with the process-management workflow from Reflex Agent Skills so the assistant restarts only the server process it owns.
