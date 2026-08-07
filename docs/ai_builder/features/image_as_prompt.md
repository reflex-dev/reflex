---
tags: AI Builder
description: Give the Reflex Build agent focused image, document, and data context with clear instructions about how to use each attachment.
---

# Images and Attachments

```python exec
import reflex as rx
```

Attach screenshots, documents, or sample data when the agent needs visual or file-based context. You can select the attachment control, drag a file into chat, or paste an image from the clipboard.

## Use an Image as a Reference

An image is often the clearest way to communicate a layout, visual hierarchy, or specific UI issue:

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/image_prompt_attachment.webp",
        alt="Using an image as a prompt in Reflex Build",
        class_name="rounded-md h-auto mb-4",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

Explain what the agent should copy and what it should ignore:

```text
Use the attached screenshot as a layout reference. Match its navigation width,
card hierarchy, and spacing, but keep the current brand colors and content.
```

For a screenshot of an existing app, include the relevant route or page name. Tightly crop references when only one component matters.

## Attach Files

Attach no more data than the task requires; smaller, focused files are faster for the agent to interpret. Use the format-specific pages for current upload limits:

- [Files](/docs/ai/files/) for supported document and data formats.
- [Images](/docs/ai/images/) for supported image formats and app assets.

## Generate a New Image

If the app needs an original visual rather than a reference, ask the agent to generate one. Generated images appear alongside the conversation and app changes. See [Agent Tools](/docs/ai/features/agent-tools/).
