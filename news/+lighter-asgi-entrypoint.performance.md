The backend no longer wraps the app in an extra `Starlette` application to run lifespan tasks, which removes a routing layer from every request.
