---
tags: AI Builder
description: Attach supported documents and structured data to a Reflex Build prompt and give the agent a clear task for each file.
---

# Files

Select the attachment control to upload a file as context for the Reflex Build agent. You can also drag a file directly into the chat.

This page covers documents and structured data. See [Images](/docs/ai/images/) for image attachments.

## Supported File Types

Reflex Build supports common:

- Documents: `.pdf`, `.doc`, `.docx`, `.odt`, and `.rtf`.
- Spreadsheets: `.xls`, `.xlsx`, `.ods`, `.csv`, and `.tsv`.
- Presentations: `.ppt`, `.pptx`, and `.odp`.
- Text and structured data: `.txt`, `.md`, `.markdown`, `.json`, `.xml`, `.yaml`, and `.yml`.

General file uploads support files up to **50 MB** each. You can attach up to **20 files in one message**.

## Give the Agent a Clear Task

Tell the agent how to use the attachment:

```text
Use the attached CSV as sample data. Build an import preview that maps the
columns, flags malformed dates, and lets the user exclude invalid rows.
```

An attachment is prompt context. If the app must serve or retain the file at runtime, ask the agent to add the appropriate app asset, upload workflow, database record, or external storage integration.

Do not attach secrets, credentials, or private production exports unless they are specifically approved for use in Reflex Build. Use [Secrets](/docs/ai/features/secrets/) or an integration form for credentials.
