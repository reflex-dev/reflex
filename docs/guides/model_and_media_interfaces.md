---
title: Build Python Model Interfaces with Reflex
meta_description: Build interactive machine learning demos in Python with Reflex. Try local predictions, image previews, and WAV audio processing with custom inputs and downloads.
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
app.add_page(model_interface, route="/")
```

Run `uv run reflex run`. Inputs 1.4 and 0.2 produce `setosa`; 6.0 and 2.5 produce `virginica`. A nonnumeric or out-of-range input clears the previous prediction and shows an error. The function can be tested independently of the interface.

## Use your own model

Replace `predict_flower` with a call to your Python inference code or model service. Load expensive resources according to their lifetime and concurrency requirements, rather than downloading a model for every input change. Keep model objects out of frontend state; store only the values the UI needs.

A slow service call needs loading, timeout, error, and duplicate-submission behavior. A CPU-heavy model needs an execution strategy that does not block the application server. See [performance and execution](/docs/advanced-onboarding/performance-and-execution/) and [background events](/docs/events/background-events/). A durable inference queue must be supplied separately when jobs must survive restarts.

## Run an image input and output workflow

A media interface can pass uploaded bytes to a Python function and display its output in a custom layout. This example makes a grayscale image preview, preserves its aspect ratio, and provides a PNG download. It demonstrates image preprocessing, not a trained image classifier. Replace the processing function with your model pipeline when you want predictions or generated images.

Install Pillow in your app:

```bash
uv add pillow
```

Copy this example into a blank app module and run it locally. File uploads run in your app; this documentation site does not accept uploads. The example accepts one still PNG or JPEG up to 2 MiB and 4 million pixels. The output is at most 512 pixels on its longest side. Processing uses a worker thread, and the form shows progress and validation errors.

```python id=image_workflow_demo
import asyncio
import base64
from io import BytesIO

import reflex as rx
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_UPLOAD_ID = "image-workflow-upload"


def prepare_image(data: bytes) -> tuple[bytes, str]:
    """Create a bounded grayscale PNG and describe the input/output dimensions."""
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Choose an image smaller than 2 MiB.")
    try:
        with Image.open(BytesIO(data), formats=("PNG", "JPEG")) as source:
            if source.width * source.height > 4_000_000:
                raise ValueError("Choose an image with at most 4 million pixels.")
            if getattr(source, "n_frames", 1) != 1:
                raise ValueError("Choose a still PNG or JPEG, not an animation.")
            oriented = ImageOps.exif_transpose(source)
            original_size = oriented.size
            oriented.thumbnail((512, 512))
            grayscale = ImageOps.grayscale(oriented)
            # Copy pixels into a fresh image so uploaded metadata is not retained.
            clean = Image.new("L", grayscale.size)
            clean.paste(grayscale)
            output = BytesIO()
            clean.save(output, format="PNG")
            summary = (
                f"{original_size[0]} x {original_size[1]} input · "
                f"{clean.width} x {clean.height} grayscale PNG"
            )
            return output.getvalue(), summary
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("Choose a valid PNG or JPEG image.") from error


class ImageWorkflowState(rx.State):
    """Keep the small generated preview in the current session."""

    preview: str = ""
    summary: str = ""
    error: str = ""
    processing: bool = False
    _output_png: bytes = b""

    @rx.event
    async def process_image(self, files: list[rx.UploadFile]):
        """Validate the upload and send its generated preview to this session."""
        if self.processing:
            return
        self.preview = ""
        self.summary = ""
        self.error = ""
        self._output_png = b""
        if len(files) != 1:
            self.error = "Choose one PNG or JPEG image."
            return
        self.processing = True
        yield
        try:
            data = await files[0].read(MAX_IMAGE_BYTES + 1)
            png, summary = await asyncio.to_thread(prepare_image, data)
            self._output_png = png
            self.preview = "data:image/png;base64," + base64.b64encode(png).decode(
                "ascii"
            )
            self.summary = summary
        except ValueError as error:
            self.error = str(error)
        except OSError:
            self.error = "The upload could not be read. Please try again."
        finally:
            self.processing = False

    @rx.event
    def download_image(self):
        """Download the output generated for the current session."""
        if self._output_png:
            return rx.download(
                data=self._output_png,
                filename="image-preview.png",
                mime_type="image/png",
            )

    @rx.event
    def clear_image(self):
        """Discard the output and clear the browser's selected file."""
        self.preview = ""
        self.summary = ""
        self.error = ""
        self._output_png = b""
        return rx.clear_selected_files(IMAGE_UPLOAD_ID)


def image_workflow():
    """Render an image upload, processing action, preview, and download."""
    return rx.vstack(
        rx.hstack(
            rx.icon("image", size=22, color=rx.color("violet", 9)),
            rx.heading("Image preparation", size="5", as_="h3"),
            spacing="3",
        ),
        rx.text(
            "Upload an image to create a grayscale preview for your model pipeline.",
            size="2",
            color=rx.color("gray", 11),
        ),
        rx.upload(
            rx.vstack(
                rx.icon("upload", size=24),
                rx.text(
                    "Drop an image here or choose a file", size="2", weight="medium"
                ),
                rx.text(
                    "PNG or JPEG · up to 2 MiB", size="1", color=rx.color("gray", 11)
                ),
                rx.foreach(
                    rx.selected_files(IMAGE_UPLOAD_ID),
                    lambda name: rx.text(name, size="2", overflow_wrap="anywhere"),
                ),
                spacing="2",
                width="100%",
            ),
            id=IMAGE_UPLOAD_ID,
            accept={"image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"]},
            multiple=False,
            disabled=ImageWorkflowState.processing,
            border=f"1px dashed {rx.color('gray', 7)}",
            border_radius="8px",
            padding="1.5rem",
            width="100%",
        ),
        rx.button(
            "Create preview",
            on_click=ImageWorkflowState.process_image(
                rx.upload_files(upload_id=IMAGE_UPLOAD_ID)
            ),
            loading=ImageWorkflowState.processing,
            disabled=rx.selected_files(IMAGE_UPLOAD_ID).length() == 0,
            size="3",
            width="100%",
        ),
        rx.cond(
            ImageWorkflowState.error != "",
            rx.text(
                ImageWorkflowState.error,
                role="alert",
                size="2",
                color=rx.color("red", 11),
            ),
        ),
        rx.cond(
            ImageWorkflowState.preview != "",
            rx.vstack(
                rx.image(
                    src=ImageWorkflowState.preview,
                    alt="Generated grayscale image preview",
                    max_height="18rem",
                    object_fit="contain",
                    width="100%",
                ),
                rx.text(
                    ImageWorkflowState.summary,
                    role="status",
                    size="2",
                    color=rx.color("gray", 11),
                ),
                rx.button(
                    "Download PNG",
                    rx.icon("download", size=16),
                    on_click=ImageWorkflowState.download_image,
                    variant="soft",
                ),
                spacing="3",
                align_items="stretch",
                width="100%",
                padding="1rem",
                border_radius="8px",
                background=rx.color("gray", 3),
            ),
        ),
        rx.button(
            "Clear image",
            on_click=ImageWorkflowState.clear_image,
            disabled=ImageWorkflowState.processing,
            variant="ghost",
        ),
        spacing="4",
        align_items="stretch",
        width="100%",
        max_width="32rem",
        padding=["1rem", "1.5rem"],
        border_radius="12px",
        border=f"1px solid {rx.color('gray', 5)}",
        background=rx.color("gray", 1),
    )
```

```python
app = rx.App()
app.add_page(image_workflow, route="/")
```

Run `uv run reflex run`, select an image, then choose **Create preview**. The generated image and **Download PNG** control appear together. Try another image, a malformed file, and **Clear image** to check the complete interaction.

The original file is not copied into the public upload directory. This small example sends a bounded preview to the current browser session and keeps download bytes in a backend-only variable. Clearing the image removes the application state; it does not erase an already downloaded copy. Configure request-size limits at your server or proxy as well: the handler's bounded read happens after the request reaches the upload endpoint.

The image function is independent of the interface. You can add crop controls, prediction labels, a review form, or a gallery without replacing the upload/event/result pattern. For larger files and long-running inference, use appropriately authorized storage and a worker service rather than sending large data URLs through state.

## Run an audio input and output workflow

This audio example accepts a short WAV file, runs a Python processing function, plays the result in the browser, and offers a WAV download. It uses Reflex's upload component, a native HTML audio player, and per-session state. No external service or additional Python audio package is required.

The example performs **peak normalization**: it scales all samples by the same factor so the loudest sample reaches about 80% of the 16-bit range. Stereo channels keep their relative levels; silence stays silent. This is audio preprocessing, not speech recognition, noise removal, or a loudness standard. A speech model can replace the processing function while keeping the surrounding input and result workflow.

Copy the code into a blank app module. It accepts uncompressed 16-bit mono or stereo PCM WAV at 8-48 kHz, up to 10 seconds and 512 KiB. MP3, compressed WAV, and other sample widths are rejected. Python's [wave module](https://docs.python.org/3/library/wave.html) reads the WAV header; the function also checks the decoded frame count before processing.

```python id=audio_workflow_demo
import asyncio
import base64
import sys
import wave
from array import array
from io import BytesIO

import reflex as rx


MAX_AUDIO_BYTES = 512 * 1024
AUDIO_UPLOAD_ID = "audio-workflow-upload"


def normalize_audio(data: bytes) -> tuple[bytes, str]:
    """Normalize the peak of a short 16-bit PCM WAV without changing its timing.

    Args:
        data: Uploaded WAV bytes, limited to 512 KiB.

    Returns:
        A new WAV file and a description of its duration, channels, and gain.

    Raises:
        ValueError: The upload is malformed or outside the supported limits.
    """
    if len(data) > MAX_AUDIO_BYTES:
        raise ValueError("Choose a WAV file no larger than 512 KiB.")
    try:
        with wave.open(BytesIO(data), "rb") as source:
            channels = source.getnchannels()
            rate = source.getframerate()
            frames = source.getnframes()
            if source.getsampwidth() != 2 or channels not in (1, 2):
                raise ValueError("Choose a 16-bit mono or stereo PCM WAV.")
            if not 8000 <= rate <= 48000 or not 0 < frames <= rate * 10:
                raise ValueError(
                    "Use 8-48 kHz audio lasting more than 0 and at most 10 seconds."
                )
            pcm = source.readframes(frames + 1)
            if len(pcm) != frames * channels * 2:
                raise ValueError("The WAV file is incomplete.")
    except (wave.Error, EOFError, RuntimeError) as error:
        raise ValueError("Choose a valid uncompressed PCM WAV file.") from error
    samples = array("h", pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    peak = max(abs(sample) for sample in samples)
    gain = 26213 / peak if peak else 1.0
    normalized = array("h", (round(sample * gain) for sample in samples))
    if sys.byteorder != "little":
        normalized.byteswap()
    output = BytesIO()
    with wave.open(output, "wb") as result:
        result.setnchannels(channels)
        result.setsampwidth(2)
        result.setframerate(rate)
        result.writeframes(normalized.tobytes())
    summary = f"{frames / rate:.2f} seconds · {channels} channel(s) · {gain:.2f}x gain"
    return output.getvalue(), summary


class AudioWorkflowState(rx.State):
    """Keep one small processed recording in the current session."""

    preview: str = ""
    summary: str = ""
    error: str = ""
    processing: bool = False
    _output_wav: bytes = b""

    @rx.event
    async def process_audio(self, files: list[rx.UploadFile]):
        """Validate an uploaded WAV and prepare its normalized playback.

        Args:
            files: Files selected by the upload component.

        Yields:
            An update displaying the processing state before reading the file.
        """
        if self.processing:
            return
        self.preview = self.summary = self.error = ""
        self._output_wav = b""
        if len(files) != 1:
            self.error = "Choose one WAV file."
            return
        self.processing = True
        yield
        try:
            data = await files[0].read(MAX_AUDIO_BYTES + 1)
            wav, summary = await asyncio.to_thread(normalize_audio, data)
            self._output_wav = wav
            self.preview = "data:audio/wav;base64," + base64.b64encode(wav).decode(
                "ascii"
            )
            self.summary = summary
        except ValueError as error:
            self.error = str(error)
        except OSError:
            self.error = "The recording could not be read. Please try again."
        finally:
            self.processing = False

    @rx.event
    def download_audio(self):
        """Download this session's generated WAV.

        Returns:
            A download event when a result is available, otherwise None.
        """
        if self._output_wav:
            return rx.download(
                data=self._output_wav, filename="normalized.wav", mime_type="audio/wav"
            )

    @rx.event
    def clear_audio(self):
        """Discard the result and reset the file selector when idle.

        Returns:
            A file-selector reset event when idle, otherwise None.
        """
        if self.processing:
            return
        self.preview = self.summary = self.error = ""
        self._output_wav = b""
        return rx.clear_selected_files(AUDIO_UPLOAD_ID)


def audio_workflow() -> rx.Component:
    """Render a custom audio upload and playback card.

    Returns:
        The upload, result player, and download controls.
    """
    return rx.vstack(
        rx.hstack(
            rx.icon("audio-lines", size=22, color=rx.color("violet", 9)),
            rx.heading("Audio preparation", size="5", as_="h3"),
            spacing="3",
            align="center",
        ),
        rx.text(
            "Normalize a short recording, listen to the result, and download the WAV.",
            size="2",
            color=rx.color("gray", 11),
        ),
        rx.upload(
            rx.vstack(
                rx.icon("upload", size=24),
                rx.text("Drop a WAV here or choose a file", size="2", weight="medium"),
                rx.text("16-bit PCM · up to 10 seconds and 512 KiB", size="1"),
                rx.foreach(
                    rx.selected_files(AUDIO_UPLOAD_ID),
                    lambda name: rx.text(name, size="2", overflow_wrap="anywhere"),
                ),
                spacing="2",
                width="100%",
            ),
            id=AUDIO_UPLOAD_ID,
            accept={"audio/wav": [".wav"]},
            multiple=False,
            disabled=AudioWorkflowState.processing,
            border=f"1px dashed {rx.color('gray', 7)}",
            border_radius="8px",
            padding="1.5rem",
            width="100%",
        ),
        rx.button(
            "Normalize recording",
            on_click=AudioWorkflowState.process_audio(
                rx.upload_files(upload_id=AUDIO_UPLOAD_ID)
            ),
            loading=AudioWorkflowState.processing,
            disabled=rx.selected_files(AUDIO_UPLOAD_ID).length() == 0,
            size="3",
            width="100%",
        ),
        rx.cond(
            AudioWorkflowState.error != "",
            rx.text(
                AudioWorkflowState.error,
                role="alert",
                size="2",
                color=rx.color("red", 11),
            ),
        ),
        rx.cond(
            AudioWorkflowState.preview != "",
            rx.vstack(
                rx.text("Processed recording", size="2", weight="medium"),
                rx.el.audio(
                    src=AudioWorkflowState.preview,
                    controls=True,
                    preload="metadata",
                    aria_label="Normalized recording",
                    width="100%",
                ),
                rx.text(AudioWorkflowState.summary, role="status", size="2"),
                rx.button(
                    "Download WAV",
                    on_click=AudioWorkflowState.download_audio,
                    variant="soft",
                ),
                spacing="3",
                align_items="stretch",
                width="100%",
                padding="1rem",
                border_radius="8px",
                background=rx.color("gray", 3),
            ),
        ),
        rx.button(
            "Clear recording",
            on_click=AudioWorkflowState.clear_audio,
            disabled=AudioWorkflowState.processing,
            variant="ghost",
        ),
        spacing="4",
        align_items="stretch",
        width="100%",
        max_width="32rem",
        padding=["1rem", "1.5rem"],
        border_radius="12px",
        border=f"1px solid {rx.color('gray', 5)}",
        background=rx.color("gray", 1),
    )
```

```python
app = rx.App()
app.add_page(audio_workflow, route="/")
```

Run `uv run reflex run`, select a WAV file, and choose **Normalize recording**. Use the player to listen when ready; playback does not start automatically. **Download WAV** saves the processed recording. An invalid replacement clears the previous result and shows an error; **Clear recording** resets the result and file selector.

The worker thread keeps the bounded sample-processing function off the event loop. The original recording is not written to the public upload directory. The small processed WAV travels to the current browser session as a data URL and stays available in a backend-only variable for download. Clearing state does not erase copies already received by the browser or downloaded. Configure server or proxy request-size limits too, since the bounded read occurs after upload handling begins. Use authorized storage and a worker service for larger or longer-running jobs.

This example receives a file; it does not record a microphone or run a speech model. For microphone capture, use a verified recording component or browser integration. For model calls, add timeouts, cancellation, and service-specific validation as described in [performance and execution](/docs/advanced-onboarding/performance-and-execution/).

## Add video playback and media capture

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
