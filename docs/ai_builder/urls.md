# URLs

When you **paste a URL directly into the AI Builder chat**, the AI will automatically decide how to handle it depending on your prompt.

You can use URLs to **copy a page’s design** or **extract its content**, without needing to set up any integration.

## How It Works

* If you say something like **“copy the design”** or **“use this layout”**, the AI will:

  * Take a **screenshot** of the page.
  * Use it as a **visual reference** to recreate the UI in your app.
  * Allow you to **customize** the generated design afterward.

* 🪄 If you say something like **“get the content”**, **“scrape this page”**, or just paste the URL without mentioning design, the AI will:

  * **Scrape the content** of the page (text, links, images, metadata).
  * Return it as structured data that can be used in components, workflows, or AI actions.

## Example Prompts

* “Copy the design of this page.”
* “Scrape the content from this blog post.”
* “Get all the product details from this URL.”
* (Paste the URL alone) → AI will assume content scraping by default.

## Notes

* **Public pages only:** The AI can only process URLs that are publicly accessible.
* **Editable:** Both the generated design and scraped content can be modified after processing.

