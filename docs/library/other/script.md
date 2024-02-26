---
components:
    - rx.script
---

```python exec
import reflex as rx
```

# Script

The Script component can be used to include inline javascript or javascript files by URL.

It uses the [`next/script` component](https://nextjs.org/docs/app/api-reference/components/script) to inject the script and can be safely used with conditional rendering to allow script side effects to be controlled by the state.

```python
rx.script("console.log('inline javascript')")
```

Complex inline scripting should be avoided.
If the code to be included is more than a couple lines, it is more maintainable to implement it in a separate javascript file in the `assets` directory and include it via the `src` prop.

```python
rx.script(src="/my-custom.js")
```

This component is particularly helpful for including tracking and social scripts.
Any additional attrs needed for the script tag can be supplied via `custom_attrs` prop.

```python
rx.script(src="//gc.zgo.at/count.js", custom_attrs=\{"data-goatcounter": "https://reflextoys.goatcounter.com/count"})
```

This code renders to something like the following to enable stat counting with a third party service.

```jsx
<script src="//gc.zgo.at/count.js" data-goatcounter="https://reflextoys.goatcounter.com/count" data-nscript="afterInteractive"></script>
```
