---
title: reflex-llamaindex-template
description: "A minimal chat app using LLamaIndex"
author: "Reflex"
image: "llamaindex.png"
source: "https://github.com/reflex-dev/reflex-llamaindex-template"
meta: [
    {"name": "keywords", "content": ""},
]
tags: ["AI/ML", "Chat"]
---

The following is an alternative UI to display the LLamaIndex app. 

## Prerequisites

If you plan on deploying your agentic workflow to prod, follow the [llama deploy tutorial](https://github.com/run-llama/llama_deploy/tree/main) to deploy your agentic workflow. 

## Setup

To run this app locally, install Reflex and run:

```bash
reflex init --template reflex-llamaindex-template
```



The following [lines](https://github.com/reflex-dev/reflex-llamaindex-template/blob/abfda49ff193ceb7da90c382e5cbdcb5fcdb665c/frontend/state.py#L55-L79) in the state.py file are where the app makes a request to your deployed agentic workflow. If you have not deployed your agentic workflow, you can edit this to call and api endpoint of your choice.

```python
client = httpx.AsyncClient()

# call the agentic workflow
input_payload = {
    "chat_history_dicts": chat_history_dicts,
    "user_input": question,
}
deployment_name = os.environ.get("DEPLOYMENT_NAME", "MyDeployment")
apiserver_url = os.environ.get("APISERVER_URL", "http://localhost:4501")
response = await client.post(
    f"\{apiserver_url}/deployments/\{deployment_name}/tasks/create",
    json=\{"input": json.dumps(input_payload)},
    timeout=60,
)
answer = response.text

for i in range(len(answer)):
    # Pause to show the streaming effect.
    await asyncio.sleep(0.01)
    # Add one letter at a time to the output.
    self.chat_history[-1] = (
        self.chat_history[-1][0],
        answer[: i + 1],
    )
    yield
```

### Run the app

Once you have set up your environment, install the dependencies and run the app:

```bash
cd reflex-llamaindex-template
pip install -r requirements.txt
reflex run
```

