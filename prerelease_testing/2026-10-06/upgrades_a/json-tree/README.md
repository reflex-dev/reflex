# json-tree

This example demonstrates "dynamic components", wherein a component is created
and stored in a State var or returned from a computed var. Dynamic components can be
constructed imperatively from complex data without having to
use `rx.cond` or `rx.foreach` as is required for normal UI components.

Although dynamic components can be less performant and affect SEO, they are more
flexible when rendering nested data and allow components to be constructed using
regular python code.

To use the example app, paste in valid JSON and see the structure of the JSON
displayed as a nested `rx.data_list`.