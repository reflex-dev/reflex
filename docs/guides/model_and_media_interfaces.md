---
title: Build Python Model Interfaces with Reflex
meta_description: Build an interactive machine learning demo with a custom Reflex UI. Run a Python prediction function, validate inputs, and display model results.
---

# Model and media interfaces

A Reflex model interface collects inputs, runs a Python prediction function or model-service call, and displays the result. You control the surrounding layout, forms, charts, and workflow. Start with a small local example, then add the execution and storage services your model needs.

You can build an interactive machine learning demo in Reflex with a local model or a hosted inference API. Define the input controls, call your Python function from an event handler, and render the returned prediction. The same interface can grow into a multi-page application with custom styling, result review, and database-backed workflows.

## A local prediction demo

This example uses one-nearest-neighbor classification on six labelled flower measurements. It finds the closest sample using Euclidean distance in petal length and width. The tiny dataset is for demonstrating a UI around inference; it is not an evaluated production classifier.

Create a blank Reflex app with the [installation guide](/docs/getting-started/installation/). Copy this code into the app module, followed by the registration lines below. No model download or API key is needed.

```python demo exec id=model_interface_demo
import math
from typing import Any

import reflex as rx


SAMPLES = [
    (1.4, 0.2, "setosa"),
    (1.5, 0.2, "setosa"),
    (4.7, 1.4, "versicolor"),
    (4.5, 1.5, "versicolor"),
    (6.0, 2.5, "virginica"),
    (5.1, 1.9, "virginica"),
]


def predict_flower(length: float, width: float) -> str:
    """Predict the nearest labelled sample using two petal measurements."""
    if not all(math.isfinite(value) and 0 < value <= 10 for value in (length, width)):
        raise ValueError("Enter measurements greater than 0 and at most 10 cm.")
    nearest = min(
        SAMPLES, key=lambda row: (row[0] - length) ** 2 + (row[1] - width) ** 2
    )
    return nearest[2]


class ModelInterfaceState(rx.State):
    prediction: str = ""
    error: str = ""

    @rx.event
    def predict(self, form_data: dict[str, Any]):
        """Validate measurements and display the prediction."""
        self.prediction = ""
        self.error = ""
        try:
            length = float(form_data.get("length", ""))
            width = float(form_data.get("width", ""))
        except ValueError:
            self.error = "Enter both measurements as numbers."
            return
        try:
            self.prediction = predict_flower(length, width)
        except ValueError as error:
            self.error = str(error)


def model_interface():
    """Render the model's input form and result."""
    return rx.vstack(
        rx.hstack(
            rx.icon("flower-2", size=22, color=rx.color("violet", 9)),
            rx.heading("Flower classifier", size="5", as_="h3"),
            align="center",
            spacing="3",
        ),
        rx.text(
            "Enter two petal measurements to find the closest sample.",
            size="2",
            color=rx.color("gray", 11),
        ),
        rx.form(
            rx.vstack(
                rx.grid(
                    rx.vstack(
                        rx.el.label(
                            "Petal length (cm)",
                            html_for="petal-length",
                            font_size="0.875rem",
                            font_weight="500",
                        ),
                        rx.input(
                            id="petal-length",
                            name="length",
                            default_value="1.4",
                            input_mode="decimal",
                            size="3",
                            width="100%",
                        ),
                        spacing="2",
                        align_items="stretch",
                    ),
                    rx.vstack(
                        rx.el.label(
                            "Petal width (cm)",
                            html_for="petal-width",
                            font_size="0.875rem",
                            font_weight="500",
                        ),
                        rx.input(
                            id="petal-width",
                            name="width",
                            default_value="0.2",
                            input_mode="decimal",
                            size="3",
                            width="100%",
                        ),
                        spacing="2",
                        align_items="stretch",
                    ),
                    columns={"initial": "1", "sm": "2"},
                    spacing="4",
                    width="100%",
                ),
                rx.button(
                    "Predict species",
                    rx.icon("arrow-right", size=16),
                    type="submit",
                    size="3",
                    width="100%",
                ),
                spacing="4",
                align_items="stretch",
            ),
            on_submit=ModelInterfaceState.predict,
            width="100%",
        ),
        rx.vstack(
            rx.text(
                "Prediction",
                size="1",
                weight="medium",
                color=rx.color("gray", 11),
            ),
            rx.cond(
                ModelInterfaceState.prediction != "",
                rx.text(
                    ModelInterfaceState.prediction,
                    size="5",
                    weight="medium",
                    text_transform="capitalize",
                ),
                rx.text(
                    "Enter measurements and select Predict species.",
                    size="2",
                    color=rx.color("gray", 11),
                ),
            ),
            role="status",
            spacing="2",
            align_items="stretch",
            width="100%",
            padding="1rem",
            border_radius="8px",
            background=rx.color("gray", 3),
        ),
        rx.cond(
            ModelInterfaceState.error != "",
            rx.text(
                ModelInterfaceState.error,
                role="alert",
                size="2",
                color=rx.color("red", 11),
            ),
        ),
        rx.text(
            "Demo model · 6 reference samples",
            size="1",
            color=rx.color("gray", 11),
        ),
        spacing="4",
        align_items="stretch",
        width="100%",
        max_width="30rem",
        padding=["1rem", "1.5rem"],
        background=rx.color("gray", 1),
        border=f"1px solid {rx.color('gray', 5)}",
        border_radius="12px",
        box_shadow="0 2px 8px rgba(0, 0, 0, 0.03)",
    )
```

```python
app = rx.App()
app.add_page(model_interface)
```

Run `uv run reflex run`. Inputs 1.4 and 0.2 produce `setosa`; 6.0 and 2.5 produce `virginica`. A nonnumeric or out-of-range input clears the previous prediction and shows an error. The function can be tested independently of the interface.

## Use your own model

Replace `predict_flower` with a call to your Python inference code or model service. Load expensive resources according to their lifetime and concurrency requirements, rather than downloading a model for every input change. Keep model objects out of frontend state; store only the values the UI needs.

A slow service call needs loading, timeout, error, and duplicate-submission behavior. A CPU-heavy model needs an execution strategy that does not block the application server. See [performance and execution](/docs/advanced-onboarding/performance-and-execution/) and [background events](/docs/events/background-events/). A durable inference queue must be supplied separately when jobs must survive restarts.

## Add files, images, audio, or video

| Need | Component or guide | Application responsibility |
| --- | --- | --- |
| Receive a file | [Upload](/docs/library/forms/upload/) | Enforce size and type limits on the backend, validate content, and handle processing errors |
| Show an image | [Image](/docs/library/media/image/) | Provide a valid image source and descriptive alternative text |
| Play audio | [Audio](/docs/library/media/audio/) | Supply a playable source and control access to private recordings |
| Play video | [Video](/docs/library/media/video/) | Supply a supported source and account for bandwidth and storage |
| Offer an output file | [Files and downloads](/docs/assets/upload-and-download-files/) | Decide retention, ownership, expiry, and download authorization |

The file input's accepted extensions are a browser convenience, not content validation. Restrict request sizes at the server or proxy as well as validating in the handler. Do not derive a filesystem destination directly from an uploaded filename.

The upload directory is for publicly served files; it is not private per-user storage. Keep sensitive artifacts in storage with an authorization check or an appropriately scoped signed URL. Do not put a secret into an output URL that is sent to every client.

Displaying audio or video is distinct from capturing a microphone or camera stream. For a capture workflow, choose and verify the component or integration that exposes the required browser API. Use the [React wrapping guide](/docs/wrapping-react/overview/) when integrating a component that is not already wrapped.

## Check the complete workflow

Test valid and invalid input, oversized or malformed files, model failure, repeated submission, and access to another user's output. Check that expired artifacts no longer resolve through the intended delivery mechanism. For streaming text output, continue with [AI applications](/docs/guides/ai-applications/) and the [chat tutorial](/docs/getting-started/chatapp-tutorial/).
