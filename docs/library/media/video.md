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
rx.video(
    url="https://www.youtube.com/embed/9bZkp7q19f0", 
    width="400px",
    height="auto"
)
```

If we had a local file in the `assets` folder named `test.mp4` we could set `url="/test.mp3"` to view the video.
