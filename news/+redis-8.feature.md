Allow redis-py 8. Reflex's redis clients disable redis-py 8's new default socket timeout, as redis-py 7 had none; on Python 3.11 that timeout loses task cancellations and can hang shutdown.
