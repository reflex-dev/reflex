"""Execute the copyable tutorial examples without calling external services."""

import asyncio
import re
import sys
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


def test_linked_charts_rejects_invalid_source_positions(monkeypatch):
    """Unrecognized traces and point positions cannot select unrelated records."""
    module = load_application_demo(
        monkeypatch, "getting_started/linked_charts_tutorial.md"
    )
    state = linked_state(module)
    state.select_points(
        selection_event([
            {},
            {"trace": 1, "index": 0},
            {"trace": 0, "index": -1},
            {"trace": 0, "index": 10},
            {"trace": 0, "index": "1"},
        ])
    )
    assert state.visible_rows == []


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
