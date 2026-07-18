# API Integration

Not every service has a first-class integration — but your app can connect to **any external API** directly. By using standard HTTP requests, you can integrate with virtually any platform, fetch or send data, and trigger workflows without needing a prebuilt connector.

This gives you full flexibility to work with modern REST, GraphQL, or other web APIs.

## What You Can Do

With custom API calls, your app can:
- Connect to **any REST or GraphQL API** on the web.  
- **Send and receive data** from external services.  
- Trigger actions like creating records, sending messages, or fetching analytics.  
- Build **custom automations** and workflows around APIs.  
- Chain API calls with other integrations or AI actions for powerful flows.

## Step 1: Get API Access

1. Identify the service you want to connect to.  
2. Check its developer documentation for API access requirements.  
3. Obtain the necessary credentials (e.g., **API key**, **token**, or **OAuth**).  
4. Store credentials securely using environment variables — **never** hardcode secrets.

   *Example:*  
   - **API Key:** `sk-xxxxxxxxxxxxxxxx`  
   - **Base URL:** `https://api.example.com/v1/`

## Step 2: Hook up with your App

1. In the AI Builder navigate to the `secrets` tab and add your API credentials as secrets.
2. Then prompt the AI to use these secrets to do what you want and it will install the necessary libraries and set up the API calls for you.

## Step 3: Notes

* **Keep secrets safe:** Use environment variables or secret storage for API keys.
* **Check rate limits:** Many APIs have request limits — build accordingly.
* **Combine with AI or other integrations:** For example, fetch data via API and summarize it using an LLM.


With API integrations, you can connect your app to **almost any modern platform or service**, giving you unlimited extensibility beyond native integrations.


