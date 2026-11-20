---
tags: Communication
description: Connect your apps to Circleback to read meeting notes, transcripts, action items, and calendar events.
---
# Circleback Integration

The **Circleback Integration** allows your app to connect to [Circleback](https://circleback.ai/) to read the meetings it records: notes, transcripts, attendees, action items, and upcoming calendar events. Once connected, your app can search past meetings, build dashboards on top of them, or turn action items into workflows.

## What You Can Do

With Circleback, your app can:
- **List and search meetings** by date, attendee, tag, or a phrase said in the transcript.
- **Read meeting notes and transcripts** to summarize, classify, or answer questions about them.
- **Track action items** and mark them done as work is completed.
- **Show upcoming calendar events** alongside what was discussed in earlier meetings.
- Power intelligent workflows (e.g., weekly meeting digests or follow-up reminders).

## Step 1: Obtain a Circleback API Key

1. Go to your [Circleback settings](https://circleback.ai/settings?tab=api-access).
2. Open **API keys** and create a new key.
3. Copy the key now: Circleback shows it only once.

> 💡 A key is personal: it reads the meetings of the person who created it, plus meetings shared with them. Create it from the account whose meetings your app should see.

   * **Example:** `cb_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Circleback** card.
2. Click **Add connection** and paste your API key into **CIRCLEBACK_API_KEY**.
3. Click **Connect** to save the connection.

Once connected, your app can read your Circleback meetings and action items.

## Step 3: Notes

* **Keep your key secure:** Never expose your Circleback API key in client-side code.
* **Mind the rate limits:** Limits apply per Circleback account, across all of its keys: 3 requests per second and 20 per minute on the free plan, 20 per second and 300 per minute on paid plans. Cache results rather than refetching them on every page load.
* **Share it across projects:** Move the connection to your organization to reuse one Circleback key in every project.
