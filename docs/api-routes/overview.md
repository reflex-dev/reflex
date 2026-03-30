```python exec
import reflex as rx
```

# API Transformer

In addition to your frontend app, Reflex uses a FastAPI backend to serve your app. The API transformer feature allows you to transform or extend the ASGI app that serves your Reflex application.

## Overview

The API transformer provides a way to:

1. Integrate existing FastAPI or Starlette applications with your Reflex app
2. Apply middleware or transformations to the ASGI app
3. Extend your Reflex app with additional API endpoints

This is useful for creating a backend API that can be used for purposes beyond your Reflex app, or for integrating Reflex with existing backend services.

## Using API Transformer

You can set the `api_transformer` parameter when initializing your Reflex app:

```python
import reflex as rx
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer

# Create a FastAPI app
fastapi_app = FastAPI(title="My API")

# Add routes to the FastAPI app
@fastapi_app.get("/api/items")
async def get_items():
    return dict(items=["Item1", "Item2", "Item3"])

# Create a Reflex app with the FastAPI app as the API transformer
app = rx.App(api_transformer=fastapi_app)
```

## Types of API Transformers

The `api_transformer` parameter can accept:

1. A Starlette or FastAPI instance
2. A callable that takes an ASGIApp and returns an ASGIApp
3. A sequence of the above

### Using a FastAPI or Starlette Instance

When you provide a FastAPI or Starlette instance as the API transformer, Reflex will mount its internal API to your app, allowing you to define additional routes:

```python
import reflex as rx
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer

# Create a FastAPI app with authentication
fastapi_app = FastAPI(title="Secure API")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Add a protected route
@fastapi_app.get("/api/protected")
async def protected_route(token: str = Depends(oauth2_scheme)):
    return dict(message="This is a protected endpoint")

# Create a token endpoint
@fastapi_app.post("/token")
async def login(username: str, password: str):
    # In a real app, you would validate credentials
    if username == "user" and password == "password":
        return dict(access_token="example_token", token_type="bearer")
    return dict(error="Invalid credentials")

# Create a Reflex app with the FastAPI app as the API transformer
app = rx.App(api_transformer=fastapi_app)
```

### Using a Callable Transformer

You can also provide a callable that transforms the ASGI app:

```python
import reflex as rx
from starlette.middleware.cors import CORSMiddleware

# Create a transformer function that returns a transformed ASGI app
def add_cors_middleware(app):
    # Wrap the app with CORS middleware and return the wrapped app
    return CORSMiddleware(
        app=app,
        allow_origins=["https://example.com"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Create a Reflex app with the transformer
app = rx.App(api_transformer=add_cors_middleware)
```

### Using Multiple Transformers

You can apply multiple transformers by providing a sequence:

```python
import reflex as rx
from fastapi import FastAPI
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Create a FastAPI app
fastapi_app = FastAPI(title="My API")

# Add routes to the FastAPI app
@fastapi_app.get("/api/items")
async def get_items():
    return dict(items=["Item1", "Item2", "Item3"])

# Create a transformer function
def add_logging_middleware(app):
    # This is a simple example middleware that logs requests
    async def middleware(scope, receive, send):
        # Log the request path
        path = scope["path"]
        print("Request:", path)
        await app(scope, receive, send)
    return middleware

# Create a Reflex app with multiple transformers
app = rx.App(api_transformer=[fastapi_app, add_logging_middleware])
```

## Reserved Routes

Some routes on the backend are reserved for the runtime of Reflex, and should not be overridden unless you know what you are doing.

### Ping

`localhost:8000/ping/`: You can use this route to check the health of the backend.

The expected return is `"pong"`.

### Event

`localhost:8000/_event`: the frontend will use this route to notify the backend that an event occurred.

```md alert error
# Overriding this route will break the event communication
```

### Upload

`localhost:8000/_upload`: This route is used for the upload of file when using `rx.upload()`.
