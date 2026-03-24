---
components:
    - rx.audio
---

# Audio

```python exec
import reflex as rx
from pcweb.pages.docs import library
```

The audio component can display an audio given an src path as an argument. This could either be a local path from the assets folder or an external link.

```python demo
rx.audio(
    src="https://www.learningcontainer.com/wp-content/uploads/2020/02/Kalimba.mp3",
    width="400px",
    height="32px",
)
```

If we had a local file in the `assets` folder named `test.mp3` we could set `src="/test.mp3"` to view the audio file.

```md alert info
# How to let your user upload an audio file
To let a user upload an audio file to your app check out the [upload docs]({library.forms.upload.path}).
```
