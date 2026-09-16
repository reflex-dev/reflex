---
tags: AI Builder
description: Use a public URL as visual reference material or extract specific public content for a Reflex Build app.
---

# URLs

Paste a public URL into the chat when the agent needs a page as a visual reference or a source of content. State which result you want instead of sending the URL by itself.

## Use a page as a visual reference

Tell the agent which visual qualities to reproduce and what must remain unchanged:

```text
Use https://example.com as a layout reference for the pricing page. Match its
section order and card hierarchy, but keep our current colors and copy.
```

The agent captures the public page and uses it as context. Review the result for copied trademarks, content, or assets before publishing.

## Extract public content

Ask for the specific information and output shape you need:

```text
Extract the product names, prices, and detail-page links from this public page.
Return a table and flag any item without a price.
```

Only public pages that the Builder can reach are supported. It cannot use your signed-in browser session to read private pages. Make sure you have permission to reuse extracted content.

## Related

- [Images and Attachments](/docs/ai/features/image-as-prompt/) — provide a screenshot when the page cannot be accessed directly.
- [Files](/docs/ai/files/) — attach approved source material directly to the prompt.
