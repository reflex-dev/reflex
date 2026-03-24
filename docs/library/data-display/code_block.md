---
components:
    - rx.code_block
---

```python exec
import reflex as rx
```

# Code Block

The Code Block component can be used to display code easily within a website.
Put in a multiline string with the correct spacing and specify and language to show the desired code.

```python demo
rx.code_block(
    """def fib(n):
    if n <= 1:
        return n
    else:
        return(fib(n-1) + fib(n-2))""",
    language="python",
    show_line_numbers=True,
)
```
