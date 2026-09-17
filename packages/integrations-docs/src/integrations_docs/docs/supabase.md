---
tags: Data Infrastructure
description: Connect your apps to Supabase to use a hosted Postgres database with real-time capabilities and powerful APIs.
---
# Supabase Integration

The **Supabase Integration** allows your app to connect to [Supabase](https://supabase.com/) — a hosted Postgres database with real-time subscriptions, authentication, and file storage. Once connected, your app can query and update data securely, power dashboards, and sync workflows in real time.

## What You Can Do

With Supabase, your app can:
- **Read and write data** using Postgres through a simple REST or client API.  
- Enable **real-time updates** that sync automatically to your UI.  
- Use **row-level security** and access control for safe data management.  
- Store and retrieve files with Supabase Storage.  
- Integrate seamlessly with AI, dashboards, or internal tools.

## Step 1: Obtain Your Supabase URL and Key

1. Go to your [Supabase Project](https://supabase.com/).
2. Choose the project you want to connect.
3. Navigate to **Project Settings**.
4. Go to **Data API** and copy your `Supabase_URL`.
5. Then go to **API Keys** and copy your `Supabase_Key` (the secret key).

   * **Example URL:** `https://your-project.supabase.co`  
   * **Example Key:** `sb_xxxxxxxxxxxxxxxxxxxxxxxxxxxx.`

## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Supabase** in your app settings.  
2. Paste your **Supabase URL** and **Supabase Key** into the fields.  
3. Click **Connect** to validate and save your integration.

Once connected, your app can query and update your Supabase database directly from workflows and UI actions.

## Step 3: Notes

* **Keep your keys secure:** Never expose the `Supabase_Key` key in client-side code.  
* **Use environment-specific keys:** Separate dev, staging, and production projects for clean access control.  
* **Realtime support:** Supabase enables live syncing of data changes.  
* **Row-level security:** Make sure to configure policies appropriately for your use case.
