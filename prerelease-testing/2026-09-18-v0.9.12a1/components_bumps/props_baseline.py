import reflex as rx
print("reflex from:", rx.__file__)
rl = rx.recharts.reference_line(y=3000, stroke="#f00", stroke_dasharray="3 3")
xa = rx.recharts.x_axis(data_key="name", tick_formatter="(value) => 'X:' + value")
for name, c in [("reference_line", rl), ("x_axis", xa)]:
    r = str(c.render())
    print(f"--- {name} ---")
    print("has strokeDasharray prop:", "strokeDasharray" in r)
    print("has tickFormatter prop:", "tickFormatter" in r)
    print("has wrapperStyle:", "wrapperStyle" in r)
    print(r[:900])
