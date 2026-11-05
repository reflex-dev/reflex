---
description: Connect your apps to Stripe to accept payments, manage subscriptions, and handle billing securely.
---
# Stripe Integration

The **Stripe Integration** allows your app to use [Stripe](https://stripe.com/) to power secure payments, subscriptions, and billing workflows. Once connected, you can process transactions, manage customers, and trigger payment flows directly from your app.

## What You Can Do

With Stripe, your app can:
- **Accept one-time payments** or set up **recurring subscriptions**.  
- **Manage customers**, payment methods, and invoices.  
- Handle **refunds, payment confirmations**, and notifications.  
- Automate billing flows and webhook-based actions.  
- Build secure, PCI-compliant checkout experiences with ease.

## Step 1: Obtain a Stripe API Key

1. Go to your [Stripe Dashboard](https://dashboard.stripe.com/).  
2. Navigate to **Developers → API Keys**.  
3. Copy your **Secret Key** (or create a restricted key for added security).

   * **Example:** `sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

> 💡 Use test keys in development environments and live keys in production.

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Stripe** card.
2. Click **Add connection** and paste your secret key into **STRIPE_API_KEY**.
3. Click **Connect** to save the connection.

Once connected, your app can process payments and manage billing directly from workflows and UI actions.

## Step 3: Notes

* **Keep your API key secure:** Never expose your Stripe key in client-side code.  
* **Use environment-specific keys:** Test keys for staging, live keys for production.  
* **Secure transactions:** All payment processing is handled through Stripe’s PCI-compliant infrastructure.  
