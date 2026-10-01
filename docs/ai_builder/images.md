---
tags: AI Builder
description: Attach images as visual context, add image assets to an app, or ask the Reflex Build agent to generate an original visual.
---

# Images

## Attach an Image as Context

Select the attachment control, drag an image into chat, or paste one from the clipboard. Describe the part of the image that matters and whether it is a visual reference, content to extract, or an existing asset to preserve.

The agent can interpret `.png`, `.jpg`, `.jpeg`, and `.webp` images as visual prompt context.

You can attach up to **5 images in one message**, with a maximum size of **5 MB per image**. Compress or resize larger reference images before attaching them. Other image formats can be added to the app as files, but they are not interpreted as visual prompt context.

See [Images and Attachments](/docs/ai/features/image-as-prompt/) for prompting guidance.

## Add an Image to the App

For an image the running app should use, such as a logo, attach it in chat and tell the agent where it should appear. Make it clear that the image is an app asset, not only a visual reference.

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/image_prompt_attachment.webp",
        alt="An image attached to a prompt in Reflex Build",
        class_name="rounded-md h-auto mb-4",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

Verify the result in **Preview**, including its crop, aspect ratio, loading behavior, and mobile layout.

## Generate an Image

Ask the agent to create an original image without leaving Reflex Build. Describe the intended size, composition, style, colors, and any space required for overlaid text. Generated images appear alongside the conversation and app changes.

See [Agent Tools](/docs/ai/features/agent-tools/) for examples and review guidance.
