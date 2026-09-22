"""Execute the copyable tutorial examples without calling external services."""

import asyncio
import re
import struct
import sys
import warnings
import wave
from contextvars import ContextVar
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import reflex as rx
from PIL import Image
from reflex_base.registry import RegistrationContext
from reflex_components_core.core.upload import Upload

DOCS = Path(__file__).resolve().parents[2] / "getting_started"
OPENAI_CHAT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
STATE_LOCKED = ContextVar("tutorial_state_locked", default=False)


@pytest.fixture(autouse=True)
def isolated_registration():
    """Keep each copied app's registration separate from other examples."""
    with RegistrationContext(_config=rx.Config(app_name="tutorial_test")):
        yield


def tutorial_block(name, section, marker):
    """Select one marked snippet within a named tutorial section."""
    source = (DOCS / name).read_text()
    assert source.count(section + "\n") == 1, f"Expected one section: {section}"
    content = source.split(section + "\n", 1)[1]
    heading_prefix = section.split(" ", 1)[0]
    content = re.split(rf"^{heading_prefix} ", content, maxsplit=1, flags=re.MULTILINE)[
        0
    ]
    blocks = re.findall(r"^```python\n(.*?)^```", content, re.MULTILINE | re.DOTALL)
    matches = [block for block in blocks if marker in block]
    assert len(matches) == 1, (
        f"Expected one {marker!r} block in {section}, got {len(matches)}"
    )
    return matches[0]


@pytest.fixture(
    params=["### Using the API", "### Final Code"], ids=["walkthrough", "final"]
)
def chat_module(monkeypatch, request):
    """Load each API state module exactly as a reader copies it."""
    source = tutorial_block(
        "chatapp_tutorial.md", request.param, "class State(rx.State):"
    )
    module = ModuleType(f"tutorial_chat_state_{uuid4().hex}")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(source, module.__dict__)
    return module


def run_answer(module, state):
    """Run a real tutorial handler with a lightweight state object."""

    class LockedState(SimpleNamespace):
        """Track the lock boundaries used by background events."""

        def __setattr__(self, name, value):
            if name in {"question", "processing", "error"}:
                assert self.locked
            super().__setattr__(name, value)

        async def __aenter__(self):
            self.locked = True
            STATE_LOCKED.set(True)
            self.lock_entries += 1
            return self

        async def __aexit__(self, *exc):
            self.locked = False
            STATE_LOCKED.set(False)

    locked_state = LockedState(**vars(state), locked=False, lock_entries=0)

    async def consume():
        async for _ in module.State.answer.fn(locked_state):
            assert not locked_state.locked

    asyncio.run(consume())
    assert locked_state.lock_entries > 0
    vars(state).update(vars(locked_state))


def fake_client(monkeypatch, module, chunks):
    """Provide the SDK's async client and stream protocols without a network."""

    async def events():
        for chunk in chunks:
            assert not STATE_LOCKED.get()
            yield chunk

    stream = MagicMock()
    stream.__aiter__.side_effect = events
    stream.__aenter__ = AsyncMock(return_value=stream)
    stream.__aexit__ = AsyncMock(return_value=False)
    client = MagicMock()

    async def create(**kwargs):
        assert not STATE_LOCKED.get()
        return stream

    client.chat.completions.create = AsyncMock(side_effect=create)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(module, "AsyncOpenAI", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    return factory, client, stream


def chunk(text):
    """Make a text or role-only streaming chunk."""
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
    )


def test_dashboard_final_code_is_self_contained(monkeypatch):
    """Copying the complete dashboard must build its UI and update chart data."""
    module = ModuleType("tutorial_dashboard_final")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(
        tutorial_block("dashboard_tutorial.md", "## Full app styled", "def index()"),
        module.__dict__,
    )
    assert module.index() is not None
    state = SimpleNamespace(users=[], users_for_graph=[], add_user_dialog_open=True)
    state.transform_data = lambda: module.State.transform_data.fn(state)
    module.State.add_user.fn(
        state, {"name": "Ada", "email": "ada@example.com", "gender": "Female"}
    )
    assert state.users[0].name == "Ada"
    assert state.users_for_graph == [{"name": "Female", "value": 1}]
    assert state.add_user_dialog_open is False


def test_chat_stream_handles_non_text_chunks_and_history(chat_module, monkeypatch):
    """Role-only and usage chunks must not drop the subsequent response."""
    assert chat_module.State.answer.is_background
    _, client, stream = fake_client(
        monkeypatch,
        chat_module,
        [
            chunk(None),
            SimpleNamespace(choices=[]),
            chunk("Hello"),
            chunk(" world"),
            chunk(None),
        ],
    )
    state = SimpleNamespace(
        question=" Next? ",
        chat_history=[("First?", "First answer")],
        processing=False,
        error="",
    )
    run_answer(chat_module, state)
    assert client.chat.completions.create.call_args.kwargs["model"] == chat_module.MODEL
    assert state.chat_history[-1] == ("Next?", "Hello world")
    assert state.question == ""
    assert state.processing is False
    assert client.chat.completions.create.call_args.kwargs["messages"] == [
        {"role": "user", "content": "First?"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": "Next?"},
    ]
    client.__aexit__.assert_awaited_once()
    stream.__aexit__.assert_awaited_once()


@pytest.mark.parametrize(("question", "processing"), [("   ", False), ("Hello", True)])
def test_chat_ignores_empty_or_duplicate_submissions(
    chat_module, monkeypatch, question, processing
):
    """Blank input and an in-flight request must not call the provider."""
    factory, _, _ = fake_client(monkeypatch, chat_module, [])
    state = SimpleNamespace(
        question=question, chat_history=[], processing=processing, error=""
    )
    run_answer(chat_module, state)
    factory.assert_not_called()
    assert state.chat_history == []


def test_chat_api_error_restores_controls(chat_module, monkeypatch):
    """A failed request leaves no unanswered turn and makes retry possible."""
    import httpx
    from openai import APIConnectionError

    _, client, _ = fake_client(monkeypatch, chat_module, [])
    client.chat.completions.create.side_effect = APIConnectionError(
        request=httpx.Request("POST", OPENAI_CHAT_ENDPOINT)
    )
    state = SimpleNamespace(
        question="Hello", chat_history=[], processing=False, error=""
    )
    run_answer(chat_module, state)
    assert state.processing is False
    assert state.error
    assert state.chat_history == []
    assert state.question == "Hello"


@pytest.mark.parametrize("name", ["dashboard_tutorial.md", "chatapp_tutorial.md"])
def test_all_python_blocks_parse(name):
    """Every copyable snippet and embedded demo must be valid Python."""
    text = (DOCS / name).read_text()
    blocks = re.findall(r"^```python[^\n]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    for index, block in enumerate(blocks):
        compile(block, f"{name}:block-{index}", "exec")


def test_chat_final_ui_builds_with_copied_modules(chat_module, monkeypatch):
    """The three final files must work together as an actual component tree."""
    package = ModuleType("chatapp")
    package.__path__ = []
    styles = ModuleType("chatapp.style")
    exec(
        tutorial_block("chatapp_tutorial.md", "### Final Code", "# style.py"),
        styles.__dict__,
    )
    package.style = styles
    monkeypatch.setitem(sys.modules, "chatapp", package)
    monkeypatch.setitem(sys.modules, "chatapp.style", styles)
    monkeypatch.setitem(sys.modules, "chatapp.state", chat_module)
    module = ModuleType("tutorial_chat_ui")
    exec(
        tutorial_block("chatapp_tutorial.md", "### Final Code", "app.add_page(index)"),
        module.__dict__,
    )
    assert module.index() is not None


def test_chat_missing_api_key_keeps_question(chat_module, monkeypatch):
    """A missing key must give an actionable error without consuming input."""
    factory, _, _ = fake_client(monkeypatch, chat_module, [])
    monkeypatch.delenv("OPENAI_API_KEY")
    state = SimpleNamespace(
        question="Hello", chat_history=[], processing=False, error=""
    )
    run_answer(chat_module, state)
    factory.assert_not_called()
    assert state.question == "Hello"
    assert state.chat_history == []
    assert "OPENAI_API_KEY" in state.error


def load_application_demo(monkeypatch, relative_path, demo_id=None):
    """Execute the exact copyable demo shown on an application guide."""
    source = (DOCS.parent / relative_path).read_text()
    marker = (
        rf"(?: demo exec)?[^\n]*\bid={re.escape(demo_id)}\b"
        if demo_id
        else " demo exec"
    )
    blocks = re.findall(
        rf"^```python{marker}[^\n]*\n(.*?)^```",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert len(blocks) == 1
    module = ModuleType(f"application_demo_{uuid4().hex}")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(blocks[0], module.__dict__)
    return module


def selection_event(rows, *, cleared=False, truncated=False):
    """Build the selection portion consumed by the XY handler."""
    return {"selection": {"rows": rows, "cleared": cleared, "truncated": truncated}}


def linked_state(module):
    """Hydrate a separate session as the runtime does."""
    import reflex as rx
    from reflex.istate.data import RouterData

    root = rx.State(
        _reflex_internal_init=True,
        rx_router_session=RouterData.from_router_data({"token": str(uuid4())}).session,
    )
    return root.get_substate(
        tuple(module.LinkedChartsState.get_full_name().split("."))[1:]
    )


def revenue_columns(state):
    """Read the data published by the exact tutorial computed var."""
    from reflex_xy.registry import registry

    return registry.get_columns(state.revenue_data.token).columns


def test_linked_charts_selection_reset_and_session_isolation(monkeypatch):
    """A real state updates both linked views without changing another session."""
    module = load_application_demo(
        monkeypatch, "getting_started/linked_charts_tutorial.md"
    )
    assert module.linked_charts() is not None
    state = linked_state(module)
    other = linked_state(module)
    assert state.source_data.token != other.source_data.token
    assert len(state.visible_rows) == 4
    state.select_points(
        selection_event([
            {"trace": 0, "index": 1},
            {"trace": 0, "index": 0},
            {"trace": 0, "index": 1},
        ])
    )
    assert state.selected_ids == ["order-b", "order-a"]
    assert [row["id"] for row in state.visible_rows] == ["order-a", "order-b"]
    assert revenue_columns(state)["revenue"] == [120, 180]
    assert len(other.visible_rows) == 4
    # A new selection replaces, rather than intersects with, the previous subset.
    state.select_points(selection_event([{"trace": 0, "index": 3}]))
    assert [row["id"] for row in state.visible_rows] == ["order-d"]
    assert revenue_columns(state)["revenue"] == [240]
    state.select_points(selection_event([]))
    assert state.visible_rows == []
    assert revenue_columns(state)["revenue"] == []
    state.select_points(selection_event([], cleared=True))
    assert len(state.visible_rows) == 4
    state.clear_selection()
    assert len(state.visible_rows) == 4
    assert state.chart_revision == 1
    assert other.chart_revision == 0


@pytest.mark.parametrize(
    "row",
    [
        {},
        {"trace": 1, "index": 0},
        {"trace": 0, "index": -1},
        {"trace": 0, "index": 10},
        {"trace": 0, "index": "1"},
        {"trace": 0, "index": True},
    ],
)
@pytest.mark.parametrize("truncated", [False, True])
def test_linked_charts_rejects_invalid_source_positions(monkeypatch, row, truncated):
    """Invalid positions retain the previous filter, even in a mixed selection."""
    module = load_application_demo(
        monkeypatch, "getting_started/linked_charts_tutorial.md"
    )
    state = linked_state(module)
    state.select_points(selection_event([{"trace": 0, "index": 1}]))
    rows = [{"trace": 0, "index": 0}, row]
    if truncated:
        monkeypatch.setattr(
            module.rxy,
            "resolve_selection",
            lambda event: SimpleNamespace(rows=lambda: rows),
        )
    state.select_points(selection_event(rows, truncated=truncated))
    assert state.selected_ids == ["order-b"]
    assert state.selection_error == "Selection unavailable. Please select again."
    state.select_points(selection_event([]))
    assert state.selected_ids == []
    assert state.selection_error == ""


def test_xy_data_handles_recover_after_pre_session_render(monkeypatch):
    """The empty compile-time handle must not stay cached after hydration."""
    import reflex as rx
    from reflex.istate.data import RouterData

    module = load_application_demo(
        monkeypatch, "getting_started/linked_charts_tutorial.md"
    )
    root = rx.State(_reflex_internal_init=True)
    state = root.get_substate(
        tuple(module.LinkedChartsState.get_full_name().split("."))[1:]
    )
    assert state.source_data.token == ""
    assert state.revenue_data.token == ""
    # Set the session without dirtying computed vars to reproduce the cached handle.
    object.__setattr__(
        root,
        "rx_router_session",
        RouterData.from_router_data({"token": str(uuid4())}).session,
    )
    assert state.source_data.token
    assert state.revenue_data.token


def test_linked_charts_resolves_truncated_selections(monkeypatch):
    """Do not silently apply only the event's bounded row sample."""
    from types import SimpleNamespace

    module = load_application_demo(
        monkeypatch, "getting_started/linked_charts_tutorial.md"
    )
    state = linked_state(module)
    monkeypatch.setattr(
        module.rxy,
        "resolve_selection",
        lambda event: SimpleNamespace(
            rows=lambda: [{"trace": 0, "index": 2}, {"trace": 0, "index": 3}]
        ),
    )
    state.select_points(selection_event([{"trace": 0, "index": 2}], truncated=True))
    assert state.selected_ids == ["order-c", "order-d"]
    monkeypatch.setattr(module.rxy, "resolve_selection", lambda event: None)
    state.select_points(selection_event([], truncated=True))
    assert state.selected_ids == ["order-c", "order-d"]
    assert state.selection_error
    state.clear_selection()
    assert state.selection_error == ""


def test_function_app_validates_and_clears_stale_results(monkeypatch):
    """Valid calculations and bad submissions produce mutually exclusive feedback."""
    module = load_application_demo(
        monkeypatch, "getting_started/python_function_to_app.md"
    )
    assert module.payment_app() is not None
    assert module.monthly_payment(12000, 0, 1) == 1000
    assert module.monthly_payment(12000, 1e-12, 1) == pytest.approx(1000)
    assert module.monthly_payment(10000, 5, 3) == pytest.approx(299.70897)
    state = module.PaymentState(_reflex_internal_init=True)
    state.calculate({"amount": "12000", "rate": "0", "years": "1"})
    assert state.result == "Monthly payment: $1,000.00"
    assert state.error == ""
    for bad_input in ("oops", "nan", "inf", "-1"):
        state.calculate({"amount": bad_input, "rate": "0", "years": "1"})
        assert state.result == ""
        assert state.error
    state.calculate({"amount": "12000", "rate": "0", "years": "0"})
    assert state.error
    state.calculate({"amount": "12000", "rate": "0", "years": "1"})
    assert state.error == ""


def test_model_interface_predictions_and_invalid_input(monkeypatch):
    """The copied model example can run inference and recover after bad input."""
    module = load_application_demo(
        monkeypatch, "guides/model_and_media_interfaces.md", "model_interface_demo"
    )
    assert module.model_interface() is not None
    assert module.predict_flower(1.4, 0.2) == "setosa"
    assert module.predict_flower(4.7, 1.4) == "versicolor"
    assert module.predict_flower(6.0, 2.5) == "virginica"
    state = module.ModelInterfaceState(_reflex_internal_init=True)
    state.predict({"length": "1.4", "width": "0.2"})
    assert state.prediction == "setosa"
    for bad_input in ("", "oops", "nan", "inf", "-1", "11"):
        state.predict({"length": bad_input, "width": "0.2"})
        assert state.prediction == ""
        assert state.error
    state.predict({"length": "6.0", "width": "2.5"})
    assert state.prediction == "virginica"
    assert state.error == ""


def image_demo(monkeypatch):
    """Load the copyable image workflow from the model guide."""
    return load_application_demo(
        monkeypatch, "guides/model_and_media_interfaces.md", "image_workflow_demo"
    )


def audio_demo(monkeypatch):
    """Load the exact standalone WAV example from the media guide."""
    return load_application_demo(
        monkeypatch, "guides/model_and_media_interfaces.md", "audio_workflow_demo"
    )


def wav_bytes(samples=(0, 1000, -2000, 500), channels=1, rate=16000, width=2):
    """Encode a deterministic WAV fixture with configurable format and samples."""
    output = BytesIO()
    with wave.open(output, "wb") as result:
        result.setnchannels(channels)
        result.setframerate(rate)
        result.setsampwidth(width)
        result.writeframes(
            struct.pack(f"<{len(samples)}h", *samples) if width == 2 else bytes(samples)
        )
    return output.getvalue()


@pytest.mark.parametrize("channels", [1, 2])
def test_audio_workflow_normalizes_samples_without_changing_timing(
    monkeypatch, channels
):
    """Known PCM samples retain sign, channel ordering, frame count, and rate."""
    module = audio_demo(monkeypatch)
    result, summary = module.normalize_audio(wav_bytes(channels=channels))
    with wave.open(BytesIO(result), "rb") as decoded:
        assert decoded.getparams()[:4] == (channels, 2, 16000, 4 // channels)
        assert struct.unpack("<4h", decoded.readframes(4)) == (0, 13106, -26213, 6553)
    assert "13.11x gain" in summary
    monkeypatch.setattr(Upload, "is_used", Upload.is_used)
    assert module.audio_workflow() is not None


@pytest.mark.parametrize(
    "samples, expected",
    [
        ((0, 0), (0, 0)),
        ((-32768, 32767), (-26213, 26212)),
    ],
)
def test_audio_workflow_handles_silence_and_full_scale(monkeypatch, samples, expected):
    """Silence avoids division by zero and full-scale peaks avoid overflow."""
    result, _ = audio_demo(monkeypatch).normalize_audio(wav_bytes(samples=samples))
    with wave.open(BytesIO(result), "rb") as decoded:
        assert struct.unpack("<2h", decoded.readframes(2)) == expected


@pytest.mark.parametrize(
    "data, message",
    [
        (b"", "valid uncompressed"),
        (b"not a WAV", "valid uncompressed"),
        (
            b"RIFF"
            + struct.pack("<I", 16)
            + b"WAVEJUNK"
            + struct.pack("<I", 1000)
            + b"x",
            "valid uncompressed",
        ),
        (wav_bytes()[:-1], "incomplete"),
        (wav_bytes(samples=()), "10 seconds"),
        (wav_bytes(rate=96000), "8-48 kHz"),
        (wav_bytes(samples=(1, 2, 3), channels=3), "mono or stereo"),
        (wav_bytes(samples=(128, 128), width=1), "16-bit"),
        (wav_bytes(samples=(0,) * 80001, rate=8000), "10 seconds"),
        (b"x" * (512 * 1024 + 1), "512 KiB"),
    ],
)
def test_audio_workflow_rejects_malformed_or_unsupported_uploads(
    monkeypatch, data, message
):
    """Server-side checks reject invalid formats, truncation, and resource limits."""
    with pytest.raises(ValueError, match=message):
        audio_demo(monkeypatch).normalize_audio(data)


def test_audio_workflow_rejects_partial_sample_frame(monkeypatch):
    """An odd-sized 16-bit data chunk must not silently drop a partial sample."""
    malformed = bytearray(wav_bytes(samples=(1, 2)))
    malformed[40:44] = struct.pack("<I", 3)
    with pytest.raises(ValueError, match="incomplete"):
        audio_demo(monkeypatch).normalize_audio(bytes(malformed))


def run_audio_upload(state, files):
    """Consume the upload handler and collect its visible progress states."""

    async def consume():
        return [state.processing async for _ in state.process_audio(files)]

    return asyncio.run(consume())


def test_audio_workflow_upload_recovery_download_and_session_isolation(monkeypatch):
    """Only the submitting session receives a result; invalid replacements clear it."""
    import base64

    module = audio_demo(monkeypatch)
    state = module.AudioWorkflowState(_reflex_internal_init=True)
    other = module.AudioWorkflowState(_reflex_internal_init=True)
    upload = SimpleNamespace(read=AsyncMock(return_value=wav_bytes()))
    assert run_audio_upload(state, [upload]) == [True]
    upload.read.assert_awaited_once_with(module.MAX_AUDIO_BYTES + 1)
    assert base64.b64decode(state.preview.split(",", 1)[1]) == state._output_wav
    assert state.download_audio() is not None
    assert other.preview == "" and other._output_wav == b""
    bad = SimpleNamespace(read=AsyncMock(return_value=b"bad"))
    run_audio_upload(state, [bad])
    assert state.error and not state.processing
    assert state.preview == "" and state.summary == "" and state._output_wav == b""
    assert state.download_audio() is None
    run_audio_upload(state, [upload])
    assert state.preview and not state.error
    state.clear_audio()
    assert state.preview == "" and state._output_wav == b"" and state.summary == ""


def test_audio_workflow_rejects_multiple_files_and_handles_read_errors(monkeypatch):
    """Missing, multiple, and unreadable inputs recover without a stale player."""
    module = audio_demo(monkeypatch)
    state = module.AudioWorkflowState(_reflex_internal_init=True)
    upload = SimpleNamespace(read=AsyncMock(side_effect=OSError("read failed")))
    for files in ([], [upload, upload]):
        assert run_audio_upload(state, files) == []
        assert "Choose one" in state.error
    upload.read.assert_not_awaited()
    run_audio_upload(state, [upload])
    assert "could not be read" in state.error and not state.processing


def test_audio_workflow_ignores_overlapping_submission_and_clear(monkeypatch):
    """A busy session keeps its current job and cannot enqueue another upload."""
    module = audio_demo(monkeypatch)
    state = module.AudioWorkflowState(_reflex_internal_init=True)
    state.processing = True
    upload = SimpleNamespace(read=AsyncMock(return_value=wav_bytes()))
    assert run_audio_upload(state, [upload]) == []
    assert state.clear_audio() is None
    upload.read.assert_not_awaited()
    assert state.processing


def image_bytes(size=(800, 400), image_format="PNG"):
    """Create a small deterministic upload without relying on external assets."""
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format=image_format)
    return output.getvalue()


@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
def test_image_workflow_prepares_bounded_grayscale_png(monkeypatch, image_format):
    """The processing function produces a usable PNG with preserved aspect ratio."""
    module = image_demo(monkeypatch)
    png, summary = module.prepare_image(image_bytes(image_format=image_format))
    with Image.open(BytesIO(png)) as result:
        assert result.format == "PNG"
        assert result.mode == "L"
        assert result.size == (512, 256)
        assert result.getpixel((0, 0)) == pytest.approx(76, abs=1)
        assert not result.getexif()
    assert "800 x 400" in summary and "512 x 256" in summary
    # Construct the standalone UI without leaking its upload flag to the docs app.
    monkeypatch.setattr(Upload, "is_used", Upload.is_used)
    assert module.image_workflow() is not None


@pytest.mark.parametrize(
    "bad_data",
    [b"", b"not an image", image_bytes(image_format="GIF")],
    ids=["empty", "malformed", "unsupported-format"],
)
def test_image_workflow_rejects_invalid_content(monkeypatch, bad_data):
    """File content, rather than a browser-supplied filename or MIME, is checked."""
    with pytest.raises(ValueError, match="valid PNG or JPEG"):
        image_demo(monkeypatch).prepare_image(bad_data)


def test_image_workflow_bounds_bytes_and_pixels(monkeypatch):
    """Both compressed size and decoded image dimensions are bounded."""
    module = image_demo(monkeypatch)
    with pytest.raises(ValueError, match="2 MiB"):
        module.prepare_image(b"x" * (module.MAX_IMAGE_BYTES + 1))
    with pytest.raises(ValueError, match="4 million pixels"):
        module.prepare_image(image_bytes(size=(2001, 2000)))


def run_image_upload(state, files):
    """Exercise the upload generator without an optional pytest async plugin."""

    async def collect_progress():
        return [state.processing async for _ in state.process_image(files)]

    return asyncio.run(collect_progress())


def test_image_workflow_upload_recovery_and_session_isolation(monkeypatch):
    """Uploads report progress, clear stale results on failure, and stay per-session."""
    module = image_demo(monkeypatch)
    state = module.ImageWorkflowState(_reflex_internal_init=True)
    other = module.ImageWorkflowState(_reflex_internal_init=True)
    file = SimpleNamespace(read=AsyncMock(return_value=image_bytes()))
    progress = run_image_upload(state, [file])
    assert progress == [True]
    assert not state.processing
    assert state.preview.startswith("data:image/png;base64,")
    assert state._output_png.startswith(b"\x89PNG")
    assert state.download_image() is not None
    assert other.preview == "" and other._output_png == b""
    file.read.assert_awaited_once_with(module.MAX_IMAGE_BYTES + 1)

    invalid = SimpleNamespace(read=AsyncMock(return_value=b"bad"))
    run_image_upload(state, [invalid])
    assert state.error and not state.processing
    assert state.preview == "" and state._output_png == b""
    assert state.download_image() is None
    run_image_upload(state, [file])
    assert state.preview and not state.error
    state.clear_image()
    assert state.preview == "" and state._output_png == b"" and state.summary == ""


def test_image_workflow_handles_read_failure_and_missing_file(monkeypatch):
    """Unreadable or absent uploads produce feedback without leaving the UI busy."""
    module = image_demo(monkeypatch)
    state = module.ImageWorkflowState(_reflex_internal_init=True)
    unreadable = SimpleNamespace(read=AsyncMock(side_effect=OSError("read failed")))
    run_image_upload(state, [unreadable])
    assert "could not be read" in state.error
    assert not state.processing and state.preview == ""
    run_image_upload(state, [])
    assert "Choose one" in state.error


def test_image_workflow_applies_orientation_and_strips_metadata(monkeypatch):
    """A rotated photo displays correctly and does not copy uploaded metadata."""
    source = Image.new("RGB", (800, 400), "red")
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "Private image description"
    data = BytesIO()
    source.save(data, format="JPEG", exif=exif)
    png, summary = image_demo(monkeypatch).prepare_image(data.getvalue())
    with Image.open(BytesIO(png)) as result:
        assert result.size == (256, 512)
        assert not result.getexif()
        assert not result.info
    assert "400 x 800" in summary


def pandas_demo(monkeypatch):
    """Load the standalone pandas example exactly as readers copy it."""
    return load_application_demo(
        monkeypatch, "getting_started/pandas_data_app.md", "pandas_data_app"
    )


def test_pandas_filters_aggregate_all_matches_beyond_preview(monkeypatch):
    """The bounded preview must not silently truncate totals or the download."""
    module = pandas_demo(monkeypatch)
    data = b"region,product,units\n" + b"North,Tea,2\n" * 70 + b"South,Coffee,3\n"
    records = module.read_orders(data)
    rows, summary, count, units = module.analyze_orders(records, "All", "tEa")
    assert len(rows) == 50
    assert count == 70 and units == 140
    assert summary == [{"region": "North", "units": 140}]
    assert module.analyze_orders(records, "South", "Tea") == ([], [], 0, 0)
    # Product search is literal, so regex symbols cannot match everything.
    assert module.analyze_orders(records, "All", ".*") == ([], [], 0, 0)
    monkeypatch.setattr(Upload, "is_used", Upload.is_used)
    assert module.pandas_data_app() is not None


def test_pandas_chart_uses_complete_filtered_totals(monkeypatch):
    """Chart data follows filters and full aggregates, including empty results."""
    from reflex.istate.data import RouterData
    from reflex_xy.registry import registry

    module = pandas_demo(monkeypatch)
    root = rx.State(
        _reflex_internal_init=True,
        rx_router_session=RouterData.from_router_data({"token": str(uuid4())}).session,
    )
    state = root.get_substate(
        tuple(module.PandasAppState.get_full_name().split("."))[1:]
    )
    state.load_sample(False)
    assert registry.get_columns(state.region_data.token).columns == {
        "region": ["North", "South", "West"],
        "units": [17, 7, 9],
    }
    state._orders = module.read_orders(
        b"region,product,units\n" + b"North,Tea,2\n" * 70 + b"South,Coffee,3\n"
    )
    state.apply_filters({"region": "All", "product": "Tea"})
    assert len(state.rows) == 50 and state.matching_count == 70
    assert registry.get_columns(state.region_data.token).columns == {
        "region": ["North"],
        "units": [140],
    }
    state.apply_filters({"region": "South", "product": "Tea"})
    assert state.total_units == 0 and not state.rows
    assert registry.get_columns(state.region_data.token).columns == {
        "region": [],
        "units": [],
    }


def test_pandas_preview_does_not_enable_uploads(monkeypatch):
    """Embedding the shared dashboard must not enable the docs upload route."""
    module = pandas_demo(monkeypatch)
    monkeypatch.setattr(Upload, "is_used", False)
    assert module.pandas_preview() is not None
    assert not Upload.is_used
    assert module.pandas_data_app() is not None
    assert Upload.is_used


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"region,product,units\n",
        b"region,product,units\nNorth,Tea,2,extra\n",
        b"region,product,units\nNorth,Tea\n",
        b"region,region,units\nNorth,Tea,2\n",
        b"region,product,units\nNorth,\xff,2\n",
        b'region,product,units\nNorth,"Tea,2',
        b"region,product,units\nOther,Tea,2\n",
        b"region,product,units\nNorth, ,2\n",
        b"region,product,units\nNorth,Tea,-1\n",
        b"region,product,units\nNorth,Tea,1.5\n",
        b"region,product,units\nNorth,Tea,nan\n",
        b"region,product,units\nNorth,Tea,1000001\n",
        b"region,product,units\nNorth," + b"a" * 81 + b",2\n",
    ],
)
def test_pandas_rejects_malformed_schema_and_values(monkeypatch, data):
    """CSV structure, encoding, and domain values are checked on the backend."""
    with pytest.raises(ValueError):
        pandas_demo(monkeypatch).read_orders(data)


def test_pandas_bounds_rows_bytes_and_preserves_text(monkeypatch):
    """A byte-order mark and NA-like names are valid; oversized inputs are not."""
    module = pandas_demo(monkeypatch)
    assert module.read_orders(b"\xef\xbb\xbfregion,product,units\nNorth,NA,0\n") == [
        {"region": "North", "product": "NA", "units": 0}
    ]
    with pytest.raises(ValueError, match="2 MiB"):
        module.read_orders(b"x" * (module.MAX_CSV_BYTES + 1))
    with pytest.raises(ValueError, match="10,000"):
        module.read_orders(b"region,product,units\n" + b"North,Tea,1\n" * 10_001)


def test_pandas_upload_does_not_change_process_warning_filters(monkeypatch):
    """A parser running in a worker must leave other sessions' warnings alone."""
    module = pandas_demo(monkeypatch)
    original_filters = list(warnings.filters)
    read_orders = module.read_orders

    def trace_parser(frame, event, arg):
        """Check the warning policy throughout execution of the copied parser."""
        if frame.f_code is read_orders.__code__:
            assert warnings.filters == original_filters
        return trace_parser

    async def parse():
        """Exercise the same worker-thread boundary as the upload handler."""

        def worker():
            """Monitor warning filters while parsing a valid upload."""
            sys.settrace(trace_parser)
            try:
                return read_orders(module.SAMPLE_CSV)
            finally:
                sys.settrace(None)

        return await asyncio.to_thread(worker)

    assert len(asyncio.run(parse())) == 4


def run_csv_upload(state, files):
    """Run the copied async handler and inspect its progress boundary."""

    async def collect():
        return [state.processing async for _ in state.upload_csv(files)]

    return asyncio.run(collect())


def test_pandas_upload_filter_download_and_session_isolation(monkeypatch):
    """Upload, filtering, download, and error recovery operate on one session."""
    module = pandas_demo(monkeypatch)
    state = module.PandasAppState(_reflex_internal_init=True)
    other = module.PandasAppState(_reflex_internal_init=True)
    upload = SimpleNamespace(read=AsyncMock(return_value=module.SAMPLE_CSV))
    assert run_csv_upload(state, [upload]) == [True]
    upload.read.assert_awaited_once_with(module.MAX_CSV_BYTES + 1)
    assert (state.loaded_count, state.matching_count, state.total_units) == (4, 4, 33)
    assert other._orders == [] and other.rows == []
    state.apply_filters({"region": "North", "product": "tea"})
    assert (state.matching_count, state.total_units) == (1, 12)
    download = MagicMock()
    monkeypatch.setattr(module.rx, "download", download)
    state.download_summary()
    assert download.call_args.kwargs["data"] == "region,units\nNorth,12\n"
    state.apply_filters({"region": "South", "product": "tea"})
    assert not state.rows and not state.summary
    assert state.download_summary() is None
    invalid = SimpleNamespace(read=AsyncMock(return_value=b"bad"))
    run_csv_upload(state, [invalid])
    assert state.error and not state.processing
    assert state.loaded_count == 0 and state._orders == [] and state.summary == []
    state.load_sample()
    assert state.loaded_count == 4 and not state.error
    assert state.region == "South" and state.product == "tea"
    state.apply_filters({"region": "All", "product": ""})
    assert state.total_units == 33


def test_pandas_failed_read_duplicate_and_invalid_filter(monkeypatch):
    """Failure paths restore controls without leaking stale output."""
    module = pandas_demo(monkeypatch)
    state = module.PandasAppState(_reflex_internal_init=True)
    state.load_sample()
    unreadable = SimpleNamespace(read=AsyncMock(side_effect=OSError("read failed")))
    run_csv_upload(state, [unreadable])
    assert "could not be read" in state.error
    assert state.loaded_count == 0 and not state.processing
    run_csv_upload(state, [])
    assert "Choose one" in state.error
    state.load_sample()
    state.apply_filters({"region": "Unknown", "product": ""})
    assert state.error and state.region == "All" and state.total_units == 33
    state.processing = True
    assert run_csv_upload(state, [unreadable]) == []
    state.apply_filters({"region": "North", "product": "Tea"})
    assert state.region == "All" and state.download_summary() is None


class DocumentSession(SimpleNamespace):
    """Check that the copied document app mutates state under its lock."""

    def __setattr__(self, name, value):
        """Require a lock before changing session fields."""
        assert STATE_LOCKED.get(), f"Unlocked assignment: {name}"
        super().__setattr__(name, value)

    async def __aenter__(self):
        """Enter the background event's state lock."""
        assert not STATE_LOCKED.get()
        STATE_LOCKED.set(True)
        return self

    async def __aexit__(self, *args):
        """Release the lock before external work resumes."""
        STATE_LOCKED.set(False)


@pytest.fixture
def document_demo(monkeypatch):
    """Load the actual complete document assistant, including its SDK import."""
    return load_application_demo(
        monkeypatch, "guides/ai_applications.md", "document_assistant"
    )


def document_session():
    """Create an independent session without prior results."""
    return DocumentSession(answer="", sources=[], error="", status="", processing=False)


def ask_document(module, state, question):
    """Execute the exact event with a submitted question."""
    asyncio.run(module.DocumentState.ask.fn(state, {"question": question}))


def test_document_permissions_precede_ranking(document_demo, monkeypatch):
    """An unauthorized passage is neither scored nor returned to the reader."""
    module = document_demo
    scanned = []
    original = module.words

    def tracked_words(text):
        scanned.append(text)
        return original(text)

    monkeypatch.setattr(module, "words", tracked_words)
    assert module.retrieve("acquisition budget", "alice") == []
    assert not any("420000" in text for text in scanned)
    assert [p.source_id for p in module.retrieve("acquisition budget", "bob")] == [
        "finance"
    ]
    assert module.retrieve("annual leave", "unknown") == []
    assert module.retrieve("cafeteria menu", "alice") == []
    assert [p.source_id for p in module.retrieve("annual leave", "alice")] == ["leave"]


@pytest.mark.parametrize("reader", ["", "unknown", "alice"])
def test_document_no_match_or_invalid_identity_skips_model(
    document_demo, monkeypatch, reader
):
    """Lack of access must not leak passages to a model or the client."""
    module = document_demo
    monkeypatch.setenv("REFLEX_DEMO_READER", reader)
    generate = AsyncMock()
    monkeypatch.setattr(module, "generate_answer", generate)
    state = document_session()
    ask_document(module, state, "acquisition budget")
    generate.assert_not_called()
    assert not state.answer and not state.sources and not state.processing
    assert bool(state.error) == (reader != "alice")


def test_document_rejects_unknown_citation_and_recovers(document_demo, monkeypatch):
    """A model cannot reveal a hidden source by naming its known identifier."""
    module = document_demo
    monkeypatch.setenv("REFLEX_DEMO_READER", "alice")
    generate = AsyncMock(
        return_value=module.GroundedAnswer(
            claims=[module.Claim(text="A claim", source_ids=["finance"])]
        )
    )
    monkeypatch.setattr(module, "generate_answer", generate)
    state, other = document_session(), document_session()
    ask_document(module, state, "annual leave")
    assert state.error and not state.answer and not state.sources
    assert not state.processing and not other.answer and not other.error
    assert [p.source_id for p in generate.call_args.args[1]] == ["leave"]
    generate.return_value = module.GroundedAnswer(
        claims=[module.Claim(text="Employees receive 20 days.", source_ids=["leave"])]
    )
    ask_document(module, state, "annual leave")
    assert not state.error and "20 days" in state.answer
    assert state.sources[0]["text"] == module.PASSAGES[0].text
    assert "420000" not in str(vars(state))
    assert not other.answer and not other.sources
    assert module.DocumentState.ask.is_background
    assert module.document_assistant() is not None


@pytest.mark.parametrize("question", ["", "   ", "x" * 1001])
def test_document_invalid_question_skips_model(document_demo, monkeypatch, question):
    """Blank and oversized submissions do not start external work."""
    generate = AsyncMock()
    monkeypatch.setattr(document_demo, "generate_answer", generate)
    state = document_session()
    ask_document(document_demo, state, question)
    generate.assert_not_called()
    assert not state.processing


@pytest.mark.parametrize("failure", [TimeoutError(), ValueError("invalid response")])
def test_document_error_and_empty_response(document_demo, monkeypatch, failure):
    """Timeouts and unsupported answers publish no stale answer or citations."""
    module = document_demo
    monkeypatch.setenv("REFLEX_DEMO_READER", "alice")
    generate = AsyncMock(side_effect=failure)
    monkeypatch.setattr(module, "generate_answer", generate)
    state = document_session()
    ask_document(module, state, "annual leave")
    assert state.error and not state.processing and not state.sources
    generate.side_effect = None
    generate.return_value = module.GroundedAnswer(claims=[])
    ask_document(module, state, "annual leave")
    assert not state.error and not state.answer and not state.sources
    assert "do not answer" in state.status


def test_document_concurrent_submission_is_rejected(document_demo, monkeypatch):
    """A second submission cannot overwrite the first request's pending state."""
    module = document_demo
    monkeypatch.setenv("REFLEX_DEMO_READER", "alice")
    calls = []
    state = document_session()

    async def generate(question, passages):
        assert not STATE_LOCKED.get()
        calls.append(question)
        await module.DocumentState.ask.fn(state, {"question": "laptop"})
        assert state.processing
        return module.GroundedAnswer(
            claims=[module.Claim(text="20 days", source_ids=["leave"])]
        )

    monkeypatch.setattr(module, "generate_answer", generate)
    ask_document(module, state, "annual leave")
    assert calls == ["annual leave"]
    assert state.answer == "20 days [leave]" and not state.processing


@pytest.mark.parametrize("missing", ["OPENAI_API_KEY", "OPENAI_MODEL"])
def test_document_missing_configuration(document_demo, monkeypatch, missing):
    """Missing provider configuration produces a retryable state without a call."""
    monkeypatch.setenv("REFLEX_DEMO_READER", "alice")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test")
    monkeypatch.setenv("OPENAI_MODEL", "offline-model")
    monkeypatch.delenv(missing)
    factory = MagicMock()
    monkeypatch.setattr(document_demo, "AsyncOpenAI", factory)
    state = document_session()
    ask_document(document_demo, state, "annual leave")
    factory.assert_not_called()
    assert state.error and not state.processing


@pytest.mark.parametrize(
    "outcome", ["answer", "refusal", "incomplete", "invalid-json", "api-error"]
)
def test_document_real_sdk_protocol(document_demo, monkeypatch, outcome):
    """The installed SDK parses the real Responses JSON format without network I/O."""
    import json

    import httpx
    from openai import AsyncOpenAI

    module = document_demo
    requests = []

    def respond(request):
        assert not STATE_LOCKED.get()
        payload = json.loads(request.content)
        requests.append(payload)
        if outcome == "api-error":
            return httpx.Response(500, json={"error": {"message": "offline failure"}})
        text = json.dumps({"claims": [{"text": "20 days", "source_ids": ["leave"]}]})
        if outcome == "invalid-json":
            text = "not json"
        content = (
            {"type": "refusal", "refusal": "I cannot answer."}
            if outcome == "refusal"
            else {"type": "output_text", "text": text, "annotations": []}
        )
        return httpx.Response(
            200,
            json={
                "id": "resp_offline",
                "object": "response",
                "created_at": 1,
                "model": "offline-model",
                "status": "incomplete" if outcome == "incomplete" else "completed",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_offline",
                        "role": "assistant",
                        "status": "completed",
                        "content": [content],
                    }
                ],
            },
        )

    def client(**kwargs):
        return AsyncOpenAI(
            **kwargs,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        )

    monkeypatch.setenv("REFLEX_DEMO_READER", "alice")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test")
    monkeypatch.setenv("OPENAI_MODEL", "offline-model")
    monkeypatch.setattr(module, "AsyncOpenAI", client)
    state = document_session()
    ask_document(module, state, "annual leave")
    assert len(requests) == 1
    payload = requests[0]
    assert payload["store"] is False and payload["max_output_tokens"] == 2048
    assert payload["text"]["format"]["type"] == "json_schema"
    context = json.loads(payload["input"])
    assert [p["source_id"] for p in context["passages"]] == ["leave"]
    assert "420000" not in json.dumps(payload)
    assert bool(state.answer) == (outcome == "answer")
    assert bool(state.error) == (outcome != "answer")
    assert not state.processing
