---
components:
    - rx.audio
---

# Audio

```python exec
import reflex as rx
```

The audio component can display an audio given an src path as an argument. This could either be a local path from the assets folder or an external link.

```python demo
rx.audio(
    url="https://www.learningcontainer.com/wp-content/uploads/2020/02/Kalimba.mp3", 
    width="400px",
    height="auto"
)
```

If we had a local file in the `assets` folder named `test.mp3` we could set `url="/test.mp3"` to view the audio file.
