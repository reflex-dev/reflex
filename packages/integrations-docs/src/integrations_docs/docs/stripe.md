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

1. Go to the [API keys](https://dashboard.stripe.com/apikeys) page in your Stripe Dashboard.  
2. Create a **restricted key** with only the permissions your app needs (recommended by Stripe), or copy your **Secret key**.  
3. Copy the key value. Stripe shows a live-mode key you create only once.

   * **Example:** `rk_test_...` (restricted) or `sk_test_...` (secret)

> 💡 Use sandbox keys (`rk_test_`/`sk_test_`) in development and live keys (`rk_live_`/`sk_live_`) in production.

## Step 2: Configure the Integration in Your App

1. In Reflex Build, open the **Integrations** tab and select the **Stripe** card.
2. Click **Add connection** and paste your restricted or secret key into **STRIPE_API_KEY**.
3. Click **Connect** to save the connection.

Once connected, your app can process payments and manage billing directly from workflows and UI actions.

## Step 3: Notes

* **Keep your API key secure:** Never expose your Stripe key in client-side code.  
* **Use environment-specific keys:** Sandbox keys for staging, live keys for production.  
* **Secure transactions:** All payment processing is handled through Stripe’s PCI-compliant infrastructure.  
