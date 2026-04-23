import sys
from pathlib import Path

import pytest
from reflex.testing import AppHarness

# Add tests directory to Python path for absolute imports
sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(scope="session")
def reflex_web_app():
    app_root = Path(__file__).parent.parent
    from reflex_docs.whitelist import WHITELISTED_PAGES

    WHITELISTED_PAGES.extend(
        [
            "/events",
            "/vars",
            "/getting-started",
            "/library/graphing",
            "/api-reference/special-events",
        ]
    )

    with AppHarness.create(root=app_root) as harness:
        yield harness


@pytest.fixture
def browser_context_args():
    """Configure browser context with video recording."""
    return {
        "record_video_dir": "test-videos/",
        "record_video_size": {"width": 1280, "height": 720},
    }


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Create metadata mapping for video files on test failure and clean up videos for passed tests."""
    outcome = yield
    report = outcome.get_result()

    # Handle test completion (both pass and fail)
    if report.when == "call":
        page = None
        if hasattr(item, "funcargs"):
            if "page" in item.funcargs:
                page = item.funcargs["page"]
            else:
                # Look for page object in other fixtures
                for fixture_value in item.funcargs.values():
                    if hasattr(fixture_value, "page") and hasattr(
                        fixture_value.page, "video"
                    ):
                        page = fixture_value.page
                        break

        if page and hasattr(page, "video") and page.video:
            try:
                import time

                video_path = None
                for _ in range(3):
                    try:
                        video_path = page.video.path()
                        if video_path and Path(video_path).exists():
                            break
                    except Exception:
                        time.sleep(0.5)

                if not video_path:
                    print(f"Failed to get video path for test: {item.name}")
                    return

                video_file = Path(video_path)

                if report.failed:
                    # Test failed - keep video and create metadata
                    test_name = item.name

                    import fcntl
                    import json
                    import os

                    split_index = os.environ.get("PYTEST_SPLIT_INDEX", "1")
                    metadata_file = (
                        Path("test-videos") / f"video_metadata_{split_index}.json"
                    )
                    metadata_file.parent.mkdir(exist_ok=True)

                    with metadata_file.open("a+") as f:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        f.seek(0)
                        try:
                            content = f.read()
                            metadata = json.loads(content) if content.strip() else {}
                        except (json.JSONDecodeError, ValueError):
                            metadata = {}

                        video_filename = video_file.name
                        metadata[video_filename] = test_name

                        f.seek(0)
                        f.truncate()
                        json.dump(metadata, f, indent=2)
                else:
                    # Test passed - remove video file
                    if video_file.exists():
                        video_file.unlink()

            except Exception as e:
                print(f"Failed to process video for test {item.name}: {e}")
                import traceback

                traceback.print_exc()
        else:
            if report.failed:
                print(f"No video available for failed test: {item.name}")
                video_dir = Path("test-videos")
                if video_dir.exists():
                    import time

                    recent_videos = [
                        f
                        for f in video_dir.glob("*.webm")
                        if f.stat().st_mtime > (time.time() - 60)
                    ]
                    print(
                        f"Recent video files found: {[f.name for f in recent_videos]}"
                    )
