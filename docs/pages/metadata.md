```python exec

import reflex as rx

meta_data = (
"""
@rx.page(
    title='My Beautiful App',
    description='A beautiful app built with Reflex',
    image='/splash.png',
    meta=meta,
)
def index():
    return rx.text('A Beautiful App')

@rx.page(title='About Page')
def about():
    return rx.text('About Page')


meta = [
    {'name': 'theme_color', 'content': '#FFFFFF'},
    {'char_set': 'UTF-8'},
    {'property': 'og:url', 'content': 'url'},
]

app = rx.App()
"""  

)

```

# Page Metadata

You can add page metadata such as:

- The title to be shown in the browser tab
- The description as shown in search results
- The preview image to be shown when the page is shared on social media
- Any additional metadata

```python
{meta_data}
```
