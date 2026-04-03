# Python Libraries


Not every service or tool has a first-class integration — but your app can still connect to **any Python library** directly. By leveraging the built-in Python runtime, the AI Builder can install packages, import libraries, and call their functions from workflows or components. This gives you maximum flexibility to extend your app with the broader Python ecosystem.

When you ask for a certain functionality the AI Builder will first check if there is a `first-class integration` available. If not, it will `search the web` to try and find a relevant Python library to fulfill your request. If it finds one, it will install the package and ask you to set any `API keys` that are required.


## Example Use Cases

### Slack 

There is no built-in integration for Slack. But if you ask the AI Builder to send a message to a Slack channel, it will research itself the best implementation and then use the `slack_sdk` Python package to send the message.


### Scikit-learn

There is no built-in integration for Scikit-learn. But if you ask the AI Builder to classify some text using scikit-learn, it will research itself the best implementation and then use the `scikit-learn` Python package to load a pre-trained model and classify the text.




## Adding Custom Knowledge

If you are working with a specialized / less well-known library, you can add custom knowledge to help the AI Builder understand how to use it. Simply provide a brief description of the library, its purpose, and example usage in the **Knowledge** section of your app settings. This will guide the AI Builder when it attempts to call functions from that library.

```python exec
import reflex as rx
```

```md alert warning
# Where to find the Knowledge Section
```

```python eval
rx.image(
    src="https://web.reflex-assets.dev/ai_builder/features/knowledge_light.avif",
    alt="Where to find the Knowledge Section",
    class_name="rounded-lg border border-secondary-a4 mb-2",
)
```


## What is Not Supported

There are a very small number of libraries that are not supported due to their size. For example, large machine learning frameworks like `torch` or `tensorflow` are not supported directly. In these cases, we recommend using a first-class integration that can emulate similar functionality (e.g., the Replicate integration for running ML models in the cloud).