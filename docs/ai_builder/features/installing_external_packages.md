# Installing External Packages

```python exec
import reflex as rx
```

Reflex Build allows you to install external python packages to use in your app. This is useful if you want to use a package that is not included in the default Reflex Build environment. Examples might include `openai`, `langsmith`, `requests`, etc.

There are two ways to install external packages:

1. **Through the Chat Interface**: You can ask the AI to install a package for you.
2. **Add to the `requirements.txt` file**: You can add the package to the `requirements.txt` file and then save the app. This will install the package in your app's environment.

## Installing through the Chat Interface

Enter the name of the package you want to install in the chat interface. The AI will then install the package for you.


```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/external_packages_input.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

## Installing through the requirements.txt file

Add the package to the `requirements.txt` file and then save the app. This will install the package in your app's environment and recompile your app.

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/external_packages_requirements.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```