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

1. Go to your [Supabase Dashboard](https://supabase.com/dashboard).
2. Choose the project you want to connect.
3. Click **Connect** and copy the project URL. The same dialog shows the publishable key.
4. For a different key, go to **Settings** → **API Keys**:
   * **Publishable key** (`sb_publishable_...`): access limited by your Row Level Security policies.
   * **Secret key** (`sb_secret_...`): full server-side access that bypasses Row Level Security.
   * Legacy `anon` and `service_role` keys still work, but Supabase is deprecating them by the end of 2026.

   * **Example URL:** `https://your-project.supabase.co`  
   * **Example Key:** `sb_publishable_xxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Supabase** card.
2. Click **Add connection** and paste your project URL into **SUPABASE_URL** and your key into **SUPABASE_KEY**.
3. Click **Connect** to save the connection.

Once connected, your app can query and update your Supabase database directly from workflows and UI actions.

## Step 3: Notes

* **Keep your keys secure:** Never expose a secret key in client-side code.  
* **Use environment-specific keys:** Separate dev, staging, and production projects for clean access control.  
* **Realtime support:** Supabase enables live syncing of data changes.  
* **Row-level security:** Policies limit the publishable (and legacy `anon`) key; a secret (or legacy `service_role`) key bypasses them. Configure policies appropriately for your use case.
