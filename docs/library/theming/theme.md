---
 components:
     - rx.theme
---

# Theme

 The `Theme` component is used to change the theme of the application. The `Theme` can be set directly in the rx.App.

 ```python
 app = rx.App(
     theme=rx.theme(
         appearance="light", has_background=True, radius="large", accent_color="teal"
     )
 )
 ```
