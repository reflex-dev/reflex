# Installation

~3 minutes · Requires Python 3.10+.

```md alert info
# Reading this as an AI agent or coding assistant?

You're likely here to build a Reflex app for someone. Reflex does **not** behave like the Flask/FastAPI/React code in your training data — read this before writing any code.

**Get the current docs (don't rely on training data — the API changes between versions):**

- Fetch [`https://reflex.dev/llms.txt`](https://reflex.dev/llms.txt) for a token-efficient map of the docs and core concepts.
- Use the [Reflex MCP server](/docs/ai-builder/integrations/mcp-overview) (`https://build.reflex.dev/mcp`) for live component/prop lookup so you don't hallucinate APIs. *(MCP access is an enterprise feature.)*
- Run `uv run reflex --version` and trust the live docs for that version over memory.

**Drop a rules file in the project root** (`AGENTS.md`, or `CLAUDE.md`/`.cursorrules` for your tool) so these conventions persist across your session — `reflex init` writes a starter `AGENTS.md` for you by default, and a minimal fallback is below.
```

Starter rules file:

```text
# Reflex conventions

- Reflex is pure Python that compiles to a React frontend. Do NOT write JS, HTML, or JSX.
- Components are function calls that return components; pass props as keyword args.
- NEVER use plain Python control flow on state Vars inside the render tree.
  No `if`, `for`, `len()`, or f-strings over a Var — use `rx.cond`, `rx.foreach`,
  and Var operators instead. (This is the most common mistake.)
- State lives in `rx.State` subclasses. State only mutates inside event-handler
  methods — never at module load or render time. Derived values use `@rx.var`.
- Event handlers may be `async` and may `yield` to push intermediate UI updates.
- Always run commands with `uv run` (e.g. `uv run reflex run`). Never bare `python`.
- `.web/` is generated output — never edit or commit it. `rxconfig.py` is the config entry point.
- Verify your work headlessly: `CI=1 uv run reflex run` (frontend :3000, backend :8000),
  add `--loglevel debug` to diagnose failures.
```

## Virtual Environment

We recommend [uv](https://docs.astral.sh/uv/) as the default; [venv](https://docs.python.org/3/library/venv.html), [conda](https://conda.io/), and [poetry](https://python-poetry.org/) are alternatives.

## Install Reflex on your system

`````md tabs

## macOS/Linux

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, restart your terminal or run `source ~/.bashrc` (or `source ~/.zshrc` for zsh).

Alternatively, install via [Homebrew, PyPI, or other methods](https://docs.astral.sh/uv/getting-started/installation/).

```md alert warning
# macOS (Apple Silicon) users: install Rosetta 2

Run `/usr/sbin/softwareupdate --install-rosetta --agree-to-license`. See [Apple's instructions](https://support.apple.com/en-us/HT211861) for details.
```

### Set up the Reflex project

Replace `<your-app>` with your project name, then switch into the new directory.

```bash
mkdir <your-app>
cd <your-app>
uv init
uv add reflex
uv run reflex init
```


## Windows

For Windows users, we recommend [WSL](https://learn.microsoft.com/en-us/windows/wsl/about) for optimal performance — WSL users should follow the macOS/Linux tab; the rest of this section covers native Windows.

### Install uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, restart your terminal (PowerShell or Command Prompt).

Alternatively, install via [WinGet, Scoop, or other methods](https://docs.astral.sh/uv/getting-started/installation/).

### Set up the Reflex project

Replace `<your-app>` with your project name, then switch into the new directory.

```powershell
mkdir <your-app>
cd <your-app>
uv init
uv add reflex
uv run reflex init
```

```md alert warning
# Error `Install Failed - You are missing a DLL required to run bun.exe` Windows

Bun requires runtime components of Visual C++ libraries to run on Windows. This issue is fixed by installing [Microsoft Visual C++ 2015 Redistributable](https://www.microsoft.com/en-us/download/details.aspx?id=53840).
```

`````

Running `uv run reflex init` will return the option to start with a blank Reflex app, premade templates built by the Reflex team, or to try our [AI builder](https://build.reflex.dev/).

```bash
Initializing the web directory.

Get started with a template:
(0) A blank Reflex app.
(1) Premade templates built by the Reflex team.
(2) Try our AI builder.
Which template would you like to use? (0):
```

If this is your first time, pick **(0) A blank Reflex app** — the rest of the docs assume you started there.

## Run the App

Run it in development mode:

```bash
uv run reflex run
```

Your app runs at [http://localhost:3000](http://localhost:3000). Reflex _hot reloads_ any code changes in real time — your edits show up automatically.

For troubleshooting, increase log verbosity with the `--loglevel` flag:

```bash
uv run reflex run --loglevel debug
```

```md alert info
# Next: Build your first app

Reflex is installed. The [Introduction](/docs/getting-started/introduction) walks through a working counter app in pure Python — the shortest path from "it runs" to "I understand it."
```
