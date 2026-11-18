---
components:
  - rx.video
---

# Video

```python exec
import reflex as rx
```

The video component can display a video given an src path as an argument. This could either be a local path from the assets folder or an external link.

```python demo
rx.video(src="https://www.youtube.com/embed/9bZkp7q19f0", width="400px", height="auto")
```

```python test
def test_video_youtube_embed(demo):
    expect(
        demo.locator("[src='https://www.youtube.com/embed/9bZkp7q19f0']")
    ).to_have_count(1)
```

If we had a local file in the `assets` folder named `test.mp4` we could set `url="/test.mp4"` to view the video.

```md alert info
# How to let your user upload a video

To let a user upload a video to your app check out the [upload docs](/docs/library/forms/upload/).
```
