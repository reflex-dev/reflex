Keep the development backend port open while hot reload restarts the worker, so requests made during a reload wait for the new worker instead of being refused.
