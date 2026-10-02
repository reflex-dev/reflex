# Single Port Proxy

Enable single-port deployment by proxying the backend to the frontend port.

## Configuration

```python
import reflex_enterprise as rxe

config = rxe.Config(
    use_single_port=True,
)
```

This allows your application to run on a single port, which is useful for deployment scenarios where you can only expose one port.