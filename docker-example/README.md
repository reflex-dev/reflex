# Pynecone Container Image Build

This example describes how to create and use a container image for Pynecone with your own code.

## Update Requirements

The `requirements.txt` includes the pynecone package which is need to install Pynecone framework. If you use additional packages in your project you have add this in the `requirements.txt` first. Copy the `Dockerfile` and the `requirements.txt` file in your project folder.

## Customize Pynecone Config

The `pcconfig.py` includes the configuration of your Pynecone service. Edit the file like the following configuration. If you want to use a custom database you can set the endpoint in this file.

```python
import pynecone as pc

config = pc.Config(
    app_name="app",
    api_url="0.0.0.0:8000",
    bun_path="/app/.bun/bin/bun",
    db_url="sqlite:///pynecone.db",
)
```

## Build Pynecone Container Image

To build your container image run the following command:

```bash
docker build -t pynecone-project:latest .
```

## Start Container Service

Finally, you can start your Pynecone container service as follows:

```bash
docker run -d -p 3000:3000 -p 8000:8000 --name pynecone pynecone-project:latest
```
