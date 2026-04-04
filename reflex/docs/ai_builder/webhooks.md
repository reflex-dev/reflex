# Webhooks

Webhooks allow your app to **send data to external services** in real time. You provide the AI Builder with a **webhook URL** created in another platform, and it can **automatically send payloads** to that URL when workflows are triggered.

This is a simple and powerful way to integrate with services that support incoming webhooks, even if there’s no first-class integration.

## What You Can Do

With outgoing webhooks, your app can:

* **Send structured payloads** to any service that supports incoming webhooks (e.g., Slack, Zapier, Make, Discord).
* **Trigger external workflows** when events happen in your app.
* **Push real-time updates** to third-party systems without writing custom backend code.
* Chain webhook calls with other integrations or AI actions.

## Step 1: Create a Webhook in the External Service

1. Go to the external service you want to connect (e.g., Slack, Zapier, Discord, Make).
2. Create a new **incoming webhook** in that service.
3. Copy the **webhook URL** it provides.


## Step 2: Add the Webhook URL to AI Builder

1. In the AI Builder chat paste the **webhook URL** you created in the external service.
2. You can then instruct the AI to **send data to this URL** whenever a workflow is triggered.
3. Optionally define the **payload structure** (e.g., JSON body) and when it should be sent.

> 💡 Example: “Send user signup data to this webhook whenever a user signs up.”

## Step 3: Sending Payloads

* The AI Builder will write the code to send a `POST` request to the webhook URL with the payload you define.
* The payload can include **dynamic data** from your app — such as user info, state variables, or model outputs.
* You can trigger these webhook calls from buttons, events, workflows, or automations.


## Step 4: Notes

* **Security:** Only use webhook URLs from trusted services — they will receive your data as-is.
* **Formatting:** Make sure the payload matches the expected format of the external service.
* **Chaining:** You can use multiple webhooks or combine them with other integrations.
* **Use cases:** Slack alerts, CRM updates, triggering automations in Zapier or Make, notifying custom systems.

