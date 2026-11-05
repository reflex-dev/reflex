Allow redis-py 8. On Python 3.11, Reflex's redis clients disable redis-py 8's default socket timeout, which otherwise loses task cancellations there and can hang shutdown.
