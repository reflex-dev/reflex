---
tags: AI Builder
description: How the Reflex Build agent uses web search, Python, and image generation while building an app.
---

# Agent Tools

Inside an app's Build conversation, the agent can search the web, run Python, and generate images. These tools appear in generation progress so you can see how the agent is working.

For MCP and Reflex Agent Skills used by local coding assistants outside the Builder, see [Agent Toolkit](/docs/ai/features/agent-toolkit/).

## Web Search

The agent can search the web when a request needs current information, package documentation, or external implementation details. The workspace shows the search queries it uses.

Tell the agent what kind of source or information to prioritize:

```text
Check the current Stripe Python SDK documentation and use the supported
Checkout Session flow. Do not use an unofficial package.
```

Review important facts before shipping. Search results provide context for the build, but they do not replace validation against an authoritative source.

## Run Python

The agent can run Python on demand while building or debugging. It can use the output to:

- Check a script or calculation before adding it to the app.
- Inspect and transform sample data.
- Verify that a package imports successfully.
- Reproduce an error or validate a proposed fix.
- Run tests and other project commands.

Ask for the result you want verified rather than prescribing every command:

```text
Test the CSV transformation with the attached sample before wiring it into
the upload workflow. Show empty rows and malformed dates as validation errors.
```

Code run during generation is part of the build process. It does not automatically become a user-facing app feature unless the agent adds the corresponding code to the project.

## Generate Images

Ask the agent to generate an image when the app needs an original illustration, background, placeholder, or other visual asset. Generated images appear alongside the conversation and app changes.

Describe the intended use, composition, and constraints:

```text
Generate a wide, abstract hero background for a financial dashboard. Use navy
and teal, leave the left third visually quiet for heading text, and do not add
words, logos, or interface elements.
```

After generation:

1. Review the image at its intended size in **Preview**.
2. Confirm that text remains legible over it.
3. Check mobile cropping and loading behavior.
4. Ask for a focused revision if the composition or style is wrong.

To provide an existing image as design context instead, see [Images and Attachments](/docs/ai/features/image-as-prompt/).

## Security and Privacy

- Do not put passwords, API keys, private tokens, or production credentials in a prompt.
- Use [Secrets](/docs/ai/features/secrets/) or an integration form for credentials.
- Do not ask the agent to search for or reproduce private data.
- Review generated assets and third-party information before publishing them.

## Related

- [Generation Controls & Collaboration](/docs/ai/features/generation-controls/)
- [Install External Packages](/docs/ai/features/installing-external-packages/)
- [Add Integrations](/docs/ai/features/integration-shortcut/)
- [Secrets](/docs/ai/features/secrets/)
