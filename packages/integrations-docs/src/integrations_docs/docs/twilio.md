---
tags: Communication
description: Connect your apps to Twilio to send SMS, WhatsApp messages, and voice calls programmatically.
---
# Twilio Integration

The **Twilio Integration** allows your app to use [Twilio](https://www.twilio.com/) to send and receive SMS, WhatsApp messages, and voice calls. Once connected, your app can trigger messages or calls directly from workflows, user actions, or automated events.

## What You Can Do

With Twilio, your app can:
- **Send SMS** messages to users or customers globally.  
- **Send and receive WhatsApp messages**.  
- **Make and manage voice calls** programmatically.  
- Automate **notifications**, **alerts**, and **transactional messages**.  
- Integrate messaging into AI workflows for dynamic, real-time communication.

## Step 1: Obtain Twilio Credentials

1. Go to your [Twilio Console](https://www.twilio.com/console).  
2. Copy your **Account SID** and **Auth Token** from the dashboard.  

   * **Example Account SID:** `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`  
   * **Example Auth Token:** `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Configure the Integration in Your App

1. Go to **Integrations → Add Twilio** in your app settings.  
2. Paste your **Account SID** and **Auth Token** in the input fields.  
3. Click **Connect** to validate and save your integration.

Once connected, your app can send messages or make calls through Twilio directly in workflows and components.

## Step 3: Notes

* **Keep your credentials secure:** Never expose your Auth Token in client-side code.  
* **Use environment-specific credentials:** Separate dev, staging, and production credentials.  
* **Phone number setup:** Ensure you’ve configured a valid Twilio number for sending messages or calls.  
* **Regulatory compliance:** Review Twilio’s messaging and voice compliance requirements for your region.
