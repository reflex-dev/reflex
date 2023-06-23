# Reflex Container Image Build

This example describes how to create and use a container image for Reflex with your own code.

## Update Requirements

The `requirements.txt` includes the reflex package which is need to install Reflex framework. If you use additional packages in your project you have add this in the `requirements.txt` first. Copy the `Dockerfile` and the `requirements.txt` file in your project folder.

## Customize Reflex Config

The `rxconfig.py` includes the configuration of your Reflex service. Edit the file like the following configuration. If you want to use a custom database you can set the endpoint in this file.

```python
import reflex as rx

config = rx.Config(
    app_name="app",
    api_url="0.0.0.0:8000",
    bun_path="/app/.bun/bin/bun",
    db_url="sqlite:///reflex.db",
)
```

## Build Reflex Container Image

To build your container image run the following command:

```bash
docker build -t reflex-project:latest .
```

## Start Container Service

Finally, you can start your Reflex container service as follows:

```bash
docker run -d -p 3000:3000 -p 8000:8000 --name reflex reflex-project:latest
```
