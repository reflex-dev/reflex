`rx.ui` components take every kind of style: values bound to state, `_hover` and other condition blocks, responsive lists and `rx.breakpoints`, `rx.color`, shorthands, keyword arguments, and a whole style dict from state. A component's variant props can be bound to state too. All of it compiles to class names, so no page ships a styling runtime. `style` is typed in the stubs, and a misspelt property is an error that names the fix:

```python
rx.ui.box("hello", width=State.width, _hover={"color": rx.color("ruby", 9)})
rx.ui.box(
    paddng="1em"
)  # rx.ui.box: unknown CSS property "paddng". Did you mean "padding"?
```
