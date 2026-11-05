Allow redis-py 8. On Python 3.11, Reflex's redis clients pin the RESP2 wire protocol, because redis-py 8's default RESP3 hangs its asyncio client there.
