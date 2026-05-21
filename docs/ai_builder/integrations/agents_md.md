# AGENTS.md and CLAUDE.md

`AGENTS.md` and `CLAUDE.md` are project-level instruction files that AI coding assistants read when they enter your repository. They give the assistant durable, repository-specific context so it follows Reflex conventions instead of generic defaults.

- `AGENTS.md` is read by agents that follow the [AGENTS.md convention](https://agents.md), including Cursor, OpenCode, OpenAI Codex, and Pi.
- `CLAUDE.md` is read by [Claude Code](https://code.claude.com/docs/en/memory). Claude Code does not read `AGENTS.md` directly — see [Sharing With Claude Code](#sharing-with-claude-code) below.

A Reflex project should have at least one of these files at the project root, next to `rxconfig.py`.

## Recommended Content

The [reflex-dev/agent-skills](https://github.com/reflex-dev/agent-skills) repository ships an `AGENTS.md` template that points assistants at the [Reflex Agent Skills](/docs/ai/integrations/skills/) for environment setup, documentation lookup, and process management. Use it as the starting point, then add anything specific to your codebase.

```md alert info
# `AGENTS.md` references skills by name, so it works once the [Reflex Agent Skills](/docs/ai/integrations/skills/) are installed in the assistant.
```

## Installation

Download the template into your project root, next to `rxconfig.py`:

```bash
curl -fsSL https://raw.githubusercontent.com/reflex-dev/agent-skills/main/AGENTS.md -o AGENTS.md
```

Or copy it manually from a local clone of the [reflex-dev/agent-skills](https://github.com/reflex-dev/agent-skills) repository.

## Sharing With Claude Code

Claude Code reads `CLAUDE.md`, not `AGENTS.md`. To avoid duplicating content, create a `CLAUDE.md` that [imports](https://code.claude.com/docs/en/memory#import-additional-files) `AGENTS.md` using the `@` syntax:

```md
@AGENTS.md

## Claude Code

Add any Claude-specific instructions here.
```

Claude Code expands the `@AGENTS.md` import at session start, then appends anything you write below it. Both files stay in sync from a single source.

After installation, your project root looks like:

```text
my_app/
  AGENTS.md
  CLAUDE.md
  rxconfig.py
  my_app/
    my_app.py
```

## Project-Specific Additions

The template covers Reflex-wide setup. Below it, add anything else the assistant should know about your project:

- Internal conventions and code style.
- Required lint, type-check, or test commands.
- Folder layout and where new code should go.
- Hosting or deployment notes.

Keep entries short and imperative — assistants follow concise, direct instructions more reliably than long paragraphs.

## Keeping Files Updated

Reflex evolves quickly. If you used `curl` to download the template, re-run the same command to refresh it:

```bash
curl -fsSL https://raw.githubusercontent.com/reflex-dev/agent-skills/main/AGENTS.md -o AGENTS.md
```

If you cloned the [reflex-dev/agent-skills](https://github.com/reflex-dev/agent-skills) repository, pull the latest changes and copy the file back into your project:

```bash
cd agent-skills
git pull
cp AGENTS.md /path/to/your/reflex-project/AGENTS.md
```

## Combining With Skills and MCP

`AGENTS.md` and `CLAUDE.md` anchor the assistant in your project. Pair them with the other onboarding tools for deeper Reflex knowledge:

- [Reflex Agent Skills](/docs/ai/integrations/skills/) provide reusable workflows that the file references by name.
- [Reflex MCP](/docs/ai/integrations/mcp-overview/) provides structured documentation lookup at runtime.
- The [llms.txt index](/llms.txt) gives a broad map of the documentation in one file.
