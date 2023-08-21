# import time
# import asyncio
#
# async def count_down(name, delay):
#     indents = (ord(name) - ord('A')) * '\t'
#
#     n = 3
#
#     while n:
#         await asyncio.sleep(delay)
#         duration = time.perf_counter() - start
#         print('-' * 40)
#         print('%.4f \t%s%s = %d' % (duration, indents, name, n))
#         # print(f"{duration}  {name} = {n}")
#         n -=1
#
#
#
#
# if __name__ == "__main__":
#     event_loop = asyncio.get_event_loop()
#     tasks = [
#         event_loop.create_task(count_down('A', 1)),
#         event_loop.create_task(count_down('B', 0.8)),
#         event_loop.create_task(count_down('C', 0.5))
#
#     ]
#     start = time.perf_counter()
#     event_loop.run_until_complete(asyncio.wait(tasks))
#
#     print('-' * 40)
#     print('Done.')


class Singleton:
    _instance = None

    def __init__(self, data):
        self.data = data

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls(data="Initial Data")
        return cls._instance

    def update_data(self, new_data):
        self.data = new_data

if __name__ == "__main__":
    # Usage
    instance1 = Singleton.get_instance()
    instance2 = Singleton.get_instance()

    # Storing a reference
    stored_reference = instance1

    print(instance1.data)  # Initial Data
    print(instance2.data)  # Initial Data
    print(stored_reference.data)  # Initial Data

    # Update instance1's data
    instance1.update_data("New Data")

    # Incorrectly assuming that stored_reference.data is still pointing to the old data
    print(stored_reference.data)  # This may mistakenly print: Initial Data (due to misunderstanding)

    print(instance1.data)  # New Data
    print(instance2.data)  # New Data
